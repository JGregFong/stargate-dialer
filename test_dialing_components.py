"""Boundary checks for the independent dialing policies."""
import unittest

from activation import Activation
from address_validation import AddressValidator
from connection import Connection
from simulator import Dialer


class ComponentTests(unittest.TestCase):
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
