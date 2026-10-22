"""SGC dialing console. Run with: python main.py"""
import math
import time
import random
import argparse
import textwrap
from pathlib import Path
import pygame
from glyph import Glyph
from glyph_database import glyphs, address_database
from simulator import Dialer
from gate_audio import GateAudio
from iris import Iris

# Console dimensions, palette, and shared gate geometry.
W, H = 1280, 960
BG = (3, 10, 16)
CYAN = (65, 208, 220)
DIM = (24, 76, 87)
RED = (248, 65, 47)
WHITE = (235, 246, 243)
YELLOW = (207, 216, 147)
GREEN = (127, 226, 103)
CENTER = (640, 435)
GATE_SCALE = 1.18
HORIZON_RADIUS = round(201 * GATE_SCALE)
# Clockwise from the top, matching the physical gate chevrons.
CHEVRON_ANGLES = (40, 80, 120, 240, 280, 320, 160, 200)
ORIGIN_ANGLE = 0


# Map address order to physical chevrons, with Earth at the top last.
def dialing_angles(symbol_count=7):
    """Origin is always last; longer addresses use the bottom chevrons."""
    if symbol_count not in (7, 8, 9):
        raise ValueError('Addresses must contain seven, eight, or nine symbols')
    return CHEVRON_ANGLES[:symbol_count - 1] + (ORIGIN_ANGLE,)


# Route each chevron to its slot through clear exterior wiring lanes.
def connector_route(angle, slot, lane):
    """Route away from the ring before using exterior wiring corridors."""
    start = polar(264, angle - 90)
    outer = polar(272 if angle == 200 else 280, angle - 90)
    # The last four wires descend outside the slot column and enter from
    # the right; the first three approach from the gate side.
    right_x = slot.right + 20 + (lane - 3) * 12 if lane >= 3 else 985 + lane * 12
    wire_y = slot.centery
    endpoint = slot.midright if lane >= 3 else slot.midleft
    top_y = {0: 56, 320: 66, 280: 76, 240: 86, 200: 96, 160: 106}.get(angle, 56)
    if angle == 0:
        return [start, (start[0], top_y), (right_x, top_y),
                (right_x, wire_y), endpoint]
    if angle == 160:
        # Reach the exterior wiring lane above the column, never through a slot.
        return [start, outer, (990, outer[1]), (990, top_y),
                (right_x, top_y), (right_x, wire_y), endpoint]
    if angle > 180:
        # Left-hand chevrons travel around the upper-left outside the gate.
        # The eighth chevron uses the inner left corridor, farther from diagnostics.
        left_x = 268 if angle == 200 else 258 - (lane - 3) * 10
        return [start, outer, (left_x, outer[1]), (left_x, top_y),
                (right_x, top_y), (right_x, wire_y), endpoint]
    return [start, outer, (right_x, outer[1]),
            (right_x, wire_y), endpoint]


# Convert gate-local radii and angles into scaled screen coordinates.
def polar(radius, angle):
    radius *= GATE_SCALE
    a = math.radians(angle)
    return CENTER[0] + math.cos(a) * radius, CENTER[1] + math.sin(a) * radius


TILE_ANGLE = 360 / 39
SPIN_FRACTION = 8 / 10.8  # Eight seconds rotating, 2.2 engaging, then a 0.6-second pause.


# Calculate alternating rotation and matching velocity with smooth easing.
def ring_rotation(sequence, elapsed, lock_seconds, velocity=False, initial_rotation=0.0):
    """Continuous alternating travel; each stop centers its symbol's tile at top."""
    rotation = initial_rotation
    elapsed = max(0, elapsed)
    for index, glyph_id in enumerate(sequence):
        direction = 1 if index % 2 == 0 else -1
        target = -glyph_id * TILE_ANGLE
        distance = ((target - rotation) * direction) % 360
        if distance < 180:
            distance += 360
        delta = direction * distance
        phase = (elapsed - index * lock_seconds) / lock_seconds
        if phase <= 0:
            return 0.0 if velocity else rotation
        if phase < SPIN_FRACTION:
            t = phase / SPIN_FRACTION
            if velocity:
                return delta * 30 * t * t * (1 - t) ** 2 / (lock_seconds * SPIN_FRACTION)
            return rotation + delta * t ** 3 * (10 - 15 * t + 6 * t * t)
        rotation += delta
        if phase < 1:
            return 0.0 if velocity else rotation
    return 0.0 if velocity else rotation


