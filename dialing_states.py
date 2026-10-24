"""Encoding state transitions for computer and incremental DHD dialing."""
from dhd_queue import DHDQueue


def update_dialing(dialer, now):
    if dialer.behavior == 'dhd':
        DHDQueue.update(dialer, now)
        return
    dialer.locked = max(0, min(dialer.symbol_count, dialer.dialing_position(now)[0]))
    dialer.message = f'CHEVRON {min(dialer.locked + 1, dialer.symbol_count)} / {dialer.symbol_count} — ACQUIRING'
    if dialer.locked == dialer.symbol_count:
        dialer.resolve_connection(now)
