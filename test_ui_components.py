"""Cross-component interaction checks using SDL's dummy drivers."""
import unittest

import pygame

from main import Console


class UIComponentTests(unittest.TestCase):
    def test_early_abort_finishes_promptly_without_a_position_jump(self):
        from ui_geometry import TILE_ANGLE, ring_rotation
        app = self.app
        for offset in (.001, .01, .1, .75, 2):
            with self.subTest(offset=offset):
                app.dialer.load_destination('Abydos')
                app.action('dial', 0)
                now = app.dialer.started + offset
                before = app.track_rotation(now)
                speed = ring_rotation(app.dialer.sequence, offset, app.dialer.lock_seconds,
                                      velocity=True, initial_rotation=app.visual.rest_rotation,
                                      rpm=app.dialer.rotation_rpm)
                app.stop_gate(now)
                duration = app.visual.ring_return[2]
                self.assertLessEqual(duration, 2.5)
                self.assertAlmostEqual(app.track_rotation(now), before)
                epsilon = 1e-5
                self.assertAlmostEqual((app.track_rotation(now + epsilon) - before) / epsilon,
                                       speed, places=3)
                app.track_rotation(now + duration + epsilon)
                self.assertIsNone(app.visual.ring_return)
                self.assertAlmostEqual(app.visual.rest_rotation / TILE_ANGLE,
                                       round(app.visual.rest_rotation / TILE_ANGLE))
                self.assertTrue(app.dialer.load_destination('Abydos'))
                app.action('dial', now + duration)
                self.assertEqual(app.dialer.state, 'dialing')
                app.dialer.reset()

    def test_failed_address_reset_preserves_ring_position(self):
        from ui_geometry import TILE_ANGLE
        app = self.app
        for action in ('clear', 'reset', 'shutdown', 'dial Abydos'):
            with self.subTest(action=action):
                app.visual.rest_rotation = 5 * TILE_ANGLE
                app.dialer.selected = [1, 2, 3, 4, 5, 6]
                self.assertTrue(app.dialer.start(0))
                now = app.dialer.cycle_elapsed(7)
                app.dialer.update(now)
                self.assertEqual(app.dialer.state, 'failed')
                before = app.track_rotation(now)
                if action == 'clear':
                    app.action(action, now)
                else:
                    app.input.text = action
                    app.commands.execute_command(now)
                self.assertAlmostEqual(app.track_rotation(now), before)
                app.dialer.reset()

    def setUp(self):
        self.app = Console()
        self.app.ui.mouse = (-1, -1)

    def tearDown(self):
        pygame.quit()

    def test_keyboard_render_preserves_console_drawing_context(self):
        app = self.app
        app.renderer.draw(0)
        canvas, buttons, mouse = app.ui.canvas, app.ui.buttons, app.ui.mouse
        app.keyboard.draw_keyboard()
        self.assertIs(app.ui.canvas, canvas)
        self.assertIs(app.ui.buttons, buttons)
        self.assertEqual(app.ui.mouse, mouse)
        self.assertNotEqual(app.keyboard.keyboard_buttons, buttons)

    def test_archive_filters_and_loads_extended_dhd_address(self):
        app = self.app
        app.dialer.set_behavior('dhd')
        app.action('load', 0)
        app.archive.archive_query = 'destiny'
        app.archive.archive_glyphs = {5, 27}
        self.assertEqual([name for name, _ in app.archive.archive_results()], ['Destiny'])
        app.renderer.draw(0)
        rect = next(rect for rect, action, enabled in app.ui.buttons
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
        self.assertFalse(app.options.options_open)
        app.dialer.selected = [26, 6, 14, 31, 11, 29]
        app.keyboard.keyboard_event(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_RETURN), 1)
        self.assertEqual(app.dialer.state, 'dialing')

    def test_configured_rpm_is_used_for_drawing_and_abort(self):
        from ui_geometry import ring_rotation
        app = Console(rotation_rpm=12)
        app.ui.mouse = (-1, -1)
        app.dialer.load_destination('Abydos')
        app.action('dial', 0)
        now = app.dialer.started + 2
        expected = ring_rotation(app.dialer.sequence, 2, app.dialer.lock_seconds, rpm=12)
        self.assertAlmostEqual(app.track_rotation(now), expected)
        expected_speed = ring_rotation(app.dialer.sequence, 2, app.dialer.lock_seconds,
                                       velocity=True, rpm=12)
        app.stop_gate(now)
        self.assertAlmostEqual(app.visual.ring_return[3], expected_speed)
        self.assertAlmostEqual(app.track_rotation(now), expected)
        app.dialer.set_behavior('dhd')
        self.assertEqual(app.dialer.rotation_rpm, 12)
