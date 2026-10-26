"""Selected, hovered, and disabled controls share a visual language across views."""
import unittest

import pygame

from drawing_context import DrawingContext
from main import Console


class ControlStyleTests(unittest.TestCase):
    def setUp(self):
        self.app = Console()

    def tearDown(self):
        pygame.quit()

    def sample(self, ui, rect):
        return (tuple(ui.canvas.get_at(rect.topleft)),
                tuple(ui.canvas.get_at((rect.right - 4, rect.top + 4))))

    def test_selections_match_across_keyboard_options_and_archive(self):
        app = self.app
        app.dialer.set_behavior('dhd')
        app.iris.target_closed = True
        app.keyboard.draw_keyboard()
        keyboard = app.keyboard
        rects = {action: rect for rect, action, _ in keyboard.ui.buttons}
        expected = self.sample(keyboard.ui, rects['toggle_dialing'])
        for action in ('iris', ('mode', 7)):
            self.assertEqual(self.sample(keyboard.ui, rects[action]), expected)
        app.options.draw_options()
        for rect, action, _ in app.ui.buttons:
            if action in ('toggle_sizing', 'toggle_computer_sounds', ('glyph_sound', 'classic')):
                self.assertEqual(self.sample(app.ui, rect), expected)
        app.archive.archive_glyphs = {0}
        app.archive.draw_archive()
        self.assertEqual(self.sample(app.ui, pygame.Rect(90, 205, 48, 40)), expected)

    def test_hover_changes_fill_but_disabled_control_does_not_react(self):
        ui = self.app.ui
        rect = pygame.Rect(0, 0, 180, 28)
        for selected in (False, True):
            ui.mouse = (-1, -1)
            ui.control(rect, selected=selected)
            normal = self.sample(ui, rect)
            ui.mouse = rect.center
            ui.control(rect, selected=selected)
            self.assertNotEqual(self.sample(ui, rect)[1], normal[1])
            ui.mouse = (-1, -1)
            ui.control(rect, enabled=False, selected=selected)
            disabled = self.sample(ui, rect)
            ui.mouse = rect.center
            ui.control(rect, enabled=False, selected=selected)
            self.assertEqual(self.sample(ui, rect), disabled)

    def test_short_buttons_center_labels_and_long_labels_fit(self):
        ui = DrawingContext(pygame.Surface((320, 80), pygame.SRCALPHA), None)
        for label in ('DHD', 'COMPUTER ENCODING SOUNDS'):
            ui.canvas.fill((0, 0, 0, 0))
            rect = pygame.Rect(10, 10, 180, 28)
            ui.button(rect, label, 'test')
            pixels = pygame.mask.from_threshold(ui.canvas, (235, 246, 243, 255), (90, 90, 90, 255))
            bounds = pixels.get_bounding_rects()
            self.assertTrue(bounds)
            text_bounds = bounds[0].unionall(bounds[1:])
            self.assertLessEqual(abs(text_bounds.centerx - rect.centerx), 1)
            self.assertLessEqual(abs(text_bounds.centery - rect.centery), 1)
            self.assertTrue(rect.inflate(-8, -4).contains(text_bounds))
