"""Cross-component interaction checks using SDL's dummy drivers."""
import unittest

import pygame

from main import Console


class UIComponentTests(unittest.TestCase):
    def setUp(self):
        self.app = Console()
        self.app.mouse = (-1, -1)

    def tearDown(self):
        pygame.quit()

    def test_keyboard_render_preserves_console_drawing_context(self):
        app = self.app
        app.draw(0)
        canvas, buttons, mouse = app.canvas, app.buttons, app.mouse
        app.keyboard.draw_keyboard()
        self.assertIs(app.canvas, canvas)
        self.assertIs(app.buttons, buttons)
        self.assertEqual(app.mouse, mouse)
        self.assertNotEqual(app.keyboard.keyboard_buttons, buttons)

    def test_archive_filters_and_loads_extended_dhd_address(self):
        app = self.app
        app.dialer.set_behavior('dhd')
        app.action('load', 0)
        app.archive.archive_query = 'destiny'
        app.archive.archive_glyphs = {5, 27}
        self.assertEqual([name for name, _ in app.archive.archive_results()], ['Destiny'])
        app.draw(0)
        rect = next(rect for rect, action, enabled in app.buttons
                    if action == ('destination', 'Destiny') and enabled)
        viewport = app.viewport()
        pos = (round(viewport.x + rect.centerx * viewport.width / 1280),
               round(viewport.y + rect.centery * viewport.height / 960))
        app.archive.archive_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        self.assertFalse(app.archive.archive_open)
        self.assertEqual(app.dialer.symbol_count, 9)
        self.assertEqual(app.dialer.state, 'dialing')
        self.assertEqual(app.dialer.sequence[-1], 0)
        self.assertFalse(app.dialer.activation_requested)

    def test_options_block_keyboard_and_escape_restores_input(self):
        app = self.app
        app.action('options', 0)
        app.keyboard.keyboard_event(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_RETURN), 0)
        self.assertEqual(app.dialer.state, 'idle')
        app.options.options_event(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertFalse(app.options_open)
        app.dialer.selected = [26, 6, 14, 31, 11, 29]
        app.keyboard.keyboard_event(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_RETURN), 1)
        self.assertEqual(app.dialer.state, 'dialing')

    def test_configured_rpm_is_used_for_drawing_and_abort(self):
        from ui_geometry import ring_rotation
        app = Console(rotation_rpm=12)
        app.mouse = (-1, -1)
        app.dialer.load_destination('Abydos')
        app.action('dial', 0)
        now = app.dialer.started + 2
        expected = ring_rotation(app.dialer.sequence, 2, app.dialer.lock_seconds, rpm=12)
        self.assertAlmostEqual(app.track_rotation(now), expected)
        expected_speed = ring_rotation(app.dialer.sequence, 2, app.dialer.lock_seconds,
                                       velocity=True, rpm=12)
        app.stop_gate(now)
        self.assertAlmostEqual(app.ring_return[3], expected_speed)
        self.assertAlmostEqual(app.track_rotation(now), expected)
        app.dialer.set_behavior('dhd')
        self.assertEqual(app.dialer.rotation_rpm, 12)
