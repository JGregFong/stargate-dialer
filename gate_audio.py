"""State-driven gate audio on channels separate from the DHD buttons."""
from pathlib import Path
import random
import pygame


class GateAudio:
    def set_volume(self, volume):
        """Adjust every gate channel, including any currently playing loops."""
        volume = max(0.0, min(1.0, volume))
        for channel in self.channels.values():
            channel.set_volume(volume)

    # Reserve independent audio channels and load gate and computer cue variants.
    def __init__(self):
        self.sounds = {}
        self.channels = {}
        self.previous_state = 'idle'
        self.spin_key = None
        self.engaged = None
        self.returning = False
        self.return_failure_played = False
        self.close_duration = 1.2
        self.open_duration = 1.2
        self.computer_enabled = True
        self.computer_token = None
        self.computer_stage = None
        if not pygame.mixer.get_init():
            return
        pygame.mixer.set_reserved(8)
        self.channels = {name: pygame.mixer.Channel(i) for i, name in enumerate(
            ('roll', 'chevron', 'effect', 'wormhole', 'computer', 'computer_beep', 'iris'), 1)}
        directory = Path(__file__).resolve().parent / 'media' / 'sounds' / 'stargate'
        files = {
            'roll': ('roll.wav',),
            'chevron': ('sgc_chevron.mp3', 'sgc_chevron2.mp3'),
            'final_chevron': ('chevron_lock.mp3',),
            'open': ('open.mp3', 'eh_usual_open.wav'),
            'wormhole': ('wormhole_loop.wav',),
            'close': ('close.mp3', 'gate_close.mp3'),
            'fail': ('dial_fail_sg1.mp3',),
        }
        for key, names in files.items():
            self.sounds[key] = []
            for name in names:
                try:
                    self.sounds[key].append(pygame.mixer.Sound(str(directory / name)))
                except (pygame.error, OSError) as error:
                    print(f'Unable to load sound {name}: {error}')

        computer_directory = directory.parent / 'computer'
        for key, names in {
            'computer_in': ('dial_chevron_encode_fr.wav', 'dial_chevron_encode2_fr.wav'),
            'computer_out': ('dial_chevron_encode.wav', 'dial_chevron_encode2.wav'),
            'computer_beep': ('dial_chevron_beep.wav', 'dial_chevron_beep2.wav'),
        }.items():
            self.sounds[key] = []
            for name in names:
                try:
                    self.sounds[key].append(pygame.mixer.Sound(str(computer_directory / name)))
                except (pygame.error, OSError) as error:
                    print(f'Unable to load sound {name}: {error}')

        # Iris motion has its own channel so gate and keyboard cues continue.
        for key in ('iris_open', 'iris_close'):
            self.sounds[key] = []
            try:
                path = directory.parent / 'iris' / (key + '.mp3')
                self.sounds[key].append(pygame.mixer.Sound(str(path)))
            except (pygame.error, OSError) as error:
                print(f'Unable to load {key}: {error}')

    # Toggle computer cues and immediately stop any cue already playing.
    def set_computer_enabled(self, enabled):
        self.computer_enabled = bool(enabled)
        self.stop('computer')
        self.stop('computer_beep')
        self.computer_token = None
        self.computer_stage = None

    # Trigger one cue per glyph-animation stage using stable dial and symbol IDs.
    def update_computer(self, dialer, returning, now, spin_fraction):
        if not self.computer_enabled or returning or dialer.state != 'dialing' or now < dialer.started:
            if self.computer_token is not None:
                self.stop('computer')
                self.stop('computer_beep')
                self.computer_token = None
                self.computer_stage = None
            return
        index, phase = dialer.dialing_position(now)
        index = min(len(dialer.sequence)-1, index)
        token = (dialer.dial_id, index)
        progress = (phase-spin_fraction) / (1-spin_fraction)
        stage = (0 if progress < 0 else 1 if progress < 1.34/2.8
                 else 2 if progress < 1.66/2.8 else 3 if progress < 2.2/2.8 else 4)
        if (token, stage) == (self.computer_token, self.computer_stage):
            return
        self.computer_token, self.computer_stage = token, stage
        self.stop('computer')
        self.stop('computer_beep')
        if stage == 1:
            self.play('computer_in', 'computer')
        elif stage == 3:
            self.play('computer_out', 'computer')
        elif stage in (2, 4):
            self.play('computer_beep', 'computer_beep')

    # Choose a sound variant and return its duration for synchronized visual effects.
    def play(self, sound, channel, loop=False):
        choices = self.sounds.get(sound, [])
        if choices and channel in self.channels:
            sound_file = random.choice(choices)
            self.channels[channel].play(sound_file, loops=-1 if loop else 0)
            return sound_file.get_length()
        return 0.0

    # Stop one dedicated channel without interrupting unrelated sounds.
    def stop(self, channel):
        if channel in self.channels:
            self.channels[channel].stop()

    # Synchronize roll, chevrons, activation, shutdown, and failure with gate state.
    def update(self, dialer, ring_return, now, spin_fraction):
        spin_fraction = dialer.spin_fraction(now)
        state = dialer.state
        returning = ring_return is not None
        self.update_computer(dialer, returning, now, spin_fraction)
        spin_key = None
        if returning:
            # Keep an already playing roll uninterrupted across an abort.
            spin_key = self.spin_key or ('return', ring_return[0])
        elif state == 'dialing' and now >= dialer.started:
            index, phase = dialer.dialing_position(now)
            index = min(len(dialer.sequence)-1, index)
            token = (dialer.dial_id, index)
            if phase < spin_fraction:
                spin_key = token
            elif self.engaged != token:
                self.play('final_chevron' if index == dialer.symbol_count - 1 else 'chevron', 'chevron')
                self.engaged = token
        if spin_key != self.spin_key:
            if spin_key is None:
                self.stop('roll')
            else:
                self.play('roll', 'roll', loop=True)
            self.spin_key = spin_key
        if returning:
            if not self.returning:
                self.return_failure_played = False
            return_end = ring_return[0] + ring_return[2]
            if not self.return_failure_played and now >= return_end - .5:
                self.play('fail', 'effect')
                self.return_failure_played = True
        elif self.returning and not self.return_failure_played:
            # Fall back if a delayed frame skipped the early cue.
            self.play('fail', 'effect')
            self.return_failure_played = True
        if state != self.previous_state:
            if state == 'connected':
                self.open_duration = self.play('open', 'effect') or 1.2
                self.play('wormhole', 'wormhole', loop=True)
            elif self.previous_state == 'connected':
                self.stop('wormhole')
                self.close_duration = self.play('close', 'effect') or 1.2
            elif state == 'failed':
                self.play('fail', 'effect')
            if state == 'idle':
                self.engaged = None
        self.previous_state = state
        self.returning = returning
