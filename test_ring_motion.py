"""Check five-RPM travel, symbol alignment, and synchronized encoding."""
import unittest

from main import ring_rotation
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


if __name__ == '__main__':
    unittest.main()
