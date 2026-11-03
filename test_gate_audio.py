"""Regression tests for audio timing at paused DHD cycle boundaries."""
import unittest
from unittest.mock import Mock, patch
from simulator import Dialer
from gate_audio import GateAudio
from themes import ABYDOS, EARTH
from dhd_queue import OFFWORLD_ENGAGE_DELAY

SPIN_FRACTION = 8 / 10.8


class DHDAudioTimingTests(unittest.TestCase):
    def test_offworld_sgc_sound_waits_for_lock(self):
        d = Dialer(rotation_rpm=5)
        d.theme = ABYDOS
        d.offworld_sgc_dialing = True
        d.set_behavior('dhd')
        d.select(26, 0)
        audio = self.audio()
        audio.update(d, None, 0, d.spin_fraction(0))
        self.assertNotIn('rotary_chevron', [c.args[0] for c in audio.play.call_args_list])
        end = d.cycle_elapsed(1)
        d.update(end)
        audio.update(d, None, end, d.spin_fraction(end))
        self.assertEqual((d.state, d.locked), ('dhd_wait', 1))
        audio.play.assert_any_call('rotary_chevron', 'chevron')

    def test_offworld_instant_locks_with_one_continuous_roll_until_final_lock(self):
        d = Dialer()
        d.theme = ABYDOS
        d.set_behavior('dhd')
        a = self.audio()
        a.stop = Mock()
        for index, glyph in enumerate((27, 25, 4, 35, 10, 28, 0)):
            self.assertTrue(d.select(glyph, index))
            self.assertEqual(d.locked, index)
            self.assertEqual(d.state, 'dialing')
            a.update(d, None, index, SPIN_FRACTION)
            d.update(index+OFFWORLD_ENGAGE_DELAY-.001)
            self.assertEqual(d.locked, index)
            d.update(index+OFFWORLD_ENGAGE_DELAY)
            self.assertEqual(d.locked, index+1)
            self.assertEqual(d.state, 'ready' if glyph == 0 else 'dhd_wait')
            a.update(d, None, index+OFFWORLD_ENGAGE_DELAY, SPIN_FRACTION)
            a.update(d, None, index+.5, SPIN_FRACTION)
            if glyph != 0:
                a.stop.assert_not_called()
            else:
                a.stop.assert_called_once_with('roll')
                self.assertIsNone(a.spin_key)
        names = [call.args[0] for call in a.play.call_args_list]
        self.assertEqual(names.count('roll'), 1)
        self.assertEqual(names.count('offworld_chevron'), 7)
        self.assertTrue(d.activate(7))
        a.update(d, None, 7, SPIN_FRACTION)
        self.assertEqual([call.args[0] for call in a.play.call_args_list].count('roll'), 1)
        d.update(7.8)
        self.assertEqual(d.state, 'connected')
        a.update(d, None, 7.8, SPIN_FRACTION)
        a.stop.assert_any_call('roll')
        self.assertIsNone(a.spin_key)

    def test_offworld_suppresses_computer_cues_and_retains_gate_cues(self):
        d = Dialer()
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.select(26, 0)
        a = self.audio()
        for now in (0, 8.01, 9.35, 9.67, 10.21):
            d.update(now)
            a.update(d, None, now, SPIN_FRACTION)
        names = [call.args[0] for call in a.play.call_args_list]
        self.assertIn('offworld_chevron', names)
        self.assertFalse(any(name.startswith('computer_') for name in names))
        self.assertTrue(a.computer_enabled)

    def test_offworld_chevron_shuffle_uses_all_clips_without_repeats(self):
        with patch('pygame.mixer.get_init', return_value=None):
            audio = GateAudio()
        clips = [Mock() for _ in range(7)]
        audio.last_offworld_chevron = clips[-1]
        audio.sounds['offworld_chevron'] = clips
        channel = Mock()
        audio.channels['chevron'] = channel
        # Force the same shuffle each round to exercise the boundary guard.
        with patch('gate_audio.random.shuffle'):
            for _ in range(21):
                audio.play('offworld_chevron', 'chevron')
        played = [call.args[0] for call in channel.play.call_args_list]
        self.assertIsNot(played[0], clips[-1])
        for start in (0, 7, 14):
            self.assertEqual(set(played[start:start+7]), set(clips))
        self.assertTrue(all(a is not b for a, b in zip(played, played[1:])))

    def test_arrival_stops_computer_channels_and_earth_restores_preference(self):
        d = Dialer()
        d.set_behavior('dhd')
        d.select(26, 0)
        a = self.audio()
        a.stop = Mock()
        a.update_computer(d, False, 8.01, SPIN_FRACTION)
        a.play.assert_called_with('computer_in', 'computer')
        d.theme = ABYDOS
        a.play.reset_mock()
        a.stop.reset_mock()
        a.update_computer(d, False, 8.02, SPIN_FRACTION)
        a.play.assert_not_called()
        a.stop.assert_any_call('computer')
        a.stop.assert_any_call('computer_beep')
        self.assertIsNone(a.computer_token)
        d.theme = EARTH
        a.update_computer(d, False, 8.03, SPIN_FRACTION)
        a.play.assert_called_with('computer_in', 'computer')
        a.set_computer_enabled(False)
        a.play.reset_mock()
        a.update_computer(d, False, 8.04, SPIN_FRACTION)
        a.play.assert_not_called()

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
