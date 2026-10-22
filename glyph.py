"""Font-backed glyph rendering. IDs follow glyph_database."""
from pathlib import Path
import pygame
from glyph_database import glyph_letters

# Shared font location and orientation corrections applied across every screen.
FONT_PATH = Path(__file__).resolve().parent / 'stargate_sg1_adress_glyphs.ttf'
CLOCKWISE_GLYPHS = frozenset({2, 11, 14, 15, 16, 24, 29})
COUNTERCLOCKWISE_GLYPHS = frozenset({3, 20, 27, 35})


class Glyph:
    # Cache fonts and rendered glyph images by ID, size, and color.
    def __init__(self):
        self.fonts = {}
        self.cache = {}

    # Render the font character, crop it, and apply the requested orientation correction.
    def image(self, glyph_id, size, color=(238, 250, 255)):
        key = (glyph_id, size, tuple(color))
        if key not in self.cache:
            if size not in self.fonts:
                self.fonts[size] = pygame.font.Font(str(FONT_PATH), size)
            surface = self.fonts[size].render(glyph_letters[glyph_id], True, color)
            bounds = surface.get_bounding_rect()
            surface = surface.subsurface(bounds).copy() if bounds.width and bounds.height else surface
            if glyph_id == 18:
                surface = pygame.transform.rotate(surface, 170)
            elif glyph_id == 7:
                surface = pygame.transform.rotate(surface, -110)
            elif glyph_id == 21:
                surface = pygame.transform.rotate(surface, -120)

            elif glyph_id in CLOCKWISE_GLYPHS:
                surface = pygame.transform.rotate(surface, -90)
            elif glyph_id in COUNTERCLOCKWISE_GLYPHS:
                surface = pygame.transform.rotate(surface, 90)
            self.cache[key] = surface
        return self.cache[key]

    # Optionally fit a rendered glyph to bounds and place it around a center point.
    def draw(self, surface, glyph_id, center, size, color=(238, 250, 255), fit=None):
        image = self.image(glyph_id, size, color)
        if fit:
            scale = min(fit[0] / max(1, image.get_width()), fit[1] / max(1, image.get_height()), 1)
            image = pygame.transform.smoothscale(image, (max(1, int(image.get_width() * scale)), max(1, int(image.get_height() * scale))))
        surface.blit(image, image.get_rect(center=center))
