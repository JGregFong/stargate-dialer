"""Cached, stationary Milky Way gate artwork in screen-pixel coordinates."""
import math
import random
import pygame
from ui_geometry import CENTER, CHEVRON_ANGLES
from ring_motion import tile_angles

# Gate-only intentional counters in the bundled font artwork.
GATE_GLYPH_OPENINGS = {
    0: ((.5, .2),),       # Earth's small circle
    2: ((.49, .37),),     # Virgo's central opening (blue in the reference)
    14: ((.55, .56),),    # Capricorn's large triangular center
    15: ((.5, .48),),     # Pisces Austrinus's large center
    22: ((.4, .62),),     # Triangulum
    25: ((.4, .68),),     # Cetus
    32: ((.55, .5),),     # Gemini
}


def ring_point(radius, angle):
    a = math.radians(angle - 90)
    return CENTER[0] + radius*math.cos(a), CENTER[1] + radius*math.sin(a)


def filled_gate_glyph(glyph, glyph_id, size, color):
    """Fill stroke bodies, preserving explicitly identified openings."""
    key = ('filled', glyph_id, size, tuple(color), glyph.origin_mark if glyph_id == 0 else None)
    if key in glyph.cache:
        return glyph.cache[key]
    # Resolve thin contours before reducing to the small gate-tile size.
    source = glyph.image(glyph_id, max(160, size), color)
    padded = pygame.Surface((source.get_width()+4, source.get_height()+4), pygame.SRCALPHA)
    padded.blit(source, (2, 2))
    # Padding connects every exterior region around the cropped font image.
    background = pygame.mask.from_surface(padded)
    background.invert()
    exterior = background.connected_component((0, 0))
    artwork_id = 39 if glyph_id == 0 and glyph.origin_mark == 'abydos' else glyph_id
    for x, y in GATE_GLYPH_OPENINGS.get(artwork_id, ()):
        seed = (2+round(x*(source.get_width()-1)), 2+round(y*(source.get_height()-1)))
        if background.get_at(seed):
            exterior.draw(background.connected_component(seed), (0, 0))
    exterior.invert()
    filled = exterior.to_surface(setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))
    # Retain the original antialiased contour outside the solid interior.
    filled.blit(padded, (0, 0))
    glyph.cache[key] = filled
    return filled


JEWEL_LIT = (230, 108, 43)
JEWEL_OFF = (76, 59, 72)


def chevron_light_color(off, light):
    return tuple(round(a+(b-a)*light) for a, b in zip(off, JEWEL_LIT))


def draw_chevron(surface, angle, lit=False, clamp_slide=0):
    """A broad, lowered clamp surrounds the narrower, projecting jewel."""
    draw_wings(surface, angle)
    draw_clamp(surface, angle, lit, clamp_slide)
    draw_jewel(surface, angle, lit)


def chevron_geometry(surface, angle, lateral_scale):
    """Shorten inward from the fixed outer edge, along each chevron's own axes."""
    a = math.radians(angle)

    def p(x, radius):
        x *= lateral_scale * .81
        # Lower just the outer tops, blending to zero before the inward ends.
        top_drop = 5*max(0, min(1, (radius-320)/36))
        radius = 366 + (radius-366)*.62 - top_drop
        return (CENTER[0] + x*math.cos(a) + radius*math.sin(a),
                CENTER[1] + x*math.sin(a) - radius*math.cos(a))

    def face(color, points, width=0):
        pygame.draw.polygon(surface, color, [p(x, r) for x, r in points], width)

    return p, face


def draw_wings(surface, angle):
    """Raised metal shoulder plates taper outward along the gate's rim."""
    p, face = chevron_geometry(surface, angle, 1)
    for side in (-1, 1):
        def points(vertices):
            return [(side*x, radius) for x, radius in vertices]

        # Each wing starts beside the jewel and slopes down toward its fine tip.
        face((29, 35, 47), points([(27, 352), (98, 335), (98, 331), (30, 342)]))
        plate = [(31, 367), (66, 355), (98, 335), (27, 352)]
        face((119, 132, 154), points(plate))
        face((170, 179, 196), points(plate), 1)
        face((77, 90, 113), points([(27, 352), (98, 335), (95, 332), (28, 347)]))
        # Shallow panel seams echo the triangular engraving on the prop.
        pygame.draw.line(surface, (88, 101, 124), p(side*45, 362), p(side*65, 343), 1)
        pygame.draw.line(surface, (88, 101, 124), p(side*33, 352), p(side*64, 353), 1)


