"""Shared console layout, palette, and ring motion geometry."""
import math
from pathlib import Path
from ring_motion import ring_rotation

# Console dimensions, palette, and shared gate geometry.
W, H = 1280, 960
BG = (0, 0, 0)
CYAN = (65, 208, 220)
DIM = (24, 76, 87)
RED = (248, 65, 47)
WHITE = (235, 246, 243)
YELLOW = (255, 254, 113)
GREEN = (127, 226, 103)
TEXT_FONT_PATH = Path(__file__).resolve().parent / 'BankGothic Bold.ttf'
CENTER = (640, 435)
GATE_SCALE = 1.2
INNER_GATE_SCALE = .975
HORIZON_RADIUS = round(201 * GATE_SCALE * INNER_GATE_SCALE)
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
