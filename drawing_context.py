"""Window-local drawing resources and hit targets; never swaps another view's state."""
import pygame
from ui_geometry import TEXT_FONT_PATH, CYAN, DIM, WHITE, GREEN


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

    def control(self, rect, enabled=True, selected=False):
        """Draw the shared state treatment for text buttons and glyph tiles."""
        rect = pygame.Rect(rect)
        hot = enabled and rect.collidepoint(self.mouse)
        if selected:
            fill = (32, 96, 62) if hot else (24, 76, 50)
            border = GREEN
        else:
            fill = (18, 48, 57) if hot else (7, 23, 31)
            border = CYAN if enabled else DIM
        pygame.draw.rect(self.canvas, fill, rect)
        pygame.draw.rect(self.canvas, border, rect, 2 if selected else 1)
        return WHITE if enabled or selected else (112, 145, 150)

    def button(self, rect, label, action, enabled=True, selected=False):
        rect = pygame.Rect(rect)
        color = self.control(rect, enabled, selected)
        # Center every label and reduce font size only when the text needs room.
        for size in range(15, 10, -1):
            if size not in self.fonts:
                self.fonts[size] = pygame.font.Font(str(TEXT_FONT_PATH), size)
            font = self.fonts[size]
            if font.size(label)[0] <= rect.width - 16:
                break
        image = font.render(label, True, color)
        image = image.subsurface(image.get_bounding_rect()).copy()
        if image.get_width() > rect.width - 16:
            image = pygame.transform.smoothscale(image, (rect.width - 16, image.get_height()))
        self.canvas.blit(image, image.get_rect(center=rect.center))
        self.buttons.append((rect, action, enabled))
        return color
