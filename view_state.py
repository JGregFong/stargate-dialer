"""Explicit mutable state shared by the controller and its views."""
from dataclasses import dataclass, field
from horizon_video import VideoSettings, HorizonVideo
from gate_motion_state import GateMotionState
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygame import Surface


@dataclass
class GateVisualState(GateMotionState):
    """Earth console animation state: telemetry, status blending and slot cascade."""
    telemetry_running: bool = False
    telemetry_started: float = 0.0
    telemetry_stopped: float | None = None
    status_key: tuple[str, tuple[int, int, int]] | None = None
    status_blend: 'Surface | None' = None
    status_fade_source: 'Surface | None' = None
    status_fade_started: float = 0.0
    closing_glyphs: tuple[int, ...] = ()
    slot_fade_started: float | None = None

    @property
    def busy(self):
        return super().busy or self.slot_fade_started is not None

    def finish_horizon_close(self, started, duration):
        self.horizon_closing = None
        self.slot_fade_started = started+duration

    def update(self, now):
        if self.horizon_closing is not None:
            started, duration = self.horizon_closing
            if now >= started+duration:
                self.finish_horizon_close(started, duration)
        if self.slot_fade_started is not None and now >= self.slot_fade_started+len(self.closing_glyphs)*.35:
            self.closing_glyphs = ()
            self.slot_fade_started = None


@dataclass
class UISettings:
    horizon_video: VideoSettings = field(default_factory=VideoSettings)
    video_player: HorizonVideo = field(init=False, repr=False)

    def __post_init__(self):
        self.video_player = HorizonVideo(self.horizon_video)
    uniform_glyph_sizing: bool = True
    glyph_sound_mode: str = 'classic'
    volume: float = 1.0


@dataclass
class CommandInput:
    text: str = ''
    focused: bool = False
