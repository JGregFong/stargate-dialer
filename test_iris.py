"""Iris motion, transparency, command routing, and independent audio checks."""
import unittest
from unittest.mock import Mock
import pygame
from iris import Iris
from main import Console


class IrisMotionTests(unittest.TestCase):
    def test_reversal_preserves_position(self):
        iris = Iris()
        self.assertEqual(iris.amount(0), 0)
        self.assertTrue(iris.set_closed(True, 10, 2))
        self.assertAlmostEqual(iris.amount(11), .5)
        self.assertTrue(iris.set_closed(False, 11, 2))
        self.assertAlmostEqual(iris.amount(11), .5)
        self.assertEqual(iris.amount(13), 0)
        self.assertFalse(iris.set_closed(False, 14, 2))

    def test_rendering_leaves_an_aperture_and_closes_it(self):
        iris = Iris()
        surface = pygame.Surface((101, 101))
        background = (4, 12, 20)
        surface.fill(background)
        iris.draw(surface, (50, 50), 45, 0)
        self.assertEqual(surface.get_at((50, 50))[:3], background)
        iris.set_closed(True, 0, 2)
        iris.draw(surface, (50, 50), 45, 1)
        self.assertEqual(surface.get_at((50, 50))[:3], background)
        self.assertNotEqual(surface.get_at((90, 50))[:3], background)
        iris.draw(surface, (50, 50), 45, 2)
        self.assertNotEqual(surface.get_at((50, 50))[:3], background)


class IrisControlTests(unittest.TestCase):
    def test_commands_button_and_audio(self):
        app = Console()
        try:
            app.gate_audio.play = Mock(return_value=2)
            app.command = 'IRIS CLOSE'
            app.execute_command(10)
            self.assertTrue(app.iris.target_closed)
            app.gate_audio.play.assert_called_once_with('iris_close', 'iris')
            app.command = 'iris close'
            app.execute_command(11)
            self.assertEqual(app.gate_audio.play.call_count, 1)
            app.command = 'iris open'
            app.execute_command(12)
            app.gate_audio.play.assert_called_with('iris_open', 'iris')
            app.action('iris', 13)
            self.assertTrue(app.iris.target_closed)
            app.stop_gate(14)
            self.assertTrue(app.iris.target_closed)
            app.command = 'iris nonsense'
            app.execute_command(15)
            self.assertIn('USAGE', app.dialer.message)
        finally:
            pygame.quit()


if __name__ == '__main__':
    unittest.main()
