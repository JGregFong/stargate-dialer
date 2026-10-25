"""Check five-RPM travel, symbol alignment, and synchronized encoding."""
import unittest

from ring_motion import ring_rotation
from simulator import Dialer, rotation_steps


class RingMotionTests(unittest.TestCase):
    def test_smooth_speed_ramps(self):
        sequence = [1]
        _, duration = next(rotation_steps(sequence))
        speed = lambda t: ring_rotation(sequence, t, 10.8, velocity=True)
        self.assertEqual(speed(0), 0)
        self.assertAlmostEqual(speed(.75), 15)
        self.assertAlmostEqual(speed(1.5), 30)
        self.assertAlmostEqual(speed(duration - 1.5), 30)
        self.assertAlmostEqual(speed(duration - .75), 15)
        self.assertEqual(speed(duration), 0)
        for t in (.4, 1.5, duration / 2, duration - 1.5, duration - .4):
            before = ring_rotation(sequence, t - .0001, 10.8)
            after = ring_rotation(sequence, t + .0001, 10.8)
            self.assertAlmostEqual((after - before) / .0002, speed(t), places=5)

    def test_speed_and_symbol_stops(self):
        sequence = [1, 17, 30, 0]
        elapsed = 0.0
        rotation = 23.0
        for glyph, (delta, duration) in zip(sequence, rotation_steps(sequence, 23.0)):
            midpoint = elapsed + duration / 2
            self.assertAlmostEqual(abs(ring_rotation(sequence, midpoint, 10.8, True, 23.0)), 30)
            self.assertAlmostEqual(ring_rotation(sequence, midpoint, 10.8, initial_rotation=23.0), rotation + delta / 2)
            rotation += delta
            self.assertAlmostEqual((rotation + glyph * 360 / 39 + 180) % 360 - 180, 0, places=6)
            self.assertAlmostEqual(ring_rotation(sequence, elapsed + duration + 1, 10.8, initial_rotation=23.0), rotation)
            elapsed += duration + 2.8

    def test_encoding_timing(self):
        dialer = Dialer(rotation_rpm=5)
        dialer.selected = [1, 2, 3, 4, 5, 6]
        self.assertTrue(dialer.start(0))
        for index, (_, spin) in enumerate(rotation_steps(dialer.sequence)):
            now = dialer.cycle_elapsed(index) + spin
            self.assertEqual(dialer.dialing_position(now)[0], index)
            self.assertAlmostEqual(dialer.dialing_position(now)[1], dialer.spin_fraction(now))
        dialer.update(dialer.cycle_elapsed(len(dialer.sequence)))
        self.assertEqual(dialer.locked, 7)


class SharedRPMTests(unittest.TestCase):
    def test_nondefault_rpm_aligns_rendering_and_both_dialing_modes(self):
        for rpm in (2, 12, 60):
            for behavior in ('current', 'dhd'):
                for name in ('Abydos', 'Atlantis', 'Destiny'):
                    with self.subTest(rpm=rpm, behavior=behavior, name=name):
                        dialer = Dialer(rotation_rpm=rpm)
                        dialer.rotation_origin = lambda: 23.0
                        dialer.set_behavior(behavior)
                        dialer.load_destination(name, 0)
                        if behavior == 'current':
                            self.assertTrue(dialer.start(0))
                        rotation = 23.0
                        elapsed = 0.0
                        for index, (delta, spin) in enumerate(rotation_steps(
                                dialer.sequence, 23.0, rpm)):
                            midpoint = elapsed + spin / 2
                            self.assertAlmostEqual(abs(ring_rotation(
                                dialer.sequence, midpoint, 10.8, True, 23.0, rpm)), rpm * 6)
                            self.assertAlmostEqual(ring_rotation(
                                dialer.sequence, midpoint, 10.8,
                                initial_rotation=23.0, rpm=rpm), rotation + delta / 2)
                            rotation += delta
                            stop = elapsed + spin
                            self.assertAlmostEqual(ring_rotation(
                                dialer.sequence, stop, 10.8,
                                initial_rotation=23.0, rpm=rpm), rotation)
                            self.assertEqual(dialer.dialing_position(stop)[0], index)
                            self.assertAlmostEqual(dialer.dialing_position(stop)[1],
                                                   dialer.spin_fraction(stop))
                            elapsed += spin + 2.8
                            dialer.update(elapsed)
                            self.assertEqual(dialer.locked, index + 1)
                        self.assertEqual(dialer.state,
                                         'ready' if behavior == 'dhd' else 'connected')

    def test_dhd_resume_retains_nondefault_speed_and_stops(self):
        dialer = Dialer(rotation_rpm=12)
        dialer.set_behavior('dhd')
        dialer.select(26, 10)
        dialer.update(10 + dialer.cycle_elapsed(1))
        self.assertEqual(dialer.state, 'dhd_wait')
        dialer.select(6, 100)
        self.assertEqual(dialer.dialing_position(100), (1, 0.0))
        self.assertEqual(dialer.rotation_rpm, 12)
        dialer.update(dialer.started + dialer.cycle_elapsed(2))
        self.assertEqual((dialer.state, dialer.locked), ('dhd_wait', 2))

    def test_invalid_rotation_speeds_are_rejected(self):
        for rpm in (0, -1, float('nan'), float('inf')):
            with self.subTest(rpm=rpm):
                with self.assertRaises(ValueError):
                    Dialer(rotation_rpm=rpm)
                with self.assertRaises(ValueError):
                    list(rotation_steps([1], rpm=rpm))


if __name__ == '__main__':
    unittest.main()
