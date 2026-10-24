"""Connection lifetime measured from successful establishment."""
from dataclasses import dataclass


@dataclass
class Connection:
    duration: float = 38 * 60
    connected_at: float = 0.0

    def connect(self, now):
        self.connected_at = now

    def remaining(self, now):
        return max(0, self.duration - (now - self.connected_at))

    def expired(self, now):
        return now - self.connected_at >= self.duration
