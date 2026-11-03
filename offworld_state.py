"""Offworld shutdown lifecycle, independent of Earth telemetry and slot fades."""
from dataclasses import dataclass
from gate_motion_state import GateMotionState
from ring_motion import DEFAULT_ROTATION_RPM, ROTATION_RAMP_SECONDS, ENCODING_SECONDS, TILE_ANGLE


@dataclass
class OffworldVisualState(GateMotionState):
    closing_slots: tuple[int, ...] = ()
    closing_dhd: tuple[int, ...] = ()
    closing_chevrons: int = 0
    fade_started: float | None = None
    fade_duration: float = 2.0
    fade_alpha: int = 0

    activation_unlock_at: float = 0.0
    activation_locked: bool = False

    spin_started: float | None = None
    spin_initial: float = 0.0
    spin_dial_id: int | None = None
    spin_finished: bool = False
    spin_stop: tuple[float, float, float] | None = None

    def spinning_position(self, dialer, now):
        speed = (dialer.rotation_rpm or DEFAULT_ROTATION_RPM)*6
        elapsed = max(0, now-self.spin_started)
        ramp = ROTATION_RAMP_SECONDS
        t = min(1, elapsed/ramp)
        travel = speed*ramp*(t**3-.5*t**4)
        travel += speed*max(0, elapsed-ramp)
        return self.spin_initial+travel, speed*t*t*(3-2*t)

    def velocity(self, dialer, now):
        if dialer.offworld_dialing_mode != 'spinning':
            return super().velocity(dialer, now)
        if self.spin_stop is not None:
            started, _, speed = self.spin_stop
            t = max(0, min(1, (now-started)/ROTATION_RAMP_SECONDS))
            return speed*(1-t*t*(3-2*t))
        if self.spin_started is not None:
            return self.spinning_position(dialer, now)[1]
        return 0.0

    def rotation(self, dialer, now):
        if self.ring_return is not None:
            return super().rotation(dialer, now)
        if dialer.offworld_dialing_mode == 'spinning':
            if self.spin_dial_id != dialer.dial_id:
                self.spin_dial_id = dialer.dial_id
                self.spin_started = self.spin_stop = None
                self.spin_finished = False
            if (not self.spin_finished and self.spin_started is None and self.spin_stop is None
                    and dialer.state in ('dialing', 'dhd_wait') and dialer.sequence):
                self.spin_started, self.spin_initial = dialer.started, self.rest_rotation
            if self.spin_started is not None:
                end = (dialer.started+dialer.cycle_elapsed(len(dialer.sequence))
                       if len(dialer.sequence) == dialer.symbol_count else None)
                if end is not None and now >= end:
                    position, speed = self.spinning_position(dialer, end)
                    self.spin_stop = (end, position, speed)
                    self.spin_started = None
                else:
                    self.rest_rotation = self.spinning_position(dialer, now)[0]
            if self.spin_stop is not None:
                started, position, speed = self.spin_stop
                t = max(0, min(1, (now-started)/ROTATION_RAMP_SECONDS))
                self.rest_rotation = position+speed*ROTATION_RAMP_SECONDS*(t-t**3+.5*t**4)
                if t >= 1:
                    self.spin_stop = None
                    self.spin_finished = True
            self.last_ring_rotation = self.rest_rotation
            return self.rest_rotation
        if not dialer.offworld_sgc_dialing:
            return self.rest_rotation
        encoding = self.rotary_encoding(dialer, now)
        if encoding is not None:
            # Hold the exact glyph center throughout clamp travel and light transfer.
            rotation = super().rotation(dialer, now)
            target = -dialer.sequence[encoding[0]]*TILE_ANGLE
            return target+round((rotation-target)/360)*360
        return super().rotation(dialer, now)

    def rotary_encoding(self, dialer, now):
        """Top clamp travel and light transfer within the existing encoding pause."""
        if (not dialer.offworld_sgc_dialing or dialer.state != 'dialing'
                or self.ring_return is not None or not dialer.sequence):
            return None
        index, phase = dialer.dialing_position(now)
        if index >= len(dialer.sequence):
            return None
        duration = dialer.cycle_durations()[index]
        elapsed = phase*duration-(duration-ENCODING_SECONDS)
        if elapsed < 0:
            return None

        def ease(start, duration):
            t = max(0, min(1, (elapsed-start)/duration))
            return t*t*(3-2*t)

        slide = 8*ease(0, .45)*(1-ease(1.1, .5))
        top_light = ease(.45, .25)*(1-ease(1.8, 1.0))
        assigned_light = ease(1.6, .2)
        return index, slide, top_light, assigned_light

    def clear_fade(self):
        self.closing_slots = self.closing_dhd = ()
        self.fade_started = None
        self.fade_alpha = 0

    def begin_fade(self, slots, dhd, now, *, delay=.2):
        self.closing_slots, self.closing_dhd = tuple(slots), tuple(dhd)
        self.fade_started, self.fade_alpha = now+delay, 255

    def begin_shutdown(self, dialer, now):
        connected = dialer.state == 'connected'
        if connected:
            self.last_connected_sequence = tuple(dialer.sequence)
        if dialer.offworld_sgc_dialing and dialer.state in ('dialing', 'dhd_wait', 'ready', 'activating'):
            self.begin_braking(dialer, now, lookahead=.15, max_duration=.8)
        elif dialer.offworld_dialing_mode == 'spinning':
            self.rotation(dialer, now)
            if self.velocity(dialer, now) > 1e-6:
                self.begin_braking(dialer, now)
            self.spin_started = self.spin_stop = None
        else:
            self.ring_return = None
        if dialer.sequence:
            braking = self.ring_return[2] if self.ring_return else 0
            self.begin_fade(dialer.sequence[:dialer.locked], dialer.sequence, now, delay=braking+.2)
        return connected

    def begin_close(self, now, duration):
        self.closing_chevrons = len(self.last_connected_sequence)
        self.rest_rotation = self.last_ring_rotation
        self.horizon_opening = None
        self.horizon_closing = (now, duration)
        self.begin_fade(self.last_connected_sequence, self.last_connected_sequence, now, delay=duration+.2)

    def finish_horizon_close(self, started, duration):
        self.horizon_closing = None
        self.closing_chevrons = 0

    def update(self, now):
        self.activation_locked = now < self.activation_unlock_at
        # Completion does not depend on whether the gate or keyboard was drawn.
        if self.horizon_closing is not None:
            started, duration = self.horizon_closing
            if now >= started+duration:
                self.finish_horizon_close(started, duration)
        if self.fade_started is not None:
            t = max(0, min(1, (now-self.fade_started)/self.fade_duration))
            self.fade_alpha = round(255*(1-t*t*(3-2*t)))
            if t >= 1:
                self.clear_fade()
