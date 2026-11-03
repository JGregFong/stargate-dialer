"""SGC dialing console. Run with: python main.py"""
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
from offworld_state import OffworldVisualState
from offworld_renderer import OffworldRenderer
from ring_motion import DEFAULT_ROTATION_RPM, validate_rpm

from ui_geometry import W, H
from keyboard_window import GlyphKeyboard
from address_archive import AddressArchive
from options_menu import OptionsMenu
from console_commands import ConsoleCommands
from console_renderer import ConsoleRenderer
from preferences import PreferencesStore, capture_preferences, restore_preferences

class Console:
    # Initialize windows, cached assets, simulator state, menus, and visual effects.
    def __init__(self, rotation_rpm=None, preferences=None):
        requested_rpm = None if rotation_rpm is None else validate_rpm(rotation_rpm)
        rotation_rpm = requested_rpm or DEFAULT_ROTATION_RPM
        self.preferences = preferences
        pygame.init()
        self.settings = UISettings()
        self.input = CommandInput()
        self.earth_visual = GateVisualState()
        self.offworld_visual = OffworldVisualState()
        self.travel_origin = None
        self.load_button_sounds()
        self.gate_audio = GateAudio()
        self.set_volume(self.settings.volume)
        self.window = pygame.Window('SGC • Stargate Dialing Computer', size=(W, H), resizable=True)
        self.ui = DrawingContext(pygame.Surface((W, H)), Glyph())
        self.clock = pygame.time.Clock()
        self.dialer = Dialer(rotation_rpm=rotation_rpm)
        if self.preferences is not None:
            restore_preferences(self.settings, self.dialer, self.gate_audio, self.preferences.load())
            if requested_rpm is not None:
                self.dialer.set_rotation_rpm(requested_rpm)
            self.set_volume(self.settings.volume)
        self.dialer.rotation_origin = lambda: self.visual.rest_rotation
        self.iris = Iris()
        self.activation_press_played = False
        self.archive = AddressArchive(ui=self.ui, dialer=self.dialer, viewport=self.viewport)
        self.options = OptionsMenu(ui=self.ui, settings=self.settings,
                                   gate_audio=self.gate_audio, viewport=self.viewport,
                                   set_volume=self.set_volume, connection=self.dialer.connection)
        self.commands = ConsoleCommands(dialer=self.dialer, visual=lambda: self.visual,
                                       input_state=self.input, iris=self.iris,
                                       action=self.action, stop_gate=self.stop_gate,
                                       reset_gate=self.reset_gate, set_iris=self.set_iris)
        self.keyboard = GlyphKeyboard(
            glyph=self.ui.glyph, dialer=self.dialer, visual=lambda: self.visual, iris=self.iris,
            window=self.window, action=self.action, stop_gate=self.stop_gate,
            modal_open=lambda: self.archive.archive_open or self.options.options_open)
        self.earth_renderer = ConsoleRenderer(
            ui=self.ui, dialer=self.dialer, visual=self.earth_visual, settings=self.settings,
            input_state=self.input, iris=self.iris, track_rotation=self.track_rotation,
            archive=self.archive, options=self.options)
        self.offworld_renderer = OffworldRenderer(
            ui=self.ui, dialer=self.dialer, visual=self.offworld_visual,
            settings=self.settings, track_rotation=self.track_rotation)

    @property
    def visual(self):
        return self.offworld_visual if self.dialer.theme.offworld else self.earth_visual

    @property
    def renderer(self):
        return self.offworld_renderer if self.dialer.theme.offworld else self.earth_renderer

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

    def set_volume(self, volume):
        self.settings.volume = max(0.0, min(1.0, volume))
        self.gate_audio.set_volume(self.settings.volume)
        if self.button_channel is not None:
            self.button_channel.set_volume(self.settings.volume)

    @property
    def button_sound_mode(self):
        if self.dialer.theme.offworld:
            return {'SGC': 'classic', 'MilkyWay': 'classic',
                    'Pegasus': 'atlantis'}[self.dialer.theme.dhd_sound_type]
        return self.settings.glyph_sound_mode

    # Choose the local DHD sound, preserving separate DIAL behavior.
    def play_button_sound(self, dial=False):
        if dial:
            sound = self.atlantis_press_sound if self.button_sound_mode == 'atlantis' else self.dial_sound
        elif self.button_sound_mode == 'silent':
            return
        elif self.button_sound_mode == 'atlantis':
            sound = self.atlantis_press_sound
        else:
            sound = random.choice(self.glyph_sounds) if self.glyph_sounds else None
        if self.button_channel is not None and sound is not None:
            self.button_channel.play(sound)

    # Combine normal dialing motion with a smooth interrupted-dial stop.
    def track_rotation(self, now):
        return self.visual.rotation(self.dialer, now)

    # Cancel dialing or close a connection while preserving the appropriate animation.
    def stop_gate(self, now):
        d = self.dialer
        if d.theme.offworld:
            interrupted = bool(d.sequence) and d.state in ('dialing', 'dhd_wait', 'ready', 'activating')
            was_connected = self.offworld_visual.begin_shutdown(d, now)
            self.reset_gate(now, 'STARGATE DISENGAGED')
            self.gate_audio.update(d, self.offworld_visual.ring_return, now, d.spin_fraction(now))
            if interrupted and self.offworld_visual.ring_return is None:
                # Instant mode has no braking completion to trigger this cue.
                self.gate_audio.play('fail', 'effect')
        else:
            was_connected = d.state == 'connected'
            if was_connected:
                self.earth_visual.last_connected_sequence = tuple(d.sequence)
            if d.state in ('dialing', 'dhd_wait', 'ready', 'activating'):
                self.earth_visual.begin_braking(d, now)
            self.reset_gate(now, 'STARGATE DISENGAGED')
        if was_connected:
            self.begin_horizon_close(now)

    def reset_gate(self, now, message=None):
        """Retain the final failed-dial position before discarding its sequence."""
        if self.dialer.state == 'failed':
            self.visual.rest_rotation = self.track_rotation(now)
        self.visual.fade_chevrons(self.dialer.locked, now)
        self.dialer.reset(message)

    # Start center-out expansion using the opening sound duration.
    def begin_horizon_open(self, now):
        self.gate_audio.update(self.dialer, self.visual.ring_return, now, self.dialer.spin_fraction(now))
        self.visual.horizon_opening = (now, self.gate_audio.open_duration * .5)
        self.dialer.connection.travel_unlock_at = now+self.gate_audio.open_duration+1
        self.dialer.connection.travel_locked = True
        if self.dialer.theme.offworld:
            self.offworld_visual.activation_unlock_at = now+self.gate_audio.open_duration+1
            self.offworld_visual.activation_locked = True

    # Retain slot contents and synchronize closure with the closing sound.
    def begin_horizon_close(self, now):
        self.gate_audio.update(self.dialer, self.visual.ring_return, now, self.dialer.spin_fraction(now))
        duration = self.settings.video_player.close_duration() or self.gate_audio.close_duration
        endpoints = [self.dialer.theme]
        chevron_fade_duration = .2 if self.travel_origin is not None else .9
        if self.travel_origin is not None:
            endpoints.append(self.travel_origin)
            self.travel_origin = None
        for theme in endpoints:
            visual = self.offworld_visual if theme.offworld else self.earth_visual
            visual.fade_chevrons(len(visual.last_connected_sequence), now+duration,
                                 duration=chevron_fade_duration)
            if theme.offworld:
                self.offworld_visual.begin_close(now, duration)
            else:
                v = self.earth_visual
                v.slot_fade_started = None
                v.closing_glyphs = v.last_connected_sequence
                v.rest_rotation = v.last_ring_rotation
                v.horizon_opening = None
                v.horizon_closing = (now, duration)

    # Dispatch shared button actions from either window to the simulator.
    def action(self, action, now):
        d = self.dialer
        if action == 'toggle_offworld_sgc':
            if d.theme.offworld and d.state == 'idle' and not self.visual.busy:
                rotation = self.track_rotation(now)
                self.visual.rest_rotation = self.visual.last_ring_rotation = rotation
                self.visual.spin_started = self.visual.spin_stop = None
                self.visual.spin_dial_id = None
                modes = ('dhd', 'spinning', 'rotary')
                d.offworld_dialing_mode = modes[(modes.index(d.offworld_dialing_mode)+1) % len(modes)]
            return
        if action == 'travel':
            origin, origin_visual = d.theme, self.visual
            if d.travel(now):
                self.gate_audio.play('teleport', 'teleport')
                self.travel_origin = origin
                origin_visual.last_connected_sequence = tuple(d.sequence)
                origin_visual.horizon_opening = None
                if d.theme.offworld:
                    self.offworld_visual = OffworldVisualState()
                    self.offworld_renderer.reset(self.offworld_visual)
                else:
                    self.earth_visual = GateVisualState()
                    self.earth_renderer.visual = self.earth_visual
                self.visual.last_connected_sequence = tuple(d.sequence)
                self.visual.incoming = True
                self.ui.glyph.origin_mark = d.theme.origin_mark
                self.archive.archive_open = False
                self.options.options_open = False
                self.input.focused = False
                self.activation_press_played = False
                self.gate_audio.update(d, None, now, d.spin_fraction(now))
                self.window.title = f'{d.theme.name} / Stargate'
                if d.theme.offworld:
                    if self.keyboard.keyboard_window is not None:
                        self.keyboard.keyboard_window.hide()
                    self.keyboard.keyboard_visible = False
                self.keyboard.draw_keyboard()
            return
        if isinstance(action, int):
            previous_count = len(d.selected)
            previous_origin = d.origin_selected
            if not self.visual.busy:
                d.select(action, now)
            if len(d.selected) > previous_count or d.origin_selected != previous_origin:
                self.visual.incoming = False
                self.visual.chevron_fade_count = 0
                if d.theme.offworld:
                    self.offworld_visual.clear_fade()
                self.play_button_sound()
                if d.theme.offworld:
                    self.gate_audio.update(d, None, now, d.spin_fraction(now))
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
                    self.activation_press_played = self.button_sound_mode == 'atlantis'
                    if self.activation_press_played:
                        self.play_button_sound(dial=True)
                    self.play_pending_activation_sound()
            elif not self.visual.busy and d.start(now + .6):
                self.play_button_sound(dial=True)
        elif action == 'toggle_dialing':
            if d.state in ('idle', 'failed') and not self.visual.busy:
                mode = 'current' if d.behavior == 'dhd' else 'dhd'
                d.set_behavior(mode)
        elif action == 'cycle_speed':
            if (d.state in ('idle', 'failed') and not self.visual.busy
                    and (not d.theme.offworld or d.offworld_dialing_mode != 'dhd')):
                rpm = next((speed for speed in (5, 10, 15, 20, 30) if speed > d.rotation_rpm), 5)
                d.set_rotation_rpm(rpm)
        elif action == 'iris':
            self.set_iris(not self.iris.target_closed, now)
        elif action == 'shutdown':
            if (d.theme.offworld and d.state == 'connected'
                    and now < self.offworld_visual.activation_unlock_at):
                return
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

    def update_gate(self, now):
        """Advance logical state and consume transient connection results before drawing."""
        if self.dialer.state != 'connected' and (self.dialer.selected or self.dialer.sequence):
            self.visual.incoming = False
        self.earth_visual.update(now)
        self.offworld_visual.update(now)
        if self.dialer.theme.offworld:
            self.offworld_visual.rotation(self.dialer, now)
        previous_state = self.dialer.state
        if previous_state == 'connected':
            self.visual.last_connected_sequence = tuple(self.dialer.sequence)
        self.dialer.update(now)
        self.play_pending_activation_sound()
        if self.dialer.state == 'failed':
            reason = self.dialer.message
            # Consume the failure cue before clearing the transient failed state.
            self.gate_audio.update(self.dialer, self.visual.ring_return, now,
                                   self.dialer.spin_fraction(now))
            self.reset_gate(now, reason + ' / GATE RESET')
        if previous_state != 'connected' and self.dialer.state == 'connected':
            self.begin_horizon_open(now)
        if previous_state == 'connected' and self.dialer.state != 'connected':
            self.begin_horizon_close(now)

    # Advance simulation, route window-specific events, update sound, and present both windows.
    def run(self):
        running = True
        while running:
            now = time.monotonic()
            viewport = self.viewport()
            mx, my = pygame.mouse.get_pos()
            self.ui.mouse = ((mx - viewport.x) * W / viewport.width, (my - viewport.y) * H / viewport.height)
            self.update_gate(now)
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
                    self.input.focused = (not self.dialer.theme.offworld
                                          and pygame.Rect(596, 891, 609, 35).collidepoint(self.ui.mouse))
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
            if self.preferences is not None:
                self.preferences.update(capture_preferences(self.settings, self.dialer, self.gate_audio), now)
            self.clock.tick(60)
        if self.preferences is not None:
            self.preferences.update(capture_preferences(self.settings, self.dialer, self.gate_audio),
                                    time.monotonic(), force=True)
        self.settings.video_player.close()
        pygame.quit()