def draw_clamp(surface, angle, lit=False, slide=0):
    """Ribbed V frame, narrowed more at its inward tip than its shoulders."""
    project, _ = chevron_geometry(surface, angle, .927)

    def p(x, radius):
        # Flare the outer shoulders by 10%, preserving the inner clamp width.
        outward = max(0, min(1, (radius-267)/96))
        flare = 1 + .1*outward
        # Reduce shoulder width 10% and inward width 30%; ribs and rails
        # follow the same taper so their edges stay aligned with the housing.
        taper = .63 + .27*outward
        # Lift the lower bevel and surrounding tip, blending into the shoulders.
        lower_lift = 16*max(0, min(1, (310-radius)/30))
        px, py = project(x*flare*taper, radius-10+lower_lift)
        a = math.radians(angle)
        return px-slide*math.sin(a), py+slide*math.cos(a)

    def face(color, points, width=0):
        pygame.draw.polygon(surface, color, [p(x, r) for x, r in points], width)
    outer = [(-48, 363), (48, 363), (21, 267), (-21, 267)]
    face((16, 19, 24), [(-51, 361), (51, 361), (23, 261), (-23, 261)])
    face((81, 88, 103), outer)
    face((106, 115, 133), outer, 1)
    face((39, 45, 58), [(-23, 353), (23, 353), (6, 281), (-6, 281)])
    # Six ribs per side extend down the shoulders, leaving the inward tip bare.
    for side in (-1, 1):
        for i in range(6):
            r = 359-i*10
            # Interpolate the housing edge at each end of the rib's depth.
            outside = 48-(363-r)*27/96
            outside_bottom = 48-(363-(r-4))*27/96
            inside = 21-(353-r)*15/72
            face(chevron_light_color(JEWEL_OFF, lit),
                 [(side*outside, r), (side*inside, r),
                  (side*(inside-1), r-4), (side*outside_bottom, r-4)])
            pygame.draw.line(surface, chevron_light_color(JEWEL_OFF, lit),
                             p(side*outside, r), p(side*inside, r), 1)
            pygame.draw.circle(surface, (33, 38, 47), p(side*(outside-2), r-2), 1)
    # Long beveled rails remain part of the clamp, outside the jewel channel.
    for side in (-1, 1):
        face((149, 159, 179), [(side*24, 366), (side*20, 365),
                                      (side*5, 284), (side*9, 284)])
    # Join the inner rails at their feet with a matching-width bottom bevel.
    face((149, 159, 179), [(-9, 284), (9, 284), (5, 280), (-5, 280)])


def draw_jewel(surface, angle, lit=False):
    """Raised jewel with a short outward extrusion and its own beveled sides."""
    project, base_face = chevron_geometry(surface, angle, .7)

    def p(x, radius):
        # Preserve the top and lift the lower tip by roughly four screen pixels.
        bottom_lift = 6*max(0, min(1, (360-radius)/66))
        return project(x, radius+6+bottom_lift)

    def face(color, points, width=0):
        pygame.draw.polygon(surface, color, [p(x, radius) for x, radius in points], width)

    # Join the original footprint to the raised face without widening the jewel.
    base_face((34, 29, 34), [(-30, 360), (30, 360), (30, 366), (-30, 366)])
    base_face((80, 73, 84), [(-27, 350), (-7, 300), (-7, 306), (-27, 356)])
    base_face((48, 42, 50), [(27, 350), (7, 300), (7, 306), (27, 356)])
    # The broad upper cap is part of the same jewel, not a metallic strip.
    jewel = [(-30, 360), (30, 360), (26, 348), (7, 294),
             (-7, 294), (-26, 348)]
    face(chevron_light_color(JEWEL_OFF, lit), jewel)
    face((38, 42, 51), [(-4, 297), (0, 299), (4, 297), (3, 293), (0, 290), (-3, 293)])
    # Open at the top: outline only the left side, bottom, and right side.
    border = [jewel[i] for i in (0, 5, 4, 3, 2, 1)]
    pygame.draw.lines(surface, (163, 169, 181), False,
                      [p(x, radius) for x, radius in border], 1)


