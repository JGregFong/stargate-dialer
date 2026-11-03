"""Quiet, validated, atomic persistence of user preferences (not live gate state)."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys
import tempfile


def preferences_path():
    if sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        return root / 'StargateDialer' / 'settings.json'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'StargateDialer' / 'settings.json'
    root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    if not root.is_absolute():
        root = Path.home() / '.config'
    return root / 'stargate-dialer' / 'settings.json'


def finite_number(value, minimum, maximum):
    return (type(value) in (int, float) and minimum <= value <= maximum
            and math.isfinite(value))


def clean_preferences(data):
    if not isinstance(data, dict) or data.get('version', 1) != 1:
        return {}
    result = {}
    for key in ('uniform_glyph_sizing', 'computer_sounds', 'random_duration', 'offworld_sgc_dialing'):
        if type(data.get(key)) is bool:
            result[key] = data[key]
    if data.get('offworld_dialing_mode') in ('dhd', 'spinning', 'rotary'):
        result['offworld_dialing_mode'] = data['offworld_dialing_mode']
    if data.get('glyph_sound_mode') in ('classic', 'atlantis', 'silent'):
        result['glyph_sound_mode'] = data['glyph_sound_mode']
    if finite_number(data.get('volume'), 0, 1):
        result['volume'] = data['volume']
    if finite_number(data.get('rpm'), .01, 1000):
        result['rpm'] = data['rpm']
    if data.get('behavior') in ('current', 'dhd'):
        result['behavior'] = data['behavior']
    if type(data.get('symbol_count')) is int and data['symbol_count'] in (7, 8, 9):
        result['symbol_count'] = data['symbol_count']
    video = data.get('video')
    if isinstance(video, dict):
        valid = {}
        path = video.get('path')
        if isinstance(path, str) and len(path) <= 4096 and '\0' not in path:
            valid['path'] = path
        if type(video.get('enabled')) is bool:
            valid['enabled'] = video['enabled']
        opening, closing = video.get('opening'), video.get('closing')
        if (finite_number(opening, 0, 10**9) and finite_number(closing, 0, 10**9)
                and opening < closing):
            valid.update(opening=opening, closing=closing)
        elif 'opening' in video or 'closing' in video:
            valid['enabled'] = False
        result['video'] = valid
    return result


def capture_preferences(settings, dialer, audio):
    video = settings.horizon_video
    return {
        'version': 1,
        'uniform_glyph_sizing': settings.uniform_glyph_sizing,
        'glyph_sound_mode': settings.glyph_sound_mode,
        'volume': settings.volume,
        'computer_sounds': audio.computer_enabled,
        'random_duration': dialer.connection.randomize_duration,
        'rpm': dialer.rotation_rpm,
        'behavior': dialer.behavior,
        'symbol_count': dialer.symbol_count,
        'offworld_dialing_mode': dialer.offworld_dialing_mode,
        'video': {'path': video.path, 'enabled': video.enabled,
                  'opening': video.opening, 'closing': video.closing},
    }


def restore_preferences(settings, dialer, audio, data):
    data = clean_preferences(data)
    for key in ('uniform_glyph_sizing', 'glyph_sound_mode', 'volume'):
        if key in data:
            setattr(settings, key, data[key])
    for key, value in data.get('video', {}).items():
        setattr(settings.horizon_video, key, value)
    if 'computer_sounds' in data:
        audio.set_computer_enabled(data['computer_sounds'])
    if 'random_duration' in data:
        dialer.connection.randomize_duration = data['random_duration']
    if 'rpm' in data:
        dialer.set_rotation_rpm(data['rpm'])
    if 'symbol_count' in data:
        dialer.set_symbol_count(data['symbol_count'])
    if 'behavior' in data:
        dialer.set_behavior(data['behavior'])
    if 'offworld_sgc_dialing' in data:
        dialer.offworld_sgc_dialing = data['offworld_sgc_dialing']
    if 'offworld_dialing_mode' in data:
        dialer.offworld_dialing_mode = data['offworld_dialing_mode']


class PreferencesStore:
    def __init__(self, path=None, delay=.6):
        self.path = Path(path) if path is not None else preferences_path()
        self.delay = delay
        self.pending = self.written = None
        self.changed_at = 0.0
        self.retry_at = 0.0

    def load(self):
        try:
            if self.path.stat().st_size > 65536:
                return {}
            return clean_preferences(json.loads(self.path.read_text(encoding='utf-8')))
        except (OSError, ValueError, UnicodeError, RecursionError):
            return {}

    def update(self, values, now, force=False):
        if values != self.pending:
            self.pending = deepcopy(values)
            self.changed_at = now
        if self.pending == self.written:
            return
        if not force and (now < self.changed_at + self.delay or now < self.retry_at):
            return
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.settings-', suffix='.tmp', delete=False) as file:
                temporary = Path(file.name)
                json.dump(self.pending, file, indent=2, allow_nan=False)
                file.write('\n')
            os.replace(temporary, self.path)
            self.written = deepcopy(self.pending)
        except (OSError, ValueError, TypeError):
            self.retry_at = now + 5
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
