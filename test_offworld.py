"""Incoming timing, priority, and recognition regression checks."""
import unittest
from simulator import Dialer
from scenarios import TYPES

class OffworldTests(unittest.TestCase):
    def test_all_types_lock_connect_expire_and_block_dialing(self):
        for kind in TYPES:
            with self.subTest(kind=kind):
                d = Dialer(rotation_rpm=5)
                self.assertTrue(d.begin_offworld(kind, 0))
                for i in range(7):
                    d.update_offworld((i+1)*1.5, True)
                    self.assertEqual(d.locked, i+1)
                    self.assertFalse(d.select(1))
                    self.assertFalse(d.start(20))
                    d.reset()
                    self.assertIsNotNone(d.offworld)
                    d.spin_fraction((i+1)*1.5)
                opened = d.offworld.established_at
                d.update_offworld(opened, True)
                self.assertEqual(d.state, 'connected')
                self.assertEqual(d.remaining(opened), 20)
                d.update(opened+21)
                self.assertIsNotNone(d.offworld)
                d.update_offworld(opened+20, True)
                self.assertEqual(d.state, 'idle')
                self.assertIsNone(d.offworld)

    def test_hostile_requires_continuous_open_iris(self):
        d = Dialer()
        d.begin_offworld('hostile', 0)
        t = d.offworld.established_at
        d.update_offworld(t, True)
        d.update_offworld(t+1, True)
        self.assertFalse(d.offworld.hostile_present)
        d.update_offworld(t+1.5, False)
        d.update_offworld(t+2, True)
        d.update_offworld(t+16.9, True)
        self.assertFalse(d.offworld.hostile_present)
        d.update_offworld(t+17, True)
        self.assertEqual(d.offworld.notification(t+17), 'Hostile Action Present')

    def test_gdo_delayed_recognition(self):
        d = Dialer()
        d.begin_offworld('friendlygdo', 0)
        e = d.offworld
        self.assertEqual(e.recognition(e.established_at+3), 0)
        self.assertAlmostEqual(e.recognition(e.established_at+5.5), .5)
        self.assertEqual(e.recognition(e.established_at+8), 1)
