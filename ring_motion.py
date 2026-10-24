"""Shared rotation configuration and motion math for both dialing behaviors."""
import math

DEFAULT_ROTATION_RPM = 5.0
ROTATION_RAMP_SECONDS = 1.5
ENCODING_SECONDS = 2.8


def validate_rpm(rpm):
    rpm = float(rpm)
    if not math.isfinite(rpm) or rpm <= 0:
        raise ValueError('RPM must be a positive finite number')
    return rpm


def rotation_ramp(distance, rpm):
    # Short, fast moves may not have room for two full 1.5-second ramps.
    return min(ROTATION_RAMP_SECONDS, distance / (rpm * 6))


def rotation_steps(sequence, initial_rotation=0.0, rpm=DEFAULT_ROTATION_RPM):
    """Return signed travel and spin duration for each alternating symbol stop."""
    rpm = validate_rpm(rpm)
    rotation = initial_rotation
    for index, glyph in enumerate(sequence):
        direction = 1 if index % 2 == 0 else -1
        distance = ((-glyph * 360 / 39 - rotation) * direction) % 360
        if distance < 180:
            distance += 360
        delta = direction * distance
        # Each smooth speed ramp covers half the distance of full-speed travel.
        yield delta, distance / (rpm * 6) + rotation_ramp(distance, rpm)
        rotation += delta


# Ease into and out of the configured RPM, pausing at each centered symbol.
def ring_rotation(sequence, elapsed, lock_seconds, velocity=False, initial_rotation=0.0, rpm=DEFAULT_ROTATION_RPM):
    rpm = validate_rpm(rpm)
    rotation = initial_rotation
    elapsed = max(0.0, elapsed)
    for delta, spin_seconds in rotation_steps(sequence, initial_rotation, rpm=rpm):
        if elapsed < spin_seconds:
            speed = math.copysign(rpm * 6, delta)
            ramp = rotation_ramp(abs(delta), rpm)
            if elapsed < ramp:
                t = elapsed / ramp
                current_speed = speed * t * t * (3 - 2 * t)
                travel = speed * ramp * (t ** 3 - .5 * t ** 4)
            elif elapsed > spin_seconds - ramp:
                t = (spin_seconds - elapsed) / ramp
                current_speed = speed * t * t * (3 - 2 * t)
                travel = delta - speed * ramp * (t ** 3 - .5 * t ** 4)
            else:
                current_speed = speed
                travel = speed * (elapsed - ramp / 2)
            return current_speed if velocity else rotation + travel
        rotation += delta
        elapsed -= spin_seconds
        if elapsed < ENCODING_SECONDS:
            return 0.0 if velocity else rotation
        elapsed -= ENCODING_SECONDS
    return 0.0 if velocity else rotation
