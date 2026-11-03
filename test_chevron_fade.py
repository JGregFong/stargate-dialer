"""Chevron shutdown lights retain their color and smoothly reach the off state."""
import unittest
from unittest.mock import patch
import pygame

from gate_art import draw_clamp, draw_jewel, JEWEL_LIT
from main import Console
from themes import EARTH, ABYDOS


class ChevronFadeTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.addCleanup(pygame.quit)

    def test_connected_shutdown_fades_both_gate_views_after_closure(self):
        for theme in (EARTH, ABYDOS):
            with self.subTest(theme=theme.name):
                app = Console()
                d = app.dialer
                d.theme = theme
                d.sequence = [1, 2, 3, 4, 5, 6, 0]
                d.locked = 7
                d.state = 'connected'
                app.stop_gate(10)
                v = app.visual
                end = sum(v.horizon_closing)
                self.assertEqual(v.chevron_light(0, 0, end), 1)
                app.update_gate(end+.45)
                self.assertAlmostEqual(v.chevron_light(0, 0, end+.45), .5)
                self.assertEqual(v.chevron_light(7, 0, end+.45), 0)
                app.renderer.draw(end+.45)
                app.update_gate(end+1)
                self.assertEqual(v.chevron_light(0, 0, end+1), 0)

    def test_interrupted_dial_retains_only_engaged_chevrons(self):
        app = Console()
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.sequence = [27, 9, 32]
        d.locked = 2
        d.state = 'dialing'
        app.stop_gate(10)
        self.assertEqual(d.locked, 0)
        self.assertEqual(app.visual.chevron_light(1, 0, 10), 1)
        self.assertAlmostEqual(app.visual.chevron_light(1, 0, 10.45), .5)
        self.assertEqual(app.visual.chevron_light(2, 0, 10.45), 0)
        self.assertEqual(app.visual.chevron_light(1, 0, 11), 0)

    def test_rib_faces_and_edges_match_lit_jewel(self):
        canvas = pygame.Surface((1280, 960))
        with patch('pygame.draw.polygon', wraps=pygame.draw.polygon) as polygons, \
                patch('pygame.draw.line', wraps=pygame.draw.line) as lines:
            draw_clamp(canvas, 0, lit=True)
            draw_jewel(canvas, 0, lit=True)
        self.assertEqual(sum(call.args[1] == JEWEL_LIT for call in polygons.call_args_list), 13)
        self.assertEqual(sum(call.args[1] == JEWEL_LIT for call in lines.call_args_list), 12)
