"""Explicit mutable state shared by the controller and its views."""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygame import Surface


@dataclass
class GateVisualState:
    ring_return: tuple[float, float, float, float] | None = None
    rest_rotation: float = 0.0
    ring_stop_target: float = 0.0
    last_ring_rotation: float = 0.0
    telemetry_running: bool = False
    telemetry_started: float = 0.0
    telemetry_stopped: float | None = None
    status_key: tuple[str, tuple[int, int, int]] | None = None
    status_blend: 'Surface | None' = None
    status_fade_source: 'Surface | None' = None
    status_fade_started: float = 0.0
    horizon_closing: tuple[float, float] | None = None
    last_connected_sequence: tuple[int, ...] = ()
    closing_glyphs: tuple[int | None, ...] = ()
    last_connected_offworld: object | None = None
    closing_offworld: object | None = None
    slot_fade_started: float | None = None
    horizon_opening: tuple[float, float] | None = None

    @property
    def busy(self):
        return (self.ring_return is not None or self.horizon_closing is not None
                or self.slot_fade_started is not None)


@dataclass
class UISettings:
    uniform_glyph_sizing: bool = True
    glyph_sound_mode: str = 'classic'
    offworld_enabled: bool = False


@dataclass
class CommandInput:
    text: str = ''
    focused: bool = False
