"""SGC dialing console. Run with: python main.py"""
import math
import time
import random
import argparse
from pathlib import Path
import pygame
from glyph import Glyph
from glyph_database import address_database
from simulator import Dialer
from gate_audio import GateAudio
from iris import Iris
from drawing_context import DrawingContext
from view_state import GateVisualState, UISettings, CommandInput
from ring_motion import DEFAULT_ROTATION_RPM, validate_rpm, ring_rotation

from ui_geometry import W, H, TILE_ANGLE
from keyboard_window import GlyphKeyboard
from address_archive import AddressArchive
from options_menu import OptionsMenu
from console_commands import ConsoleCommands
from console_renderer import ConsoleRenderer

class Console:
    # Initialize windows, cached assets, simulator state, menus, and visual effects.
    def __init__(self, rotation_rpm=DEFAULT_ROTATION_RPM):
        rotation_rpm = validate_rpm(rotation_rpm)
        pygame.init()
        self.settings = UISettings()
        self.input = CommandInput()
        self.visual = GateVisualState()
        self.load_button_sounds()
        self.gate_audio = GateAudio()
        self.window = pygame.Window('SGC • Stargate Dialing Computer', size=(W, H), resizable=True)
        self.ui = DrawingContext(pygame.Surface((W, H)), Glyph())
        self.clock = pygame.time.Clock()
        self.dialer = Dialer(rotation_rpm=rotation_rpm)
        self.dialer.rotation_origin = lambda: self.visual.rest_rotation
        self.iris = Iris()
        self.activation_press_played = False
        self.archive = AddressArchive(ui=self.ui, dialer=self.dialer, viewport=self.viewport)
        self.options = OptionsMenu(ui=self.ui, settings=self.settings,
                                   gate_audio=self.gate_audio, viewport=self.viewport)
        self.commands = ConsoleCommands(dialer=self.dialer, visual=self.visual,
                                       input_state=self.input, iris=self.iris,
                                       action=self.action, stop_gate=self.stop_gate,
                                       reset_gate=self.reset_gate, set_iris=self.set_iris)
        self.keyboard = GlyphKeyboard(
            glyph=self.ui.glyph, dialer=self.dialer, visual=self.visual, iris=self.iris,
            window=self.window, action=self.action, stop_gate=self.stop_gate,
            modal_open=lambda: self.archive.archive_open or self.options.options_open)
        self.renderer = ConsoleRenderer(
            ui=self.ui, dialer=self.dialer, visual=self.visual, settings=self.settings,
            input_state=self.input, iris=self.iris, track_rotation=self.track_rotation,
            archive=self.archive, options=self.options)

    # Load classic and Atlantis button sounds separately from gate audio.
    def load_button_sounds(self):
        self.glyph_sounds = []
        self.atlantis_press_sound = None
        self.settings.glyph_sound_mode = 'classic'
        self.dial_sound = None
        self.button_channel = None
        if not pygame.mixer.get_init():
            return
        self.button_channel = pygame.mixer.Channel(0)
        pygame.mixer.set_reserved(1)
        directory = Path(__file__).resolve().parent / 'media' / 'sounds' / 'dhd'
        for path in sorted(directory.glob('*.wav')):
            stem = path.stem.lower()
            numbered = stem.startswith('dhd_usual_') and stem[len('dhd_usual_'):].isdigit()
            if not numbered and stem != 'dhd_usual_dial':
                continue
            try:
                sound = pygame.mixer.Sound(str(path))
            except (pygame.error, OSError) as error:
                print(f'Unable to load sound {path.name}: {error}')
                continue
            if numbered:
                self.glyph_sounds.append(sound)
            else:
                self.dial_sound = sound

        try:
            self.atlantis_press_sound = pygame.mixer.Sound(str(directory / 'atlantis' / 'press.mp3'))
        except (pygame.error, OSError) as error:
            print(f'Unable to load Atlantis press.mp3: {error}')

    # Choose the selected button sound, preserving separate DIAL behavior.
    def play_button_sound(self, dial=False):
        if dial:
            sound = self.atlantis_press_sound if self.settings.glyph_sound_mode == 'atlantis' else self.dial_sound
        elif self.settings.glyph_sound_mode == 'silent':
            return
        elif self.settings.glyph_sound_mode == 'atlantis':
            sound = self.atlantis_press_sound
        else:
            sound = random.choice(self.glyph_sounds) if self.glyph_sounds else None
        if self.button_channel is not None and sound is not None:
            self.button_channel.play(sound)

    # Combine normal dialing motion with a smooth interrupted-dial stop.
    def track_rotation(self, now):
        if self.visual.ring_return is not None:
            started, initial, duration, speed = self.visual.ring_return
            t = min(1.0, max(0.0, (now - started) / duration))
            if speed:
                # Preserve incoming speed; progressively apply and release braking.
                rotation = initial + speed * duration * (t - t ** 3 + .5 * t ** 4)
                # A bounded stop may need extra travel to reach the tile center.
                correction = -initial - speed * duration / 2
                rotation += correction * t ** 3 * (10 - 15 * t + 6 * t * t)
            else:
                rotation = initial * (1 - t ** 3 * (10 - 15 * t + 6 * t * t))
            rotation += self.visual.ring_stop_target
            if t >= 1:
                self.visual.ring_return = None
                self.visual.rest_rotation = self.visual.ring_stop_target
            return rotation
        d = self.dialer
        elapsed = now - d.started if d.state == 'dialing' else d.cycle_elapsed(len(d.sequence))
        return ring_rotation(d.sequence, elapsed, d.lock_seconds, initial_rotation=self.visual.rest_rotation, rpm=d.rotation_rpm)

    # Cancel dialing or close a connection while preserving the appropriate animation.
    def stop_gate(self, now):
        was_connected = self.dialer.state == 'connected'
        if was_connected:
            self.visual.last_connected_sequence = tuple(self.dialer.sequence)
        if self.dialer.state in ('dialing', 'dhd_wait', 'ready', 'activating'):
            rotation = self.track_rotation(now)
            speed = ring_rotation(
                self.dialer.sequence, now-self.dialer.started,
                self.dialer.lock_seconds, velocity=True,
                initial_rotation=self.visual.rest_rotation, rpm=self.dialer.rotation_rpm) if self.dialer.state == 'dialing' else 0.0
            if abs(speed) > 1e-6:
                # Brake over roughly 1.5 seconds, extending to the next whole
                # tile in the same direction so the top chevron stays centered.
                projected = rotation + speed * .75
                tile = math.ceil(projected / TILE_ANGLE) if speed > 0 else math.floor(projected / TILE_ANGLE)
                self.visual.ring_stop_target = tile * TILE_ANGLE
                initial = rotation - self.visual.ring_stop_target
                duration = min(2.5, 2 * abs(initial / speed))
            else:
                self.visual.ring_stop_target = round(rotation / TILE_ANGLE) * TILE_ANGLE
                initial = rotation-self.visual.ring_stop_target
                speed = 0.0
                duration = .3
            self.visual.ring_return = (now, initial, duration, speed)
        self.reset_gate(now, 'STARGATE DISENGAGED')
        if was_connected:
            self.begin_horizon_close(now)

    def reset_gate(self, now, message=None):
        """Retain the final failed-dial position before discarding its sequence."""
        if self.dialer.state == 'failed':
            self.visual.rest_rotation = self.track_rotation(now)
        self.dialer.reset(message)

    # Start center-out expansion using the opening sound duration.
    def begin_horizon_open(self, now):
        self.gate_audio.update(self.dialer, self.visual.ring_return, now, self.dialer.spin_fraction(now))
        self.visual.horizon_opening = (now, self.gate_audio.open_duration * .5)

    # Retain slot contents and synchronize closure with the closing sound.
    def begin_horizon_close(self, now):
        self.visual.slot_fade_started = None
        self.visual.closing_glyphs = self.visual.last_connected_sequence
        self.visual.rest_rotation = self.visual.last_ring_rotation
        self.visual.horizon_opening = None
        self.gate_audio.update(self.dialer, self.visual.ring_return, now, self.dialer.spin_fraction(now))
        self.visual.horizon_closing = (now, self.gate_audio.close_duration)

    # Dispatch shared button actions from either window to the simulator.
    def action(self, action, now):
        d = self.dialer
        if isinstance(action, int):
            previous_count = len(d.selected)
            previous_origin = d.origin_selected
            if not self.visual.busy:
                d.select(action, now)
            if len(d.selected) > previous_count or d.origin_selected != previous_origin:
                self.play_button_sound()
        elif isinstance(action, tuple) and action[0] == 'mode':
            if not self.visual.busy:
                d.set_symbol_count(action[1])
        elif action == 'undo' and d.state == 'idle' and d.selected:
            if d.origin_selected:
                d.origin_selected = False
            else:
                d.selected.pop()
            d.destination = 'MANUAL ADDRESS'
        elif action == 'clear':
            self.reset_gate(now)
        elif action == 'dial':
            if d.behavior == 'dhd':
                if d.activate(now):
                    self.activation_press_played = self.settings.glyph_sound_mode == 'atlantis'
                    if self.activation_press_played:
                        self.play_button_sound(dial=True)
                    self.play_pending_activation_sound()
            elif not self.visual.busy and d.start(now + .6):
                self.play_button_sound(dial=True)
        elif action == 'toggle_dialing':
            if d.state in ('idle', 'failed') and not self.visual.busy:
                mode = 'current' if d.behavior == 'dhd' else 'dhd'
                d.set_behavior(mode)
        elif action == 'iris':
            self.set_iris(not self.iris.target_closed, now)
        elif action == 'shutdown':
            self.stop_gate(now)
        elif action == 'keyboard':
            self.keyboard.open_keyboard()
        elif action == 'options':
            self.options.options_open = True
            self.input.focused = False
        elif action == 'load' and d.state == 'idle':
            self.archive.archive_open = True
            self.archive.archive_drag_offset = None
            self.archive.archive_info = None
            self.archive.archive_search_focus = True
            self.input.focused = False
            self.archive.archive_scroll = 0

    # Iris state is independent of dialing and remains in place after shutdown.
    def set_iris(self, closed, now):
        if bool(closed) == self.iris.target_closed:
            return
        cue = 'iris_close' if closed else 'iris_open'
        duration = self.gate_audio.play(cue, 'iris') or 1.2
        self.iris.set_closed(closed, now, duration)

    # Play the delayed DHD activation cue once, unless Atlantis already played it.
    def play_pending_activation_sound(self):
        if self.dialer.consume_activation_sound():
            if not self.activation_press_played:
                self.play_button_sound(dial=True)
            self.activation_press_played = False

    # Letterbox the main console and provide the inverse mapping for mouse coordinates.
    def viewport(self):
        ww, wh = self.window.size
        scale = min(ww / W, wh / H)
        width, height = max(1, int(W * scale)), max(1, int(H * scale))
        return pygame.Rect((ww - width) // 2, (wh - height) // 2, width, height)

    # Advance simulation, route window-specific events, update sound, and present both windows.
    def run(self):
        running = True
        while running:
            now = time.monotonic()
            viewport = self.viewport()
            mx, my = pygame.mouse.get_pos()
            self.ui.mouse = ((mx - viewport.x) * W / viewport.width, (my - viewport.y) * H / viewport.height)
            # Update logical state before effects so opening/closing cues fire once.
            previous_state = self.dialer.state
            if previous_state == 'connected':
                self.visual.last_connected_sequence = tuple(self.dialer.sequence)
            self.dialer.update(now)
            self.play_pending_activation_sound()
            if previous_state != 'connected' and self.dialer.state == 'connected':
                self.begin_horizon_open(now)
            if previous_state == 'connected' and self.dialer.state != 'connected':
                self.begin_horizon_close(now)
            self.renderer.draw(now)
            self.keyboard.draw_keyboard()
            for event in pygame.event.get():
                event_window = getattr(event, 'window', None)
                window_id = getattr(event_window, 'id', event_window)
                if self.keyboard.keyboard_window is not None and window_id == self.keyboard.keyboard_window.id:
                    self.keyboard.keyboard_event(event, now)
                    continue
                if hasattr(event, 'pos'):
                    self.ui.mouse = ((event.pos[0]-viewport.x)*W/viewport.width,
                                  (event.pos[1]-viewport.y)*H/viewport.height)
                if event.type == pygame.QUIT or event.type == pygame.WINDOWCLOSE:
                    running = False
                elif self.options.options_open:
                    self.options.options_event(event)
                elif self.archive.archive_open:
                    self.archive.archive_event(event)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.input.focused = pygame.Rect(596, 891, 609, 35).collidepoint(self.ui.mouse)
                    for rect, action, enabled in self.ui.buttons:
                        if enabled and rect.collidepoint(self.ui.mouse):
                            self.action(action, now)
                            break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.stop_gate(now)
                        self.input.focused = False
                    elif self.input.focused:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            if self.input.text.strip():
                                self.commands.execute_command(now)
                            else:
                                self.action('dial', now)
                        elif event.key == pygame.K_BACKSPACE:
                            self.input.text = self.input.text[:-1]
                        elif event.unicode.isprintable() and len(self.input.text) < 45:
                            self.input.text += event.unicode
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.action('dial', now)
                    elif event.key == pygame.K_BACKSPACE:
                        self.action('undo', now)
            self.gate_audio.update(self.dialer, self.visual.ring_return, now, self.dialer.spin_fraction(now))
            # Reacquire the surface each frame because resizing can replace it.
            surface = self.window.get_surface()
            surface.fill((0, 0, 0))
            surface.blit(pygame.transform.smoothscale(self.ui.canvas, viewport.size), viewport)
            self.window.flip()
            self.clock.tick(60)
        pygame.quit()

# Command-line launch or an off-screen connected-state screenshot.
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', type=Path, help='Save a connected-state screenshot and exit')
    parser.add_argument('--rpm', type=validate_rpm, default=DEFAULT_ROTATION_RPM,
                        help='Ring speed shared by computer and DHD dialing (default: 5)')
    args = parser.parse_args()
    app = Console(rotation_rpm=args.rpm)
    if args.preview:
        app.ui.mouse = (-1, -1)
        app.dialer.selected = address_database['Abydos']['Address'][:]
        app.dialer.start(0)
        preview_time = app.dialer.cycle_elapsed(len(app.dialer.sequence))
        app.dialer.update(preview_time)
        app.renderer.draw(preview_time)
        pygame.image.save(app.ui.canvas, str(args.preview))
        pygame.quit()
    else:
        app.run()

