"""Time-based dialing logic, independent of Pygame."""
from glyph_database import address_database
from address_validation import AddressValidator
from dialing_states import update_dialing
from dhd_queue import DHDQueue
from activation import Activation
from connection import Connection

# Re-export motion helpers for existing callers.
from ring_motion import (
    ROTATION_RAMP_SECONDS, ENCODING_SECONDS, rotation_steps, validate_rpm,
)


class Dialer:
    # Initialize pure dialing state and configurable cycle and connection timing.
    def __init__(self, lock_seconds=10.8, connection_seconds=38 * 60, rotation_rpm=None):
        self.lock_seconds = lock_seconds
        self.rotation_rpm = None if rotation_rpm is None else validate_rpm(rotation_rpm)
        self.rotation_origin = lambda: 0.0
        self.connection = Connection(connection_seconds)
        self.activation = Activation()
        self.addresses = AddressValidator(address_database)
        self.dial_id = 0
        self.behavior = 'current'
        self.symbol_count = 7
        self.selected = []
        self.origin_selected = False
        self.sequence = []
        self.locked = 0
        self.activation.reset()
        self.state = 'idle'
        self.message = f'SELECT {self.symbol_count - 1} DISTINCT GLYPHS'
        self.destination = 'MANUAL ADDRESS'
        self.started = 0.0
        self.connected_at = 0.0

    # Compatibility attributes delegate storage to their owning components.
    @property
    def connection_seconds(self):
        return self.connection.duration

    @connection_seconds.setter
    def connection_seconds(self, value):
        self.connection.duration = value

    @property
    def connected_at(self):
        return self.connection.connected_at

    @connected_at.setter
    def connected_at(self, value):
        self.connection.connected_at = value

    @property
    def activation_requested(self):
        return self.activation.requested

    @activation_requested.setter
    def activation_requested(self, value):
        self.activation.requested = value

    @property
    def activation_at(self):
        return self.activation.deadline

    @activation_at.setter
    def activation_at(self, value):
        self.activation.deadline = value

    @property
    def activation_sound_pending(self):
        return self.activation.sound_pending

    @activation_sound_pending.setter
    def activation_sound_pending(self, value):
        self.activation.sound_pending = value

    # Change speed only between dialing attempts.
    def set_rotation_rpm(self, rpm):
        if self.state not in ('idle', 'failed'):
            return False
        self.rotation_rpm = validate_rpm(rpm)
        return True

    # Switch between 7-, 8-, and 9-symbol addresses while idle.
    def set_symbol_count(self, count):
        if self.state != 'idle' or count not in (7, 8, 9):
            return False
        self.symbol_count = count
        self.reset()
        return True

    # Load an ordered address and automatically queue encoding in DHD mode.
    def load_destination(self, name, now=0):
        data = address_database[name]
        if not self.set_symbol_count(len(data['Address']) + 1):
            return False
        self.selected = data['Address'][:]
        self.origin_selected = True
        self.destination = name.upper()
        if self.behavior == 'dhd':
            self.sequence = self.selected[:] + [0]
            self.started = now
            self.state = 'dialing'
            self.message = 'DHD / ENCODING ADDRESS'
        return True

    # Change dialing behavior only when no active procedure would be interrupted.
    def set_behavior(self, behavior):
        if behavior not in ('current', 'dhd') or self.state not in ('idle', 'failed'):
            return False
        self.behavior = behavior
        self.reset()
        return True

    # Validate glyph entry and immediately queue or resume DHD encoding.
    def select(self, glyph, now=0):
        allowed = self.state == 'idle' or (self.behavior == 'dhd' and self.state in ('dialing', 'dhd_wait'))
        if not allowed or not self.addresses.can_select(glyph, self.selected, self.symbol_count, self.origin_selected):
            return False
        if glyph == 0:
            self.origin_selected = True
        else:
            self.selected.append(glyph)
            self.destination = 'MANUAL ADDRESS'
        if self.behavior == 'dhd':
            DHDQueue.append(self, glyph, now)
        return True

    # Clear address and activation state while retaining selected mode preferences.
    def reset(self, message=None):
        self.dial_id += 1
        self.selected = []
        self.origin_selected = False
        self.sequence = []
        self.locked = 0
        self.activation.reset()
        self.state = 'idle'
        self.destination = 'MANUAL ADDRESS'
        self.message = message or f'SELECT {self.symbol_count - 1} DISTINCT GLYPHS'

    # Begin the complete-address dialing sequence in computer mode.
    def start(self, now):
        if self.behavior == 'dhd' or self.state != 'idle' or not self.addresses.complete(self.selected, self.symbol_count):
            return False
        self.origin_selected = True
        self.sequence = self.selected[:] + [0]
        self.locked = 0
        self.activation.reset()
        self.dial_id += 1
        self.started = now
        self.state = 'dialing'
        self.message = 'DIALING SEQUENCE INITIATED'
        return True

    # Keep animation and audio on the same floating-point-safe cycle boundary.
    def cycle_durations(self):
        if self.rotation_rpm is None:
            return [self.lock_seconds] * len(self.sequence)
        return [spin + ENCODING_SECONDS for _, spin in rotation_steps(
            self.sequence, self.rotation_origin(), self.rotation_rpm)]

    def cycle_elapsed(self, count):
        return sum(self.cycle_durations()[:count])

    def spin_fraction(self, now):
        if self.rotation_rpm is None or not self.sequence:
            return 8 / 10.8
        index = min(self.dialing_position(now)[0], len(self.sequence) - 1)
        duration = self.cycle_durations()[index]
        return (duration - ENCODING_SECONDS) / duration

    def dialing_position(self, now):
        """One shared, boundary-safe cycle clock for animation and sound."""
        elapsed = max(0.0, now-self.started)
        if self.rotation_rpm is not None:
            durations = self.cycle_durations()
            for index, duration in enumerate(durations):
                if elapsed < duration - 1e-7:
                    return index, max(0.0, elapsed) / duration
                elapsed -= duration
            return len(durations), 0.0
        nearest = round(elapsed/self.lock_seconds)
        if abs(elapsed-nearest*self.lock_seconds) < 1e-7:
            return nearest, 0.0
        index = int(elapsed/self.lock_seconds)
        return index, (elapsed-index*self.lock_seconds)/self.lock_seconds

    # Advance glyph locks, queued activation, destination resolution, and timeout.
    def update(self, now):
        if self.state == 'dialing':
            update_dialing(self, now)
        elif self.state == 'activating' and self.activation.due(now):
            self.resolve_connection(now)
        elif self.state == 'connected' and self.connection.expired(now):
            self.reset('CONNECTION LIMIT REACHED / DISENGAGED')

    # Accept a DHD activation request once every address symbol has been selected.
    def activate(self, now):
        if not self.activation.request(self.behavior, self.state, self.sequence,
                                       self.symbol_count, self.origin_selected):
            return False
        if self.state == 'ready':
            self.begin_activation(now)
        else:
            self.message = 'ACTIVATION QUEUED / WAITING FOR FINAL LOCK'
        return True

    # Schedule the post-lock activation pause and one pending button sound.
    def begin_activation(self, now):
        self.state = 'activating'
        self.activation.begin(now)
        self.message = 'ALL SYMBOLS LOCKED / ACTIVATING WORMHOLE'

    # Consume the one-shot notification used by the UI audio layer.
    def consume_activation_sound(self):
        return self.activation.consume_sound()

    # Check address order and eligibility before connecting or reporting failure.
    def resolve_connection(self, now):
        result = self.addresses.resolve(self.selected)
        if result.destination is not None:
            self.destination = result.destination.upper()
        self.state = 'connected' if result.available else 'failed'
        self.message = result.message
        if result.available:
            self.connection.connect(now)

    # Return the nonnegative remaining connected duration.
    def remaining(self, now):
        return self.connection.remaining(now)

    # Reset the logical gate; the UI owns the visible shutdown animations.
    def shutdown(self):
        self.reset('STARGATE DISENGAGED')
