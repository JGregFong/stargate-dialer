"""Connection lifetime measured from successful establishment."""
from dataclasses import dataclass, field
import random

TRAVEL_CLOSE_SECONDS = 1.5


@dataclass
class Connection:
    duration: float = 38 * 60
    connected_at: float = 0.0
    origin: str | None = None
    destination: str | None = None
    arrival_close_at: float | None = None
    travel_unlock_at: float = 0.0
    travel_locked: bool = False
    randomize_duration: bool = False
    extra_seconds: int = field(default=0, init=False)

    def connect(self, now):
        self.connected_at = now
        self.arrival_close_at = None
        self.travel_unlock_at = 0.0
        self.travel_locked = False
        self.extra_seconds = random.randint(5, 45) if self.randomize_duration else 0

    @property
    def active_duration(self):
        return self.duration + self.extra_seconds

    def elapsed(self, now):
        return max(0.0, now - self.connected_at)

    def remaining(self, now):
        return max(0, self.active_duration - self.elapsed(now))

    def expired(self, now):
        return self.elapsed(now) >= self.active_duration
