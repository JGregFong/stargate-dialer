"""Cached, aspect-preserving playback of the bundled SGC logo."""
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path

import pygame


LOGO_PATH = Path(__file__).resolve().parent / 'media' / 'images' / 'SGC_Spinning_Logo_Large.gif'


@lru_cache(maxsize=4)
def load_frames(path, bounds):
    frames, deadlines = [], []
    elapsed = 0.0
    for frame, milliseconds in pygame.image.load_animation(str(path)):
        scale = min(bounds[0] / frame.get_width(), bounds[1] / frame.get_height())
        size = (max(1, round(frame.get_width() * scale)),
                max(1, round(frame.get_height() * scale)))
        frames.append(pygame.transform.smoothscale(frame, size))
        elapsed += max(milliseconds, 10) / 1000
        deadlines.append(elapsed)
    return tuple(frames), tuple(deadlines)


class AnimatedLogo:
    def __init__(self, rect, path=LOGO_PATH):
        self.rect = pygame.Rect(rect)
        self.frames, self.deadlines = load_frames(path, self.rect.size)

    def frame_at(self, now):
        index = bisect_right(self.deadlines, max(0.0, now) % self.deadlines[-1])
        return self.frames[index]

    def draw(self, surface, now):
        frame = self.frame_at(now)
        surface.blit(frame, frame.get_rect(center=self.rect.center))
