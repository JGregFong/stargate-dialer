"""Regression checks for address rules and timed state transitions."""
import unittest
from simulator import Dialer
from glyph_database import address_database


class DialerTests(unittest.TestCase):
    def ready(self, name='Abydos'):
        d = Dialer(lock_seconds=1, connection_seconds=5)
        for glyph in address_database[name]['Address']:
            d.select(glyph)
        self.assertTrue(d.start(100))
        return d

    def test_selection_rules(self):
        d = Dialer()
        for glyph in [0, -1, 39, 1, 1, 2, 3, 4, 5, 6, 7]:
            d.select(glyph)
        self.assertEqual(d.selected, [1, 2, 3, 4, 5, 6])
        self.assertTrue(d.start(0))
        self.assertEqual(d.sequence, [1, 2, 3, 4, 5, 6, 0])
        d.select(8)
        self.assertEqual(d.selected, [1, 2, 3, 4, 5, 6])

    def test_lock_progress_success_and_timeout(self):
        d = self.ready()
        d.update(103.4)
        self.assertEqual(d.locked, 3)
        self.assertEqual(d.state, 'dialing')
        d.update(107)
        self.assertEqual(d.state, 'connected')
        self.assertEqual(d.locked, 7)
        self.assertEqual(d.remaining(109), 3)
        d.update(112)
        self.assertEqual(d.state, 'idle')
        self.assertEqual(d.sequence, [])
        self.assertEqual(d.locked, 0)

    def test_unknown_address(self):
        d = Dialer(lock_seconds=1)
        d.selected = [1, 2, 3, 4, 5, 6]
        d.start(0)
        d.update(7)
        self.assertEqual(d.state, 'failed')
        self.assertEqual(d.locked, 7)

    def test_restricted_and_inactive(self):
        for name in ('P3W-451', 'Tollan'):
            d = self.ready(name)
            d.update(107)
            self.assertEqual(d.state, 'failed')

    def test_shutdown_and_redial(self):
        d = self.ready()
        d.shutdown()
        self.assertEqual(d.state, 'idle')
        self.assertEqual(d.selected, [])
        self.assertFalse(d.start(120))
        d.selected = address_database['Chulak']['Address'][:]
        self.assertTrue(d.start(120))
        d.update(127)
        self.assertEqual(d.state, 'connected')


class ExtendedAddressTests(unittest.TestCase):
    def test_known_long_addresses(self):
        for name, count in [('Atlantis', 8), ('Othala', 8), ('Destiny', 9)]:
            with self.subTest(name=name):
                d = Dialer(lock_seconds=1)
                self.assertTrue(d.load_destination(name))
                self.assertEqual(d.symbol_count, count)
                self.assertTrue(d.start(0))
                d.update(count - .1)
                self.assertEqual(d.state, 'dialing')
                d.update(count + .01)
                self.assertEqual(d.state, 'connected')
                self.assertEqual(len(d.sequence), count)
                self.assertEqual(d.sequence[-1], 0)

    def test_manual_lengths_and_duplicates(self):
        for count in (7, 8, 9):
            d = Dialer()
            self.assertTrue(d.set_symbol_count(count))
            for glyph in range(1, count):
                d.select(glyph)
                d.select(glyph)
            d.select(count)
            self.assertEqual(d.selected, list(range(1, count)))
            self.assertTrue(d.start(0))
            self.assertFalse(d.set_symbol_count(7))
            self.assertEqual(d.symbol_count, count)

    def test_mode_change_resets_entry(self):
        d = Dialer()
        d.select(1)
        self.assertTrue(d.set_symbol_count(9))
        self.assertEqual(d.selected, [])
        self.assertFalse(d.start(0))
        self.assertFalse(d.set_symbol_count(10))


class DHDDialingTests(unittest.TestCase):
    def test_incremental_pause_resume_and_activation(self):
        d = Dialer(lock_seconds=1)
        self.assertTrue(d.set_behavior('dhd'))
        address = address_database['Abydos']['Address']
        self.assertTrue(d.select(address[0], 10))
        self.assertEqual(d.state, 'dialing')
        d.update(11.01)
        self.assertEqual((d.state, d.locked), ('dhd_wait', 1))
        self.assertFalse(d.activate(20))
        for glyph in address[1:]:
            self.assertTrue(d.select(glyph, 30))
        self.assertTrue(d.select(0, 30))
        self.assertFalse(d.select(address[0], 30))
        d.update(36.01)
        self.assertEqual(d.state, 'ready')
        d.update(100)
        self.assertEqual(d.state, 'ready')
        self.assertTrue(d.activate(100))
        self.assertEqual(d.state, 'activating')
        d.update(100.81)
        self.assertEqual(d.state, 'connected')
        self.assertEqual(d.connected_at, 100.81)

    def test_queued_lengths_and_final_origin(self):
        for name in ('Abydos', 'Atlantis', 'Destiny'):
            with self.subTest(name=name):
                d = Dialer(lock_seconds=1)
                d.set_behavior('dhd')
                self.assertTrue(d.load_destination(name, 10))
                self.assertEqual(d.state, 'dialing')
                d.update(10 + d.symbol_count + .01)
                self.assertEqual(d.state, 'ready')
                self.assertEqual(d.sequence[-1], 0)
                self.assertTrue(d.activate(30))
                self.assertEqual(d.state, 'activating')
                d.update(30.81)
                self.assertEqual(d.state, 'connected')

    def test_invalid_only_fails_on_activation(self):
        d = Dialer(lock_seconds=1)
        d.set_behavior('dhd')
        for glyph in (1, 2, 3, 4, 5, 6, 0):
            self.assertTrue(d.select(glyph, 0))
        d.update(7.01)
        self.assertEqual(d.state, 'ready')
        d.activate(8)
        self.assertEqual(d.state, 'activating')
        d.update(8.81)
        self.assertEqual(d.state, 'failed')
        d.shutdown()
        self.assertEqual(d.sequence, [])
        self.assertEqual(d.behavior, 'dhd')

    def test_early_activation_waits_for_locks_and_pause(self):
        d = Dialer(lock_seconds=1)
        d.set_behavior('dhd')
        d.load_destination('Abydos', 0)
        self.assertTrue(d.activate(.1))
        self.assertFalse(d.consume_activation_sound())
        self.assertFalse(d.activate(.2))
        d.update(6.9)
        self.assertEqual(d.state, 'dialing')
        self.assertFalse(d.consume_activation_sound())
        d.update(7.01)
        self.assertEqual(d.state, 'activating')
        self.assertEqual(d.locked, 7)
        self.assertTrue(d.consume_activation_sound())
        self.assertFalse(d.consume_activation_sound())
        d.update(7.7)
        self.assertEqual(d.state, 'activating')
        d.update(7.82)
        self.assertEqual(d.state, 'connected')

    def test_cannot_change_behavior_mid_encoding(self):
        d = Dialer()
        d.set_behavior('dhd')
        self.assertFalse(d.select(0, 0))
        d.select(1, 0)
        self.assertFalse(d.select(1, 0))
        self.assertFalse(d.set_behavior('current'))
        self.assertFalse(d.start(0))


if __name__ == '__main__':
    unittest.main()
