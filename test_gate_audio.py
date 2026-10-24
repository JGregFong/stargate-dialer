"""Regression tests for audio timing at paused DHD cycle boundaries."""
import unittest
from unittest.mock import Mock, patch
from simulator import Dialer
from gate_audio import GateAudio

SPIN_FRACTION = 8 / 10.8


class DHDAudioTimingTests(unittest.TestCase):
    def audio(self):
        with patch('pygame.mixer.get_init', return_value=None):
            audio = GateAudio()
        audio.play = Mock(return_value=1.0)
        return audio

    def test_resumed_symbols_do_not_engage_on_click(self):
        for count in (7, 8, 9):
            with self.subTest(count=count):
                d = Dialer()
                d.set_symbol_count(count)
                d.set_behavior('dhd')
                a = self.audio()
                now = 1000000.1
                for index, glyph in enumerate(list(range(1, count)) + [0]):
                    a.play.reset_mock()
                    self.assertTrue(d.select(glyph, now))
                    d.update(now)
                    self.assertEqual(d.dialing_position(now), (index, 0.0))
                    a.update(d, None, now, SPIN_FRACTION)
                    names = [call.args[0] for call in a.play.call_args_list]
                    self.assertIn('roll', names)
                    self.assertNotIn('chevron', names)
                    self.assertNotIn('final_chevron', names)
                    self.assertNotIn('computer_in', names)
                    a.play.reset_mock()
                    d.update(now + 8.01)
                    a.update(d, None, now + 8.01, SPIN_FRACTION)
                    cue = 'final_chevron' if glyph == 0 else 'chevron'
                    a.play.assert_any_call(cue, 'chevron')
                    count_before = a.play.call_count
                    a.update(d, None, now + 8.02, SPIN_FRACTION)
                    self.assertEqual(a.play.call_count, count_before)
                    d.update(now + d.lock_seconds + .01)
                    a.update(d, None, now + d.lock_seconds + .01, SPIN_FRACTION)
                    now += 73.137

    def test_computer_stages_stay_in_order_after_resume(self):
        d = Dialer()
        d.set_behavior('dhd')
        a = self.audio()
        for index, glyph in enumerate((26, 6)):
            now = 1000000.3 + index * 100.137
            d.select(glyph, now)
            a.play.reset_mock()
            for offset in (0, 8.01, 9.35, 9.67, 10.21):
                d.update(now+offset)
                a.update_computer(d, False, now+offset, SPIN_FRACTION)
            self.assertEqual([c.args[0] for c in a.play.call_args_list],
                             ['computer_in', 'computer_beep', 'computer_out', 'computer_beep'])
            d.update(now+10.81)
            a.update(d, None, now+10.81, SPIN_FRACTION)


    def test_nondefault_rpm_chevron_cue_matches_rendered_stop(self):
        for rpm in (2, 12, 60):
            for behavior in ('current', 'dhd'):
                with self.subTest(rpm=rpm, behavior=behavior):
                    d = Dialer(rotation_rpm=rpm)
                    d.set_behavior(behavior)
                    d.load_destination('Abydos', 0)
                    if behavior == 'current':
                        d.start(0)
                    a = self.audio()
                    spin = d.cycle_durations()[0] - 2.8
                    a.update(d, None, spin - .001, d.spin_fraction(spin - .001))
                    self.assertNotIn('chevron', [c.args[0] for c in a.play.call_args_list])
                    a.play.reset_mock()
                    a.update(d, None, spin + .001, d.spin_fraction(spin + .001))
                    a.play.assert_any_call('chevron', 'chevron')
                    self.assertNotIn('roll', [c.args[0] for c in a.play.call_args_list])


if __name__ == '__main__':
    unittest.main()
