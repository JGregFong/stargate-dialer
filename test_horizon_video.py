"""Video timestamp validation, bounded decoding, circular masking, and settings."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import av
import pygame

from horizon_video import (VideoSettings, VideoDecoder, HorizonVideo, parse_timestamp,
                           validate_video, playback_time, probe_video)
from drawing_context import DrawingContext
from video_options import VideoOptions


class VideoTimingTests(unittest.TestCase):
    def test_travel_resize_holds_same_connection_frame_in_both_directions(self):
        for departure, arrival in ((5, 7), (7, 5)):
            with self.subTest(departure=departure, arrival=arrival):
                decoder = SimpleNamespace(lock=Lock(), info={'sample': 10}, errors={},
                                          request=Mock(return_value=bytes((20, 80, 200, 255))
                                                       *(departure*2+1)**2))
                player = HorizonVideo(VideoSettings(path='sample', enabled=True,
                                                     opening=1, closing=8), decoder)
                player.closing_decoder = SimpleNamespace(request=Mock())
                dialer = SimpleNamespace(state='connected', dial_id=1,
                                          connection=SimpleNamespace(connected_at=100,
                                                                     elapsed=lambda t:t-100))
                visual = SimpleNamespace(horizon_closing=None)
                player.frame(dialer, visual, 102, departure)
                session = player.session
                decoder.request.return_value = None
                held = player.frame(dialer, visual, 102.1, arrival)
                self.assertEqual(held.get_size(), (arrival*2+1, arrival*2+1))
                for actual, expected in zip(held.get_at((arrival, arrival)), (20, 80, 200, 255)):
                    self.assertAlmostEqual(actual, expected, delta=2)
                self.assertEqual(held.get_at((0, 0)).a, 0)
                self.assertEqual(player.session, session)
                path, target, diameter = decoder.request.call_args.args
                self.assertEqual((path, diameter), ('sample', arrival*2+1))
                self.assertAlmostEqual(target, 3.1)
                decoder.request.return_value = bytes((30, 90, 210, 255))*(arrival*2+1)**2
                resumed = player.frame(dialer, visual, 102.2, arrival)
                self.assertEqual(resumed.get_at((arrival, arrival)), (30, 90, 210, 255))

    def test_buffered_playback_does_not_repeat_keyframe_seeks(self):
        from fractions import Fraction
        context = SimpleNamespace(thread_count=0, thread_type='')
        stream = SimpleNamespace(codec_context=context, time_base=Fraction(1, 10),
                                 duration=100, average_rate=10)
        frames = []
        for index in range(100):
            frame = av.VideoFrame(32, 32, 'rgb24')
            frame.pts, frame.time_base = index, Fraction(1, 10)
            frame.planes[0].update(bytes(frame.planes[0].buffer_size))
            frames.append(frame)
        container = SimpleNamespace(streams=SimpleNamespace(video=[stream]),
                                    seek=Mock(), decode=lambda _: iter(frames), close=Mock())
        decoder = VideoDecoder()
        try:
            with patch('av.open', return_value=container):
                decoder.request('buffer-test', .2, 31)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    with decoder.lock:
                        ready = bool(decoder.frames and decoder.frames[-1][0] >= .85)
                    if ready:
                        break
                    time.sleep(.01)
                self.assertTrue(ready)
                for target in (.21, .24, .27, .3, .35, .4):
                    self.assertIsNotNone(decoder.request('buffer-test', target, 31))
                    time.sleep(.01)
                self.assertEqual(container.seek.call_count, 1)
                with decoder.lock:
                    self.assertLessEqual(len(decoder.frames), decoder.MAX_FRAMES)
        finally:
            decoder.close()

    def test_closing_uses_prepared_decoder_instead_of_seeking_active_video(self):
        active = SimpleNamespace(lock=Lock(), info={'sample': 10}, errors={},
                                 request=Mock(return_value=bytes((0, 0, 255, 255))*121))
        closing = SimpleNamespace(request=Mock(return_value=bytes((0, 0, 255, 255))*121))
        player = HorizonVideo(VideoSettings(path='sample', enabled=True, opening=1, closing=8), active)
        player.closing_decoder = closing
        dialer = SimpleNamespace(state='connected', dial_id=1,
                                  connection=SimpleNamespace(connected_at=100, elapsed=lambda t:t-100))
        visual = SimpleNamespace(horizon_closing=None)
        player.frame(dialer, visual, 101, 5)
        closing.request.assert_called_once_with('sample', 8, 11)
        active.request.reset_mock()
        dialer.state = 'idle'
        visual.horizon_closing = (102, 2)
        player.frame(dialer, visual, 102.2, 5)
        active.request.assert_not_called()
        self.assertAlmostEqual(closing.request.call_args.args[1], 8.2)

    def test_closing_buffer_misses_hold_last_frame_for_both_gate_sizes(self):
        for radius in (5, 7):
            with self.subTest(radius=radius):
                pixels = (radius*2+1)**2
                active = SimpleNamespace(lock=Lock(), info={'sample': 10}, errors={},
                                         request=Mock(return_value=bytes((20, 80, 200, 255))*pixels))
                closing = SimpleNamespace(request=Mock(return_value=None))
                player = HorizonVideo(VideoSettings(path='sample', enabled=True,
                                                     opening=1, closing=8), active)
                player.closing_decoder = closing
                dialer = SimpleNamespace(state='connected', dial_id=1,
                                          connection=SimpleNamespace(connected_at=100,
                                                                     elapsed=lambda t:t-100))
                visual = SimpleNamespace(horizon_closing=None)
                live = player.frame(dialer, visual, 101, radius)
                dialer.state = 'idle'
                dialer.dial_id += 1  # Shutdown resets logical dialing state.
                visual.horizon_closing = (102, 2)
                held = player.frame(dialer, visual, 102, radius)
                self.assertEqual(held.get_at((radius, radius)), live.get_at((radius, radius)))
                self.assertEqual(held.get_at((0, 0)).a, 0)
                closing.request.return_value = bytes((10, 30, 70, 255))*pixels
                frame = player.frame(dialer, visual, 102.1, radius)
                self.assertEqual(frame.get_at((radius, radius)), (10, 30, 70, 255))
                closing.request.return_value = None
                held = player.frame(dialer, visual, 102.2, radius)
                self.assertEqual(held.get_at((radius, radius)), (10, 30, 70, 255))
                # Callers may modify the returned surface without corrupting the cache.
                held.fill((255, 0, 0))
                self.assertEqual(player.frame(dialer, visual, 102.3, radius).get_at(
                    (radius, radius)), (10, 30, 70, 255))
                # A new connection must never inherit the previous closing image.
                dialer.state = 'connected'
                dialer.connection.connected_at = 110
                visual.horizon_closing = None
                active.request.return_value = None
                self.assertEqual(player.frame(dialer, visual, 110, radius).get_at(
                    (radius, radius)), (0, 0, 0, 255))

    def test_timestamps_and_timeline(self):
        self.assertEqual(parse_timestamp('01:02:03.5'), 3723.5)
        self.assertEqual(parse_timestamp('38:33'), 2313)
        for invalid in ('-1', 'nan', 'inf', '1:99', '', 'x'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_timestamp(invalid)
        config = VideoSettings(opening=2, closing=20)
        validate_video(config, 25)
        self.assertEqual(playback_time(config, 0, 25), 2)
        self.assertEqual(playback_time(config, 3, 25), 5)
        self.assertEqual(playback_time(config, 18, 25), 7)
        self.assertEqual(playback_time(config, 500, 25, closing_elapsed=2), 22)
        with self.assertRaises(ValueError):
            validate_video(config, 19)

    def test_actual_decoder_can_seek_small_generated_video(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / 'sample.mkv')
            with av.open(path, 'w') as output:
                stream = output.add_stream('mpeg4', rate=10)
                stream.width, stream.height, stream.pix_fmt = 64, 32, 'yuv420p'
                for index in range(30):
                    frame = av.VideoFrame(64, 32, 'rgb24')
                    color = (255, 0, 0) if index < 15 else (0, 0, 255)
                    frame.planes[0].update(bytes(color) * (frame.planes[0].buffer_size // 3))
                    for packet in stream.encode(frame):
                        output.mux(packet)
                for packet in stream.encode():
                    output.mux(packet)
            self.assertGreater(probe_video(path), 2.5)
            decoder = VideoDecoder()
            try:
                decoder.request(path, 2, 31)
                deadline = time.monotonic() + 5
                data = None
                while data is None and time.monotonic() < deadline:
                    time.sleep(.01)
                    data = decoder.request(path, 2, 31)
                self.assertIsNotNone(data, decoder.errors)
                image = pygame.image.frombuffer(data, (31, 31), 'RGBA')
                self.assertGreater(image.get_at((15, 15)).b, 200)
                self.assertEqual(len(data), 31*31*4)
            finally:
                decoder.close()

    def test_mask_session_snapshot_and_closing(self):
        config = VideoSettings(path='sample', enabled=True, opening=1, closing=8)
        decoder = SimpleNamespace(lock=Lock(), info={'sample': 10}, errors={},
                                  request=Mock(return_value=bytes((20, 80, 200, 255))*121))
        player = HorizonVideo(config, decoder)
        connection = SimpleNamespace(connected_at=100, elapsed=lambda now: now-100)
        dialer = SimpleNamespace(state='connected', dial_id=1, connection=connection)
        visual = SimpleNamespace(horizon_closing=None)
        frame = player.frame(dialer, visual, 102, 5)
        self.assertEqual(frame.get_at((0, 0)).a, 0)
        self.assertEqual(frame.get_at((5, 5)).a, 255)
        decoder.request.assert_called_with('sample', 3, 11)
        config.enabled = False
        self.assertIsNotNone(player.frame(dialer, visual, 103, 5))
        dialer.state = 'idle'
        visual.horizon_closing = (105, 2)
        player.frame(dialer, visual, 106, 5)
        decoder.request.assert_called_with('sample', 9, 11)
        self.assertEqual(player.close_duration(), 2)
        decoder.errors['sample'] = 'Cannot decode'
        self.assertIsNone(player.frame(dialer, visual, 106, 5))


class VideoOptionsTests(unittest.TestCase):
    def setUp(self):
        pygame.font.init()

    def test_file_selection_apply_validation_and_cancel(self):
        config = VideoSettings(path='original', enabled=False)
        menu = VideoOptions(DrawingContext(pygame.Surface((1280, 960)), None), config)
        menu.open()
        with patch('video_options.probe_video', return_value=30):
            menu.select('custom.mp4')
            menu.text = {'opening': '00:02', 'closing': '00:25'}
            menu.draw()
            menu.apply()
        self.assertTrue(config.enabled)
        self.assertEqual((config.opening, config.closing), (2, 25))
        menu.open()
        menu.text['closing'] = '00:01'
        with patch('video_options.probe_video', return_value=30):
            menu.apply()
        self.assertTrue(menu.opened)
        self.assertTrue(menu.error)
        self.assertEqual(config.closing, 25)
        menu.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertFalse(menu.opened)

    def test_timestamp_field_replaces_value_on_typing(self):
        menu = VideoOptions(DrawingContext(pygame.Surface((1280, 960)), None), VideoSettings())
        menu.open()
        menu.ui.mouse = menu.fields['opening'].center
        menu.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1))
        menu.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5, unicode='5'))
        self.assertEqual(menu.text['opening'], '5')
