"""GlyphKeyboard: a focused view/controller composed by Console.

Dependencies are injected explicitly; this component owns its interaction state.
"""
import pygame
from drawing_context import DrawingContext
from glyph_database import glyphs
from ui_geometry import BG, CYAN, DIM, WHITE, YELLOW, GREEN


class GlyphKeyboard:
    def __init__(self, *, glyph, dialer, visual, iris, window, action, stop_gate, modal_open):
        self.glyph = glyph
        self.dialer = dialer
        self.visual = visual
        self.iris = iris
        self.window = window
        self.action = action
        self.stop_gate = stop_gate
        self.modal_open = modal_open
        self.keyboard_window = None
        self.keyboard_visible = False
        self.ui = DrawingContext(pygame.Surface((1280, 240)), glyph)
        self.keyboard_buttons = []
        self.keyboard_mouse = (-1, -1)
        self.hover = None

    def open_keyboard(self):
        if self.keyboard_window is None:
            x, y = self.window.position
            desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
            width = min(1280, desktop_w-40)
            self.keyboard_window = pygame.Window(
                'SGC / Glyph Keyboard', size=(width, 240), resizable=True,
                position=(max(0, min(x, desktop_w-width)),
                          max(0, min(y+round(self.window.size[1]*.74), desktop_h-280))))
        self.keyboard_visible = True
        self.keyboard_window.show()
        self.keyboard_window.focus()

    def draw_keyboard(self):
        self.ui.buttons = []
        self.ui.mouse = self.keyboard_mouse
        self.ui.canvas.fill(BG)
        self.ui.text('GLYPH KEYBOARD / EARTH + 38 DESTINATION SYMBOLS', (35, 72), 13, CYAN)
        pygame.draw.rect(self.ui.canvas, CYAN, (8, 8, 1264, 224), 2, border_radius=12)
        d = self.dialer
        idle = d.state == 'idle' and not self.visual.busy
        accepting_glyphs = (idle or (d.behavior == 'dhd' and d.state in ('dialing', 'dhd_wait'))) and not self.visual.busy
        self.ui.button((35, 19, 235, 42), 'EARTH / ORIGIN', 0, accepting_glyphs and len(d.selected) == d.symbol_count - 1 and not d.origin_selected)
        self.ui.glyph.draw(self.ui.canvas, 0, (241, 40), 30, GREEN if d.origin_selected else CYAN, (30, 30))
        for count in (7, 8, 9):
            self.ui.button((335 + (count-7)*80, 19, 70, 42), f'{count} SYM', ('mode', count), idle)
            if d.symbol_count == count:
                self.ui.panel((335 + (count-7)*80, 19, 70, 42), GREEN)
        self.ui.button((595, 19, 105, 42), 'UNDO', 'undo', idle and bool(d.selected))
        self.ui.button((710, 19, 105, 42), 'CLEAR', 'clear', idle or d.state == 'failed')
        self.ui.button((825, 19, 155, 42), 'ACTIVATE', 'dial', d.state in ('dialing', 'ready') and len(d.sequence) == d.symbol_count and not d.activation_requested if d.behavior == 'dhd' else idle and len(d.selected) == d.symbol_count - 1)
        self.ui.button((990, 19, 215, 42), 'SHUTDOWN / ESC', 'shutdown', d.state != 'idle')
        self.hover = None
        for glyph_id in range(1, 39):
            index = glyph_id - 1
            rect = pygame.Rect(35 + index % 19 * 62, 94 + index // 19 * 53, 56, 47)
            enabled = accepting_glyphs and not d.origin_selected and glyph_id not in d.selected and len(d.selected) < d.symbol_count - 1
            hot = rect.collidepoint(self.ui.mouse)
            if hot:
                self.hover = glyph_id
            pygame.draw.rect(self.ui.canvas, (24, 59, 68) if hot and enabled else (12, 31, 40), rect)
            self.ui.panel(rect, GREEN if glyph_id in d.selected else CYAN if enabled else DIM)
            self.ui.glyph.draw(self.ui.canvas, glyph_id, (rect.centerx, rect.centery - 3), 29, WHITE if enabled else DIM, (33, 28))
            self.ui.text(f'{glyph_id:02}', (rect.x + 3, rect.bottom - 13), 10, YELLOW)
            self.ui.buttons.append((rect, glyph_id, enabled))
        self.ui.text(glyphs[self.hover].upper() if self.hover else 'ADDRESS APPEARS IN RIGHT SLOTS. EARTH IS THE FIXED ORIGIN.', (35, 204), 13, YELLOW)
        mode_editable = d.state in ('idle', 'failed') and not self.visual.busy
        self.ui.button((760, 201, 445, 28),
                    ('[X] ' if d.behavior == 'dhd' else '[ ] ') + 'DHD DIALING',
                    'toggle_dialing', mode_editable)
        self.ui.button((595, 201, 145, 28), 'IRIS', 'iris')
        if self.iris.target_closed:
            self.ui.panel((595, 201, 145, 28), GREEN)
        self.keyboard_buttons = self.ui.buttons[:]
        if self.modal_open():
            cover = pygame.Surface(self.ui.canvas.get_size(), pygame.SRCALPHA)
            cover.fill((0, 0, 0, 170))
            self.ui.canvas.blit(cover, (0, 0))
            self.ui.text('CLOSE THE CONSOLE MENU TO USE THE KEYBOARD', (370, 115), 20, CYAN)
        if self.keyboard_window is not None and self.keyboard_visible:
            surface = self.keyboard_window.get_surface()
            surface.blit(pygame.transform.smoothscale(self.ui.canvas, surface.get_size()), (0, 0))
            self.keyboard_window.flip()

    def keyboard_event(self, event, now):
        if event.type == pygame.WINDOWCLOSE:
            self.keyboard_window.hide()
            self.keyboard_visible = False
            return
        if self.modal_open():
            return
        if hasattr(event, 'pos'):
            ww, wh = self.keyboard_window.size
            self.keyboard_mouse = (event.pos[0]*1280/max(1,ww), event.pos[1]*240/max(1,wh))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action, enabled in self.keyboard_buttons:
                if enabled and rect.collidepoint(self.keyboard_mouse):
                    self.action(action, now)
                    break
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.action('dial', now)
            elif event.key == pygame.K_ESCAPE:
                self.stop_gate(now)
            elif event.key == pygame.K_BACKSPACE:
                self.action('undo', now)
