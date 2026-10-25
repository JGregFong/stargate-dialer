"""Console command parsing and dispatch through the shared action controller."""
from glyph_database import address_database


class ConsoleCommands:
    def __init__(self, *, dialer, visual, input_state, iris, action, stop_gate, reset_gate, set_iris):
        self.dialer = dialer
        self.visual = visual
        self.input_state = input_state
        self.iris = iris
        self.action = action
        self.stop_gate = stop_gate
        self.reset_gate = reset_gate
        self.set_iris = set_iris

    def execute_command(self, now):
        parts = self.input_state.text.strip().split(maxsplit=1)
        verb = parts[0].casefold() if parts else ''
        d = self.dialer
        if verb in ('shutdown', 'abort') and len(parts) == 1:
            self.stop_gate(now)
        elif verb == 'reset' and len(parts) == 1 and d.state in ('idle', 'failed'):
            self.reset_gate(now)
        elif verb == 'iris':
            argument = parts[1].strip().casefold() if len(parts) > 1 else ''
            if argument in ('', 'open', 'close'):
                closed = not self.iris.target_closed if not argument else argument == 'close'
                self.set_iris(closed, now)
            else:
                d.message = 'USAGE: IRIS / IRIS OPEN / IRIS CLOSE'
        elif verb == 'start' and len(parts) == 1:
            self.action('dial', now)
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
                elif d.state not in ('idle', 'failed') or self.visual.busy:
                    d.message = 'GATE BUSY / SHUTDOWN BEFORE DIALING ANOTHER ADDRESS'
                else:
                    if d.state == 'failed':
                        self.reset_gate(now)
                    # Loading chooses address length. DHD queues activation while
                    # current mode starts its normal complete-address sequence.
                    if d.load_destination(name, now):
                        self.action('dial', now)
        else:
            d.message = 'COMMANDS: START / DIAL <NAME> / IRIS [OPEN/CLOSE] / SHUTDOWN / RESET'
        self.input_state.text = ''
