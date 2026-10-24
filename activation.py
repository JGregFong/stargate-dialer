"""Queued activation, post-lock delay, and one-shot audio notification."""
from dataclasses import dataclass


@dataclass
class Activation:
    requested: bool = False
    deadline: float | None = None
    sound_pending: bool = False

    def reset(self):
        self.requested = False
        self.deadline = None
        self.sound_pending = False

    def request(self, behavior, state, sequence, symbol_count, origin_selected):
        if (behavior != 'dhd' or state not in ('dialing', 'ready')
                or len(sequence) != symbol_count or not origin_selected or self.requested):
            return False
        self.requested = True
        return True

    def begin(self, now):
        self.deadline = now + .8
        self.sound_pending = True

    def due(self, now):
        return self.deadline is not None and now >= self.deadline

    def consume_sound(self):
        pending = self.sound_pending
        self.sound_pending = False
        return pending
