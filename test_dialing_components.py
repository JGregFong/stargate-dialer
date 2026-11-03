"""Boundary checks for the independent dialing policies."""
import unittest

from activation import Activation
from address_validation import AddressValidator
from connection import Connection
from simulator import Dialer
from themes import ABYDOS
from dhd_queue import OFFWORLD_ENGAGE_DELAY


class ComponentTests(unittest.TestCase):
    def test_offworld_short_delay_preserves_order_and_cancels_on_shutdown(self):
        for rpm in (None, 5, 30):
            with self.subTest(rpm=rpm):
                d = Dialer(rotation_rpm=rpm)
                d.theme = ABYDOS
                d.set_behavior('dhd')
                for glyph in (27, 25, 4):
                    self.assertTrue(d.select(glyph, 10))
                self.assertEqual(d.selected, [27, 25, 4])
                self.assertEqual(d.locked, 0)
                d.update(10+OFFWORLD_ENGAGE_DELAY-.001)
                self.assertEqual(d.locked, 0)
                d.update(10+OFFWORLD_ENGAGE_DELAY)
                self.assertEqual(d.locked, 1)
                d.update(10+2*OFFWORLD_ENGAGE_DELAY)
                self.assertEqual(d.locked, 2)
                d.shutdown()
                d.update(100)
                self.assertEqual((d.locked, d.sequence, d.state), (0, [], 'idle'))

    def test_offworld_sgc_matches_earth_dhd_queue_pause_resume_and_activation(self):
        earth, offworld = Dialer(rotation_rpm=5), Dialer(rotation_rpm=5)
        offworld.theme = ABYDOS
        offworld.offworld_sgc_dialing = True
        for d in (earth, offworld):
            d.set_behavior('dhd')
            self.assertTrue(d.select(8, 0))
            self.assertTrue(d.select(1, .1))
        first_end = earth.cycle_elapsed(1)
        for d in (earth, offworld):
            d.update(first_end)
            self.assertEqual((d.state, d.locked), ('dialing', 1))
        end = earth.cycle_elapsed(2)
        for d in (earth, offworld):
            d.update(end)
            self.assertEqual((d.state, d.locked), ('dhd_wait', 2))
            # Resume after a long pause, then queue the rest without waiting.
            for glyph in (22, 14, 36, 19, 0):
                self.assertTrue(d.select(glyph, end+100))
            self.assertTrue(d.activate(end+100))
            self.assertEqual(d.locked, 2)
        self.assertEqual(earth.started, offworld.started)
        self.assertEqual(earth.cycle_durations(), offworld.cycle_durations())
        final_lock = earth.started+earth.cycle_elapsed(7)
        for d in (earth, offworld):
            d.update(final_lock)
            self.assertEqual((d.state, d.locked), ('activating', 7))
            d.update(final_lock+.81)
            self.assertEqual(d.state, 'connected')
            self.assertEqual(d.destination, 'CHULAK')

    def test_resolution_preserves_order_and_restriction_precedence(self):
        validator = AddressValidator({
            'Blocked': {'Address': [1, 2], 'Active': False, 'Locked': True},
            'Offline': {'Address': [2, 1], 'Active': False, 'Locked': False},
        })
        self.assertEqual(validator.resolve([1, 2]).message, 'DESTINATION RESTRICTED')
        self.assertEqual(validator.resolve([2, 1]).message, 'DESTINATION UNAVAILABLE')
        self.assertIsNone(validator.resolve([1, 3]).destination)
        self.assertFalse(validator.resolve([1, 2]).available)

    def test_activation_deadline_and_cancellation(self):
        activation = Activation()
        self.assertFalse(activation.due(100))
        self.assertTrue(activation.request('dhd', 'ready', list(range(7)), 7, True))
        activation.begin(10)
        self.assertFalse(activation.due(10.79))
        self.assertTrue(activation.due(10.8))
        self.assertTrue(activation.consume_sound())
        self.assertFalse(activation.consume_sound())
        activation.reset()
        self.assertFalse(activation.requested)
        self.assertFalse(activation.due(100))

    def test_connection_expiration_boundary(self):
        connection = Connection(duration=5)
        connection.connect(100)
        self.assertFalse(connection.expired(104.99))
        self.assertTrue(connection.expired(105))
        self.assertEqual(connection.remaining(106), 0)
        connection.connect(200)
        self.assertEqual(connection.remaining(200), 5)

    def test_shutdown_cancels_pending_activation(self):
        dialer = Dialer(lock_seconds=1)
        dialer.set_behavior('dhd')
        dialer.load_destination('Abydos', 0)
        dialer.activate(0)
        dialer.update(7)
        self.assertEqual(dialer.state, 'activating')
        dialer.shutdown()
        dialer.update(100)
        self.assertEqual(dialer.state, 'idle')
        self.assertFalse(dialer.consume_activation_sound())
        self.assertIsNone(dialer.activation_at)

    def test_extended_status_uses_selected_length(self):
        for name, count in (('Atlantis', 8), ('Destiny', 9)):
            for behavior in ('current', 'dhd'):
                with self.subTest(name=name, behavior=behavior):
                    dialer = Dialer(lock_seconds=1)
                    dialer.set_behavior(behavior)
                    dialer.load_destination(name)
                    if behavior == 'current':
                        dialer.start(0)
                    for locked in range(count):
                        dialer.update(locked + .5)
                        expected = (f'ENCODING GLYPH {locked + 1} / {count}'
                                    if behavior == 'dhd' else
                                    f'CHEVRON {locked + 1} / {count} — ACQUIRING')
                        self.assertEqual(dialer.message, expected)
                    dialer.update(count)
                    self.assertEqual(dialer.state,
                                     'ready' if behavior == 'dhd' else 'connected')
