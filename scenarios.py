"""Deterministic incoming activation timing, independent of the UI."""
from dataclasses import dataclass

TYPES = ('unknown', 'hostile', 'friendlygdo', 'friendly_wo')
CHEVRON_SECONDS = 1.5
FORM_SECONDS = 1.2
WORMHOLE_SECONDS = 20.0

@dataclass
class OffworldActivation:
    kind: str
    started: float
    open_since: float | None = None
    hostile_present: bool = False

    @property
    def established_at(self):
        return self.started + 7 * CHEVRON_SECONDS + FORM_SECONDS

    def recognition(self, now):
        if self.kind != 'friendlygdo':
            return 0.0
        return max(0.0, min(1.0, (now - self.established_at - 3) / 5))

    def notification(self, now):
        if now < self.established_at:
            return 'OFFWORLD ACTIVATION'
        if self.kind == 'unknown':
            return 'Unknown'
        if self.kind == 'hostile':
            return 'Hostile Action Present' if self.hostile_present else 'HOSTILE OFFWORLD ACTIVATION'
        if self.kind == 'friendly_wo':
            return 'Ally has arrived'
        return 'GDO TRANSMISSION' if now >= self.established_at + 3 else 'FRIENDLY OFFWORLD ACTIVATION'
