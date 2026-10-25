"""Window-local drawing resources and hit targets; never swaps another view's state."""
import pygame
from ui_geometry import TEXT_FONT_PATH, CYAN, DIM, WHITE


class DrawingContext:
    def __init__(self, canvas, glyph):
        self.canvas = canvas
        self.glyph = glyph
        self.fonts = {}
        self.buttons = []
        self.mouse = (-1, -1)

    def text(self, text, pos, size=16, color=CYAN, surface=None):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(str(TEXT_FONT_PATH), size)
        (surface or self.canvas).blit(self.fonts[size].render(str(text), True, color), pos)

    def centered_slot_text(self, text, cell, y, size, color):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(str(TEXT_FONT_PATH), size)
        label = self.fonts[size].render(text, True, color)
        if label.get_width() > cell.width - 8:
            label = pygame.transform.smoothscale(label, (cell.width - 8, label.get_height()))
        self.canvas.blit(label, label.get_rect(midtop=(cell.centerx, y)))

    def panel(self, rect, color=CYAN, surface=None):
        pygame.draw.rect(surface or self.canvas, color, rect, 1)

    def button(self, rect, label, action, enabled=True):
        rect = pygame.Rect(rect)
        hot = rect.collidepoint(self.mouse)
        pygame.draw.rect(self.canvas, (18, 48, 57) if hot and enabled else (7, 23, 31), rect)
        self.panel(rect, CYAN if enabled else DIM)
        self.text(label, (rect.x + 10, rect.y + 10), 15, WHITE if enabled else DIM)
        self.buttons.append((rect, action, enabled))
