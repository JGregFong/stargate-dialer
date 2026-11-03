"""Travel preserves a single two-ended connection until delayed closure."""
import unittest
from unittest.mock import Mock, patch
import pygame
from main import Console
from themes import EARTH, ABYDOS
from connection import TRAVEL_CLOSE_SECONDS
from offworld import can_travel, fitted_dhd_glyph
from ui_geometry import CENTER


class TravelTests(unittest.TestCase):
    def test_travel_waits_for_opening_sound_plus_one_second(self):
        for origin in (EARTH, ABYDOS):
            with self.subTest(origin=origin.name):
                app, ready = self.connected_console(origin, wait_for_travel=False)
                d = app.dialer
                self.assertAlmostEqual(ready, d.connected_at+app.gate_audio.open_duration+1)
                app.update_gate(ready-.001)
                self.assertFalse(can_travel(d))
                self.assertFalse(d.travel(ready-.001))
                app.gate_audio.play.reset_mock()
                app.action('travel', ready-.001)
                app.gate_audio.play.assert_not_called()
                self.assertEqual(d.theme, origin)
                app.renderer.draw(ready-.001)
                self.assertFalse(next(enabled for _, action, enabled in app.ui.buttons
                                      if action == 'travel'))
                if origin.offworld:
                    app.keyboard.draw_keyboard()
                    self.assertFalse(next(enabled for _, action, enabled in app.keyboard.keyboard_buttons
                                          if action == 'travel'))
                app.update_gate(ready)
                self.assertTrue(can_travel(d))
                app.action('travel', ready)
                self.assertNotEqual(d.theme, origin)

    def test_teleport_plays_once_on_successful_travel_in_both_directions(self):
        for origin in (EARTH, ABYDOS):
            with self.subTest(origin=origin.name):
                app, now = self.connected_console(origin)
                app.gate_audio.play.reset_mock()
                app.action('travel', now)
                app.gate_audio.play.assert_any_call('teleport', 'teleport')
                app.action('travel', now+.1)
                self.assertEqual(sum(call.args[0] == 'teleport'
                                     for call in app.gate_audio.play.call_args_list), 1)

    def test_no_teleport_sound_when_travel_is_unavailable(self):
        app = Console()
        self.addCleanup(pygame.quit)
        app.gate_audio.play = Mock()
        app.action('travel', 0)
        app.gate_audio.play.assert_not_called()

    def connected_console(self, origin, *, wait_for_travel=True):
        app = Console()
        # These tests assert the procedural horizon's color and audio-led timing.
        app.settings.horizon_video.enabled = False
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = origin
        app.ui.glyph.origin_mark = origin.origin_mark
        app.gate_audio.play = Mock(return_value=1)
        if origin.offworld:
            d.set_behavior('dhd')
        target = 'Earth' if origin.offworld else 'Abydos'
        self.assertTrue(d.load_destination(target, 0))
        if origin.offworld:
            self.assertTrue(d.activate(0))
        else:
            self.assertTrue(d.start(0))
        end = d.cycle_elapsed(len(d.sequence))
        app.update_gate(end)
        if d.state == 'activating':
            app.update_gate(d.activation_at+.001)
        self.assertEqual(d.state, 'connected')
        ready = d.connection.travel_unlock_at
        if wait_for_travel:
            app.update_gate(ready)
        return app, ready

    def test_both_ends_stay_open_then_close_together_in_both_directions(self):
        for origin, target in ((EARTH, ABYDOS), (ABYDOS, EARTH)):
            with self.subTest(origin=origin.name):
                app, now = self.connected_console(origin)
                d = app.dialer
                connection, connected_at = d.connection, d.connected_at
                sequence = d.sequence[:]
                source_visual = app.visual
                app.gate_audio.play.reset_mock()
                app.action('travel', now)
                self.assertIs(d.connection, connection)
                self.assertEqual(d.connected_at, connected_at)
                self.assertEqual((d.theme, d.state), (target, 'connected'))
                self.assertEqual((d.connection.origin, d.connection.destination), (origin.name, target.name))
                self.assertEqual(d.sequence, sequence)
                self.assertEqual(d.locked, 7)
                self.assertIs(source_visual, app.earth_visual if not origin.offworld else app.offworld_visual)
                self.assertFalse(can_travel(d))
                self.assertFalse(d.select(1, now))
                self.assertFalse(d.travel(now+.1))
                self.assertFalse(app.keyboard.keyboard_visible)
                app.gate_audio.play.assert_called_once_with('teleport', 'teleport')
                app.renderer.draw(now)
                self.assertGreater(app.ui.canvas.get_at(CENTER).b, 100)
                app.update_gate(now+TRAVEL_CLOSE_SECONDS-.001)
                self.assertEqual(d.state, 'connected')
                self.assertIsNone(app.earth_visual.horizon_closing)
                self.assertIsNone(app.offworld_visual.horizon_closing)
                closes = now+TRAVEL_CLOSE_SECONDS
                app.update_gate(closes)
                self.assertEqual(d.state, 'idle')
                self.assertEqual(app.earth_visual.horizon_closing, (closes, 1))
                self.assertEqual(app.offworld_visual.horizon_closing, (closes, 1))
                for visual in (app.earth_visual, app.offworld_visual):
                    self.assertEqual(visual.chevron_fade_duration, .2)
                    self.assertAlmostEqual(visual.chevron_light(0, 0, closes+1.1), .5)
                    self.assertEqual(visual.chevron_light(0, 0, closes+1.21), 0)
                names = [c.args[0] for c in app.gate_audio.play.call_args_list]
                self.assertEqual(names.count('close'), 1)
                self.assertNotIn('open', names)
                self.assertNotIn('fail', names)
                app.update_gate(closes+1.01)
                app.renderer.draw(closes+1.01)
                self.assertIsNone(app.earth_visual.horizon_closing)
                self.assertIsNone(app.offworld_visual.horizon_closing)

    def test_manual_shutdown_during_arrival_closes_both_without_second_close(self):
        app, now = self.connected_console(EARTH)
        app.action('travel', now)
        app.gate_audio.play.reset_mock()
        app.action('shutdown', now+.2)
        self.assertEqual(app.dialer.state, 'idle')
        self.assertIsNone(app.dialer.connection.arrival_close_at)
        self.assertIsNotNone(app.earth_visual.horizon_closing)
        self.assertIsNotNone(app.offworld_visual.horizon_closing)
        app.update_gate(now+5)
        names = [c.args[0] for c in app.gate_audio.play.call_args_list]
        self.assertEqual(names.count('close'), 1)
        self.assertNotIn('fail', names)

    def test_arrival_hides_departure_address_through_closure_in_both_directions(self):
        for origin in (EARTH, ABYDOS):
            with self.subTest(origin=origin.name):
                app, now = self.connected_console(origin)
                departure = app.visual
                app.action('travel', now)
                d = app.dialer
                self.assertTrue(app.visual.incoming)
                self.assertFalse(departure.incoming)
                self.assertFalse(app.visual.show_address(d))
                # Slots may draw their frames, but must not render address images.
                app.renderer.slot_glyph_image = Mock(side_effect=AssertionError('Arrival address leaked'))
                app.renderer.draw(now)
                if d.theme.offworld:
                    app.keyboard.draw_keyboard()
                    # Selected orange glyphs must not leak into the arrival DHD.
                    orange = (246, 174, 83)
                    with patch('offworld.fitted_dhd_glyph', wraps=fitted_dhd_glyph) as glyph:
                        app.keyboard.draw_keyboard()
                        self.assertFalse(any(c.args[2] == orange for c in glyph.call_args_list))
                closes = now+TRAVEL_CLOSE_SECONDS
                app.update_gate(closes)
                app.renderer.draw(closes)
                self.assertFalse(app.visual.show_address(d))
                app.update_gate(closes+1.01)
                app.renderer.draw(closes+1.01)
                app.update_gate(closes+4)
                app.action(27, closes+4)
                self.assertFalse(app.visual.incoming)
                self.assertTrue(app.visual.show_address(d))
                self.assertEqual(d.selected, [27])
