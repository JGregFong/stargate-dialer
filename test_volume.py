"""Master volume affects live channels and follows scaled slider input."""
import unittest

import pygame

from main import Console


class VolumeTests(unittest.TestCase):
    def setUp(self):
        self.app = Console()

    def tearDown(self):
        pygame.quit()

    def test_volume_applies_to_all_channels_and_clamps(self):
        app = self.app
        for requested, expected in ((.4, .4), (-1, 0), (2, 1)):
            app.set_volume(requested)
            self.assertEqual(app.settings.volume, expected)
            for channel in [app.button_channel, *app.gate_audio.channels.values()]:
                self.assertAlmostEqual(channel.get_volume(), expected, delta=1/128)

    def test_slider_click_drag_clamp_and_release_in_scaled_viewport(self):
        app = self.app
        menu = app.options
        menu.viewport = lambda: pygame.Rect(50, 30, 640, 480)
        track = menu.volume_track

        def event(kind, x, **extra):
            menu.options_event(pygame.event.Event(
                kind, pos=(50 + x / 2, 30 + track.centery / 2), **extra))

        event(pygame.MOUSEBUTTONDOWN, track.centerx, button=1)
        self.assertAlmostEqual(app.settings.volume, .5)
        event(pygame.MOUSEMOTION, track.left - 100)
        self.assertEqual(app.settings.volume, 0)
        event(pygame.MOUSEMOTION, track.right + 100)
        self.assertEqual(app.settings.volume, 1)
        event(pygame.MOUSEBUTTONUP, track.right, button=1)
        event(pygame.MOUSEMOTION, track.left)
        self.assertEqual(app.settings.volume, 1)
        self.assertFalse(menu.volume_dragging)

    def test_escape_cancels_drag_and_no_audio_device_is_safe(self):
        app = self.app
        app.options.volume_dragging = True
        app.options.options_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertFalse(app.options.volume_dragging)
        app.button_channel = None
        app.gate_audio.channels = {}
        app.set_volume(0)
        self.assertEqual(app.settings.volume, 0)
