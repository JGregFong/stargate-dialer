"""OptionsMenu: a focused view/controller composed by Console.

Dependencies are injected explicitly; this component owns its interaction state.
"""
import pygame
from ui_geometry import W, H, BG, CYAN, WHITE, YELLOW


class OptionsMenu:
    def __init__(self, *, ui, settings, gate_audio, viewport, set_volume):
        self.ui = ui
        self.settings = settings
        self.gate_audio = gate_audio
        self.viewport = viewport
        self.options_open = False
        self.set_volume = set_volume
        self.volume_track = pygame.Rect(330, 622, 600, 8)
        self.volume_dragging = False

    def draw_options(self):
        self.ui.buttons = []
        box = pygame.Rect(290, 230, 700, 490)
        pygame.draw.rect(self.ui.canvas, BG, box)
        pygame.draw.rect(self.ui.canvas, CYAN, box, 2, border_radius=12)
        self.ui.text('OPTIONS', (320, 256), 26, CYAN)
        self.ui.text('Applies to right-hand slots and placement animations.', (320, 306), 17, WHITE)
        self.ui.button((320, 350, 355, 44),
                    'UNIFORM GLYPH SIZING', 'toggle_sizing',
                    selected=self.settings.uniform_glyph_sizing)
        self.ui.text('ON: shared scale. OFF: each glyph fits its slot.', (320, 410), 16, YELLOW)
        self.ui.button((320, 437, 630, 38),
                       'ENABLE OFFWORLD ACTIVATION SCENARIOS', 'toggle_offworld',
                       selected=self.settings.offworld_enabled)
        self.ui.text('GLYPH PRESS SOUND', (320, 490), 22, CYAN)
        for index, (mode, label) in enumerate([('classic', 'CLASSIC DHD'), ('atlantis', 'ATLANTIS'), ('silent', 'SILENT')]):
            selected = self.settings.glyph_sound_mode == mode
            self.ui.button((320 + index*210, 535, 200, 42),
                        label, ('glyph_sound', mode), selected=selected)
        self.ui.text('MASTER VOLUME', (320, 590), 16, CYAN)
        self.ui.text(f'{round(self.settings.volume * 100)}%', (875, 590), 16, WHITE)
        pygame.draw.rect(self.ui.canvas, (24, 76, 87), self.volume_track, border_radius=4)
        knob_x = self.volume_track.left + round(self.settings.volume * self.volume_track.width)
        pygame.draw.line(self.ui.canvas, CYAN, self.volume_track.midleft,
                         (knob_x, self.volume_track.centery), 4)
        pygame.draw.circle(self.ui.canvas, WHITE, (knob_x, self.volume_track.centery), 8)
        self.ui.button((320, 650, 150, 42), 'CLOSE / ESC', 'options_close')
        self.ui.button((580, 650, 370, 42),
                    'COMPUTER ENCODING SOUNDS', 'toggle_computer_sounds',
                    selected=self.gate_audio.computer_enabled)

    def options_event(self, event):
        if hasattr(event, 'pos'):
            viewport = self.viewport()
            self.ui.mouse = ((event.pos[0]-viewport.x)*W/viewport.width,
                             (event.pos[1]-viewport.y)*H/viewport.height)
        if ((event.type == pygame.MOUSEBUTTONUP and event.button == 1)
                or event.type == pygame.WINDOWFOCUSLOST):
            self.volume_dragging = False
        elif event.type == pygame.MOUSEMOTION and self.volume_dragging:
            self.update_volume()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.options_open = False
            self.volume_dragging = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.volume_track.inflate(20, 24).collidepoint(self.ui.mouse):
                self.volume_dragging = True
                self.update_volume()
                return
            for rect, action, enabled in self.ui.buttons:
                if enabled and rect.collidepoint(self.ui.mouse):
                    if action == 'toggle_offworld':
                        self.settings.offworld_enabled = not self.settings.offworld_enabled
                    elif action == 'options_close':
                        self.options_open = False
                        self.volume_dragging = False
                    elif action == 'toggle_computer_sounds':
                        self.gate_audio.set_computer_enabled(not self.gate_audio.computer_enabled)
                    elif action == 'toggle_sizing':
                        self.settings.uniform_glyph_sizing = not self.settings.uniform_glyph_sizing
                    elif isinstance(action, tuple) and action[0] == 'glyph_sound':
                        self.settings.glyph_sound_mode = action[1]
                    break

    def update_volume(self):
        volume = (self.ui.mouse[0] - self.volume_track.left) / self.volume_track.width
        self.set_volume(max(0.0, min(1.0, volume)))
