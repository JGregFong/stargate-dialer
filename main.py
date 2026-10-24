"""SGC dialing console. Run with: python main.py"""
import math
import time
import random
import argparse
from pathlib import Path
import pygame
from glyph import Glyph
from glyph_database import glyphs, address_database
from simulator import Dialer
from gate_audio import GateAudio
from iris import Iris
from ring_motion import DEFAULT_ROTATION_RPM, validate_rpm

# Keep the existing geometry imports available to callers of main.
from ui_geometry import (
    W, H, BG, CYAN, DIM, RED, WHITE, YELLOW, GREEN, TEXT_FONT_PATH,
    CENTER, GATE_SCALE, INNER_GATE_SCALE, HORIZON_RADIUS, CHEVRON_ANGLES,
    ORIGIN_ANGLE, TILE_ANGLE, dialing_angles, connector_route, polar, ring_rotation,
)
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
        self.keyboard = GlyphKeyboard(self)
        self.archive = AddressArchive(self)
        self.options = OptionsMenu(self)
        self.commands = ConsoleCommands(self)
        self.renderer = ConsoleRenderer(self)

        self.load_button_sounds()
        self.gate_audio = GateAudio()
        self.window = pygame.Window('SGC • Stargate Dialing Computer', size=(W, H), resizable=True)
        self.canvas = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.fonts = {}
        self.glyph = Glyph()
        slot_sources = [self.glyph.image(i, 215) for i in range(len(glyphs))]
        self.slot_reference_size = (max(image.get_width() for image in slot_sources),
                                    max(image.get_height() for image in slot_sources))
        self.dialer = Dialer(rotation_rpm=rotation_rpm)
        self.dialer.rotation_origin = lambda: self.rest_rotation
        self.iris = Iris()
        self.ring_return = None
        self.rest_rotation = 0.0
        self.ring_stop_target = 0.0
        self.last_ring_rotation = 0.0
        self.telemetry_running = False
        self.telemetry_started = 0.0
        self.telemetry_stopped = None
        self.command = ''
        self.command_focus = False
        self.activation_press_played = False
        self.status_key = None
        self.status_blend = None
        self.status_fade_source = None
        self.status_fade_started = 0.0
        self.buttons = []
        self.uniform_glyph_sizing = True
        self.dialing_behavior_option = 'current'
        self.base = pygame.Surface((W, H))
        self.draw_static()
        self.event_horizon = self.make_event_horizon()
        self.horizon_closing = None
        self.last_connected_sequence = ()
        self.closing_glyphs = ()
        self.slot_fade_started = None
        self.horizon_opening = None

    # Compatibility accessors; each view owns its interaction state.
    @property
    def keyboard_window(self):
        return self.keyboard.keyboard_window

    @keyboard_window.setter
    def keyboard_window(self, value):
        self.keyboard.keyboard_window = value

    @property
    def keyboard_visible(self):
        return self.keyboard.keyboard_visible

    @keyboard_visible.setter
    def keyboard_visible(self, value):
        self.keyboard.keyboard_visible = value

    @property
    def keyboard_canvas(self):
        return self.keyboard.keyboard_canvas

    @keyboard_canvas.setter
    def keyboard_canvas(self, value):
        self.keyboard.keyboard_canvas = value

    @property
    def keyboard_buttons(self):
        return self.keyboard.keyboard_buttons

    @keyboard_buttons.setter
    def keyboard_buttons(self, value):
        self.keyboard.keyboard_buttons = value

    @property
    def keyboard_mouse(self):
        return self.keyboard.keyboard_mouse

    @keyboard_mouse.setter
    def keyboard_mouse(self, value):
        self.keyboard.keyboard_mouse = value

    @property
    def hover(self):
        return self.keyboard.hover

    @hover.setter
    def hover(self, value):
        self.keyboard.hover = value

    @property
    def destinations(self):
        return self.archive.destinations

    @destinations.setter
    def destinations(self, value):
        self.archive.destinations = value

    @property
    def archive_open(self):
        return self.archive.archive_open

    @archive_open.setter
    def archive_open(self, value):
        self.archive.archive_open = value

    @property
    def archive_info(self):
        return self.archive.archive_info

    @archive_info.setter
    def archive_info(self, value):
        self.archive.archive_info = value

    @property
    def archive_drag_offset(self):
        return self.archive.archive_drag_offset

    @archive_drag_offset.setter
    def archive_drag_offset(self, value):
        self.archive.archive_drag_offset = value

    @property
    def archive_query(self):
        return self.archive.archive_query

    @archive_query.setter
    def archive_query(self, value):
        self.archive.archive_query = value

    @property
    def archive_glyphs(self):
        return self.archive.archive_glyphs

    @archive_glyphs.setter
    def archive_glyphs(self, value):
        self.archive.archive_glyphs = value

    @property
    def archive_scroll(self):
        return self.archive.archive_scroll

    @archive_scroll.setter
    def archive_scroll(self, value):
        self.archive.archive_scroll = value

    @property
    def archive_search_focus(self):
        return self.archive.archive_search_focus

    @archive_search_focus.setter
    def archive_search_focus(self, value):
        self.archive.archive_search_focus = value

    @property
    def options_open(self):
        return self.options.options_open

    @options_open.setter
    def options_open(self, value):
        self.options.options_open = value

    # Load classic and Atlantis button sounds separately from gate audio.
    def load_button_sounds(self):
        self.glyph_sounds = []
        self.atlantis_press_sound = None
        self.glyph_sound_mode = 'classic'
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
            sound = self.atlantis_press_sound if self.glyph_sound_mode == 'atlantis' else self.dial_sound
        elif self.glyph_sound_mode == 'silent':
            return
        elif self.glyph_sound_mode == 'atlantis':
            sound = self.atlantis_press_sound
        else:
            sound = random.choice(self.glyph_sounds) if self.glyph_sounds else None
        if self.button_channel is not None and sound is not None:
            self.button_channel.play(sound)

    # Cache interface fonts and draw ordinary left-aligned labels.
    def text(self, text, pos, size=16, color=CYAN, surface=None):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(str(TEXT_FONT_PATH), size)
        (surface or self.canvas).blit(self.fonts[size].render(str(text), True, color), pos)

    # Center archive constellation labels and fit long names within their cells.
    def centered_slot_text(self, text, cell, y, size, color):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(str(TEXT_FONT_PATH), size)
        label = self.fonts[size].render(text, True, color)
        if label.get_width() > cell.width - 8:
            label = pygame.transform.smoothscale(label, (cell.width - 8, label.get_height()))
        self.canvas.blit(label, label.get_rect(midtop=(cell.centerx, y)))

    # Draw a thin rectangular border on the chosen surface.
    def panel(self, rect, color=CYAN, surface=None):
        pygame.draw.rect(surface or self.canvas, color, rect, 1)

    # Cache the fixed console frame, ring boundaries, and diagnostic panels.
    def draw_static(self):
        return self.renderer.draw_static()

    # Combine normal dialing motion with a smooth interrupted-dial stop.
    def track_rotation(self, now):
        if self.ring_return is not None:
            started, initial, duration, speed = self.ring_return
            t = min(1.0, max(0.0, (now - started) / duration))
            if speed:
                # Preserve incoming speed; progressively apply and release braking.
                rotation = initial + speed * duration * (t - t ** 3 + .5 * t ** 4)
            else:
                rotation = initial * (1 - t ** 3 * (10 - 15 * t + 6 * t * t))
            rotation += self.ring_stop_target
            if t >= 1:
                self.ring_return = None
                self.rest_rotation = self.ring_stop_target
            return rotation
        d = self.dialer
        elapsed = now - d.started if d.state == 'dialing' else d.cycle_elapsed(len(d.sequence))
        return ring_rotation(d.sequence, elapsed, d.lock_seconds, initial_rotation=self.rest_rotation, rpm=d.rotation_rpm)

    # Cancel dialing or close a connection while preserving the appropriate animation.
    def stop_gate(self, now):
        was_connected = self.dialer.state == 'connected'
        if was_connected:
            self.last_connected_sequence = tuple(self.dialer.sequence)
        if self.dialer.state in ('dialing', 'dhd_wait', 'ready', 'activating'):
            rotation = self.track_rotation(now)
            speed = ring_rotation(
                self.dialer.sequence, now-self.dialer.started,
                self.dialer.lock_seconds, velocity=True,
                initial_rotation=self.rest_rotation, rpm=self.dialer.rotation_rpm) if self.dialer.state == 'dialing' else 0.0
            if abs(speed) > 1e-6:
                # Brake over roughly 1.5 seconds, extending to the next whole
                # tile in the same direction so the top chevron stays centered.
                projected = rotation + speed * .75
                tile = math.ceil(projected / TILE_ANGLE) if speed > 0 else math.floor(projected / TILE_ANGLE)
                self.ring_stop_target = tile * TILE_ANGLE
                initial = rotation - self.ring_stop_target
                duration = 2 * abs(initial / speed)
            else:
                self.ring_stop_target = round(rotation / TILE_ANGLE) * TILE_ANGLE
                initial = rotation-self.ring_stop_target
                speed = 0.0
                duration = .3
            self.ring_return = (now, initial, duration, speed)
        self.dialer.shutdown()
        if was_connected:
            self.begin_horizon_close(now)

    # Start center-out expansion using the opening sound duration.
    def begin_horizon_open(self, now):
        self.gate_audio.update(self.dialer, self.ring_return, now, self.dialer.spin_fraction(now))
        self.horizon_opening = (now, self.gate_audio.open_duration * .5)

    # Retain slot contents and synchronize closure with the closing sound.
    def begin_horizon_close(self, now):
        self.slot_fade_started = None
        self.closing_glyphs = self.last_connected_sequence
        self.rest_rotation = self.last_ring_rotation
        self.horizon_opening = None
        self.gate_audio.update(self.dialer, self.ring_return, now, self.dialer.spin_fraction(now))
        self.horizon_closing = (now, self.gate_audio.close_duration)

    # Draw the soft idle/dialing glow, completely invisible at minimum size.
    def draw_center_pulse(self, now):
        return self.renderer.draw_center_pulse(now)

    # Rotate tile dividers without drawing constellation symbols on the ring.
    def draw_glyph_track(self, now):
        return self.renderer.draw_glyph_track(now)

    # Feed opposite-moving number streams, then drain them after stopping.
    def draw_telemetry(self, now):
        return self.renderer.draw_telemetry(now)

    # Build and cache the blue radial gradient used by the wormhole.
    def make_event_horizon(self):
        return self.renderer.make_event_horizon()

    # Render the active pulse and center-out opening or feathered closing effects.
    def draw_event_horizon(self, now):
        return self.renderer.draw_event_horizon(now)

    # Draw a button and register its enabled click target for this frame.
    def button(self, rect, label, action, enabled=True):
        rect = pygame.Rect(rect)
        hot = rect.collidepoint(self.mouse)
        pygame.draw.rect(self.canvas, (18, 48, 57) if hot and enabled else (7, 23, 31), rect)
        self.panel(rect, CYAN if enabled else DIM)
        self.text(label, (rect.x + 10, rect.y + 10), 15, WHITE if enabled else DIM)
        self.buttons.append((rect, action, enabled))

    # Calculate evenly spaced right-hand slots for the selected address length.
    def glyph_slot(self, index):
        return self.renderer.glyph_slot(index)

    # Crossfade between status labels while retaining the slow opacity pulse.
    def draw_status_text(self, status, color, now):
        return self.renderer.draw_status_text(status, color, now)

    # Scale a glyph with either shared sizing or individual fit-to-slot sizing.
    def slot_glyph_image(self, glyph_id, slot, color=WHITE):
        return self.renderer.slot_glyph_image(glyph_id, slot, color)

    # Place a prepared glyph image at the center of its address slot.
    def draw_slot_glyph(self, glyph_id, slot, color=WHITE, alpha=255):
        return self.renderer.draw_slot_glyph(glyph_id, slot, color, alpha)

    # Fade one stored slot at a time after the event horizon has fully closed.
    def slot_fade_alpha(self, index, now):
        return self.renderer.slot_fade_alpha(index, now)

    def update_slot_fade(self, now):
        return self.renderer.update_slot_fade(now)

    # Compose the live main console, then draw any active menu overlay.
    def draw(self, now):
        return self.renderer.draw(now)

    # Create or reopen the separate resizable glyph keyboard near the console bottom.
    def open_keyboard(self):
        return self.keyboard.open_keyboard()

    # Render keyboard controls on their own surface without replacing main-window targets.
    def draw_keyboard(self):
        return self.keyboard.draw_keyboard()

    # Handle only keyboard-window input, hiding it on close and blocking modal input.
    def keyboard_event(self, event, now):
        return self.keyboard.keyboard_event(event, now)

    # Dispatch shared button actions from either window to the simulator.
    def action(self, action, now):
        d = self.dialer
        if isinstance(action, int):
            previous_count = len(d.selected)
            previous_origin = d.origin_selected
            if self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None:
                d.select(action, now)
            if len(d.selected) > previous_count or d.origin_selected != previous_origin:
                self.play_button_sound()
        elif isinstance(action, tuple) and action[0] == 'mode':
            if self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None:
                d.set_symbol_count(action[1])
        elif action == 'undo' and d.state == 'idle' and d.selected:
            if d.origin_selected:
                d.origin_selected = False
            else:
                d.selected.pop()
            d.destination = 'MANUAL ADDRESS'
        elif action == 'clear':
            d.reset()
        elif action == 'dial':
            if d.behavior == 'dhd':
                if d.activate(now):
                    self.activation_press_played = self.glyph_sound_mode == 'atlantis'
                    if self.activation_press_played:
                        self.play_button_sound(dial=True)
                    self.play_pending_activation_sound()
            elif self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None and d.start(now + .6):
                self.play_button_sound(dial=True)
        elif action == 'toggle_dialing':
            if d.state in ('idle', 'failed') and self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None:
                mode = 'current' if d.behavior == 'dhd' else 'dhd'
                if d.set_behavior(mode):
                    self.dialing_behavior_option = mode
        elif action == 'iris':
            self.set_iris(not self.iris.target_closed, now)
        elif action == 'shutdown':
            self.stop_gate(now)
        elif action == 'keyboard':
            self.open_keyboard()
        elif action == 'options':
            self.options_open = True
            self.command_focus = False
        elif action == 'load' and d.state == 'idle':
            self.archive_open = True
            self.archive_drag_offset = None
            self.archive_info = None
            self.archive_search_focus = True
            self.command_focus = False
            self.archive_scroll = 0

    # Iris state is independent of dialing and remains in place after shutdown.
    def set_iris(self, closed, now):
        if bool(closed) == self.iris.target_closed:
            return
        cue = 'iris_close' if closed else 'iris_open'
        duration = self.gate_audio.play(cue, 'iris') or 1.2
        self.iris.set_closed(closed, now, duration)

    # Show glyph sizing and sound controls; dialing mode lives on the keyboard.
    def draw_options(self):
        return self.options.draw_options()

    # Play the delayed DHD activation cue once, unless Atlantis already played it.
    def play_pending_activation_sound(self):
        if self.dialer.consume_activation_sound():
            if not self.activation_press_played:
                self.play_button_sound(dial=True)
            self.activation_press_played = False

    # Apply menu settings without allowing dialing behavior to change mid-operation.
    def options_event(self, event):
        return self.options.options_event(event)

    # Filter destination names and unordered sets of selected glyphs together.
    def archive_results(self):
        return self.archive.archive_results()

    # Clamp archive row scrolling to the current filtered result count.
    def archive_scroll_by(self, amount):
        return self.archive.archive_scroll_by(amount)

    # Render the searchable destination table and interactive scrollbar.
    def draw_archive(self):
        return self.archive.draw_archive()

    # Derive scrollbar track and thumb geometry from visible rows and scroll position.
    def archive_scrollbar(self):
        return self.archive.archive_scrollbar()

    # Convert held mouse movement into a clamped archive row offset.
    def drag_archive_scrollbar(self, mouse_y):
        return self.archive.drag_archive_scrollbar(mouse_y)

    # Show a destination address, eligibility, and profile fields for later expansion.
    def draw_address_info(self):
        return self.archive.draw_address_info()

    # Route archive searches, glyph filters, row loading, INFO, and scrollbar dragging.
    def archive_event(self, event):
        return self.archive.archive_event(event)

    # Interpret the small simulator command set, never operating-system commands.
    def execute_command(self, now):
        return self.commands.execute_command(now)

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
            self.mouse = ((mx - viewport.x) * W / viewport.width, (my - viewport.y) * H / viewport.height)
            # Update logical state before effects so opening/closing cues fire once.
            previous_state = self.dialer.state
            if previous_state == 'connected':
                self.last_connected_sequence = tuple(self.dialer.sequence)
            self.dialer.update(now)
            self.play_pending_activation_sound()
            if previous_state != 'connected' and self.dialer.state == 'connected':
                self.begin_horizon_open(now)
            if previous_state == 'connected' and self.dialer.state != 'connected':
                self.begin_horizon_close(now)
            self.draw(now)
            self.draw_keyboard()
            for event in pygame.event.get():
                event_window = getattr(event, 'window', None)
                window_id = getattr(event_window, 'id', event_window)
                if self.keyboard_window is not None and window_id == self.keyboard_window.id:
                    self.keyboard_event(event, now)
                    continue
                if hasattr(event, 'pos'):
                    self.mouse = ((event.pos[0]-viewport.x)*W/viewport.width,
                                  (event.pos[1]-viewport.y)*H/viewport.height)
                if event.type == pygame.QUIT or event.type == pygame.WINDOWCLOSE:
                    running = False
                elif self.options_open:
                    self.options_event(event)
                elif self.archive_open:
                    self.archive_event(event)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.command_focus = pygame.Rect(596, 891, 609, 35).collidepoint(self.mouse)
                    for rect, action, enabled in self.buttons:
                        if enabled and rect.collidepoint(self.mouse):
                            self.action(action, now)
                            break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.stop_gate(now)
                        self.command_focus = False
                    elif self.command_focus:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            if self.command.strip():
                                self.execute_command(now)
                            else:
                                self.action('dial', now)
                        elif event.key == pygame.K_BACKSPACE:
                            self.command = self.command[:-1]
                        elif event.unicode.isprintable() and len(self.command) < 45:
                            self.command += event.unicode
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.action('dial', now)
                    elif event.key == pygame.K_BACKSPACE:
                        self.action('undo', now)
            self.gate_audio.update(self.dialer, self.ring_return, now, self.dialer.spin_fraction(now))
            # Reacquire the surface each frame because resizing can replace it.
            surface = self.window.get_surface()
            surface.fill((0, 0, 0))
            surface.blit(pygame.transform.smoothscale(self.canvas, viewport.size), viewport)
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
        app.mouse = (-1, -1)
        app.dialer.selected = address_database['Abydos']['Address'][:]
        app.dialer.start(0)
        preview_time = app.dialer.cycle_elapsed(len(app.dialer.sequence))
        app.dialer.update(preview_time)
        app.draw(preview_time)
        pygame.image.save(app.canvas, str(args.preview))
        pygame.quit()
    else:
        app.run()



