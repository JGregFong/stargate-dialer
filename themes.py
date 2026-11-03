"""Planet presentation profiles. Origin ID 0 always means the *local* origin."""
from dataclasses import dataclass

BASE_DHD_COLOR = (82, 79, 69)
MAX_DHD_TINT = 24

# Clockwise from twelve o'clock, using glyph_database IDs. Zero is local origin.
DHD_OUTER_RING = (37, 5, 28, 23, 33, 11, 36, 10, 20, 2, 3, 19, 8, 4, 31, 0, 18, 21, 6)
DHD_INNER_RING = (27, 9, 32, 38, 25, 22, 17, 13, 16, 1, 24, 35, 7, 26, 30, 14, 34, 29, 15)


@dataclass(frozen=True)
class PlanetTheme:
    name: str
    background: tuple[int, int, int]
    dhd_color: tuple[int, int, int] = BASE_DHD_COLOR
    dhd_style: str = 'weathered-stone'
    offworld: bool = True
    origin_mark: str = 'three-moons'
    # One replaceable shared symbol makes room for the local origin.
    omitted_glyph: int = 12
    dhd_sound_type: str = 'MilkyWay'
    ambient_sound: str | None = None  # Reserved asset path; playback comes later.

    def __post_init__(self):
        if self.dhd_sound_type not in ('SGC', 'MilkyWay', 'Pegasus'):
            raise ValueError('Unknown DHD sound type')
        for color in (self.background, self.dhd_color):
            if len(color) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in color):
                raise ValueError('Theme colors must be RGB byte triples')
        if any(abs(c-b) > MAX_DHD_TINT for c, b in zip(self.dhd_color, BASE_DHD_COLOR)):
            raise ValueError('DHD tint exceeds the base color range')
        if self.omitted_glyph not in range(1, 39):
            raise ValueError('Choose a shared glyph to replace with the local origin')
        if self.dhd_style not in ('weathered-stone', 'smooth-metal'):
            raise ValueError('Unknown DHD style')
        if self.origin_mark not in ('earth', 'three-moons', 'abydos'):
            raise ValueError('Unknown origin artwork')

    @property
    def keyboard_glyphs(self):
        # Keep origin fixed. Custom inventories restore Aquila in the omitted
        # symbol's position rather than shifting neighboring keys.
        return tuple(12 if i == self.omitted_glyph else i
                     for i in DHD_OUTER_RING + DHD_INNER_RING)


EARTH = PlanetTheme('Earth', (3, 12, 19), offworld=False, origin_mark='earth', dhd_sound_type='SGC')
ABYDOS = PlanetTheme('Abydos', (46, 34, 24), (66, 68, 74),
                     dhd_style='smooth-metal', origin_mark='abydos')
PLANET_THEMES = {theme.name.casefold(): theme for theme in (EARTH, ABYDOS)}


def theme_for(name):
    """Unsupported destinations deliberately have no travel profile yet."""
    return PLANET_THEMES.get(name.casefold())
