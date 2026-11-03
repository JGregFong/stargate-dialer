"""Bounded read-ahead video playback with separately warmed transition decoders."""
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from threading import Event, Lock, Thread
import math

import pygame


SUPPLIED_VIDEO = Path(__file__).resolve().parent / 'media' / 'videos' / (
    '38 Minutes of Stargate Rear-Projection Puddle Effect (2160p_24fps_VP9-128kbit_AAC).mkv')


@dataclass
class VideoSettings:
    path: str = ''
    enabled: bool = False
    opening: float = 2.0
    closing: float = 2313.0


def parse_timestamp(text):
    parts = text.strip().split(':')
    if not 1 <= len(parts) <= 3 or any(not part for part in parts):
        raise ValueError('Use seconds, MM:SS, or HH:MM:SS.')
    values = [float(part) for part in parts]
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('Timestamps must be nonnegative finite numbers.')
    if len(values) > 1 and any(value >= 60 for value in values[1:]):
        raise ValueError('Seconds and minutes after a colon must be below 60.')
    total = 0.0
    for value in values:
        total = total * 60 + value
    return total


def format_timestamp(seconds):
    minutes, seconds = divmod(seconds, 60)
    return f'{int(minutes):02}:{seconds:06.3f}'


def probe_video(path):
    import av
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError('The selected file has no video stream.')
        stream = container.streams.video[0]
        duration = (float(stream.duration * stream.time_base) if stream.duration
                    else (container.duration or 0) / av.time_base)
        if duration <= 0:
            raise ValueError('Unable to determine the video duration.')
        return duration


def validate_video(settings, duration):
    if not (0 <= settings.opening < settings.closing < duration):
        raise ValueError('Use 0 <= opening < closing < video duration.')


def playback_time(settings, elapsed, duration, closing_elapsed=None):
    """Loop only the steady section if the connection outlasts the active footage."""
    if closing_elapsed is not None:
        return min(duration - .001, settings.closing + max(0, closing_elapsed))
    target = settings.opening + max(0, elapsed)
    if target >= settings.closing:
        loop_start = min(settings.opening + 5, settings.closing - .1)
        target = loop_start + (target - settings.closing) % (settings.closing - loop_start)
    return target


class VideoDecoder:
    """Small read-ahead buffer; ordinary playback never repeatedly seeks keyframes."""
    LOOKAHEAD = .65
    MAX_FRAMES = 48

    def __init__(self):
        self.lock, self.wake = Lock(), Event()
        self.stopped = Event()
        self.requested = None
        self.result = None
        self.frames = []
        self.buffer_key = None
        self.info = {}
        self.errors = {}
        self.thread = None

    def request(self, path, seconds, diameter):
        with self.lock:
            self.requested = (path, seconds, diameter)
            if self.thread is None or not self.thread.is_alive():
                self.stopped.clear()
                self.thread = Thread(target=self._run, daemon=True, name='horizon-video')
                self.thread.start()
            result = None
            if self.buffer_key == (path, diameter) and self.frames:
                pts, data = min(self.frames, key=lambda item: abs(item[0] - seconds))
                if abs(pts - seconds) <= .25:
                    result = data
        self.wake.set()
        return result

    @staticmethod
    def _pixels(frame, diameter):
        scale = diameter / min(frame.width, frame.height)
        width = max(diameter, round(frame.width * scale))
        height = max(diameter, round(frame.height * scale))
        rgb = frame.reformat(width=width, height=height, format='rgba')
        plane = rgb.planes[0]
        raw, pitch = bytes(plane), plane.line_size
        x, y = (width-diameter)//2, (height-diameter)//2
        return b''.join(raw[(y+row)*pitch+x*4:(y+row)*pitch+(x+diameter)*4]
                        for row in range(diameter))

    def _run(self):
        try:
            import av
        except ImportError as error:
            with self.lock:
                self.errors[self.requested[0]] = f'Video decoding unavailable: {error}'
            return
        container, iterator = None, None
        current_path, current_size, last_time = None, None, -1.0
        while not self.stopped.is_set():
            if not self.wake.wait(3):
                if container is not None:
                    container.close()
                    container, iterator = None, None
                continue
            self.wake.clear()
            if self.stopped.is_set():
                break
            with self.lock:
                path, target, diameter = self.requested
                frames = self.frames[:] if self.buffer_key == (path, diameter) else []
            # Already buffered: no decode, conversion, or keyframe seek is needed.
            if frames and frames[0][0] - .05 <= target and frames[-1][0] >= target + self.LOOKAHEAD:
                continue
            try:
                if container is None or path != current_path:
                    if container is not None:
                        container.close()
                    container = av.open(path)
                    stream = container.streams.video[0]
                    stream.codec_context.thread_count = 2
                    stream.codec_context.thread_type = 'AUTO'
                    duration = (float(stream.duration * stream.time_base) if stream.duration
                                else (container.duration or 0) / av.time_base)
                    with self.lock:
                        self.info[path] = duration
                    current_path, iterator, last_time = path, None, -1.0
                needs_seek = (iterator is None or diameter != current_size
                              or (frames and target < frames[0][0] - .1)
                              or target - last_time > 5)
                if needs_seek:
                    container.seek(int(target / float(stream.time_base)), stream=stream)
                    iterator = container.decode(stream)
                    last_time, current_size = -1.0, diameter
                    with self.lock:
                        self.frames, self.buffer_key = [], (path, diameter)
                if last_time >= target + self.LOOKAHEAD:
                    continue
                found = False
                for frame in iterator:
                    if self.stopped.is_set():
                        break
                    last_time = frame.time or 0.0
                    if last_time < target - .1:
                        continue
                    data = self._pixels(frame, diameter)
                    with self.lock:
                        self.frames.append((last_time, data))
                        self.frames = self.frames[-self.MAX_FRAMES:]
                        self.result = (path, diameter, data)
                        self.errors.pop(path, None)
                        newest = self.requested
                    found = True
                    # Prioritize a new seek/file rather than completing obsolete work.
                    if newest[0] != path or newest[2] != diameter or abs(newest[1] - target) > 2:
                        break
                    if last_time >= target + self.LOOKAHEAD:
                        break
                if not found and target - last_time > .25:
                    raise ValueError('No frame available at the requested timestamp.')
            except Exception as error:
                with self.lock:
                    self.errors[path] = str(error)
                if container is not None:
                    container.close()
                container, iterator = None, None
        if container is not None:
            container.close()

    def close(self):
        self.stopped.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(timeout=2)