# Command-line launch or an off-screen connected-state screenshot.
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', type=Path, help='Save a connected-state screenshot and exit')
    parser.add_argument('--theme', choices=('earth', 'abydos'), default='earth',
                        help='Preview a planet environment without travelling')
    parser.add_argument('--abydos', dest='theme', action='store_const', const='abydos',
                        help='Start directly on Abydos (shortcut for --theme abydos)')
    parser.add_argument('--keyboard-preview', type=Path, help='Save the glyph keyboard and exit')
    parser.add_argument('--rpm', type=validate_rpm, default=None,
                        help='Ring speed override (otherwise restore saved speed, or default to 5)')
    args = parser.parse_args()
    store = None if args.preview or args.keyboard_preview else PreferencesStore()
    app = Console(rotation_rpm=args.rpm, preferences=store)
    if args.theme != 'earth':
        from themes import theme_for
        app.dialer.theme = theme_for(args.theme)
        app.dialer.set_symbol_count(7)
        app.dialer.set_behavior('dhd')
        app.ui.glyph.origin_mark = app.dialer.theme.origin_mark
        app.window.title = f'{app.dialer.theme.name} / Stargate'
    if args.keyboard_preview:
        app.keyboard.draw_keyboard()
        pygame.image.save(app.keyboard.ui.canvas, str(args.keyboard_preview))
        pygame.quit()
        raise SystemExit
    if args.preview:
        app.ui.mouse = (-1, -1)
        if app.dialer.behavior == 'dhd':
            app.dialer.load_destination('Earth', 0)
            app.dialer.activate(0)
        else:
            app.dialer.selected = address_database['Abydos']['Address'][:]
            app.dialer.start(0)
        preview_time = app.dialer.cycle_elapsed(len(app.dialer.sequence))
        app.dialer.update(preview_time)
        if app.dialer.state == 'activating':
            preview_time += 1
            app.dialer.update(preview_time)
        app.renderer.draw(preview_time)
        pygame.image.save(app.ui.canvas, str(args.preview))
        pygame.quit()
    else:
        app.run()

