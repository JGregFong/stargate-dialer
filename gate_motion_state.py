"""Presentation-independent ring and horizon state shared by gate views."""
from dataclasses import dataclass
import math
from ring_motion import ring_rotation, TILE_ANGLE


@dataclass
class GateMotionState:
    ring_return: tuple[float, float, float, float] | None = None
    rest_rotation: float = 0.0
    ring_stop_target: float = 0.0
    last_ring_rotation: float = 0.0
    horizon_closing: tuple[float, float] | None = None
    horizon_opening: tuple[float, float] | None = None
    last_connected_sequence: tuple[int, ...] = ()
    incoming: bool = False
    chevron_fade_count: int = 0
    chevron_fade_started: float = 0.0
    chevron_fade_duration: float = .9

    def fade_chevrons(self, count, now, *, duration=.9):
        if count:
            self.chevron_fade_count = count
            self.chevron_fade_started = now
            self.chevron_fade_duration = duration

    def chevron_light(self, index, locked, now):
        if index < locked:
            return 1.0
        if index >= self.chevron_fade_count:
            return 0.0
        t = max(0.0, min(1.0, (now-self.chevron_fade_started)/self.chevron_fade_duration))
        return 1-t*t*(3-2*t)


    def show_address(self, dialer):
        """Incoming connections have no locally entered address to display."""
        return not self.incoming or (dialer.state != 'connected' and bool(dialer.selected or dialer.sequence))

    @property
    def busy(self):
        return self.ring_return is not None or self.horizon_closing is not None

    def finish_horizon_close(self, started, duration):
        self.horizon_closing = None

    def rotation(self, dialer, now):
        if self.ring_return is not None:
            started, initial, duration, speed = self.ring_return
            t = min(1.0, max(0.0, (now-started)/duration))
            ease = t**3*(10-15*t+6*t*t)
            if speed:
                travel = initial+speed*duration*(t-t**3+.5*t**4)
                travel += (-initial-speed*duration/2)*ease
            else:
                travel = initial*(1-ease)
            rotation = travel+self.ring_stop_target
            if t >= 1:
                self.ring_return = None
                self.rest_rotation = self.ring_stop_target
            return rotation
        elapsed = now-dialer.started if dialer.state == 'dialing' else dialer.cycle_elapsed(len(dialer.sequence))
        return ring_rotation(dialer.sequence, elapsed, dialer.lock_seconds,
                             initial_rotation=self.rest_rotation, rpm=dialer.rotation_rpm)

    def velocity(self, dialer, now):
        return ring_rotation(dialer.sequence, now-dialer.started, dialer.lock_seconds,
                              velocity=True, initial_rotation=self.rest_rotation,
                              rpm=dialer.rotation_rpm) if dialer.state == 'dialing' else 0.0

    def begin_braking(self, dialer, now, *, lookahead=.75, max_duration=2.5):
        rotation = self.rotation(dialer, now)
        speed = self.velocity(dialer, now)
        if abs(speed) > 1e-6:
            projected = rotation+speed*lookahead
            tile = math.ceil(projected/TILE_ANGLE) if speed > 0 else math.floor(projected/TILE_ANGLE)
            self.ring_stop_target = tile*TILE_ANGLE
            initial = rotation-self.ring_stop_target
            duration = min(max_duration, 2*abs(initial/speed))
        else:
            self.ring_stop_target = round(rotation/TILE_ANGLE)*TILE_ANGLE
            initial, speed, duration = rotation-self.ring_stop_target, 0.0, .3
        self.ring_return = (now, initial, duration, speed)
