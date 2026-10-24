"""OptionsMenu: a focused view/controller composed by Console.

The console supplies shared drawing helpers, the dialer, and action dispatch.
This component owns its local interaction state.
"""
import pygame
from ui_geometry import W, H, BG, CYAN, WHITE, YELLOW


class OptionsMenu:
    def __init__(self, console):
        self.console = console
        self.options_open = False

    def draw_options(self):
        self.console.buttons = []
        box = pygame.Rect(290, 230, 700, 490)
        pygame.draw.rect(self.console.canvas, BG, box)
        pygame.draw.rect(self.console.canvas, CYAN, box, 2, border_radius=12)
        self.console.text('OPTIONS', (320, 256), 26, CYAN)
        self.console.text('Applies to right-hand slots and placement animations.', (320, 306), 17, WHITE)
        self.console.button((320, 350, 355, 44),
                    ('[X] ' if self.console.uniform_glyph_sizing else '[ ] ') + 'UNIFORM GLYPH SIZING',
                    'toggle_sizing')
        self.console.text('ON: shared scale. OFF: each glyph fits its slot.', (320, 410), 16, YELLOW)
        self.console.text('GLYPH PRESS SOUND', (320, 490), 22, CYAN)
        for index, (mode, label) in enumerate([('classic', 'CLASSIC DHD'), ('atlantis', 'ATLANTIS'), ('silent', 'SILENT')]):
            selected = self.console.glyph_sound_mode == mode
            self.console.button((320 + index*210, 535, 200, 42),
                        ('[X] ' if selected else '[ ] ') + label, ('glyph_sound', mode))
        self.console.button((320, 650, 150, 42), 'CLOSE / ESC', 'options_close')
        self.console.button((580, 650, 370, 42),
                    ('[X] ' if self.console.gate_audio.computer_enabled else '[ ] ') + 'COMPUTER ENCODING SOUNDS',
                    'toggle_computer_sounds')

    def options_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.options_open = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hasattr(event, 'pos'):
                viewport = self.console.viewport()
                self.console.mouse = ((event.pos[0]-viewport.x)*W/viewport.width,
                              (event.pos[1]-viewport.y)*H/viewport.height)
            for rect, action, enabled in self.console.buttons:
                if enabled and rect.collidepoint(self.console.mouse):
                    if action == 'options_close':
                        self.options_open = False
                    elif action == 'toggle_computer_sounds':
                        self.console.gate_audio.set_computer_enabled(not self.console.gate_audio.computer_enabled)
                    elif action == 'toggle_sizing':
                        self.console.uniform_glyph_sizing = not self.console.uniform_glyph_sizing
                    elif isinstance(action, tuple) and action[0] == 'glyph_sound':
                        self.console.glyph_sound_mode = action[1]
                    break
