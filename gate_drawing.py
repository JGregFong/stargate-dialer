"""Shared drawing primitives; no Earth/offworld lifecycle decisions."""
import math
import pygame
from ui_geometry import CENTER, HORIZON_RADIUS, GATE_SCALE, WHITE


class GateDrawing:
    horizon_radius = HORIZON_RADIUS

    def make_event_horizon(self):
        radius = self.horizon_radius
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
        video = getattr(self.settings, 'video_player', None)
        if video and self.dialer.state in ('dialing', 'ready', 'activating', 'dhd_wait'):
            video.prepare(self.horizon_radius)
        if self.visual.horizon_closing is not None:
            started, duration = self.visual.horizon_closing
            if now >= started + duration:
                self.visual.finish_horizon_close(started, duration)
                return
        if self.dialer.state == 'connected' or self.visual.horizon_closing is not None:
            video = getattr(self.settings, 'video_player', None)
            image = video.frame(self.dialer, self.visual, now, self.horizon_radius) if video else None
            if image is not None:
                self.ui.canvas.blit(image, (CENTER[0]-self.horizon_radius, CENTER[1]-self.horizon_radius))
                return
        if self.event_horizon is None:
            if self.dialer.state != 'connected' and self.visual.horizon_closing is None:
                return
            self.event_horizon = self.make_event_horizon()
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
                self.visual.finish_horizon_close(started, duration)
                return
            image = image.copy()
            # A broad, feathered clearing front travels from center to rim.
            feather = getattr(self, 'horizon_feather', round(70 * GATE_SCALE))
            front = (self.horizon_radius + feather) * progress * progress * (3-2*progress)
            mask = pygame.Surface(image.get_size(), pygame.SRCALPHA)
            mask.fill((255, 255, 255, 255))
            for radius in range(self.horizon_radius, -1, -1):
                opacity = max(0, min(1, (radius-front+feather) / feather))
                opacity = opacity * opacity * (3-2*opacity)
                alpha = round(255 * opacity)
                if radius:
                    pygame.draw.circle(mask, (255, 255, 255, alpha),
                                       (self.horizon_radius, self.horizon_radius), radius)
                else:
                    mask.set_at((self.horizon_radius, self.horizon_radius), (255, 255, 255, alpha))
            image.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        elif self.dialer.state != 'connected':
            return
        elif self.visual.horizon_opening is not None:
            started, duration = self.visual.horizon_opening
            progress = max(0, min(1, (now-started)/duration))
            if progress >= 1:
                self.visual.horizon_opening = None
            else:
                radius = round(self.horizon_radius * progress * progress * (3-2*progress))
                if radius < 1:
                    return
                # Scale the full gradient so the growing disk retains its fade.
                diameter = radius * 2 + 1
                image = pygame.transform.smoothscale(image, (diameter, diameter))
                self.ui.canvas.blit(image, (CENTER[0]-radius, CENTER[1]-radius))
                return
        self.ui.canvas.blit(image, (CENTER[0]-self.horizon_radius, CENTER[1]-self.horizon_radius))

    def glyph_slot(self, index):
        top, bottom, gap = 116, 872, 8
        count = self.dialer.symbol_count
        height = (bottom - top - gap * (count - 1)) / count
        y = round(top + index * (height + gap))
        end = round(top + index * (height + gap) + height)
        return pygame.Rect(1040, y, 133, end - y)

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
        if not self.visual.show_address(self.dialer):
            return
        image, center = self.slot_glyph_image(glyph_id, slot, color)
        image.set_alpha(alpha)
        self.ui.canvas.blit(image, image.get_rect(center=center))
