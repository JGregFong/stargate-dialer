"""Console command parsing and dispatch through the shared action controller."""
from glyph_database import address_database


class ConsoleCommands:
    def __init__(self, console):
        self.console = console

    def execute_command(self, now):
        parts = self.console.command.strip().split(maxsplit=1)
        verb = parts[0].casefold() if parts else ''
        d = self.console.dialer
        if verb in ('shutdown', 'abort') and len(parts) == 1:
            self.console.stop_gate(now)
        elif verb == 'reset' and len(parts) == 1 and d.state in ('idle', 'failed'):
            d.reset()
        elif verb == 'iris':
            argument = parts[1].strip().casefold() if len(parts) > 1 else ''
            if argument in ('', 'open', 'close'):
                closed = not self.console.iris.target_closed if not argument else argument == 'close'
                self.console.set_iris(closed, now)
            else:
                d.message = 'USAGE: IRIS / IRIS OPEN / IRIS CLOSE'
        elif verb == 'start' and len(parts) == 1:
            self.console.action('dial', now)
        elif verb == 'dial':
            if len(parts) < 2:
                d.message = 'USAGE: DIAL <DESTINATION NAME> / EXAMPLE: DIAL ATLANTIS'
            else:
                query = parts[1].strip()
                if len(query) >= 2 and query[0] == query[-1] and query[0] in ('"', "'"):
                    query = query[1:-1]
                normalized = ' '.join(query.split()).casefold()
                name = next((name for name in address_database
                             if ' '.join(name.split()).casefold() == normalized), None)
                if name is None:
                    d.message = 'UNKNOWN DESTINATION / SEARCH THE ADDRESS ARCHIVE'
                elif d.state not in ('idle', 'failed') or self.console.ring_return is not None or self.console.horizon_closing is not None or self.console.slot_fade_started is not None:
                    d.message = 'GATE BUSY / SHUTDOWN BEFORE DIALING ANOTHER ADDRESS'
                else:
                    if d.state == 'failed':
                        d.reset()
                    # Loading chooses address length. DHD queues activation while
                    # current mode starts its normal complete-address sequence.
                    if d.load_destination(name, now):
                        self.console.action('dial', now)
        else:
            d.message = 'COMMANDS: START / DIAL <NAME> / IRIS [OPEN/CLOSE] / SHUTDOWN / RESET'
        self.console.command = ''
