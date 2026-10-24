"""Incremental DHD encoding and pause/resume timeline management.

The dialer supplies the shared sequence and cycle clock so rendering and audio
observe the same progress as the queue.
"""


class DHDQueue:
    @staticmethod
    def append(dialer, glyph, now):
        dialer.sequence.append(glyph)
        if dialer.state in ('idle', 'dhd_wait'):
            dialer.started = now - dialer.cycle_elapsed(dialer.locked)
            dialer.state = 'dialing'
        dialer.message = 'DHD / ENCODING SELECTED GLYPHS'

    @staticmethod
    def update(dialer, now):
        dialer.locked = min(len(dialer.sequence), max(0, dialer.dialing_position(now)[0]))
        if dialer.locked == len(dialer.sequence):
            dialer.state = 'ready' if dialer.locked == dialer.symbol_count else 'dhd_wait'
            dialer.message = ('ADDRESS ENCODED / PRESS DIAL TO ACTIVATE'
                              if dialer.state == 'ready' else 'DHD / SELECT NEXT GLYPH')
            if dialer.state == 'ready' and dialer.activation_requested:
                dialer.begin_activation(now)
        else:
            dialer.message = f'ENCODING GLYPH {dialer.locked+1} / {dialer.symbol_count}'
