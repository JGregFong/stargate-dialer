"""Offworld gate rendering; does not call into the Earth console renderer."""
import pygame
from gate_drawing import GateDrawing
from gate_art import make_gate_image, draw_chevron
from ui_geometry import CENTER, CHEVRON_ANGLES, HORIZON_RADIUS, GATE_SCALE, dialing_angles
from offworld import can_travel


class OffworldRenderer(GateDrawing):
    horizon_radius = 268
    horizon_feather = round(70*GATE_SCALE*268/HORIZON_RADIUS)

    def __init__(self, *, ui, dialer, visual, settings, track_rotation):
        self.ui, self.dialer, self.visual = ui, dialer, visual
        self.settings, self.track_rotation = settings, track_rotation
        self.gate_image = None
        self.ring_image = None
        sources = [ui.glyph.image(i, 215) for i in range(39)]
        self.slot_reference_size = (max(s.get_width() for s in sources), max(s.get_height() for s in sources))
        self.event_horizon = None

    def reset(self, visual):
        self.visual = visual
        self.gate_image = self.ring_image = None

    def draw(self, now):
        ui, d = self.ui, self.dialer
        self.visual.update(now)
        ui.canvas.fill(d.theme.background)
        ui.buttons = []
        if self.gate_image is None:
            self.gate_image = make_gate_image(ui, include_chevrons=False)
        ui.canvas.blit(self.gate_image, (0, 0))
        if self.ring_image is None:
            clean = make_gate_image(ui, include_chevrons=False)
            mask = pygame.Surface(clean.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), CENTER, 321)
            pygame.draw.circle(mask, (0, 0, 0, 0), CENTER, 285)
            clean.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            # An even crop puts the gate center exactly at the transform pivot.
            # Odd dimensions offset the artwork by half a pixel when rotating.
            self.ring_image = clean.subsurface((CENTER[0] - 322, CENTER[1] - 322, 644, 644)).copy()
        rotation = self.track_rotation(now)
        self.visual.last_ring_rotation = rotation
        ring = pygame.transform.rotozoom(self.ring_image, -rotation, 1)
        ui.canvas.blit(ring, ring.get_rect(center=CENTER))
        pygame.draw.circle(ui.canvas, (0, 0, 0), CENTER, self.horizon_radius)
        self.draw_event_horizon(now)
        locked = self.visual.closing_chevrons if self.visual.horizon_closing else d.locked
        lights = {angle: self.visual.chevron_light(index, locked, now)
                  for index, angle in enumerate(dialing_angles(d.symbol_count))}
        slide = 0
        encoding = self.visual.rotary_encoding(d, now)
        if encoding is not None:
            index, slide, top_light, assigned_light = encoding
            assigned_angle = dialing_angles(d.symbol_count)[index]
            lights[assigned_angle] = max(lights.get(assigned_angle, 0), assigned_light)
            lights[0] = max(lights.get(0, 0), top_light)
        for angle in (0,) + CHEVRON_ANGLES:
            draw_chevron(ui.canvas, angle, lit=lights.get(angle, 0),
                         clamp_slide=slide if angle == 0 else 0)
        for index in range(d.symbol_count):
            slot = self.glyph_slot(index)
            ui.panel(slot, (146, 126, 94))
            if index < d.locked:
                self.draw_slot_glyph(d.sequence[index], slot)
            elif index < len(self.visual.closing_slots):
                self.draw_slot_glyph(self.visual.closing_slots[index], slot,
                                     alpha=self.visual.fade_alpha)
        # The only persistent controls are access to the DHD and traversal.
        ui.button((435, 883, 215, 30), 'GLYPH KEYBOARD', 'keyboard')
        ui.button((675, 883, 155, 30), 'TRAVEL', 'travel', can_travel(d))
