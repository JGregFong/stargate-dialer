"""Offworld DHD layout, fitted glyphs, and annular button hit targets."""
import math
import pygame
from themes import theme_for
from ui_geometry import WHITE
from gate_art import filled_gate_glyph
from glyph_database import glyphs
from ring_motion import DEFAULT_ROTATION_RPM

# Offworld DHD only; Pygame angles are positive counterclockwise.
DHD_GLYPH_ROTATIONS = {15: -90, 14: 45, 32: -45, 34: 90, 38: -40, 25: 80, 22: 180, 17: 270, 13: 90, 16: -10, 24: -90,
                       35: 30, 7: 90, 26: 90, 30: 90,
                       37: 330, 5: 200, 33: 90, 11: -15, 10: 90, 20: 90, 2: -100, 3: -180, 19: 180, 8: 180, 31: 290,
                       18: 90, 21: 150, 6: 60}


def can_travel(d):
    target = theme_for(d.destination)
    return (d.state == 'connected' and target is not None and target != d.theme
            and d.connection.arrival_close_at is None and not d.connection.travel_locked)


class Sector:
    """Annular hit target: gaps, adjacent keys and the dome never overlap."""

    def __init__(self, inner, outer, angle):
        self.inner, self.outer, self.angle = inner, outer, angle

    def collidepoint(self, point):
        x, y = point[0] - 640, point[1] - 322
        delta = (math.degrees(math.atan2(y, x)) - self.angle + 180) % 360 - 180
        return self.inner <= math.hypot(x, y) <= self.outer and abs(delta) <= 180 / 19 - 1


def point(radius, angle):
    a = math.radians(angle)
    return (640 + radius * math.cos(a), 322 + radius * math.sin(a))


def fitted_dhd_glyph(glyph, glyph_id, color, inner, outer, angle):
    """Fit in a padded rectangle inscribed in the annular button, then rotate."""
    correction = DHD_GLYPH_ROTATIONS.get(glyph_id, 0)
    key = ('dhd-fit', glyph_id, tuple(color), inner, outer, angle, glyph.origin_mark, correction)
    if key not in glyph.cache:
        radius = (inner + outer) / 2
        source = filled_gate_glyph(glyph, glyph_id, 40, color)
        if correction:
            source = pygame.transform.rotozoom(source, correction, 1)
            source = source.subsurface(source.get_bounding_rect()).copy()
        aspect = source.get_width() / source.get_height()
        # Use the narrow inward end, not the wider center of the wedge.
        half_angle = math.radians(180 / 19 - 1)
        height = min(60, outer - inner - 20,
                     (2 * radius * math.tan(half_angle) - 12) / (aspect + math.tan(half_angle)))
        width = 2 * ((radius - height / 2) * math.tan(half_angle) - 6)
        scale = min(width / source.get_width(), height / source.get_height())
        image = pygame.transform.smoothscale(source,
                                             (max(1, math.floor(source.get_width() * scale)),
                                              max(1, math.floor(source.get_height() * scale))))
        # Upright at twelve o'clock, following the radial orientation elsewhere.
        glyph.cache[key] = pygame.transform.rotozoom(image, -angle - 90, 1)
    return glyph.cache[key]