class Console:
    # Initialize windows, cached assets, simulator state, menus, and visual effects.
    def __init__(self):
        pygame.init()
        self.load_button_sounds()
        self.gate_audio = GateAudio()
        self.window = pygame.Window('SGC • Stargate Dialing Computer', size=(W, H), resizable=True)
        self.canvas = pygame.Surface((W, H))
        self.keyboard_window = None
        self.keyboard_visible = False
        self.keyboard_canvas = pygame.Surface((1280, 240))
        self.keyboard_buttons = []
        self.keyboard_mouse = (-1, -1)
        self.clock = pygame.time.Clock()
        self.fonts = {}
        self.glyph = Glyph()
        slot_sources = [self.glyph.image(i, 215) for i in range(len(glyphs))]
        self.slot_reference_size = (max(image.get_width() for image in slot_sources),
                                    max(image.get_height() for image in slot_sources))
        self.dialer = Dialer()
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
        self.hover = None
        self.buttons = []
        self.destinations = [(n, d) for n, d in address_database.items() if len(d['Address']) in (6, 7, 8)]
        self.uniform_glyph_sizing = True
        self.dialing_behavior_option = 'current'
        self.options_open = False
        self.archive_open = False
        self.archive_info = None
        self.archive_drag_offset = None
        self.archive_query = ''
        self.archive_glyphs = set()
        self.archive_scroll = 0
        self.archive_search_focus = False
        self.base = pygame.Surface((W, H))
        self.draw_static()
        self.event_horizon = self.make_event_horizon()
        self.horizon_closing = None
        self.last_connected_sequence = ()
        self.closing_glyphs = ()
        self.slot_fade_started = None
        self.horizon_opening = None

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
            self.fonts[size] = pygame.font.SysFont('consolas', size, bold=True)
        (surface or self.canvas).blit(self.fonts[size].render(str(text), True, color), pos)

    # Center archive constellation labels and fit long names within their cells.
    def centered_slot_text(self, text, cell, y, size, color):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.SysFont('consolas', size, bold=True)
        label = self.fonts[size].render(text, True, color)
        if label.get_width() > cell.width - 8:
            label = pygame.transform.smoothscale(label, (cell.width - 8, label.get_height()))
        self.canvas.blit(label, label.get_rect(midtop=(cell.centerx, y)))

    # Draw a thin rectangular border on the chosen surface.
    def panel(self, rect, color=CYAN, surface=None):
        pygame.draw.rect(surface or self.canvas, color, rect, 1)

    # Cache the fixed console frame, ring boundaries, and diagnostic panels.
    def draw_static(self):
        s = self.base
        s.fill(BG)
        pygame.draw.rect(s, CYAN, (16, 16, 1248, 928), 2, border_radius=24)

        for radius, color, width in [(255, CYAN, 2), (247, DIM, 2), (232, YELLOW, 2), (210, YELLOW, 2), (203, CYAN, 2)]:
            pygame.draw.circle(s, color, CENTER, round(radius * GATE_SCALE), width)
        for clockwise_angle in range(20, 360, 40):
            if clockwise_angle in (100, 180, 260):
                continue
            angle = clockwise_angle - 90
            pygame.draw.line(s, WHITE, polar(269, angle - 2), polar(269, angle + 2), 5)
        for y in (115, 370):
            self.panel((35, y, 182, 235), surface=s)
            self.text('TELEMETRY' if y == 115 else 'SUBSPACE ARRAY', (43, y + 8), 14, surface=s)
        self.panel((35, 625, 182, 247), surface=s)
        self.text('CHEVRON STATUS', (44, 636), 15, surface=s)
        self.panel((358, 790, 565, 82), surface=s)
        self.text('CONNECTION STATUS', (367, 774), 12, YELLOW, s)

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
        elapsed = now - d.started if d.state == 'dialing' else len(d.sequence) * d.lock_seconds
        return ring_rotation(d.sequence, elapsed, d.lock_seconds, initial_rotation=self.rest_rotation)

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
                initial_rotation=self.rest_rotation) if self.dialer.state == 'dialing' else 0.0
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
        self.gate_audio.update(self.dialer, self.ring_return, now, SPIN_FRACTION)
        self.horizon_opening = (now, self.gate_audio.open_duration * .5)

    # Retain slot contents and synchronize closure with the closing sound.
    def begin_horizon_close(self, now):
        self.slot_fade_started = None
        self.closing_glyphs = self.last_connected_sequence
        self.rest_rotation = self.last_ring_rotation
        self.horizon_opening = None
        self.gate_audio.update(self.dialer, self.ring_return, now, SPIN_FRACTION)
        self.horizon_closing = (now, self.gate_audio.close_duration)

    # Draw the soft idle/dialing glow, completely invisible at minimum size.
    def draw_center_pulse(self, now):
        if self.horizon_closing is not None or self.dialer.state not in ('idle', 'dialing', 'dhd_wait', 'ready', 'activating'):
            return
        pulse = (1 - math.cos(now * math.tau / 3.2)) / 2
        radius = round(40 * GATE_SCALE * pulse)
        if radius < 1:
            return
        # Transparent edge blends with whatever is beneath the glow.
        glow = pygame.Surface((radius * 2 + 1, radius * 2 + 1), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            falloff = (1 - r / radius) ** 2
            alpha = round(220 * pulse * falloff)
            pygame.draw.circle(glow, (*CYAN, alpha), (radius, radius), r)
        glow.set_at((radius, radius), (*CYAN, round(220 * pulse)))
        self.canvas.blit(glow, (CENTER[0] - radius, CENTER[1] - radius))

    # Rotate tile dividers without drawing constellation symbols on the ring.
    def draw_glyph_track(self, now):
        rotation = self.track_rotation(now)
        self.last_ring_rotation = rotation
        for tile in range(39):
            # Boundaries straddle the top chevron when a tile is engaged.
            angle = -90 - TILE_ANGLE / 2 + tile * TILE_ANGLE + rotation
            pygame.draw.line(self.canvas, YELLOW, polar(211, angle), polar(231, angle), 1)

    # Feed opposite-moving number streams, then drain them after stopping.
    def draw_telemetry(self, now):
        """Feed rows from opposite edges, then drain the existing stream on stop."""
        active = self.dialer.state in ('dialing', 'dhd_wait', 'ready', 'activating', 'connected')
        if active:
            if not self.telemetry_running:
                self.telemetry_started = self.dialer.started
                self.telemetry_stopped = None
        elif self.telemetry_running:
            self.telemetry_stopped = now
        self.telemetry_running = active
        if not active and self.telemetry_stopped is None:
            return
        elapsed = max(0, now - self.telemetry_started)
        if elapsed <= 0:
            return
        previous_clip = self.canvas.get_clip()
        try:
            for panel_index, y in enumerate((115, 370)):
                area = pygame.Rect(43, y + 31, 166, 194)
                self.canvas.set_clip(area)
                speed = 23 + panel_index * 6
                position = elapsed * speed
                first_row = max(0, int((position-area.height) // 15) - 1)
                last_row = int(position // 15)
                if self.telemetry_stopped is not None:
                    # No new rows enter after the gate stops; existing rows coast out.
                    admitted = max(0, self.telemetry_stopped-self.telemetry_started) * speed
                    last_row = min(last_row, int(admitted // 15))
                for row in range(first_row, last_row + 1):
                    rng = random.Random((panel_index + 1) * 1000003 + row)
                    bits = ''.join(rng.choice('01') for _ in range(17))
                    row_y = (area.bottom + row*15 - position if panel_index == 0
                             else area.top - 15 - row*15 + position)
                    self.text(bits, (area.x, row_y), 13, YELLOW)
        finally:
            self.canvas.set_clip(previous_clip)
        if self.telemetry_stopped is not None and now-self.telemetry_stopped > 10:
            self.telemetry_stopped = None

    # Build and cache the blue radial gradient used by the wormhole.
    def make_event_horizon(self):
        radius = HORIZON_RADIUS
        diameter = radius * 2 + 1
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        for y in range(diameter):
            for x in range(diameter):
                distance = math.hypot(x-radius, y-radius) / radius
                if distance <= 1:
                    # Opaque center; a gentle color and opacity fade near the rim.
                    edge = max(0, (distance - .35) / .65)
                    edge = edge * edge * (3 - 2 * edge)
                    surface.set_at((x, y), (round(65-25*edge), round(175-45*edge),
                                             round(245-35*edge), round(255-65*edge)))
        return surface

    # Render the active pulse and center-out opening or feathered closing effects.
    def draw_event_horizon(self, now):
        image = self.event_horizon
        if self.dialer.state == 'connected':
            # A subtle 3.2-second breathing cycle; keep opacity and size intact.
            pulse = (1 - math.cos(now * math.tau / 3.2)) / 2
            brightness = round(235 + 20 * pulse)
            image = image.copy()
            image.fill((brightness, brightness, brightness, 255),
                       special_flags=pygame.BLEND_RGBA_MULT)
        if self.horizon_closing is not None:
            started, duration = self.horizon_closing
            progress = max(0, min(1, (now-started)/duration))
            if progress >= 1:
                self.horizon_closing = None
                self.slot_fade_started = started + duration
                return
            image = image.copy()
            # A broad, feathered clearing front travels from center to rim.
            feather = round(70 * GATE_SCALE)
            front = (HORIZON_RADIUS + feather) * progress * progress * (3-2*progress)
            mask = pygame.Surface(image.get_size(), pygame.SRCALPHA)
            mask.fill((255, 255, 255, 255))
            for radius in range(HORIZON_RADIUS, -1, -1):
                opacity = max(0, min(1, (radius-front+feather) / feather))
                opacity = opacity * opacity * (3-2*opacity)
                alpha = round(255 * opacity)
                if radius:
                    pygame.draw.circle(mask, (255, 255, 255, alpha),
                                       (HORIZON_RADIUS, HORIZON_RADIUS), radius)
                else:
                    mask.set_at((HORIZON_RADIUS, HORIZON_RADIUS), (255, 255, 255, alpha))
            image.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        elif self.dialer.state != 'connected':
            return
        elif self.horizon_opening is not None:
            started, duration = self.horizon_opening
            progress = max(0, min(1, (now-started)/duration))
            if progress >= 1:
                self.horizon_opening = None
            else:
                radius = round(HORIZON_RADIUS * progress * progress * (3-2*progress))
                if radius < 1:
                    return
                # Scale the full gradient so the growing disk retains its fade.
                diameter = radius * 2 + 1
                image = pygame.transform.smoothscale(image, (diameter, diameter))
                self.canvas.blit(image, (CENTER[0]-radius, CENTER[1]-radius))
                return
        self.canvas.blit(image, (CENTER[0]-HORIZON_RADIUS, CENTER[1]-HORIZON_RADIUS))

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
        top, bottom, gap = 116, 872, 8
        count = self.dialer.symbol_count
        height = (bottom - top - gap * (count - 1)) / count
        y = round(top + index * (height + gap))
        end = round(top + index * (height + gap) + height)
        return pygame.Rect(1040, y, 133, end - y)

    # Crossfade between status labels while retaining the slow opacity pulse.
    def draw_status_text(self, status, color, now):
        panel = pygame.Rect(358, 790, 565, 82)
        if 52 not in self.fonts:
            self.fonts[52] = pygame.font.SysFont('consolas', 52, bold=True)
        image = self.fonts[52].render(status, True, color)
        image = image.subsurface(image.get_bounding_rect()).copy()
        image = pygame.transform.smoothscale(image,
            (min(panel.width-24, round(image.get_width()*2.1)), panel.height-16))
        target = pygame.Surface(panel.size, pygame.SRCALPHA)
        target.blit(image, image.get_rect(center=(panel.width//2, panel.height//2)))
        key = (status, tuple(color))
        if key != self.status_key:
            self.status_fade_source = self.status_blend.copy() if self.status_blend is not None else None
            self.status_fade_started = now
            self.status_key = key
        blend = target
        if self.status_fade_source is not None:
            progress = max(0, min(1, (now-self.status_fade_started)/.8))
            if progress >= 1:
                self.status_fade_source = None
            elif progress <= 0:
                blend = self.status_fade_source.copy()
            else:
                progress = progress*progress*(3-2*progress)
                blend = pygame.Surface(panel.size, pygame.SRCALPHA)
                outgoing = self.status_fade_source.copy()
                outgoing.set_alpha(round(255*(1-progress)))
                incoming = target.copy()
                incoming.set_alpha(round(255*progress))
                blend.blit(outgoing, (0, 0))
                blend.blit(incoming, (0, 0))
        # Store the unpulsed blend so interrupted transitions remain continuous.
        self.status_blend = blend.copy()
        blend.set_alpha(round(255*(1-math.cos(now*math.tau/4.0))/2))
        self.canvas.blit(blend, panel.topleft)

    # Scale a glyph with either shared sizing or individual fit-to-slot sizing.
    def slot_glyph_image(self, glyph_id, slot, color=WHITE):
        area = pygame.Rect(slot.left + 6, slot.top + 6, slot.width - 12, slot.height - 12)
        image = self.glyph.image(glyph_id, 215, color)
        # Uniform uses one reference scale; fit-to-slot restores per-glyph sizing.
        reference = self.slot_reference_size if self.uniform_glyph_sizing else image.get_size()
        scale = min(area.width / reference[0], area.height / reference[1])
        image = pygame.transform.smoothscale(image, (max(1, round(image.get_width()*scale)),
                                                     max(1, round(image.get_height()*scale))))
        return image, area.center

    # Place a prepared glyph image at the center of its address slot.
    def draw_slot_glyph(self, glyph_id, slot, color=WHITE, alpha=255):
        image, center = self.slot_glyph_image(glyph_id, slot, color)
        image.set_alpha(alpha)
        self.canvas.blit(image, image.get_rect(center=center))

    # Fade one stored slot at a time after the event horizon has fully closed.
    def slot_fade_alpha(self, index, now):
        if self.slot_fade_started is None:
            return 255
        progress = max(0, min(1, (now-self.slot_fade_started-index*.35)/.35))
        return round(255*(1-progress*progress*(3-2*progress)))

    def update_slot_fade(self, now):
        if self.slot_fade_started is not None and now >= self.slot_fade_started + len(self.closing_glyphs)*.35:
            self.closing_glyphs = ()
            self.slot_fade_started = None

    # Compose the live main console, then draw any active menu overlay.
    def draw(self, now):
        self.canvas.blit(self.base, (0, 0))
        self.buttons = []
        d = self.dialer
        self.draw_telemetry(now)
        self.draw_glyph_track(now)
        self.draw_center_pulse(now)
        self.draw_event_horizon(now)
        self.update_slot_fade(now)
        self.iris.draw(self.canvas, CENTER, HORIZON_RADIUS, now, YELLOW)
        illuminated_chevrons = len(self.closing_glyphs) if self.horizon_closing is not None else d.locked
        # Gate chevrons, exterior connections, and address slot contents.
        active_angles = dialing_angles(d.symbol_count)
        # Inactive bottom chevrons are drawn without a glyph-slot connection.
        for index, clockwise_angle in enumerate(active_angles + tuple(a for a in CHEVRON_ANGLES if a not in active_angles)):
            angle = clockwise_angle - 90
            color = RED if index < illuminated_chevrons else CYAN if index >= d.symbol_count else DIM
            # Match the inner trapezoid, with the outer top base slightly
            # inward (lower on the top chevron) relative to the inner top base.
            outer_outline = [
                polar(250, angle - 6),
                polar(250, angle + 6),
                polar(218, angle + 2.5),
                polar(218, angle - 2.5),
            ]
            # Equal-radius vertex pairs produce parallel bases and mirrored sides.
            inner_outline = [
                polar(259, angle - 3.4),   # Wide outer base.
                polar(259, angle + 3.4),
                polar(228, angle + 1.25), # Narrow inner base.
                polar(228, angle - 1.25),
            ]
            # Trim the outer stroke before filling the inner chevron.
            vertices = outer_outline + inner_outline
            bounds = pygame.Rect(
                math.floor(min(x for x, y in vertices)) - 4,
                math.floor(min(y for x, y in vertices)) - 4,
                math.ceil(max(x for x, y in vertices)) - math.floor(min(x for x, y in vertices)) + 9,
                math.ceil(max(y for x, y in vertices)) - math.floor(min(y for x, y in vertices)) + 9,
            )
            layer = pygame.Surface(bounds.size, pygame.SRCALPHA)
            local_outer = [(x - bounds.x, y - bounds.y) for x, y in outer_outline]
            local_inner = [(x - bounds.x, y - bounds.y) for x, y in inner_outline]
            pygame.draw.polygon(layer, (0, 0, 0, 255), local_outer)
            pygame.draw.polygon(layer, color, local_outer, 3)
            pygame.draw.polygon(layer, (0, 0, 0, 0), local_inner)
            self.canvas.blit(layer, bounds.topleft)
            pygame.draw.polygon(self.canvas, (0, 0, 0), inner_outline)
            pygame.draw.polygon(self.canvas, color, inner_outline, 2)
            if index < d.symbol_count:
                slot = self.glyph_slot(index)
                route = connector_route(clockwise_angle, slot, index)
                pygame.draw.lines(self.canvas, color, False, route, 2)
                closing_glyph = self.horizon_closing is not None and index < len(self.closing_glyphs)
                self.panel(slot, RED if index < d.locked or closing_glyph else DIM)
                self.text(index + 1, (slot.left - 25, slot.top + 3), 18, WHITE)
                if index < len(self.closing_glyphs) and (closing_glyph or self.slot_fade_started is not None):
                    alpha = self.slot_fade_alpha(index, now)
                    if alpha:
                        self.draw_slot_glyph(self.closing_glyphs[index], slot, alpha=alpha)
                elif index < d.locked:
                    self.draw_slot_glyph(d.sequence[index], slot)
                elif d.state == 'idle' and index < len(d.selected):
                    self.draw_slot_glyph(d.selected[index], slot, CYAN)
                elif d.state == 'idle' and index == d.symbol_count - 1 and d.origin_selected:
                    self.draw_slot_glyph(0, slot, CYAN)
        # Three-stage glyph motion: top-to-center, center hold, then slot placement.
        cycle_progress = d.dialing_position(now)[1]
        if d.state == 'dialing' and now >= d.started and d.locked < d.symbol_count and cycle_progress >= SPIN_FRACTION:
            progress = (cycle_progress - SPIN_FRACTION) / (1 - SPIN_FRACTION)
            if progress < 1.34 / 2.8:
                travel = progress / (1.34 / 2.8)
                travel = travel * travel * (3 - 2 * travel)
                origin = polar(239, -90)
                center = (origin[0] + (CENTER[0] - origin[0]) * travel,
                          origin[1] + (CENTER[1] - origin[1]) * travel)
                size = round(24 + 191 * travel)
            else:
                flight = min(1.0, max(0, (progress - 1.66 / 2.8) / (.54 / 2.8)))
                flight = flight * flight * (3 - 2 * flight)
                slot_image, target = self.slot_glyph_image(d.sequence[d.locked], self.glyph_slot(d.locked))
                center = (CENTER[0] + (target[0] - CENTER[0]) * flight,
                          CENTER[1] + (target[1] - CENTER[1]) * flight)
                size = round(215 - 166 * flight)
            if progress >= 1.66 / 2.8:
                source = self.glyph.image(d.sequence[d.locked], 215)
                scale = min(215/source.get_width(), 215/source.get_height(), 1)
                start_width, start_height = source.get_width()*scale, source.get_height()*scale
                width = max(1, round(start_width + (slot_image.get_width()-start_width)*flight))
                height = max(1, round(start_height + (slot_image.get_height()-start_height)*flight))
                image = pygame.transform.smoothscale(source, (width, height))
                self.canvas.blit(image, image.get_rect(center=center))
            else:
                self.glyph.draw(self.canvas, d.sequence[d.locked], center, size, fit=(size, size))
            #self.text(f'ACQUIRING SYMBOL {d.locked + 1}', (435, 505), 17, YELLOW)

        # Diagnostic lock indicators, destination header, and connection status.
        for i in range(d.symbol_count):
            y = 670 + i * (27 if d.symbol_count == 7 else 22)
            color = GREEN if i < illuminated_chevrons else DIM
            pygame.draw.rect(self.canvas, color, (46, y + 3, 45, 9))
            self.text(f'{i + 1}  {"OK" if i < illuminated_chevrons else "--"}', (106, y), 15, color)
        destination_label = d.destination[:24]
        label_border = pygame.Rect(1107, 22, 133, 30)
        if 16 not in self.fonts:
            self.fonts[16] = pygame.font.SysFont('consolas', 16, bold=True)
        label_image = self.fonts[16].render(destination_label, True, WHITE)
        if label_image.get_width() > label_border.width - 12:
            label_image = pygame.transform.smoothscale(
                label_image, (label_border.width - 12, label_image.get_height()))
        self.panel(label_border, CYAN)
        self.canvas.blit(label_image, label_image.get_rect(center=label_border.center))
        status = {'idle': 'IDLE', 'dialing': 'DIALING', 'connected': 'ACTIVE', 'failed': 'ERROR', 'dhd_wait': 'INPUT', 'ready': 'READY', 'activating': 'WAIT'}[d.state]
        if self.horizon_closing is not None:
            status = 'CLOSING'
        self.draw_status_text(status, RED if d.state in ('connected', 'failed') else CYAN, now)
        if d.state == 'connected':
            seconds = math.ceil(d.remaining(now))
            self.text('WORMHOLE TIMER', (235, 805), 12, YELLOW)
            self.text(f'{seconds // 60:02}:{seconds % 60:02}', (245, 827), 24, WHITE)
        self.text(d.message.replace('—', '/'), (358, 751), 13, YELLOW)

        idle = d.state == 'idle' and self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None
        self.button((35, 883, 182, 30), 'LOAD DESTINATION', 'load', idle)
        self.panel((596, 891, 609, 35), CYAN if self.command_focus else DIM)
        self.text('> ' + self.command + ('_' if self.command_focus else '  [click: help / dial NAME / shutdown]'), (605, 900), 13, WHITE)
        self.button((35, 86, 182, 24), 'OPTIONS', 'options')
        self.button((245, 883, 215, 30), 'GLYPH KEYBOARD', 'keyboard')
        if self.archive_open:
            self.draw_archive()
        elif self.options_open:
            self.draw_options()

    # Create or reopen the separate resizable glyph keyboard near the console bottom.
    def open_keyboard(self):
        if self.keyboard_window is None:
            x, y = self.window.position
            desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
            width = min(1280, desktop_w-40)
            self.keyboard_window = pygame.Window(
                'SGC / Glyph Keyboard', size=(width, 240), resizable=True,
                position=(max(0, min(x, desktop_w-width)),
                          max(0, min(y+round(self.window.size[1]*.74), desktop_h-280))))
        self.keyboard_visible = True
        self.keyboard_window.show()
        self.keyboard_window.focus()

    # Render keyboard controls on their own surface without replacing main-window targets.
    def draw_keyboard(self):
        previous_canvas, previous_buttons, previous_mouse = self.canvas, self.buttons, self.mouse
        self.canvas = self.keyboard_canvas
        self.buttons = []
        self.mouse = self.keyboard_mouse
        self.canvas.fill(BG)
        self.text('GLYPH KEYBOARD / EARTH + 38 DESTINATION SYMBOLS', (35, 72), 13, CYAN)
        pygame.draw.rect(self.canvas, CYAN, (8, 8, 1264, 224), 2, border_radius=12)
        d = self.dialer
        try:
            idle = d.state == 'idle' and self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None
            accepting_glyphs = (idle or (d.behavior == 'dhd' and d.state in ('dialing', 'dhd_wait'))) and self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None
            self.button((35, 19, 235, 42), 'EARTH / ORIGIN', 0, accepting_glyphs and len(d.selected) == d.symbol_count - 1 and not d.origin_selected)
            self.glyph.draw(self.canvas, 0, (241, 40), 30, GREEN if d.origin_selected else CYAN, (30, 30))
            for count in (7, 8, 9):
                self.button((335 + (count-7)*80, 19, 70, 42), f'{count} SYM', ('mode', count), idle)
                if d.symbol_count == count:
                    self.panel((335 + (count-7)*80, 19, 70, 42), GREEN)
            self.button((595, 19, 105, 42), 'UNDO', 'undo', idle and bool(d.selected))
            self.button((710, 19, 105, 42), 'CLEAR', 'clear', idle or d.state == 'failed')
            self.button((825, 19, 155, 42), 'DIAL / ENTER', 'dial', d.state in ('dialing', 'ready') and len(d.sequence) == d.symbol_count and not d.activation_requested if d.behavior == 'dhd' else idle and len(d.selected) == d.symbol_count - 1)
            self.button((990, 19, 215, 42), 'SHUTDOWN / ESC', 'shutdown', d.state != 'idle')
            self.hover = None
            for glyph_id in range(1, 39):
                index = glyph_id - 1
                rect = pygame.Rect(35 + index % 19 * 62, 94 + index // 19 * 53, 56, 47)
                enabled = accepting_glyphs and not d.origin_selected and glyph_id not in d.selected and len(d.selected) < d.symbol_count - 1
                hot = rect.collidepoint(self.mouse)
                if hot:
                    self.hover = glyph_id
                pygame.draw.rect(self.canvas, (24, 59, 68) if hot and enabled else (12, 31, 40), rect)
                self.panel(rect, GREEN if glyph_id in d.selected else CYAN if enabled else DIM)
                self.glyph.draw(self.canvas, glyph_id, (rect.centerx, rect.centery - 3), 29, WHITE if enabled else DIM, (33, 28))
                self.text(f'{glyph_id:02}', (rect.x + 3, rect.bottom - 13), 10, YELLOW)
                self.buttons.append((rect, glyph_id, enabled))
            self.text(glyphs[self.hover].upper() if self.hover else 'ADDRESS APPEARS IN RIGHT SLOTS. EARTH IS THE FIXED ORIGIN.', (35, 204), 13, YELLOW)
            mode_editable = d.state in ('idle', 'failed') and self.ring_return is None and self.horizon_closing is None and self.slot_fade_started is None
            self.button((760, 201, 445, 28),
                        ('[X] ' if d.behavior == 'dhd' else '[ ] ') + 'DHD DIALING',
                        'toggle_dialing', mode_editable)
            self.button((595, 201, 145, 28), 'IRIS', 'iris')
            if self.iris.target_closed:
                self.panel((595, 201, 145, 28), GREEN)
            self.keyboard_buttons = self.buttons[:]
            if self.options_open or self.archive_open:
                cover = pygame.Surface(self.canvas.get_size(), pygame.SRCALPHA)
                cover.fill((0, 0, 0, 170))
                self.canvas.blit(cover, (0, 0))
                self.text('CLOSE THE CONSOLE MENU TO USE THE KEYBOARD', (370, 115), 20, CYAN)
        finally:
            self.canvas, self.buttons, self.mouse = previous_canvas, previous_buttons, previous_mouse
        if self.keyboard_window is not None and self.keyboard_visible:
            surface = self.keyboard_window.get_surface()
            surface.blit(pygame.transform.smoothscale(self.keyboard_canvas, surface.get_size()), (0, 0))
            self.keyboard_window.flip()

    # Handle only keyboard-window input, hiding it on close and blocking modal input.
    def keyboard_event(self, event, now):
        if event.type == pygame.WINDOWCLOSE:
            self.keyboard_window.hide()
            self.keyboard_visible = False
            return
        if self.options_open or self.archive_open:
            return
        if hasattr(event, 'pos'):
            ww, wh = self.keyboard_window.size
            self.keyboard_mouse = (event.pos[0]*1280/max(1,ww), event.pos[1]*240/max(1,wh))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action, enabled in self.keyboard_buttons:
                if enabled and rect.collidepoint(self.keyboard_mouse):
                    self.action(action, now)
                    break
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.action('dial', now)
            elif event.key == pygame.K_ESCAPE:
                self.stop_gate(now)
            elif event.key == pygame.K_BACKSPACE:
                self.action('undo', now)

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
        self.buttons = []
        box = pygame.Rect(290, 230, 700, 490)
        pygame.draw.rect(self.canvas, BG, box)
        pygame.draw.rect(self.canvas, CYAN, box, 2, border_radius=12)
        self.text('OPTIONS', (320, 256), 26, CYAN)
        self.text('Applies to right-hand slots and placement animations.', (320, 306), 17, WHITE)
        self.button((320, 350, 355, 44),
                    ('[X] ' if self.uniform_glyph_sizing else '[ ] ') + 'UNIFORM GLYPH SIZING',
                    'toggle_sizing')
        self.text('ON: shared scale. OFF: each glyph fits its slot.', (320, 410), 16, YELLOW)
        self.text('GLYPH PRESS SOUND', (320, 490), 22, CYAN)
        for index, (mode, label) in enumerate([('classic', 'CLASSIC DHD'), ('atlantis', 'ATLANTIS'), ('silent', 'SILENT')]):
            selected = self.glyph_sound_mode == mode
            self.button((320 + index*210, 535, 200, 42),
                        ('[X] ' if selected else '[ ] ') + label, ('glyph_sound', mode))
        self.button((320, 650, 150, 42), 'CLOSE / ESC', 'options_close')
        self.button((580, 650, 370, 42),
                    ('[X] ' if self.gate_audio.computer_enabled else '[ ] ') + 'COMPUTER ENCODING SOUNDS',
                    'toggle_computer_sounds')

    # Play the delayed DHD activation cue once, unless Atlantis already played it.
    def play_pending_activation_sound(self):
        if self.dialer.consume_activation_sound():
            if not self.activation_press_played:
                self.play_button_sound(dial=True)
            self.activation_press_played = False

    # Apply menu settings without allowing dialing behavior to change mid-operation.
    def options_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.options_open = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hasattr(event, 'pos'):
                viewport = self.viewport()
                self.mouse = ((event.pos[0]-viewport.x)*W/viewport.width,
                              (event.pos[1]-viewport.y)*H/viewport.height)
            for rect, action, enabled in self.buttons:
                if enabled and rect.collidepoint(self.mouse):
                    if action == 'options_close':
                        self.options_open = False
                    elif action == 'toggle_computer_sounds':
                        self.gate_audio.set_computer_enabled(not self.gate_audio.computer_enabled)
                    elif action == 'toggle_sizing':
                        self.uniform_glyph_sizing = not self.uniform_glyph_sizing
                    elif isinstance(action, tuple) and action[0] == 'glyph_sound':
                        self.glyph_sound_mode = action[1]
                    break

    # Filter destination names and unordered sets of selected glyphs together.
    def archive_results(self):
        query = self.archive_query.strip().casefold()
        return [(name, data) for name, data in self.destinations
                if query in name.casefold()
                and self.archive_glyphs.issubset(set(data['Address']) | {0})]

    # Clamp archive row scrolling to the current filtered result count.
    def archive_scroll_by(self, amount):
        maximum = max(0, len(self.archive_results()) - 5)
        self.archive_scroll = max(0, min(maximum, self.archive_scroll + amount))

    # Render the searchable destination table and interactive scrollbar.
    def draw_archive(self):
        # Modal archive: its controls replace all underlying hit targets.
        self.buttons = []
        pygame.draw.rect(self.canvas, BG, (65, 65, 1150, 850))
        pygame.draw.rect(self.canvas, CYAN, (65, 65, 1150, 850), 2, border_radius=12)
        if self.archive_info is not None:
            self.draw_address_info()
            return
        self.text('SYSTEM GLYPHS / ADDRESS ARCHIVE', (90, 84), 27, CYAN)
        self.button((1080, 80, 110, 38), 'CLOSE', 'archive_close')
        self.panel((90, 131, 780, 40), CYAN if self.archive_search_focus else DIM)
        self.text('NAME > ' + self.archive_query + ('_' if self.archive_search_focus else ''), (102, 141), 17, WHITE)
        self.button((890, 131, 150, 40), 'CLEAR FILTERS', 'archive_clear')
        self.text('GLYPH FILTER / MATCH ALL SELECTED SYMBOLS IN ANY ORDER', (90, 182), 14, YELLOW)
        for glyph_id in range(39):
            rect = pygame.Rect(90 + glyph_id % 20 * 54, 205 + glyph_id // 20 * 46, 48, 40)
            selected = glyph_id in self.archive_glyphs
            pygame.draw.rect(self.canvas, (20, 53, 49) if selected else (9, 26, 34), rect)
            self.panel(rect, GREEN if selected else DIM)
            self.glyph.draw(self.canvas, glyph_id, rect.center, 28, GREEN if selected else WHITE, (35, 30))
            self.buttons.append((rect, ('filter', glyph_id), True))
        results = self.archive_results()
        self.archive_scroll_by(0)
        self.text(f'{len(results)} DESTINATIONS / CLICK A ROW TO LOAD / WHEEL OR PGUP-PGDN TO SCROLL', (90, 306), 14, CYAN)
        for i in range(9):
            self.text(str(i+1), (115 + i * 73, 334), 16, YELLOW)
        self.text('DESTINATION / PROFILE', (795, 334), 16, YELLOW)
        for row, (name, data) in enumerate(results[self.archive_scroll:self.archive_scroll+5]):
            y = 360 + row * 96
            rect = pygame.Rect(90, y, 1065, 88)
            if rect.collidepoint(self.mouse):
                pygame.draw.rect(self.canvas, (15, 40, 48), rect)
            self.panel(rect, CYAN)
            for i, glyph_id in enumerate(data['Address'] + [0]):
                cell = pygame.Rect(90 + i*73, y, 73, 88)
                self.panel(cell, DIM)
                self.glyph.draw(self.canvas, glyph_id, (cell.centerx, y+32), 43, WHITE, (56, 46))
                self.centered_slot_text(glyphs[glyph_id][:9].upper(), cell, y+65, 12, YELLOW)
            state = 'RESTRICTED' if data['Locked'] else 'ACTIVE' if data['Active'] else 'INACTIVE'
            self.text(name[:30].upper(), (775, y+13), 19, WHITE)
            self.text(state, (775, y+41), 15, GREEN if state == 'ACTIVE' else RED)
            self.text('SELECT TO LOAD ADDRESS', (775, y+64), 12, CYAN)
            self.button((1050, y+42, 90, 34), 'INFO', ('info', name))
            self.buttons.append((rect, ('destination', name), True))
        if not results:
            self.text('NO MATCHING DESTINATIONS / ADJUST THE FILTERS', (250, 470), 22, YELLOW)
        track, thumb, maximum = self.archive_scrollbar()
        self.panel(track, DIM)
        pygame.draw.rect(self.canvas, WHITE if self.archive_drag_offset is not None else CYAN, thumb)
        self.button((90, 856, 100, 38), 'UP', 'archive_up', self.archive_scroll > 0)
        self.button((200, 856, 100, 38), 'DOWN', 'archive_down', self.archive_scroll < maximum)
        self.text(f'ROWS {min(len(results), self.archive_scroll+1)}-{min(len(results), self.archive_scroll+5)} / {len(results)}', (330, 868), 16)
        self.text('ESC / RETURN TO DIALING CONSOLE', (810, 868), 14, YELLOW)

    # Derive scrollbar track and thumb geometry from visible rows and scroll position.
    def archive_scrollbar(self):
        count = len(self.archive_results())
        maximum = max(0, count - 5)
        track = pygame.Rect(1167, 360, 16, 472)
        height = max(30, round(track.height * min(1, 5 / max(1, count))))
        y = track.y + round((track.height-height) * self.archive_scroll / max(1, maximum))
        return track, pygame.Rect(track.x+2, y, track.width-4, height), maximum

    # Convert held mouse movement into a clamped archive row offset.
    def drag_archive_scrollbar(self, mouse_y):
        track, thumb, maximum = self.archive_scrollbar()
        travel = track.height - thumb.height
        if maximum and travel:
            fraction = (mouse_y - self.archive_drag_offset - track.top) / travel
            self.archive_scroll = round(max(0, min(1, fraction)) * maximum)

    # Show a destination address, eligibility, and profile fields for later expansion.
    def draw_address_info(self):
        name = self.archive_info
        data = address_database[name]
        self.text('ADDRESS ARCHIVE / DESTINATION INFORMATION', (90, 86), 25)
        self.button((90, 140, 150, 40), '< BACK', 'info_back')
        self.button((980, 140, 210, 40), 'LOAD ADDRESS', 'info_load')
        self.text(name.upper(), (90, 208), 30, WHITE)
        state = 'RESTRICTED' if data['Locked'] else 'ACTIVE' if data['Active'] else 'INACTIVE'
        self.text('STATUS: ' + state, (90, 252), 18, GREEN if state == 'ACTIVE' else RED)
        self.text('ORDERED ADDRESS / EARTH ORIGIN', (90, 294), 16, YELLOW)
        for i, glyph_id in enumerate(data['Address'] + [0]):
            cell = pygame.Rect(90+i*120, 327, 110, 118)
            self.panel(cell, CYAN)
            self.text(str(i+1), (cell.x+7, cell.y+5), 13, YELLOW)
            self.glyph.draw(self.canvas, glyph_id, (cell.centerx, cell.y+47), 58, WHITE, (88, 65))
            self.centered_slot_text(glyphs[glyph_id][:12].upper(), cell, cell.y+87, 13, WHITE)
            self.centered_slot_text(f'GLYPH {glyph_id:02}', cell, cell.y+102, 11, CYAN)
        self.panel((90, 475, 1095, 345), DIM)
        self.text('DESTINATION PROFILE', (108, 492), 20)
        y = 532
        for label, key in [('ENVIRONMENT', 'Environment'), ('INHABITANTS', 'Inhabitants'),
                           ('MISSION INFORMATION', 'Mission'), ('NOTES', 'Notes'), ('SOURCE', 'Source')]:
            value = str(data.get(key) or 'Information to be added.')
            lines = textwrap.wrap(label + ': ' + value, width=106)[:3]
            for line in lines:
                self.text(line, (108, y), 16, WHITE)
                y += 21
            y += 12
        self.text('ESC / BACK TO RESULTS', (90, 864), 15, YELLOW)

    # Route archive searches, glyph filters, row loading, INFO, and scrollbar dragging.
    def archive_event(self, event):
        if hasattr(event, 'pos'):
            viewport = self.viewport()
            self.mouse = ((event.pos[0]-viewport.x)*W/viewport.width,
                          (event.pos[1]-viewport.y)*H/viewport.height)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.archive_drag_offset = None
            return
        if self.archive_info is None:
            if event.type == pygame.MOUSEMOTION and self.archive_drag_offset is not None:
                self.drag_archive_scrollbar(self.mouse[1])
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                track, thumb, maximum = self.archive_scrollbar()
                if maximum and track.collidepoint(self.mouse):
                    self.archive_search_focus = False
                    self.archive_drag_offset = self.mouse[1]-thumb.top if thumb.collidepoint(self.mouse) else thumb.height/2
                    self.drag_archive_scrollbar(self.mouse[1])
                    return
        if self.archive_info is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.archive_info = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, action, enabled in self.buttons:
                    if enabled and rect.collidepoint(self.mouse):
                        if action == 'info_back':
                            self.archive_info = None
                        elif action == 'info_load':
                            name = self.archive_info
                            self.dialer.load_destination(name, time.monotonic())
                            self.archive_info = None
                            self.archive_open = False
                        break
            return
        if event.type == pygame.MOUSEWHEEL:
            self.archive_scroll_by(-event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (4, 5):
                self.archive_scroll_by(-1 if event.button == 4 else 1)
            elif event.button == 1:
                self.archive_search_focus = pygame.Rect(90,131,780,40).collidepoint(self.mouse)
                for rect, action, enabled in self.buttons:
                    if enabled and rect.collidepoint(self.mouse):
                        if action == 'archive_close':
                            self.archive_open = False
                        elif action == 'archive_clear':
                            self.archive_query = ''
                            self.archive_glyphs.clear()
                            self.archive_scroll = 0
                        elif action in ('archive_up', 'archive_down'):
                            self.archive_scroll_by(-1 if action == 'archive_up' else 1)
                        elif isinstance(action, tuple) and action[0] == 'info':
                            self.archive_info = action[1]
                            self.archive_search_focus = False
                        elif isinstance(action, tuple) and action[0] == 'filter':
                            glyph_id = action[1]
                            self.archive_glyphs.symmetric_difference_update({glyph_id})
                            self.archive_scroll = 0
                        elif isinstance(action, tuple) and action[0] == 'destination':
                            name = action[1]
                            self.dialer.load_destination(name, time.monotonic())
                            self.archive_open = False
                        break
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.archive_open = False
            elif event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                self.archive_scroll_by(-5 if event.key == pygame.K_PAGEUP else 5)
            elif self.archive_search_focus:
                if event.key == pygame.K_BACKSPACE:
                    self.archive_query = self.archive_query[:-1]
                elif event.unicode.isprintable() and len(self.archive_query) < 64:
                    self.archive_query += event.unicode
                self.archive_scroll = 0

    # Interpret the small simulator command set, never operating-system commands.
    def execute_command(self, now):
        parts = self.command.strip().split(maxsplit=1)
        verb = parts[0].casefold() if parts else ''
        d = self.dialer
        if verb in ('shutdown', 'abort') and len(parts) == 1:
            self.stop_gate(now)
        elif verb == 'reset' and len(parts) == 1 and d.state in ('idle', 'failed'):
            d.reset()
        elif verb == 'iris':
            argument = parts[1].strip().casefold() if len(parts) > 1 else ''
            if argument in ('', 'open', 'close'):
                closed = not self.iris.target_closed if not argument else argument == 'close'
                self.set_iris(closed, now)
            else:
                d.message = 'USAGE: IRIS / IRIS OPEN / IRIS CLOSE'
        elif verb == 'start' and len(parts) == 1:
            self.action('dial', now)
        elif verb == 'dial':
            if len(parts) < 2:
                d.message = 'USAGE: DIAL <DESTINATION NAME> / EXAMPLE: DIAL ATLANTIS'
            else:
                query = parts[1].strip()
                if len(query) >= 2 and query[0] == query[-1] and query[0] in ('"', "'"):
                    query = query[1:-1]
                normalized = ' '.join(query.split()).casefold()
                name = next((name for name in address_database
                             if ' '.join(name.split()).casefold() == normalized), None)
                if name is None:
                    d.message = 'UNKNOWN DESTINATION / SEARCH THE ADDRESS ARCHIVE'
                elif d.state not in ('idle', 'failed') or self.ring_return is not None or self.horizon_closing is not None or self.slot_fade_started is not None:
                    d.message = 'GATE BUSY / SHUTDOWN BEFORE DIALING ANOTHER ADDRESS'
                else:
                    if d.state == 'failed':
                        d.reset()
                    # Loading chooses address length. DHD queues activation while
                    # current mode starts its normal complete-address sequence.
                    if d.load_destination(name, now):
                        self.action('dial', now)
        else:
            d.message = 'COMMANDS: START / DIAL <NAME> / IRIS [OPEN/CLOSE] / SHUTDOWN / RESET'
        self.command = ''

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
                        if event.key == pygame.K_RETURN:
                            self.execute_command(now)
                        elif event.key == pygame.K_BACKSPACE:
                            self.command = self.command[:-1]
                        elif event.unicode.isprintable() and len(self.command) < 45:
                            self.command += event.unicode
                    elif event.key == pygame.K_RETURN:
                        self.action('dial', now)
                    elif event.key == pygame.K_BACKSPACE:
                        self.action('undo', now)
            self.gate_audio.update(self.dialer, self.ring_return, now, SPIN_FRACTION)
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
    args = parser.parse_args()
    app = Console()
    if args.preview:
        app.mouse = (-1, -1)
        app.dialer.selected = address_database['Abydos']['Address'][:]
        app.dialer.start(0)
        preview_time = 7 * app.dialer.lock_seconds
        app.dialer.update(preview_time)
        app.draw(preview_time)
        pygame.image.save(app.canvas, str(args.preview))
        pygame.quit()
    else:
        app.run()



