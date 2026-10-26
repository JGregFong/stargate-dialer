"""Main console rendering, telemetry, glyph placement, and visual effects."""
import random
import math
import pygame
from ui_geometry import (
    dialing_angles,
    connector_route,
    polar,
    BG,
    CYAN,
    DIM,
    RED,
    WHITE,
    YELLOW,
    GREEN,
    TEXT_FONT_PATH,
    CENTER,
    GATE_SCALE,
    INNER_GATE_SCALE,
    HORIZON_RADIUS,
    CHEVRON_ANGLES,
    TILE_ANGLE,
)


class ConsoleRenderer:
    def __init__(self, *, ui, dialer, visual, settings, input_state, iris, track_rotation, archive, options):
        self.ui = ui
        self.dialer = dialer
        self.visual = visual
        self.settings = settings
        self.input_state = input_state
        self.iris = iris
        self.track_rotation = track_rotation
        self.archive = archive
        self.options = options
        self.base = pygame.Surface((1280, 960))
        sources = [ui.glyph.image(i, 215) for i in range(39)]
        self.slot_reference_size = (max(image.get_width() for image in sources),
                                    max(image.get_height() for image in sources))
        self.draw_static()
        self.event_horizon = self.make_event_horizon()

    def draw_static(self):
        s = self.base
        s.fill(BG)
        pygame.draw.rect(s, CYAN, (16, 16, 1248, 928), 2, border_radius=24)

        for radius, color, width in [(255, CYAN, 2), (247, DIM, 2), (232, YELLOW, 2), (210, YELLOW, 2), (203, CYAN, 2)]:
            scale = INNER_GATE_SCALE if radius <= 232 else 1
            pygame.draw.circle(s, color, CENTER, round(radius * GATE_SCALE * scale), width)
        for clockwise_angle in range(20, 360, 40):
            if clockwise_angle in (100, 180, 260):
                continue
            angle = clockwise_angle - 90
            pygame.draw.line(s, WHITE, polar(269, angle - 2), polar(269, angle + 2), 5)
        for y in (115, 370):
            self.ui.panel((35, y, 182, 235), surface=s)
            self.ui.text('TELEMETRY' if y == 115 else 'SUBSPACE ARRAY', (43, y + 8), 14, surface=s)
        self.ui.panel((35, 625, 182, 247), surface=s)
        self.ui.text('CHEVRON STATUS', (44, 636), 15, surface=s)
        self.ui.panel((358, 790, 565, 82), surface=s)
        self.ui.text('CONNECTION STATUS', (367, 774), 12, YELLOW, s)

    def draw_center_pulse(self, now):
        if self.visual.horizon_closing is not None or self.dialer.state not in ('idle', 'dialing', 'dhd_wait', 'ready', 'activating'):
            return
        pulse = (1 - math.cos(now * math.tau / 2.6)) / 2
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
        self.ui.canvas.blit(glow, (CENTER[0] - radius, CENTER[1] - radius))

    def draw_glyph_track(self, now):
        rotation = self.track_rotation(now)
        self.visual.last_ring_rotation = rotation
        d = self.dialer
        spin_fraction = d.spin_fraction(now)
        cycle_progress = d.dialing_position(now)[1]
        if (d.state == 'dialing' and now >= d.started
                and d.locked < len(d.sequence) and self.visual.ring_return is None
                and cycle_progress >= spin_fraction):
            encoding_progress = (cycle_progress - spin_fraction) / (1 - spin_fraction)
            # Flash the engaged tile two times, ending before the lock pause.
            if encoding_progress < 2.2 / 2.8:
                pulse = math.sin(math.pi * 2 * encoding_progress / (2.2 / 2.8)) ** 2
                color = tuple(round(a + (b - a) * pulse) for a, b in zip(BG, RED))
                angle = -90 + d.sequence[d.locked] * TILE_ANGLE + rotation
                offsets = [TILE_ANGLE * (step / 12 - .5) for step in range(13)]
                outline = ([polar(231 * INNER_GATE_SCALE, angle + offset) for offset in offsets]
                           + [polar(211 * INNER_GATE_SCALE, angle + offset) for offset in reversed(offsets)])
                pygame.draw.polygon(self.ui.canvas, color, outline)
        for tile in range(39):
            # Boundaries straddle the top chevron when a tile is engaged.
            angle = -90 - TILE_ANGLE / 2 + tile * TILE_ANGLE + rotation
            pygame.draw.line(self.ui.canvas, YELLOW, polar(211 * INNER_GATE_SCALE, angle), polar(231 * INNER_GATE_SCALE, angle), 1)

    def draw_telemetry(self, now):
        """Feed rows from opposite edges, then drain the existing stream on stop."""
        active = self.dialer.state in ('dialing', 'dhd_wait', 'ready', 'activating', 'connected')
        if active:
            if not self.visual.telemetry_running:
                self.visual.telemetry_started = self.dialer.started
                self.visual.telemetry_stopped = None
        elif self.visual.telemetry_running:
            self.visual.telemetry_stopped = now
        self.visual.telemetry_running = active
        if not active and self.visual.telemetry_stopped is None:
            return
        elapsed = max(0, now - self.visual.telemetry_started)
        if elapsed <= 0:
            return
        previous_clip = self.ui.canvas.get_clip()
        try:
            for panel_index, y in enumerate((115, 370)):
                area = pygame.Rect(43, y + 31, 166, 194)
                self.ui.canvas.set_clip(area)
                speed = 23 + panel_index * 6
                position = elapsed * speed
                first_row = max(0, int((position-area.height) // 15) - 1)
                last_row = int(position // 15)
                if self.visual.telemetry_stopped is not None:
                    # No new rows enter after the gate stops; existing rows coast out.
                    admitted = max(0, self.visual.telemetry_stopped-self.visual.telemetry_started) * speed
                    last_row = min(last_row, int(admitted // 15))
                for row in range(first_row, last_row + 1):
                    rng = random.Random((panel_index + 1) * 1000003 + row)
                    bits = ''.join(rng.choice('01') for _ in range(17))
                    row_y = (area.bottom + row*15 - position if panel_index == 0
                             else area.top - 15 - row*15 + position)
                    self.ui.text(bits, (area.x, row_y), 13, YELLOW)
        finally:
            self.ui.canvas.set_clip(previous_clip)
        if self.visual.telemetry_stopped is not None and now-self.visual.telemetry_stopped > 10:
            self.visual.telemetry_stopped = None

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

    def draw_event_horizon(self, now):
        image = self.event_horizon
        if self.dialer.state == 'connected':
            # A subtle 3.2-second breathing cycle; keep opacity and size intact.
            pulse = (1 - math.cos(now * math.tau / 3.2)) / 2
            brightness = round(235 + 20 * pulse)
            image = image.copy()
            image.fill((brightness, brightness, brightness, 255),
                       special_flags=pygame.BLEND_RGBA_MULT)
        if self.visual.horizon_closing is not None:
            started, duration = self.visual.horizon_closing
            progress = max(0, min(1, (now-started)/duration))
            if progress >= 1:
                self.visual.horizon_closing = None
                if self.visual.closing_offworld is not None:
                    self.visual.closing_glyphs = ()
                    self.visual.closing_offworld = None
                    self.visual.slot_fade_started = None
                else:
                    self.visual.slot_fade_started = started + duration
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
        elif self.visual.horizon_opening is not None:
            started, duration = self.visual.horizon_opening
            progress = max(0, min(1, (now-started)/duration))
            if progress >= 1:
                self.visual.horizon_opening = None
            else:
                radius = round(HORIZON_RADIUS * progress * progress * (3-2*progress))
                if radius < 1:
                    return
                # Scale the full gradient so the growing disk retains its fade.
                diameter = radius * 2 + 1
                image = pygame.transform.smoothscale(image, (diameter, diameter))
                self.ui.canvas.blit(image, (CENTER[0]-radius, CENTER[1]-radius))
                return
        self.ui.canvas.blit(image, (CENTER[0]-HORIZON_RADIUS, CENTER[1]-HORIZON_RADIUS))

    def glyph_slot(self, index):
        top, bottom, gap = 116, 872, 8
        count = self.dialer.symbol_count
        height = (bottom - top - gap * (count - 1)) / count
        y = round(top + index * (height + gap))
        end = round(top + index * (height + gap) + height)
        return pygame.Rect(1040, y, 133, end - y)

    def draw_status_text(self, status, color, now):
        panel = pygame.Rect(358, 790, 565, 82)
        if 52 not in self.ui.fonts:
            self.ui.fonts[52] = pygame.font.Font(str(TEXT_FONT_PATH), 52)
        image = self.ui.fonts[52].render(status, True, color)
        image = image.subsurface(image.get_bounding_rect()).copy()
        image = pygame.transform.smoothscale(image,
            (min(panel.width-24, round(image.get_width()*2.1)), panel.height-16))
        target = pygame.Surface(panel.size, pygame.SRCALPHA)
        target.blit(image, image.get_rect(center=(panel.width//2, panel.height//2)))
        key = (status, tuple(color))
        if key != self.visual.status_key:
            self.visual.status_fade_source = self.visual.status_blend.copy() if self.visual.status_blend is not None else None
            self.visual.status_fade_started = now
            self.visual.status_key = key
        blend = target
        if self.visual.status_fade_source is not None:
            progress = max(0, min(1, (now-self.visual.status_fade_started)/.8))
            if progress >= 1:
                self.visual.status_fade_source = None
            elif progress <= 0:
                blend = self.visual.status_fade_source.copy()
            else:
                progress = progress*progress*(3-2*progress)
                blend = pygame.Surface(panel.size, pygame.SRCALPHA)
                outgoing = self.visual.status_fade_source.copy()
                outgoing.set_alpha(round(255*(1-progress)))
                incoming = target.copy()
                incoming.set_alpha(round(255*progress))
                blend.blit(outgoing, (0, 0))
                blend.blit(incoming, (0, 0))
        # Store the unpulsed blend so interrupted transitions remain continuous.
        self.visual.status_blend = blend.copy()
        blend.set_alpha(round(255*(1-math.cos(now*math.tau/4.0))/2))
        self.ui.canvas.blit(blend, panel.topleft)

    def slot_glyph_image(self, glyph_id, slot, color=WHITE):
        area = pygame.Rect(slot.left + 6, slot.top + 6, slot.width - 12, slot.height - 12)
        image = self.ui.glyph.image(glyph_id, 215, color)
        # Uniform uses one reference scale; fit-to-slot restores per-glyph sizing.
        reference = self.slot_reference_size if self.settings.uniform_glyph_sizing else image.get_size()
        scale = min(area.width / reference[0], area.height / reference[1])
        image = pygame.transform.smoothscale(image, (max(1, round(image.get_width()*scale)),
                                                     max(1, round(image.get_height()*scale))))
        return image, area.center

    def draw_slot_glyph(self, glyph_id, slot, color=WHITE, alpha=255):
        image, center = self.slot_glyph_image(glyph_id, slot, color)
        image.set_alpha(alpha)
        self.ui.canvas.blit(image, image.get_rect(center=center))

    def slot_fade_alpha(self, index, now):
        if self.visual.slot_fade_started is None:
            return 255
        progress = max(0, min(1, (now-self.visual.slot_fade_started-index*.35)/.35))
        return round(255*(1-progress*progress*(3-2*progress)))

    def update_slot_fade(self, now):
        if self.visual.slot_fade_started is not None and now >= self.visual.slot_fade_started + len(self.visual.closing_glyphs)*.35:
            self.visual.closing_glyphs = ()
            self.visual.slot_fade_started = None

    def draw(self, now):
        self.ui.canvas.blit(self.base, (0, 0))
        self.ui.buttons = []
        d = self.dialer
        self.draw_telemetry(now)
        self.draw_glyph_track(now)
        self.draw_center_pulse(now)
        self.draw_event_horizon(now)
        self.update_slot_fade(now)
        self.iris.draw(self.ui.canvas, CENTER, HORIZON_RADIUS, now, YELLOW)
        illuminated_chevrons = len(self.visual.closing_glyphs) if self.visual.horizon_closing is not None else d.locked
        event = d.offworld
        recognized = event is not None and event.recognition(now) >= 1
        closing_event = self.visual.closing_offworld
        indicator_event = event or closing_event
        friendly = indicator_event is not None and (
            indicator_event.recognition(now) >= 1 or (
                indicator_event.kind == 'friendly_wo' and now >= indicator_event.established_at))
        incoming_color = GREEN if friendly else RED
        # Gate chevrons, exterior connections, and address slot contents.
        active_angles = dialing_angles(d.symbol_count)
        # Inactive bottom chevrons are drawn without a glyph-slot connection.
        for index, clockwise_angle in enumerate(active_angles + tuple(a for a in CHEVRON_ANGLES if a not in active_angles)):
            angle = clockwise_angle - 90
            chevron_color = incoming_color if index < illuminated_chevrons else CYAN if index >= d.symbol_count else YELLOW
            # The clamp surrounds the jewel and tapers toward the gate center.
            clamp_outline = [
                polar(250, angle - 6),
                polar(250, angle + 6),
                polar(250 - (250 - 218) * 1.05 * 1.03, angle + 2.0),
                polar(250 - (250 - 218) * 1.05 * 1.03, angle - 2.0),
            ]
            # Equal-radius vertex pairs produce parallel bases and mirrored sides.
            jewel_outline = [
                polar(259, angle - 3.4),   # Wide outer base.
                polar(259, angle + 3.4),
                polar(259 - (259 - 228) * 1.05 * 1.03, angle + 1.25), # Narrow inner base.
                polar(259 - (259 - 228) * 1.05 * 1.03, angle - 1.25),
            ]
            # Trim the clamp outline where the jewel overlaps it.
            vertices = clamp_outline + jewel_outline
            bounds = pygame.Rect(
                math.floor(min(x for x, y in vertices)) - 4,
                math.floor(min(y for x, y in vertices)) - 4,
                math.ceil(max(x for x, y in vertices)) - math.floor(min(x for x, y in vertices)) + 9,
                math.ceil(max(y for x, y in vertices)) - math.floor(min(y for x, y in vertices)) + 9,
            )
            layer = pygame.Surface(bounds.size, pygame.SRCALPHA)
            local_clamp = [(x - bounds.x, y - bounds.y) for x, y in clamp_outline]
            local_jewel = [(x - bounds.x, y - bounds.y) for x, y in jewel_outline]
            pygame.draw.polygon(layer, (0, 0, 0, 255), local_clamp)
            pygame.draw.polygon(layer, chevron_color, local_clamp, 3)
            # Six ribs on each clamp side flank the plain central jewel.
            for stripe in range(1, 7):
                progress = .12 + .58 * stripe / 7
                left = pygame.Vector2(local_clamp[0]).lerp(local_clamp[3], progress)
                right = pygame.Vector2(local_clamp[1]).lerp(local_clamp[2], progress)
                span = right - left
                pygame.draw.line(layer, chevron_color, left + span * .06, left + span * .28, 1)
                pygame.draw.line(layer, chevron_color, right - span * .28, right - span * .06, 1)
            pygame.draw.polygon(layer, (0, 0, 0, 0), local_jewel)
            self.ui.canvas.blit(layer, bounds.topleft)
            pygame.draw.polygon(self.ui.canvas, (0, 0, 0), jewel_outline)
            pygame.draw.polygon(self.ui.canvas, chevron_color, jewel_outline, 2)
            if index < d.symbol_count:
                slot = self.glyph_slot(index)
                route = connector_route(clockwise_angle, slot, index)
                connector_color = incoming_color if index < illuminated_chevrons else DIM
                pygame.draw.lines(self.ui.canvas, connector_color, False, route, 2)
                closing_glyph = self.visual.horizon_closing is not None and index < len(self.visual.closing_glyphs)
                self.ui.panel(slot, RED if index < d.locked or closing_glyph else DIM)
                self.ui.text(index + 1, (slot.left - 25, slot.top + 3), 20, WHITE)
                if (event is not None and index < d.locked) or (closing_event is not None and closing_glyph):
                    pygame.draw.rect(self.ui.canvas, incoming_color, slot)
                elif index < len(self.visual.closing_glyphs) and (closing_glyph or self.visual.slot_fade_started is not None):
                    alpha = self.slot_fade_alpha(index, now)
                    if alpha:
                        self.draw_slot_glyph(self.visual.closing_glyphs[index], slot, alpha=alpha)
                elif index < d.locked:
                    self.draw_slot_glyph(d.sequence[index], slot)
                elif d.state == 'idle' and index < len(d.selected):
                    self.draw_slot_glyph(d.selected[index], slot, CYAN)
                elif d.state == 'idle' and index == d.symbol_count - 1 and d.origin_selected:
                    self.draw_slot_glyph(0, slot, CYAN)
        # Three-stage glyph motion: top-to-center, center hold, then slot placement.
        spin_fraction = d.spin_fraction(now)
        cycle_progress = d.dialing_position(now)[1]
        if d.state == 'dialing' and now >= d.started and d.locked < d.symbol_count and cycle_progress >= spin_fraction:
            progress = (cycle_progress - spin_fraction) / (1 - spin_fraction)
            if progress < 1.34 / 2.8:
                travel = progress / (1.34 / 2.8)
                travel = travel * travel * (3 - 2 * travel)
                origin = polar(221 * INNER_GATE_SCALE, -90)
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
                source = self.ui.glyph.image(d.sequence[d.locked], 215)
                scale = min(215/source.get_width(), 215/source.get_height(), 1)
                start_width, start_height = source.get_width()*scale, source.get_height()*scale
                width = max(1, round(start_width + (slot_image.get_width()-start_width)*flight))
                height = max(1, round(start_height + (slot_image.get_height()-start_height)*flight))
                image = pygame.transform.smoothscale(source, (width, height))
                self.ui.canvas.blit(image, image.get_rect(center=center))
            else:
                self.ui.glyph.draw(self.ui.canvas, d.sequence[d.locked], center, size, fit=(size, size))
            #self.text(f'ACQUIRING SYMBOL {d.locked + 1}', (435, 505), 17, YELLOW)

        # Diagnostic lock indicators, destination header, and connection status.
        for i in range(d.symbol_count):
            y = 670 + i * (27 if d.symbol_count == 7 else 22)
            color = GREEN if i < illuminated_chevrons else DIM
            pygame.draw.rect(self.ui.canvas, color, (46, y + 3, 45, 9))
            self.ui.text(f'{i + 1}  {"OK" if i < illuminated_chevrons else "--"}', (106, y), 15, color)
        destination_label = d.destination[:24]
        label_border = pygame.Rect(1107, 22, 133, 30)
        label_border.centerx = self.glyph_slot(0).centerx
        if 16 not in self.ui.fonts:
            self.ui.fonts[16] = pygame.font.Font(str(TEXT_FONT_PATH), 16)
        label_image = self.ui.fonts[16].render(destination_label, True, WHITE)
        if label_image.get_width() > label_border.width - 12:
            label_image = pygame.transform.smoothscale(
                label_image, (label_border.width - 12, label_image.get_height()))
        self.ui.panel(label_border, CYAN)
        self.ui.canvas.blit(label_image, label_image.get_rect(center=label_border.center))
        status = {'incoming': 'INCOMING', 'idle': 'IDLE', 'dialing': 'DIALING', 'connected': 'ACTIVE', 'failed': 'ERROR', 'dhd_wait': 'INPUT', 'ready': 'READY', 'activating': 'WAIT'}[d.state]
        if self.visual.horizon_closing is not None:
            status = 'CLOSING'
        if recognized:
            status = 'signal recognized'
        self.draw_status_text(status, GREEN if recognized else RED if d.state in ('connected', 'failed') else CYAN, now)
        if d.state == 'connected':
            seconds = math.ceil(d.remaining(now))
            self.ui.text('WORMHOLE TIMER', (225, 805), 12, YELLOW)
            self.ui.text(f'{seconds // 60:02}:{seconds % 60:02}', (248, 827), 24, WHITE)
        self.ui.text(d.message.replace('—', '/'), (350, 751), 13, YELLOW)

        idle = d.state == 'idle' and not self.visual.busy
        self.ui.button((35, 883, 182, 30), 'LOAD DESTINATION', 'load', idle)
        self.ui.panel((596, 891, 609, 35), CYAN if self.input_state.focused else DIM)
        self.ui.text('> ' + self.input_state.text + ('_' if self.input_state.focused else '  [click: help / dial NAME / shutdown]'), (605, 900), 13, WHITE)
        self.ui.button((35, 86, 182, 24), 'OPTIONS', 'options')
        self.ui.button((245, 883, 215, 30), 'GLYPH KEYBOARD', 'keyboard')
        self.draw_offworld_notification(now)
        if self.archive.archive_open:
            self.archive.draw_archive()
        elif self.options.options_open:
            self.options.draw_options()

    def draw_offworld_notification(self, now):
        event = self.dialer.offworld
        if event is None:
            return
        waveform = event.kind == 'friendlygdo' and now >= event.established_at + 3
        box = pygame.Rect(370, 310, 540, 235 if waveform else 110)
        pygame.draw.rect(self.ui.canvas, BG, box)
        pygame.draw.rect(self.ui.canvas, CYAN, box, 3)
        self.ui.text(event.notification(now), (390, 328), 22, CYAN)
        if waveform:
            area = pygame.Rect(390, 373, 500, 112)
            pygame.draw.rect(self.ui.canvas, CYAN, area, 2)
            points = []
            for i in range(125):
                amplitude = (math.sin(i*2.31 + now*7) * math.sin(i*.73-now*3)
                             + .3*math.sin(i*4.9+now*11)) * 35
                points.append((area.left+5+i*3.95, area.centery+amplitude))
            pygame.draw.lines(self.ui.canvas, RED, False, points, 2)
            clip = self.ui.canvas.get_clip()
            self.ui.canvas.set_clip(pygame.Rect(area.left, area.top, round(area.width*event.recognition(now)), area.height))
            pygame.draw.lines(self.ui.canvas, GREEN, False, points, 2)
            self.ui.canvas.set_clip(clip)
            recognized = event.recognition(now) >= 1
            self.ui.text('signal recognized' if recognized else 'RECEIVING IDC TRANSMISSION',
                         (390, 505), 20, GREEN if recognized else RED)