def draw_keyboard(keyboard):
    ui, d = keyboard.ui, keyboard.dialer
    theme = d.theme
    metallic = theme.dhd_style == 'smooth-metal'
    edge_color = (117, 123, 134) if metallic else (138, 126, 99)
    ui.canvas.fill(theme.background)
    ui.buttons = []
    ui.mouse = keyboard.keyboard_mouse
    keyboard.hover = None
    show_address = keyboard.visual.show_address(d)
    accepting = d.state in ('idle', 'dialing', 'dhd_wait') and not keyboard.visual.busy
    pygame.draw.circle(ui.canvas, (38, 36, 32), (640, 322), 282)
    pygame.draw.circle(ui.canvas, theme.dhd_color, (640, 322), 275, 8)
    if metallic:
        pygame.draw.circle(ui.canvas, (107, 113, 125), (640, 322), 279, 1)
        pygame.draw.circle(ui.canvas, (38, 41, 48), (640, 322), 271, 2)
    for index, glyph_id in enumerate(theme.keyboard_glyphs):
        ring, position = divmod(index, 19)
        inner, outer = ((177, 263) if ring == 0 else (88, 171))
        angle = -90 + position * 360 / 19
        hit = Sector(inner, outer, angle)
        enabled = accepting and not d.origin_selected and (
            len(d.selected) == d.symbol_count - 1 if glyph_id == 0
            else glyph_id not in d.selected and len(d.selected) < d.symbol_count - 1)
        selected = show_address and (d.origin_selected if glyph_id == 0 else glyph_id in d.selected)
        fading = show_address and glyph_id in keyboard.visual.closing_dhd
        fade = keyboard.visual.fade_alpha/255 if fading else 0
        hot = enabled and hit.collidepoint(ui.mouse)
        if hit.collidepoint(ui.mouse):
            keyboard.hover = glyph_id
        tint = 34 if selected else 34*fade if fading else 20 if hot else 0
        color = tuple(min(255, c + tint) for c in theme.dhd_color)
        edges = [angle - 180 / 19 + 1 + i * (360 / 19 - 2) / 10 for i in range(11)]
        shape = [point(outer, a) for a in edges] + [point(inner, a) for a in reversed(edges)]
        pygame.draw.polygon(ui.canvas, color, shape)
        if selected:
            pygame.draw.polygon(ui.canvas, (143, 89, 41), shape, 5)
        border = tuple(round(base+(lit-base)*fade) for base, lit in zip(edge_color, (246, 174, 83)))
        pygame.draw.polygon(ui.canvas, (246, 174, 83) if selected else border,
                            shape, 2 if selected or fading else 1)
        center = point((inner + outer) / 2, angle)
        glyph_color = ((246, 174, 83) if selected else
                       tuple(min(255, c+(80 if enabled else 44)) for c in color))
        shadow = fitted_dhd_glyph(ui.glyph, glyph_id, (16, 18, 23), inner, outer, angle).copy()
        shadow.set_alpha(150)
        ui.canvas.blit(shadow, shadow.get_rect(center=(center[0]+1, center[1]+2)))
        glyph_image = fitted_dhd_glyph(ui.glyph, glyph_id, glyph_color, inner, outer, angle)
        ui.canvas.blit(glyph_image, glyph_image.get_rect(center=center))
        if fading and not selected:
            lit_image = fitted_dhd_glyph(ui.glyph, glyph_id, (246, 174, 83), inner, outer, angle).copy()
            lit_image.set_alpha(keyboard.visual.fade_alpha)
            ui.canvas.blit(lit_image, lit_image.get_rect(center=center))
        ui.buttons.append((hit, glyph_id, enabled))
    ready = d.state in ('dialing', 'ready') and len(d.sequence) == d.symbol_count and not d.activation_requested
    pygame.draw.circle(ui.canvas, (42, 31, 28), (640, 322), 84)
    active = d.state == 'connected' or (d.activation_requested and d.state in ('dialing', 'ready', 'activating'))
    if active:
        glow = pygame.Surface((168, 168), pygame.SRCALPHA)
        for radius in range(83, 71, -1):
            pygame.draw.circle(glow, (255, 42, 25, (84 - radius) * 5), (84, 84), radius)
        ui.canvas.blit(glow, (556, 238))
    center_color = (255, 68, 47) if active else (124, 35, 28)
    edge_color = (196, 31, 23) if active else (89, 26, 22)
    for radius in range(72, -1, -1):
        brightness = 1-(radius/72)**2
        color = tuple(round(edge+(center-edge)*brightness)
                      for center, edge in zip(center_color, edge_color))
        pygame.draw.circle(ui.canvas, color, (640, 322), radius)
    pygame.draw.circle(ui.canvas, (255, 125, 96) if active else (132, 65, 48), (640, 322), 72, 2)

    dome_action = 'dial' if ready else 'shutdown'
    dome_enabled = (ready or d.state not in ('idle', 'failed')) and not (
        d.state == 'connected' and keyboard.visual.activation_locked)
    ui.buttons.append((Dome(), dome_action, dome_enabled))
    ui.text(f'{theme.name.upper()} / LOCAL DHD', (470, 16), 20, WHITE)
    ui.button((572, 615, 135, 32), 'TRAVEL', 'travel', can_travel(d))
    ui.button((950, 300, 240, 38), {'dhd': 'DHD DIALING', 'spinning': 'SPINNING DIALING',
               'rotary': 'ROTARY DIALING'}[d.offworld_dialing_mode], 'toggle_offworld_sgc',
              d.state == 'idle' and not keyboard.visual.busy,
              selected=d.offworld_dialing_mode != 'dhd')
    ui.button((950, 350, 240, 38), f'SPEED: {d.rotation_rpm or DEFAULT_ROTATION_RPM:g} RPM',
              'cycle_speed', d.offworld_dialing_mode != 'dhd'
              and d.state in ('idle', 'failed') and not keyboard.visual.busy)
    if keyboard.hover is not None:
        glyph_id = keyboard.hover
        name = f'{theme.name} / ORIGIN' if glyph_id == 0 else glyphs[glyph_id]
        display_id = 39 if glyph_id == 0 and theme.origin_mark == 'abydos' else glyph_id
        ui.text(f'GLYPH {display_id:02}', (950, 415), 16, WHITE)
        ui.centered_slot_text(name.upper(), pygame.Rect(935, 443, 285, 40), 443, 18, WHITE)
    keyboard.keyboard_buttons = ui.buttons[:]


class Dome:
    def collidepoint(self, point):
        return math.hypot(point[0] - 640, point[1] - 322) <= 72