@lru_cache(maxsize=2)
def video_decoder(channel='active'):
    return VideoDecoder()


class HorizonVideo:
    def __init__(self, settings, decoder=None):
        self.settings = settings
        self.decoder = decoder or video_decoder()
        self.closing_decoder = decoder or video_decoder('closing')
        self.session = None
        self.active = None
        self.masks = {}
        self.last_frames = {}

    def prepare(self, radius):
        """Warm both transition buffers while the gate is still dialing."""
        config = self.settings
        if config.enabled:
            diameter = radius * 2 + 1
            self.decoder.request(config.path, config.opening, diameter)
            self.closing_decoder.request(config.path, config.closing, diameter)

    def close(self):
        self.decoder.close()
        if self.closing_decoder is not self.decoder:
            self.closing_decoder.close()

    def frame(self, dialer, visual, now, radius):
        key = (dialer.dial_id, dialer.connection.connected_at)
        if dialer.state == 'connected' and key != self.session:
            self.session, self.active = key, replace(self.settings)
            self.last_frames.clear()
        config = self.active
        if config is None or not config.enabled:
            return None
        with self.decoder.lock:
            duration = self.decoder.info.get(config.path)
            error = self.decoder.errors.get(config.path)
        if error:
            return None
        duration = duration or max(config.closing + 1, config.opening + 1)
        try:
            validate_video(config, duration)
        except ValueError:
            return None
        closing = now - visual.horizon_closing[0] if visual.horizon_closing else None
        target = playback_time(config, dialer.connection.elapsed(now), duration, closing)
        diameter = radius * 2 + 1
        decoder = self.closing_decoder if closing is not None else self.decoder
        if closing is None:
            self.closing_decoder.request(config.path, config.closing, diameter)
        data = decoder.request(config.path, target, diameter)
        if data is None:
            # Decoder handoffs and read-ahead misses must not flash black between
            # valid frames. Keep the last displayed image for this gate size.
            if radius in self.last_frames:
                return self.last_frames[radius].copy()
            if self.last_frames:
                # Travel changes the gate diameter without changing the connection.
                # Hold its current footage at the arrival size while decoding resizes.
                previous = next(reversed(self.last_frames.values()))
                image = pygame.transform.smoothscale(previous, (diameter, diameter))
            else:
                image = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
                image.fill((0, 0, 0, 255))
        else:
            image = pygame.image.frombuffer(data, (diameter, diameter), 'RGBA').copy()
        if radius not in self.masks:
            mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (radius, radius), radius)
            self.masks[radius] = mask
        image.blit(self.masks[radius], (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if data is not None:
            self.last_frames[radius] = image.copy()
        return image

    def close_duration(self):
        if self.active is not None and self.active.enabled:
            with self.decoder.lock:
                duration = self.decoder.info.get(self.active.path)
                error = self.decoder.errors.get(self.active.path)
            if duration and not error:
                return max(.1, duration - self.active.closing)
        return None
