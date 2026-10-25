"""Separate keyboard window routing and layout checks (SDL dummy compatible)."""
import unittest
import pygame
from main import Console


class KeyboardWindowTests(unittest.TestCase):
    def setUp(self):
        self.app = Console()
        self.app.ui.mouse = (-1, -1)
        self.app.keyboard.open_keyboard()

    def tearDown(self):
        pygame.quit()

    def click(self, action):
        app = self.app
        app.keyboard.draw_keyboard()
        rect = next(rect for rect, value, enabled in app.keyboard.keyboard_buttons
                    if value == action and enabled)
        width, height = app.keyboard.keyboard_window.size
        position = (round(rect.centerx * width / 1280), round(rect.centery * height / 240))
        app.keyboard.keyboard_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position), 0)

    def test_all_glyphs_and_selection(self):
        app = self.app
        app.keyboard.draw_keyboard()
        self.assertEqual({a for r, a, e in app.keyboard.keyboard_buttons if isinstance(a, int)}, set(range(39)))
        self.click(26)
        self.assertEqual(app.dialer.selected, [26])
        self.click('undo')
        self.assertEqual(app.dialer.selected, [])
        self.click(('mode', 9))
        self.assertEqual(app.dialer.symbol_count, 9)

    def test_window_can_close_and_reopen(self):
        app = self.app
        app.keyboard.keyboard_event(pygame.event.Event(pygame.WINDOWCLOSE), 0)
        self.assertFalse(app.keyboard.keyboard_visible)
        self.assertEqual(app.dialer.state, 'idle')
        app.keyboard.open_keyboard()
        self.assertTrue(app.keyboard.keyboard_visible)

    def test_dialing_toggle_is_keyboard_only_and_busy_locked(self):
        app = self.app
        self.click('toggle_dialing')
        self.assertEqual(app.dialer.behavior, 'dhd')
        app.dialer.select(26, 0)
        app.keyboard.draw_keyboard()
        self.assertFalse(next(e for r, a, e in app.keyboard.keyboard_buttons if a == 'toggle_dialing'))
        app.action('toggle_dialing', 1)
        self.assertEqual(app.dialer.behavior, 'dhd')
        app.options.options_open = True
        app.renderer.draw(2)
        self.assertNotIn('toggle_dialing', [a for r, a, e in app.ui.buttons])

    def test_named_dial_command_and_invalid_usage(self):
        app = self.app
        for behavior in ('current', 'dhd'):
            app.dialer.shutdown()
            app.dialer.set_behavior(behavior)
            app.input.text = 'dial AtLaNtIs'
            app.commands.execute_command(100)
            self.assertEqual(app.dialer.destination, 'ATLANTIS')
            self.assertEqual(app.dialer.symbol_count, 8)
            self.assertEqual(app.dialer.state, 'dialing')
            if behavior == 'dhd':
                self.assertTrue(app.dialer.activation_requested)
            before = app.dialer.sequence[:]
            app.input.text = 'dial destiny'
            app.commands.execute_command(101)
            self.assertEqual(app.dialer.sequence, before)
        app.dialer.shutdown()
        app.input.text = 'dial'
        app.commands.execute_command(200)
        self.assertIn('USAGE', app.dialer.message)
        self.assertEqual(app.dialer.state, 'idle')
        app.input.text = 'dial no such destination'
        app.commands.execute_command(200)
        self.assertIn('UNKNOWN', app.dialer.message)

    def test_expanded_slot_columns(self):
        for count in (7, 8, 9):
            self.app.dialer.set_symbol_count(count)
            self.assertEqual(self.app.renderer.glyph_slot(count-1).bottom, 872)


if __name__ == '__main__':
    unittest.main()
