"""Address entry rules and destination eligibility, independent of dialing time."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AddressResult:
    destination: str | None
    available: bool
    message: str


class AddressValidator:
    def __init__(self, destinations):
        self.destinations = destinations

    @staticmethod
    def can_select(glyph, selected, symbol_count, origin_selected):
        if origin_selected:
            return False
        if glyph == 0:
            return len(selected) == symbol_count - 1
        return (glyph in range(1, 39) and glyph not in selected
                and len(selected) < symbol_count - 1)

    @staticmethod
    def complete(selected, symbol_count):
        return (len(selected) == symbol_count - 1
                and len(set(selected)) == symbol_count - 1
                and all(glyph in range(1, 39) for glyph in selected))

    def resolve(self, selected):
        match = next(((name, data) for name, data in self.destinations.items()
                      if data['Address'] == selected), None)
        if match is None:
            return AddressResult(None, False, 'INVALID ADDRESS / NO CONNECTION')
        name, data = match
        if data['Locked']:
            return AddressResult(name, False, 'DESTINATION RESTRICTED')
        if not data['Active']:
            return AddressResult(name, False, 'DESTINATION UNAVAILABLE')
        return AddressResult(name, True, 'WORMHOLE ESTABLISHED / EARTH ORIGIN')
