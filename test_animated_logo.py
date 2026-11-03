"""Logo playback retains GIF timing and fits its reserved space."""
import unittest
from unittest.mock import patch

import pygame

from animated_logo import AnimatedLogo, load_frames


class AnimatedLogoTests(unittest.TestCase):
    def test_original_proportions_and_loop(self):
        logo = AnimatedLogo((35, 22, 182, 60))
        self.assertEqual(len(logo.frames), 96)
        self.assertEqual(logo.frames[0].get_size(), (60, 60))
        self.assertIs(logo.frame_at(0), logo.frames[0])
        self.assertIs(logo.frame_at(.041), logo.frames[1])
        self.assertIs(logo.frame_at(logo.deadlines[-1]), logo.frames[0])
        self.assertEqual(logo.rect.bottom, 82)  # Options begins at y=86.

    def test_non_square_animation_is_not_stretched(self):
        load_frames.cache_clear()
        with patch('pygame.image.load_animation', return_value=[
                (pygame.Surface((200, 100)), 100), (pygame.Surface((200, 100)), 200)]):
            logo = AnimatedLogo((0, 0, 80, 60), path='test-logo.gif')
        self.assertEqual(logo.frames[0].get_size(), (80, 40))
        self.assertIs(logo.frame_at(.15), logo.frames[1])
        load_frames.cache_clear()
