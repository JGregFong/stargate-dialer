"""AddressArchive: a focused view/controller composed by Console.

Dependencies are injected explicitly; this component owns its interaction state.
"""
import time
import textwrap
import pygame
from glyph_database import glyphs, address_database
from ui_geometry import W, H, BG, CYAN, DIM, RED, WHITE, YELLOW, GREEN


class AddressArchive:
    def __init__(self, *, ui, dialer, viewport):
        self.ui = ui
        self.dialer = dialer
        self.viewport = viewport
        self.destinations = [(n, d) for n, d in address_database.items() if len(d['Address']) in (6, 7, 8)]
        self.archive_open = False
        self.archive_info = None
        self.archive_drag_offset = None
        self.archive_query = ''
        self.archive_glyphs = set()
        self.archive_scroll = 0
        self.archive_search_focus = False

    def archive_results(self):
        query = self.archive_query.strip().casefold()
        return [(name, data) for name, data in self.destinations
                if query in name.casefold()
                and self.archive_glyphs.issubset(set(data['Address']) | {0})]

    def archive_scroll_by(self, amount):
        maximum = max(0, len(self.archive_results()) - 5)
        self.archive_scroll = max(0, min(maximum, self.archive_scroll + amount))

    def draw_archive(self):
        # Modal archive: its controls replace all underlying hit targets.
        self.ui.buttons = []
        pygame.draw.rect(self.ui.canvas, BG, (65, 65, 1150, 850))
        pygame.draw.rect(self.ui.canvas, CYAN, (65, 65, 1150, 850), 2, border_radius=12)
        if self.archive_info is not None:
            self.draw_address_info()
            return
        self.ui.text('SYSTEM GLYPHS / ADDRESS ARCHIVE', (90, 84), 27, CYAN)
        self.ui.button((1080, 80, 110, 38), 'CLOSE', 'archive_close')
        self.ui.panel((90, 131, 780, 40), CYAN if self.archive_search_focus else DIM)
        self.ui.text('NAME > ' + self.archive_query + ('_' if self.archive_search_focus else ''), (102, 141), 17, WHITE)
        self.ui.button((890, 131, 150, 40), 'CLEAR FILTERS', 'archive_clear')
        self.ui.text('GLYPH FILTER / MATCH ALL SELECTED SYMBOLS IN ANY ORDER', (90, 182), 14, YELLOW)
        for glyph_id in range(39):
            rect = pygame.Rect(90 + glyph_id % 20 * 54, 205 + glyph_id // 20 * 46, 48, 40)
            selected = glyph_id in self.archive_glyphs
            pygame.draw.rect(self.ui.canvas, (20, 53, 49) if selected else (9, 26, 34), rect)
            self.ui.panel(rect, GREEN if selected else DIM)
            self.ui.glyph.draw(self.ui.canvas, glyph_id, rect.center, 28, GREEN if selected else WHITE, (35, 30))
            self.ui.buttons.append((rect, ('filter', glyph_id), True))
        results = self.archive_results()
        self.archive_scroll_by(0)
        self.ui.text(f'{len(results)} DESTINATIONS / CLICK A ROW TO LOAD / WHEEL OR PGUP-PGDN TO SCROLL', (90, 306), 14, CYAN)
        for i in range(9):
            self.ui.text(str(i+1), (115 + i * 73, 334), 16, YELLOW)
        self.ui.text('DESTINATION / PROFILE', (795, 334), 16, YELLOW)
        for row, (name, data) in enumerate(results[self.archive_scroll:self.archive_scroll+5]):
            y = 360 + row * 96
            rect = pygame.Rect(90, y, 1065, 88)
            if rect.collidepoint(self.ui.mouse):
                pygame.draw.rect(self.ui.canvas, (15, 40, 48), rect)
            self.ui.panel(rect, CYAN)
            for i, glyph_id in enumerate(data['Address'] + [0]):
                cell = pygame.Rect(90 + i*73, y, 73, 88)
                self.ui.panel(cell, DIM)
                self.ui.glyph.draw(self.ui.canvas, glyph_id, (cell.centerx, y+32), 43, WHITE, (56, 46))
                self.ui.centered_slot_text(glyphs[glyph_id][:9].upper(), cell, y+65, 12, YELLOW)
            state = 'RESTRICTED' if data['Locked'] else 'ACTIVE' if data['Active'] else 'INACTIVE'
            self.ui.text(name[:30].upper(), (775, y+13), 19, WHITE)
            self.ui.text(state, (775, y+41), 15, GREEN if state == 'ACTIVE' else RED)
            self.ui.text('SELECT TO LOAD ADDRESS', (775, y+64), 12, CYAN)
            self.ui.button((1050, y+42, 90, 34), 'INFO', ('info', name))
            self.ui.buttons.append((rect, ('destination', name), True))
        if not results:
            self.ui.text('NO MATCHING DESTINATIONS / ADJUST THE FILTERS', (250, 470), 22, YELLOW)
        track, thumb, maximum = self.archive_scrollbar()
        self.ui.panel(track, DIM)
        pygame.draw.rect(self.ui.canvas, WHITE if self.archive_drag_offset is not None else CYAN, thumb)
        self.ui.button((90, 856, 100, 38), 'UP', 'archive_up', self.archive_scroll > 0)
        self.ui.button((200, 856, 100, 38), 'DOWN', 'archive_down', self.archive_scroll < maximum)
        self.ui.text(f'ROWS {min(len(results), self.archive_scroll+1)}-{min(len(results), self.archive_scroll+5)} / {len(results)}', (330, 868), 16)
        self.ui.text('ESC / RETURN TO DIALING CONSOLE', (810, 868), 14, YELLOW)

    def archive_scrollbar(self):
        count = len(self.archive_results())
        maximum = max(0, count - 5)
        track = pygame.Rect(1167, 360, 16, 472)
        height = max(30, round(track.height * min(1, 5 / max(1, count))))
        y = track.y + round((track.height-height) * self.archive_scroll / max(1, maximum))
        return track, pygame.Rect(track.x+2, y, track.width-4, height), maximum

    def drag_archive_scrollbar(self, mouse_y):
        track, thumb, maximum = self.archive_scrollbar()
        travel = track.height - thumb.height
        if maximum and travel:
            fraction = (mouse_y - self.archive_drag_offset - track.top) / travel
            self.archive_scroll = round(max(0, min(1, fraction)) * maximum)

    def draw_address_info(self):
        name = self.archive_info
        data = address_database[name]
        self.ui.text('ADDRESS ARCHIVE / DESTINATION INFORMATION', (90, 86), 25)
        self.ui.button((90, 140, 150, 40), '< BACK', 'info_back')
        self.ui.button((980, 140, 210, 40), 'LOAD ADDRESS', 'info_load')
        self.ui.text(name.upper(), (90, 208), 30, WHITE)
        state = 'RESTRICTED' if data['Locked'] else 'ACTIVE' if data['Active'] else 'INACTIVE'
        self.ui.text('STATUS: ' + state, (90, 252), 18, GREEN if state == 'ACTIVE' else RED)
        self.ui.text('ORDERED ADDRESS / EARTH ORIGIN', (90, 294), 16, YELLOW)
        for i, glyph_id in enumerate(data['Address'] + [0]):
            cell = pygame.Rect(90+i*120, 327, 110, 118)
            self.ui.panel(cell, CYAN)
            self.ui.text(str(i+1), (cell.x+7, cell.y+5), 13, YELLOW)
            self.ui.glyph.draw(self.ui.canvas, glyph_id, (cell.centerx, cell.y+47), 58, WHITE, (88, 65))
            self.ui.centered_slot_text(glyphs[glyph_id][:12].upper(), cell, cell.y+87, 13, WHITE)
            self.ui.centered_slot_text(f'GLYPH {glyph_id:02}', cell, cell.y+102, 11, CYAN)
        self.ui.panel((90, 475, 1095, 345), DIM)
        self.ui.text('DESTINATION PROFILE', (108, 492), 20)
        y = 532
        for label, key in [('ENVIRONMENT', 'Environment'), ('INHABITANTS', 'Inhabitants'),
                           ('MISSION INFORMATION', 'Mission'), ('NOTES', 'Notes'), ('SOURCE', 'Source')]:
            value = str(data.get(key) or 'Information to be added.')
            lines = textwrap.wrap(label + ': ' + value, width=106)[:3]
            for line in lines:
                self.ui.text(line, (108, y), 16, WHITE)
                y += 21
            y += 12
        self.ui.text('ESC / BACK TO RESULTS', (90, 864), 15, YELLOW)

    def archive_event(self, event):
        if hasattr(event, 'pos'):
            viewport = self.viewport()
            self.ui.mouse = ((event.pos[0]-viewport.x)*W/viewport.width,
                          (event.pos[1]-viewport.y)*H/viewport.height)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.archive_drag_offset = None
            return
        if self.archive_info is None:
            if event.type == pygame.MOUSEMOTION and self.archive_drag_offset is not None:
                self.drag_archive_scrollbar(self.ui.mouse[1])
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                track, thumb, maximum = self.archive_scrollbar()
                if maximum and track.collidepoint(self.ui.mouse):
                    self.archive_search_focus = False
                    self.archive_drag_offset = self.ui.mouse[1]-thumb.top if thumb.collidepoint(self.ui.mouse) else thumb.height/2
                    self.drag_archive_scrollbar(self.ui.mouse[1])
                    return
        if self.archive_info is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.archive_info = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, action, enabled in self.ui.buttons:
                    if enabled and rect.collidepoint(self.ui.mouse):
                        if action == 'info_back':
                            self.archive_info = None
                        elif action == 'info_load':
                            name = self.archive_info
                            self.dialer.load_destination(name, time.monotonic())
                            self.archive_info = None
                            self.archive_open = False
                        break
            return
        if event.type == pygame.MOUSEWHEEL:
            self.archive_scroll_by(-event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (4, 5):
                self.archive_scroll_by(-1 if event.button == 4 else 1)
            elif event.button == 1:
                self.archive_search_focus = pygame.Rect(90,131,780,40).collidepoint(self.ui.mouse)
                for rect, action, enabled in self.ui.buttons:
                    if enabled and rect.collidepoint(self.ui.mouse):
                        if action == 'archive_close':
                            self.archive_open = False
                        elif action == 'archive_clear':
                            self.archive_query = ''
                            self.archive_glyphs.clear()
                            self.archive_scroll = 0
                        elif action in ('archive_up', 'archive_down'):
                            self.archive_scroll_by(-1 if action == 'archive_up' else 1)
                        elif isinstance(action, tuple) and action[0] == 'info':
                            self.archive_info = action[1]
                            self.archive_search_focus = False
                        elif isinstance(action, tuple) and action[0] == 'filter':
                            glyph_id = action[1]
                            self.archive_glyphs.symmetric_difference_update({glyph_id})
                            self.archive_scroll = 0
                        elif isinstance(action, tuple) and action[0] == 'destination':
                            name = action[1]
                            self.dialer.load_destination(name, time.monotonic())
                            self.archive_open = False
                        break
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.archive_open = False
            elif event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                self.archive_scroll_by(-5 if event.key == pygame.K_PAGEUP else 5)
            elif self.archive_search_focus:
                if event.key == pygame.K_BACKSPACE:
                    self.archive_query = self.archive_query[:-1]
                elif event.unicode.isprintable() and len(self.archive_query) < 64:
                    self.archive_query += event.unicode
                self.archive_scroll = 0
