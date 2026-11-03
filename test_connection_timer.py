"""Elapsed display and optional, per-connection duration extensions."""
import unittest
from unittest.mock import patch

import pygame

from connection import Connection
from main import Console


class ConnectionTimerTests(unittest.TestCase):
    def test_default_duration_counts_up_and_expires_normally(self):
        connection = Connection()
        with patch('connection.random.randint') as draw:
            connection.connect(100)
        draw.assert_not_called()
        self.assertEqual(connection.elapsed(100), 0)
        self.assertEqual(connection.elapsed(99), 0)
        self.assertEqual(connection.elapsed(161), 61)
        self.assertEqual(connection.active_duration, 38 * 60)
        self.assertFalse(connection.expired(100 + 38 * 60 - .1))
        self.assertTrue(connection.expired(100 + 38 * 60))

    def test_random_extension_is_sampled_once_per_connection(self):
        connection = Connection(duration=100, randomize_duration=True)
        with patch('connection.random.randint', side_effect=[5, 45]) as draw:
            connection.connect(10)
            self.assertEqual(connection.active_duration, 105)
            connection.randomize_duration = False
            self.assertFalse(connection.expired(114.9))
            self.assertTrue(connection.expired(115))
            self.assertEqual(connection.remaining(114), 1)
            draw.assert_called_once_with(5, 45)
            connection.randomize_duration = True
            connection.connect(200)
            self.assertEqual(connection.active_duration, 145)
            self.assertEqual(draw.call_count, 2)
        connection.randomize_duration = False
        connection.connect(400)
        self.assertEqual(connection.active_duration, 100)
        self.assertEqual(connection.elapsed(400), 0)

    def test_menu_toggle_and_elapsed_display(self):
        app = Console()
        self.addCleanup(pygame.quit)
        menu = app.options
        menu.draw_options()
        rect = next(rect for rect, action, _ in app.ui.buttons
                    if action == 'toggle_random_duration')
        menu.viewport = lambda: pygame.Rect(0, 0, 1280, 960)
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)
        menu.options_event(click)
        self.assertTrue(app.dialer.connection.randomize_duration)
        menu.options_event(click)
        self.assertFalse(app.dialer.connection.randomize_duration)
        app.dialer.load_destination('Abydos')
        app.dialer.resolve_connection(100)
        with patch.object(app.ui, 'text', wraps=app.ui.text) as text:
            app.renderer.draw(100)
            self.assertTrue(any(call.args[0] == '00:00' for call in text.call_args_list))
            text.reset_mock()
            app.renderer.draw(161.9)
            self.assertTrue(any(call.args[0] == '01:01' for call in text.call_args_list))
