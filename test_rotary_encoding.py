"""Rotary dialing transfers the top locking flash after the clamp returns."""
import unittest
from unittest.mock import Mock, patch
from simulator import Dialer
from offworld_state import OffworldVisualState
from ring_motion import ring_rotation, TILE_ANGLE
from themes import ABYDOS
from gate_audio import GateAudio


class RotaryEncodingTests(unittest.TestCase):
    def setUp(self):
        self.d = Dialer(rotation_rpm=10)
        self.d.theme = ABYDOS
        self.d.set_behavior('dhd')
        self.d.offworld_sgc_dialing = True
        self.d.select(27, 0)
        self.d.select(9, .1)
        self.v = OffworldVisualState()
        self.spin = self.d.cycle_durations()[0]-2.8

    def test_clamp_then_light_then_return_then_transfer_then_fade(self):
        self.assertIsNone(self.v.rotary_encoding(self.d, self.spin-.1))
        index, slide, top, assigned = self.v.rotary_encoding(self.d, self.spin+.45)
        self.assertEqual(index, 0)
        self.assertAlmostEqual(slide, 8)
        self.assertAlmostEqual(top, 0)
        self.assertEqual(assigned, 0)
        _, slide, top, assigned = self.v.rotary_encoding(self.d, self.spin+1)
        self.assertAlmostEqual(slide, 8)
        self.assertAlmostEqual(top, 1)
        self.assertEqual(assigned, 0)
        _, slide, top, assigned = self.v.rotary_encoding(self.d, self.spin+1.8)
        self.assertAlmostEqual(slide, 0)
        self.assertAlmostEqual(top, 1)
        self.assertAlmostEqual(assigned, 1)
        _, slide, top, assigned = self.v.rotary_encoding(self.d, self.spin+2.3)
        self.assertAlmostEqual(top, .5)
        self.assertEqual(assigned, 1)
        for t in (.1, .7, 1.5, 2.7):
            rotation = self.v.rotation(self.d, self.spin+t)
            self.assertAlmostEqual((rotation+27*TILE_ANGLE) % 360, 0)
            self.assertEqual(ring_rotation(self.d.sequence, self.spin+t, self.d.lock_seconds,
                                           velocity=True, rpm=10), 0)
        self.d.update(self.spin+2.8)
        self.assertEqual(self.d.locked, 1)
        self.assertIsNone(self.v.rotary_encoding(self.d, self.spin+2.8))

    def test_other_modes_and_shutdown_have_no_transient_top_animation(self):
        self.v.ring_return = (0, 1, 1, 0)
        self.assertIsNone(self.v.rotary_encoding(self.d, self.spin+1))
        self.v.ring_return = None
        for mode in ('dhd', 'spinning'):
            self.d.offworld_dialing_mode = mode
            self.assertIsNone(self.v.rotary_encoding(self.d, self.spin+1))

    def test_lock_sound_starts_with_clamp_motion_once(self):
        audio = GateAudio()
        audio.play = Mock(return_value=1)
        audio.update(self.d, None, self.spin-.01, self.d.spin_fraction(0))
        self.assertFalse(any(c.args[0] == 'rotary_chevron' for c in audio.play.call_args_list))
        audio.update(self.d, None, self.spin, self.d.spin_fraction(0))
        audio.play.assert_any_call('rotary_chevron', 'chevron')
        audio.update(self.d, None, self.spin+.7, self.d.spin_fraction(0))
        self.d.update(self.spin+2.8)
        audio.update(self.d, None, self.spin+2.8, self.d.spin_fraction(0))
        self.assertEqual(sum(c.args[0] == 'rotary_chevron' for c in audio.play.call_args_list), 1)

    def test_final_rotary_symbol_uses_lock_sound(self):
        self.d.reset()
        self.d.load_destination('Earth', 0)
        audio = GateAudio()
        audio.play = Mock(return_value=1)
        final_encoding = self.d.cycle_elapsed(7)-2.8
        self.d.update(final_encoding+.7)
        audio.update(self.d, None, final_encoding+.7, self.d.spin_fraction(final_encoding+.7))
        audio.play.assert_any_call('final_chevron', 'chevron')
        self.assertFalse(any(c.args[0] in ('rotary_chevron', 'offworld_chevron')
                             for c in audio.play.call_args_list))
        self.d.update(self.d.cycle_elapsed(7))
        audio.update(self.d, None, self.d.cycle_elapsed(7), self.d.spin_fraction(0))
        self.assertEqual(sum(c.args[0] == 'final_chevron' for c in audio.play.call_args_list), 1)

    def test_roll_stops_for_encoding_and_restarts_only_with_next_rotation(self):
        audio = GateAudio()
        audio.play, audio.stop = Mock(return_value=1), Mock()
        audio.update(self.d, None, self.spin/2, self.d.spin_fraction(0))
        self.assertIsNotNone(audio.spin_key)
        for offset in (.01, .7, 1.6, 2.7):
            audio.update(self.d, None, self.spin+offset, self.d.spin_fraction(self.spin+offset))
            self.assertIsNone(audio.spin_key)
        audio.stop.assert_any_call('roll')
        self.d.update(self.spin+2.8)
        audio.update(self.d, None, self.spin+2.81, self.d.spin_fraction(self.spin+2.81))
        self.assertIsNotNone(audio.spin_key)

    def test_paused_rotary_dhd_has_no_roll(self):
        self.d.sequence = self.d.sequence[:1]
        self.d.selected = self.d.selected[:1]
        end = self.d.cycle_elapsed(1)
        self.d.update(end)
        audio = GateAudio()
        audio.play = Mock(return_value=1)
        audio.update(self.d, None, end+1, self.d.spin_fraction(end+1))
        self.assertIsNone(audio.spin_key)
        self.assertFalse(any(c.args[0] == 'roll' for c in audio.play.call_args_list))

    def test_every_queued_glyph_is_centered_throughout_its_lock(self):
        self.d.reset()
        self.v.rest_rotation = 23.75
        self.d.rotation_origin = lambda: self.v.rest_rotation
        self.d.load_destination('Earth', 0)
        for index, glyph in enumerate(self.d.sequence):
            end = self.d.cycle_elapsed(index+1)
            for offset in (.01, .7, 1.6, 2.79):
                now = end-2.8+offset
                rotation = self.v.rotation(self.d, now)
                angle = (rotation+glyph*TILE_ANGLE+180) % 360-180
                self.assertAlmostEqual(angle, 0, places=9)

    def test_rendered_tile_centers_stay_under_top_chevron_for_all_glyphs(self):
        import pygame
        from main import Console
        from gate_art import ring_point
        from ui_geometry import CENTER
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.offworld_sgc_dialing = True
        renderer = app.renderer
        # Place a diagnostic marker at each tile center, then exercise the real
        # renderer crop, rotation, and placement without covering it with a clamp.
        with patch('offworld_renderer.draw_chevron'):
            for glyph in range(39):
                d.sequence, d.state, d.started, d.locked = [glyph], 'dialing', 0, 0
                ring = pygame.Surface((644, 644), pygame.SRCALPHA)
                x, y = ring_point(303, glyph*TILE_ANGLE)
                pygame.draw.circle(ring, (255, 0, 255),
                                   (round(x-CENTER[0]+322), round(y-CENTER[1]+322)), 3)
                renderer.ring_image = ring
                spin = d.cycle_elapsed(1)-2.8
                previous_center = None
                for offset in (.01, .7, 1.6, 2.79):
                    renderer.draw(spin+offset)
                    samples = []
                    for yy in range(CENTER[1]-310, CENTER[1]-295):
                        for xx in range(CENTER[0]-7, CENTER[0]+8):
                            red, green, blue, _ = app.ui.canvas.get_at((xx, yy))
                            if red > 160 and blue > 160 and green < 30:
                                samples.append((xx, yy))
                    self.assertTrue(samples, f'Glyph {glyph} marker missing')
                    center = tuple(sum(p[axis] for p in samples)/len(samples) for axis in (0, 1))
                    self.assertAlmostEqual(center[0], CENTER[0], delta=1.25)
                    self.assertAlmostEqual(center[1], CENTER[1]-303, delta=1.25)
                    if previous_center is not None:
                        self.assertEqual(center, previous_center)
                    previous_center = center
