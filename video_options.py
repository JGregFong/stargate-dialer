"""File selection and editable timestamps for event-horizon video playback."""
from dataclasses import replace
from pathlib import Path
import textwrap

import pygame

from horizon_video import (SUPPLIED_VIDEO, parse_timestamp, format_timestamp,
                           probe_video, validate_video, video_decoder)
from ui_geometry import BG, CYAN, WHITE, YELLOW, RED


def select_video_file():
    from tkinter import Tk, filedialog
    root = Tk()
    root.withdraw()
    try:
        root.attributes('-topmost', True)
        return filedialog.askopenfilename(title='Select event-horizon video', filetypes=[
            ('Video files', '*.mkv *.mp4 *.webm *.avi *.mov *.m4v'), ('All files', '*.*')])
    finally:
        root.destroy()


class VideoOptions:
    fields = {'opening': pygame.Rect(640, 406, 390, 38),
              'closing': pygame.Rect(640, 458, 390, 38)}

    def __init__(self, ui, settings, choose_file=select_video_file):
        self.ui, self.settings, self.choose_file = ui, settings, choose_file
        self.opened = False
        self.focus = None
        self.error = ''
        self.duration = None
        self.replace_text = False

    def open(self):
        self.draft = replace(self.settings)
        self.text = {'opening': format_timestamp(self.draft.opening),
                     'closing': format_timestamp(self.draft.closing)}
        self.opened, self.focus, self.error, self.duration = True, None, '', None

    def draw(self):
        ui = self.ui
        ui.buttons = []
        decoder = video_decoder()
        with decoder.lock:
            playback_error = decoder.errors.get(self.draft.path, '')
        error_lines = textwrap.wrap(self.error or playback_error, 82)[:2]
        box = pygame.Rect(220, 230, 840, 456 + len(error_lines)*18)
        pygame.draw.rect(ui.canvas, BG, box)
        pygame.draw.rect(ui.canvas, CYAN, box, 2, border_radius=12)
        ui.text('EVENT HORIZON VIDEO', (250, 254), 25)
        ui.button((830, 250, 200, 40), 'BACK / CANCEL', 'video_back')
        ui.button((250, 310, 380, 40), 'DISABLE VIDEO' if self.draft.enabled else 'USE VIDEO', 'video_toggle',
                  enabled=bool(self.draft.path), selected=self.draft.enabled and bool(self.draft.path))
        ui.button((650, 310, 380, 40), 'SELECT VIDEO FILE', 'video_browse')
        ui.centered_slot_text(Path(self.draft.path).name or 'No video selected',
                              pygame.Rect(245, 0, 790, 30), 368, 14, WHITE)
        for name, rect in self.fields.items():
            ui.text(name.upper() + ' TIMESTAMP', (250, rect.y + 10), 16, CYAN)
            ui.control(rect, selected=self.focus == name)
            ui.text(self.text[name] + ('_' if self.focus == name else ''),
                    (rect.x + 12, rect.y + 10), 16, WHITE)
        for i, line in enumerate([
                'Use seconds, MM:SS, or HH:MM:SS (decimals supported).',
                'Opening: where playback starts when the wormhole connects.',
                'Closing: where playback jumps when the gate shuts down.',
                'Long connections loop the steady section; video audio is muted.',
                'Changes apply to the next connection. Existing gate sounds remain.']):
            ui.text(line, (250, 518 + i*20), 13, YELLOW)
        for i, line in enumerate(error_lines):
            ui.text(line, (250, 618 + i*18), 13, RED)
        ui.button((250, 626 + len(error_lines)*18, 780, 40), 'APPLY', 'video_apply')

    def select(self, path):
        if not path:
            return
        try:
            duration = probe_video(path)
            supplied = Path(path).resolve() == SUPPLIED_VIDEO.resolve()
            self.draft.path, self.draft.enabled = str(Path(path).resolve()), True
            self.duration = duration
            self.draft.opening = 2.0 if supplied else 0.0
            self.draft.closing = 2313.0 if supplied else max(.1, duration - min(5, duration/4))
            self.text = {'opening': format_timestamp(self.draft.opening),
                         'closing': format_timestamp(self.draft.closing)}
            self.error = ''
        except Exception as error:
            self.error = f'Cannot load video: {error}'

    def apply(self):
        try:
            self.draft.opening = parse_timestamp(self.text['opening'])
            self.draft.closing = parse_timestamp(self.text['closing'])
            if self.draft.enabled:
                duration = probe_video(self.draft.path)
                validate_video(self.draft, duration)
            for name in ('path', 'enabled', 'opening', 'closing'):
                setattr(self.settings, name, getattr(self.draft, name))
            decoder = video_decoder()
            with decoder.lock:
                decoder.errors.pop(self.draft.path, None)
            self.opened = False
        except Exception as error:
            self.error = str(error)

    def event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.opened = False
            elif self.focus:
                if event.key == pygame.K_BACKSPACE:
                    self.text[self.focus] = '' if self.replace_text else self.text[self.focus][:-1]
                    self.replace_text = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.apply()
                elif event.key == pygame.K_TAB:
                    self.focus = 'closing' if self.focus == 'opening' else 'opening'
                    self.replace_text = True
                else:
                    value = getattr(event, 'unicode', '')
                    if value and all(c in '0123456789:.' for c in value) and len(self.text[self.focus]) < 20:
                        self.text[self.focus] = value if self.replace_text else self.text[self.focus] + value
                        self.replace_text = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focus = next((name for name, rect in self.fields.items()
                               if rect.collidepoint(self.ui.mouse)), None)
            self.replace_text = self.focus is not None
            for rect, action, enabled in self.ui.buttons:
                if enabled and rect.collidepoint(self.ui.mouse):
                    if action == 'video_toggle' and self.draft.path:
                        self.draft.enabled = not self.draft.enabled
                    elif action == 'video_browse':
                        try:
                            self.select(self.choose_file())
                        except Exception as error:
                            self.error = f'File picker unavailable: {error}'
                    elif action == 'video_apply':
                        self.apply()
                    elif action == 'video_back':
                        self.opened = False
                    break
