"""Planet DHD sounds are independent of Earth console sound preferences."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from main import Console
from themes import EARTH, ABYDOS


class PlanetDHDSoundTests(unittest.TestCase):
    def app(self, theme, preference):
        app = Console.__new__(Console)
        app.dialer = SimpleNamespace(theme=theme)
        app.settings = SimpleNamespace(glyph_sound_mode=preference)
        app.glyph_sounds = ['classic-press']
        app.atlantis_press_sound = 'pegasus-press'
        app.dial_sound = 'classic-activate'
        app.button_channel = Mock()
        return app

    def test_milky_way_is_independent_of_all_sgc_options(self):
        for option in ('classic', 'atlantis', 'silent'):
            app = self.app(ABYDOS, option)
            app.play_button_sound()
            app.button_channel.play.assert_called_with('classic-press')
            app.play_button_sound(dial=True)
            app.button_channel.play.assert_called_with('classic-activate')
            self.assertEqual(app.settings.glyph_sound_mode, option)

    def test_pegasus_uses_its_press_and_activation_cues(self):
        app = self.app(replace(ABYDOS, dhd_sound_type='Pegasus'), 'silent')
        app.play_button_sound()
        app.play_button_sound(dial=True)
        self.assertEqual(app.button_channel.play.call_count, 2)
        app.button_channel.play.assert_called_with('pegasus-press')
        self.assertEqual(app.button_sound_mode, 'atlantis')

    def test_earth_options_restore_after_visiting_offworld(self):
        app = self.app(EARTH, 'silent')
        app.play_button_sound()
        app.button_channel.play.assert_not_called()
        app.dialer.theme = ABYDOS
        app.play_button_sound()
        app.button_channel.play.assert_called_once_with('classic-press')
        app.dialer.theme = EARTH
        app.button_channel.reset_mock()
        app.play_button_sound()
        app.button_channel.play.assert_not_called()

    def test_sgc_planet_type_and_validation(self):
        self.assertEqual(EARTH.dhd_sound_type, 'SGC')
        self.assertEqual(ABYDOS.dhd_sound_type, 'MilkyWay')
        app = self.app(replace(ABYDOS, dhd_sound_type='SGC'), 'atlantis')
        self.assertEqual(app.button_sound_mode, 'classic')
        with self.assertRaises(ValueError):
            replace(ABYDOS, dhd_sound_type='Unknown')