def make_gate_image(ui, *, include_chevrons=True):
    image = pygame.Surface(ui.canvas.get_size(), pygame.SRCALPHA)
    # Raised concentric moldings surround the recessed glyph track.
    for radius, color, width in (
        (356, (28, 33, 43), 5), (352, (134, 143, 162), 3),
        (349, (68, 78, 97), 19), (331, (144, 152, 171), 3),
        (328, (35, 43, 58), 8), (321, (92, 101, 120), 36),
        (286, (151, 158, 176), 2), (284, (60, 70, 89), 13),
        (272, (135, 145, 166), 2), (270, (32, 39, 53), 3),
    ):
        pygame.draw.circle(image, color, CENTER, radius, width)
    # Paired arches and engraved panel divisions in the outer band.
    for i in range(180):
        angle = i*2
        pygame.draw.line(image, (35, 43, 59), ring_point(333, angle), ring_point(347, angle), 1)
        for base, height in ((333, 12), (333, 6)):
            arch = [ring_point(base+height*math.sin(math.pi*j/12), angle+j*2/12) for j in range(13)]
            pygame.draw.lines(image, (127, 138, 158), False, arch, 1)
        # Cross-braced lattice between the ornamental frieze and glyph track.
        pygame.draw.line(image, (141, 150, 167), ring_point(322, angle), ring_point(328, angle+2), 1)
        pygame.draw.line(image, (109, 120, 140), ring_point(328, angle), ring_point(322, angle+2), 1)
    for i in range(39):
        angle = i*360/39
        pygame.draw.circle(image, (27, 32, 44), ring_point(350, angle), 2)
        pygame.draw.circle(image, (163, 170, 184), ring_point(350, angle), 2, 1)
    for i in range(39):
        angle, start, end = tile_angles(i)
        # All 39 panels share the same radii and exact half-pitch boundaries.
        # The thin highlight sits inside the panel, without shifting its seam.
        for boundary, color in ((start, (32, 37, 48)), (start+.35, (151, 156, 166))):
            pygame.draw.line(image, color, ring_point(288, boundary), ring_point(320, boundary), 1)
        center = ring_point(303, angle)
        # Symbols follow their tiles around the ring, as on the physical prop.
        for color, offset in (((26, 31, 43), (1, 2)), ((166, 174, 191), (0, 0))):
            glyph = filled_gate_glyph(ui.glyph, i, 42, color)
            scale = min(29/glyph.get_width(), 28/glyph.get_height())
            glyph = pygame.transform.smoothscale(glyph, (max(1, round(glyph.get_width()*scale)),
                                                       max(1, round(glyph.get_height()*scale))))
            glyph = pygame.transform.rotate(glyph, -angle)
            image.blit(glyph, glyph.get_rect(center=(center[0]+offset[0], center[1]+offset[1])))
    # Narrow inner vents and the zigzag engraving directly around the aperture.
    for i in range(195):
        angle = i*360/195
        pygame.draw.line(image, (20, 27, 40), ring_point(275, angle), ring_point(282, angle), 2)
        pygame.draw.line(image, (135, 146, 168), ring_point(275, angle+.3), ring_point(282, angle+.3), 1)
    zigzag = [ring_point(268 if i % 2 else 272, i*360/156) for i in range(157)]
    pygame.draw.lines(image, (126, 132, 146), False, zigzag, 1)
    # Fixed weathering: rebuilding the cache always produces the same surface.
    rng = random.Random(7143)
    for _ in range(650):
        radius, angle = rng.uniform(289, 319), rng.uniform(0, 360)
        pygame.draw.line(image, rng.choice(((105, 111, 123), (75, 81, 96))),
                         ring_point(radius, angle), ring_point(radius+rng.uniform(-3, 3), angle+.7), 1)
    if include_chevrons:
        for angle in (0,) + CHEVRON_ANGLES:
            draw_chevron(image, angle)
    return image
