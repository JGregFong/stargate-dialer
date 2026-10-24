"""GlyphKeyboard: a focused view/controller composed by Console.

The console supplies shared drawing helpers, the dialer, and action dispatch.
This component owns its local interaction state.
"""
import pygame
from glyph_database import glyphs
from ui_geometry import BG, CYAN, DIM, WHITE, YELLOW, GREEN


class GlyphKeyboard:
    def __init__(self, console):
        self.console = console
        self.keyboard_window = None
        self.keyboard_visible = False
        self.keyboard_canvas = pygame.Surface((1280, 240))
        self.keyboard_buttons = []
        self.keyboard_mouse = (-1, -1)
        self.hover = None

    def open_keyboard(self):
        if self.keyboard_window is None:
            x, y = self.console.window.position
            desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
            width = min(1280, desktop_w-40)
            self.keyboard_window = pygame.Window(
                'SGC / Glyph Keyboard', size=(width, 240), resizable=True,
                position=(max(0, min(x, desktop_w-width)),
                          max(0, min(y+round(self.console.window.size[1]*.74), desktop_h-280))))
        self.keyboard_visible = True
        self.keyboard_window.show()
        self.keyboard_window.focus()

    def draw_keyboard(self):
        previous_canvas, previous_buttons, previous_mouse = self.console.canvas, self.console.buttons, self.console.mouse
        self.console.canvas = self.keyboard_canvas
        self.console.buttons = []
        self.console.mouse = self.keyboard_mouse
        self.console.canvas.fill(BG)
        self.console.text('GLYPH KEYBOARD / EARTH + 38 DESTINATION SYMBOLS', (35, 72), 13, CYAN)
        pygame.draw.rect(self.console.canvas, CYAN, (8, 8, 1264, 224), 2, border_radius=12)
        d = self.console.dialer
        try:
            idle = d.state == 'idle' and self.console.ring_return is None and self.console.horizon_closing is None and self.console.slot_fade_started is None
            accepting_glyphs = (idle or (d.behavior == 'dhd' and d.state in ('dialing', 'dhd_wait'))) and self.console.ring_return is None and self.console.horizon_closing is None and self.console.slot_fade_started is None
            self.console.button((35, 19, 235, 42), 'EARTH / ORIGIN', 0, accepting_glyphs and len(d.selected) == d.symbol_count - 1 and not d.origin_selected)
            self.console.glyph.draw(self.console.canvas, 0, (241, 40), 30, GREEN if d.origin_selected else CYAN, (30, 30))
            for count in (7, 8, 9):
                self.console.button((335 + (count-7)*80, 19, 70, 42), f'{count} SYM', ('mode', count), idle)
                if d.symbol_count == count:
                    self.console.panel((335 + (count-7)*80, 19, 70, 42), GREEN)
            self.console.button((595, 19, 105, 42), 'UNDO', 'undo', idle and bool(d.selected))
            self.console.button((710, 19, 105, 42), 'CLEAR', 'clear', idle or d.state == 'failed')
            self.console.button((825, 19, 155, 42), 'ACTIVATE', 'dial', d.state in ('dialing', 'ready') and len(d.sequence) == d.symbol_count and not d.activation_requested if d.behavior == 'dhd' else idle and len(d.selected) == d.symbol_count - 1)
            self.console.button((990, 19, 215, 42), 'SHUTDOWN / ESC', 'shutdown', d.state != 'idle')
            self.hover = None
            for glyph_id in range(1, 39):
                index = glyph_id - 1
                rect = pygame.Rect(35 + index % 19 * 62, 94 + index // 19 * 53, 56, 47)
                enabled = accepting_glyphs and not d.origin_selected and glyph_id not in d.selected and len(d.selected) < d.symbol_count - 1
                hot = rect.collidepoint(self.console.mouse)
                if hot:
                    self.hover = glyph_id
                pygame.draw.rect(self.console.canvas, (24, 59, 68) if hot and enabled else (12, 31, 40), rect)
                self.console.panel(rect, GREEN if glyph_id in d.selected else CYAN if enabled else DIM)
                self.console.glyph.draw(self.console.canvas, glyph_id, (rect.centerx, rect.centery - 3), 29, WHITE if enabled else DIM, (33, 28))
                self.console.text(f'{glyph_id:02}', (rect.x + 3, rect.bottom - 13), 10, YELLOW)
                self.console.buttons.append((rect, glyph_id, enabled))
            self.console.text(glyphs[self.hover].upper() if self.hover else 'ADDRESS APPEARS IN RIGHT SLOTS. EARTH IS THE FIXED ORIGIN.', (35, 204), 13, YELLOW)
            mode_editable = d.state in ('idle', 'failed') and self.console.ring_return is None and self.console.horizon_closing is None and self.console.slot_fade_started is None
            self.console.button((760, 201, 445, 28),
                        ('[X] ' if d.behavior == 'dhd' else '[ ] ') + 'DHD DIALING',
                        'toggle_dialing', mode_editable)
            self.console.button((595, 201, 145, 28), 'IRIS', 'iris')
            if self.console.iris.target_closed:
                self.console.panel((595, 201, 145, 28), GREEN)
            self.keyboard_buttons = self.console.buttons[:]
            if self.console.options_open or self.console.archive_open:
                cover = pygame.Surface(self.console.canvas.get_size(), pygame.SRCALPHA)
                cover.fill((0, 0, 0, 170))
                self.console.canvas.blit(cover, (0, 0))
                self.console.text('CLOSE THE CONSOLE MENU TO USE THE KEYBOARD', (370, 115), 20, CYAN)
        finally:
            self.console.canvas, self.console.buttons, self.console.mouse = previous_canvas, previous_buttons, previous_mouse
        if self.keyboard_window is not None and self.keyboard_visible:
            surface = self.keyboard_window.get_surface()
            surface.blit(pygame.transform.smoothscale(self.keyboard_canvas, surface.get_size()), (0, 0))
            self.keyboard_window.flip()

    def keyboard_event(self, event, now):
        if event.type == pygame.WINDOWCLOSE:
            self.keyboard_window.hide()
            self.keyboard_visible = False
            return
        if self.console.options_open or self.console.archive_open:
            return
        if hasattr(event, 'pos'):
            ww, wh = self.keyboard_window.size
            self.keyboard_mouse = (event.pos[0]*1280/max(1,ww), event.pos[1]*240/max(1,wh))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action, enabled in self.keyboard_buttons:
                if enabled and rect.collidepoint(self.keyboard_mouse):
                    self.console.action(action, now)
                    break
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.console.action('dial', now)
            elif event.key == pygame.K_ESCAPE:
                self.console.stop_gate(now)
            elif event.key == pygame.K_BACKSPACE:
                self.console.action('undo', now)
