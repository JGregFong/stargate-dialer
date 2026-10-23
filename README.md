# stargate-dialer
<img width="1280" height="960" alt="01-idle-console" src="https://github.com/user-attachments/assets/f9fc1339-dd69-44b2-b625-b5647a66dc43" />

Used PyGame and ChatGPT's Codex

"stargate_sg1_adress_glyphs.ttf" by "Joy Anne Baker" from "https://www.thescifiworld.net/fonts.htm" was used for the glyphs.

Sounds were from a fork of RafaelDeJongh's Carter's Addon pack for Garry's Mod.

All materials and copyright under the Stargate brand belongs to Amazon and MGM Studios.



DISCLAIMER: 
ChatGPT's Codex was used in the generation of code in PyGame. 
Artwork generated was only through the use of PyGame's existing documentation and ChatGPT's Codex.
No other artwork, sound effects, and voices were generated through ChatGPT.


## Pygame simulator

Run from this folder using the project environment:

```powershell
.\.venv\Scripts\python.exe main.py
```

The GUI uses pygame-ce (the earlier PyQt6 note above is historical).

- Click six distinct glyphs in the glyph keyboard and then confirm with the Earth Point of Origin and Dial/Enter button.
- Hover over a glyph to see its name. Backspace or UNDO removes the last selection.
- Press Enter or click DIAL to start. Input is frozen while the seven symbols lock.
- <img width="1280" height="960" alt="03-encoding-symbol" src="https://github.com/user-attachments/assets/b052ecd1-f1b5-4751-bfca-c674da2acd6a" />
- Click LOAD DESTINATION to open the address archive. Search by destination name and/or select glyph filters (matched in any order). Scroll with the mouse wheel, Page Up/Page Down, or UP/DOWN buttons. Click a destination row to load its ordered address; CLOSE or Escape returns without loading. Restricted and inactive entries remain available for failed-connection scenarios.
<img width="1280" height="960" alt="07-address-archive" src="https://github.com/user-attachments/assets/cb24fa98-3174-4d19-ba89-9dbe7853c751" />
- Successful connections show ACTIVE, seven green OK indicators, an animated blue event horizon, and a 38-minute countdown.
<img width="1280" height="960" alt="04-connected" src="https://github.com/user-attachments/assets/4c448535-784a-46e6-9d6f-6c243b4a5829" />
- Unknown, restricted, or inactive destinations show ERROR with a dark gate center. CLEAR resets the failed attempt.
- ESC or SHUTDOWN disengages or aborts. The bottom command field accepts `dial`, `shutdown`, `abort`, `reset`, and `help` followed by Enter.
- The window resizes with letterboxing to preserve the console proportions.

Connection logic is in `simulator.py`; `glyph.py` renders the bundled font; `main.py` draws and operates the console. Assets resolve relative to the source directory. The authoritative destination data is `address_database`; legacy `address_list` remains for compatibility. Longer addresses are not offered in standard seven-chevron mode.

Verification:

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_simulator
.\.venv\Scripts\python.exe main.py --preview connected.png
```

The blue event horizon is generated procedurally; no additional texture download is required. The interface is inspired by the supplied reference photographs rather than a pixel-for-pixel reproduction.

Glyph animation starts small at the top chevron, grows while moving to the gate center, pauses there, then shrinks into its assigned slot.

## Address length modes

Use 7 SYM, 8 SYM, or 9 SYM to select the total address length, including Earth. Enter respectively six, seven, or eight distinct destination glyphs. Changing modes clears the current manual entry. Loading an archive destination chooses its length automatically. Atlantis and Othala use eight symbols; Destiny uses nine. Earth is always last at the top chevron; extra destination chevrons use 160 and 200 degrees. The final lock sound, slot layout, and diagnostic rows follow the selected length.

## DHD dialing behavior

In OPTIONS, choose DHD under Dialing Behavior while the gate is idle. Each glyph click immediately starts encoding; further clicks queue distinct glyphs in order. The ring pauses if it finishes the current queue before another selection. Select Earth after the destination glyphs to encode the final chevron. Once all glyphs are encoded, READY is displayed and DIAL / ENTER activates the wormhole (or reports ERROR for an unavailable address). The connection timer starts on activation. Archive loading queues the complete address, including Earth, in DHD mode. Switching behavior clears idle entry; behavior cannot change mid-dial. Current mode retains the original enter-address-then-dial flow.

DHD activation can be requested as soon as every symbol (including Earth) has been selected. DIAL queues the connection while remaining symbols encode. After the final lock, the DHD dial sound plays once, followed by a 0.8-second pause before the connection attempt. Shutdown cancels a pending activation.

## Separate glyph keyboard

Click GLYPH KEYBOARD to open its separate resizable window near the bottom of the console; it stays closed at startup. It contains Earth (0), glyphs 1-38, the 7/8/9-symbol modes, UNDO, CLEAR, DIAL / ENTER, and SHUTDOWN / ESC. Closing this window hides it without stopping the simulator; GLYPH KEYBOARD on the main console reopens it. Enter, Backspace, and Escape work from the keyboard window. Console menus temporarily block keyboard interaction. The expanded main console retains Options, Load Destination, diagnostics, gate, glyph slots, status, and command input.

## Dialing controls and named commands

DHD DIALING is now toggled in the glyph keyboard, not Options. It is disabled while dialing, waiting for DHD input or activation, connected, braking, or closing. In the console command field, use `dial <destination name>` (for example `dial atlantis` or `dial Martin Lloyd's Homeworld`). Names match case-insensitively. The command loads the complete address, selects its length, and starts dialing. In DHD mode it also queues activation after encoding and the existing delay. Bare `dial` shows usage; Enter in the glyph keyboard still operates DIAL / ENTER normally. Busy gates reject replacement dial commands.

`start` performs the same action as the keyboard DIAL / ENTER button on the currently entered address. `dial <destination>` continues to load and dial a named database address. Commands are case-insensitive.

## Iris

The IRIS button on the glyph keyboard toggles the aperture. Commands: `iris` toggles, `iris open` opens, and `iris close` closes. The iris can operate whether the gate is idle or connected, and stays in its chosen position after shutdown. Individual black blades with tile-ring-colored outlines reveal curved edges, gather into a flower-like center while closing, and retract on opening. Each transition plays the corresponding iris MP3 on an independent audio channel and uses its duration; repeated requests for the current target do not replay the sound. Mid-motion reversal preserves the current opening size.

## Windows executable

A single-file Windows build is defined by `StargateDialer.spec`. It includes the Python runtime, pygame-ce libraries, the bundled glyph font, and the media directory. The `reference/` images, source tests, project virtual environment, and IDE files are not distributed.

From the project folder in PowerShell:

```powershell
# One-time setup in the existing project environment:
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt

# Build or rebuild after code/asset changes:
.\build.ps1
```

The executable is `dist\StargateDialer.exe`. Copy that file to another Windows x64 PC; Python does not need to be installed there. The keyboard stays closed until GLYPH KEYBOARD is clicked. One-file builds extract their included runtime/assets to a temporary directory when launched. Rebuild whenever code, destination data, or assets change. This build is not code-signed.

`build.ps1 -OutputDirectory <path>` can select another output folder. To verify the packaged renderer without leaving the GUI open:

```powershell
.\dist\StargateDialer.exe --preview connected.png
```
