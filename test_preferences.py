"""Preferences restore quietly and save only after changes, never live gate state."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import pygame

from main import Console
from preferences import PreferencesStore, capture_preferences, clean_preferences


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'config' / 'settings.json'
        self.addCleanup(pygame.quit)

    def test_session_round_trip_and_explicit_speed_override(self):
        app = Console()
        app.set_volume(.3)
        app.settings.glyph_sound_mode = 'atlantis'
        app.settings.uniform_glyph_sizing = False
        app.gate_audio.set_computer_enabled(False)
        app.dialer.connection.randomize_duration = True
        app.dialer.set_rotation_rpm(20)
        app.dialer.set_symbol_count(9)
        app.dialer.set_behavior('dhd')
        app.dialer.offworld_sgc_dialing = True
        app.settings.horizon_video.path = 'custom.mkv'
        app.settings.horizon_video.enabled = True
        app.settings.horizon_video.opening = 3
        app.settings.horizon_video.closing = 50
        values = capture_preferences(app.settings, app.dialer, app.gate_audio)
        store = PreferencesStore(self.path)
        store.update(values, 0, force=True)
        restored = Console(preferences=PreferencesStore(self.path))
        self.assertEqual(capture_preferences(restored.settings, restored.dialer, restored.gate_audio), values)
        self.assertAlmostEqual(restored.button_channel.get_volume(), .3, delta=1/128)
        self.assertEqual(restored.dialer.state, 'idle')
        self.assertEqual(restored.dialer.selected, [])
        override = Console(rotation_rpm=15, preferences=PreferencesStore(self.path))
        self.assertEqual(override.dialer.rotation_rpm, 15)

    def test_debounce_atomic_write_and_no_repeat_writes(self):
        store = PreferencesStore(self.path, delay=.5)
        store.update({'volume': .5}, 0)
        self.assertFalse(self.path.exists())
        store.update({'volume': .6}, .4)
        store.update({'volume': .6}, .8)
        self.assertFalse(self.path.exists())
        store.update({'volume': .6}, 1)
        self.assertEqual(json.loads(self.path.read_text())['volume'], .6)
        with patch('preferences.os.replace') as replace:
            store.update({'volume': .6}, 2)
            replace.assert_not_called()
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        store.update({'volume': .7}, 2.1, force=True)
        self.assertEqual(json.loads(self.path.read_text())['volume'], .7)

    def test_missing_corrupt_or_invalid_values_keep_safe_defaults(self):
        store = PreferencesStore(self.path)
        self.assertEqual(store.load(), {})
        self.path.parent.mkdir()
        self.path.write_text('{invalid')
        self.assertEqual(store.load(), {})
        values = clean_preferences({'volume': float('nan'), 'rpm': 10**400,
                                    'symbol_count': True, 'behavior': 'invalid',
                                    'computer_sounds': False,
                                    'video': {'opening': 10, 'closing': 2, 'enabled': True}})
        self.assertNotIn('volume', values)
        self.assertNotIn('rpm', values)
        self.assertNotIn('symbol_count', values)
        self.assertFalse(values['computer_sounds'])
        self.assertFalse(values['video']['enabled'])

    def test_write_failure_is_silent_and_preserves_existing_file(self):
        store = PreferencesStore(self.path)
        store.update({'volume': .4}, 0, force=True)
        before = self.path.read_bytes()
        with patch('preferences.os.replace', side_effect=PermissionError('read only')) as replace:
            store.update({'volume': .8}, 1, force=True)
            store.update({'volume': .8}, 2)
            self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_video_drafts_are_not_saved_before_apply(self):
        app = Console()
        before = capture_preferences(app.settings, app.dialer, app.gate_audio)
        app.options.video.open()
        app.options.video.draft.enabled = not app.options.video.draft.enabled
        app.options.video.text['opening'] = '00:10'
        self.assertEqual(capture_preferences(app.settings, app.dialer, app.gate_audio), before)

    def test_exit_flushes_pending_preferences(self):
        app = Console(preferences=PreferencesStore(self.path))
        app.set_volume(.2)
        with patch('pygame.event.get', return_value=[pygame.event.Event(pygame.QUIT)]):
            app.run()
        self.assertAlmostEqual(PreferencesStore(self.path).load()['volume'], .2)
