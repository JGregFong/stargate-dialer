"""Time-based dialing logic, independent of Pygame."""
from glyph_database import address_database

ROTATION_RAMP_SECONDS = 1.5


def rotation_steps(sequence, initial_rotation=0.0, rpm=5):
    """Return signed travel and spin duration for each alternating symbol stop."""
    rotation = initial_rotation
    for index, glyph in enumerate(sequence):
        direction = 1 if index % 2 == 0 else -1
        distance = ((-glyph * 360 / 39 - rotation) * direction) % 360
        if distance < 180:
            distance += 360
        delta = direction * distance
        # Each smooth speed ramp covers half the distance of full-speed travel.
        yield delta, distance / (rpm * 6) + ROTATION_RAMP_SECONDS
        rotation += delta


class Dialer:
    # Initialize pure dialing state and configurable cycle and connection timing.
    def __init__(self, lock_seconds=10.8, connection_seconds=38 * 60, rotation_rpm=None):
        self.lock_seconds = lock_seconds
        self.rotation_rpm = rotation_rpm
        self.rotation_origin = lambda: 0.0
        self.connection_seconds = connection_seconds
        self.dial_id = 0
        self.behavior = 'current'
        self.symbol_count = 7
        self.selected = []
        self.origin_selected = False
        self.sequence = []
        self.locked = 0
        self.activation_requested = False
        self.activation_at = None
        self.activation_sound_pending = False
        self.state = 'idle'
        self.message = f'SELECT {self.symbol_count - 1} DISTINCT GLYPHS'
        self.destination = 'MANUAL ADDRESS'
        self.started = 0.0
        self.connected_at = 0.0

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
        if not allowed or self.origin_selected:
            return False
        if glyph == 0:
            if len(self.selected) != self.symbol_count - 1:
                return False
            self.origin_selected = True
        elif glyph in range(1, 39) and glyph not in self.selected and len(self.selected) < self.symbol_count - 1:
            self.selected.append(glyph)
            self.destination = 'MANUAL ADDRESS'
        else:
            return False
        if self.behavior == 'dhd':
            self.sequence.append(glyph)
            if self.state in ('idle', 'dhd_wait'):
                # Rebase the timeline to resume at the next unencoded symbol.
                self.started = now - self.cycle_elapsed(self.locked)
                self.state = 'dialing'
            self.message = 'DHD / ENCODING SELECTED GLYPHS'
        return True

    # Clear address and activation state while retaining selected mode preferences.
    def reset(self, message=None):
        self.dial_id += 1
        self.selected = []
        self.origin_selected = False
        self.sequence = []
        self.locked = 0
        self.activation_requested = False
        self.activation_at = None
        self.activation_sound_pending = False
        self.state = 'idle'
        self.destination = 'MANUAL ADDRESS'
        self.message = message or f'SELECT {self.symbol_count - 1} DISTINCT GLYPHS'

    # Begin the complete-address dialing sequence in computer mode.
    def start(self, now):
        if self.behavior == 'dhd' or self.state != 'idle' or len(self.selected) != self.symbol_count - 1 or len(set(self.selected)) != self.symbol_count - 1 or any(g not in range(1, 39) for g in self.selected):
            return False
        self.origin_selected = True
        self.sequence = self.selected[:] + [0]
        self.locked = 0
        self.activation_requested = False
        self.activation_at = None
        self.activation_sound_pending = False
        self.dial_id += 1
        self.started = now
        self.state = 'dialing'
        self.message = 'DIALING SEQUENCE INITIATED'
        return True

    # Keep animation and audio on the same floating-point-safe cycle boundary.
    def cycle_durations(self):
        if self.rotation_rpm is None:
            return [self.lock_seconds] * len(self.sequence)
        return [spin + 2.8 for _, spin in rotation_steps(
            self.sequence, self.rotation_origin(), self.rotation_rpm)]

    def cycle_elapsed(self, count):
        return sum(self.cycle_durations()[:count])

    def spin_fraction(self, now):
        if self.rotation_rpm is None or not self.sequence:
            return 8 / 10.8
        index = min(self.dialing_position(now)[0], len(self.sequence) - 1)
        duration = self.cycle_durations()[index]
        return (duration - 2.8) / duration

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
            if self.behavior == 'dhd':
                self.locked = min(len(self.sequence), max(0, self.dialing_position(now)[0]))
                if self.locked == len(self.sequence):
                    self.state = 'ready' if self.locked == self.symbol_count else 'dhd_wait'
                    self.message = 'ADDRESS ENCODED / PRESS DIAL TO ACTIVATE' if self.state == 'ready' else 'DHD / SELECT NEXT GLYPH'
                    if self.state == 'ready' and self.activation_requested:
                        self.begin_activation(now)
                else:
                    self.message = f'ENCODING GLYPH {self.locked+1} / {self.symbol_count}'
                return
            self.locked = max(0, min(self.symbol_count, self.dialing_position(now)[0]))
            self.message = f'CHEVRON {min(self.locked + 1, 7)} / 7 — ACQUIRING'
            if self.locked == self.symbol_count:
                self.resolve_connection(now)
        elif self.state == 'activating' and now >= self.activation_at:
            self.resolve_connection(now)
        elif self.state == 'connected' and now - self.connected_at >= self.connection_seconds:
            self.reset('CONNECTION LIMIT REACHED / DISENGAGED')

    # Accept a DHD activation request once every address symbol has been selected.
    def activate(self, now):
        if (self.behavior != 'dhd' or self.state not in ('dialing', 'ready')
                or len(self.sequence) != self.symbol_count or not self.origin_selected
                or self.activation_requested):
            return False
        self.activation_requested = True
        if self.state == 'ready':
            self.begin_activation(now)
        else:
            self.message = 'ACTIVATION QUEUED / WAITING FOR FINAL LOCK'
        return True

    # Schedule the post-lock activation pause and one pending button sound.
    def begin_activation(self, now):
        self.state = 'activating'
        self.activation_at = now + .8
        self.activation_sound_pending = True
        self.message = 'ALL SYMBOLS LOCKED / ACTIVATING WORMHOLE'

    # Consume the one-shot notification used by the UI audio layer.
    def consume_activation_sound(self):
        pending = self.activation_sound_pending
        self.activation_sound_pending = False
        return pending

    # Check address order and eligibility before connecting or reporting failure.
    def resolve_connection(self, now):
        match = next(((name, data) for name, data in address_database.items() if data['Address'] == self.selected), None)
        if match:
            self.destination = match[0].upper()
        if match and match[1]['Active'] and not match[1]['Locked']:
            self.state = 'connected'
            self.connected_at = now
            self.message = 'WORMHOLE ESTABLISHED / EARTH ORIGIN'
        else:
            self.state = 'failed'
            self.message = 'DESTINATION RESTRICTED' if match and match[1]['Locked'] else 'DESTINATION UNAVAILABLE' if match else 'INVALID ADDRESS / NO CONNECTION'

    # Return the nonnegative remaining connected duration.
    def remaining(self, now):
        return max(0, self.connection_seconds - (now - self.connected_at))

    # Reset the logical gate; the UI owns the visible shutdown animations.
    def shutdown(self):
        self.reset('STARGATE DISENGAGED')
