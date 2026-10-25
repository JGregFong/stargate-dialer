"""Views work with explicit dependencies rather than a mutable Console facade."""
import unittest
from unittest.mock import Mock, patch

import pygame

from console_commands import ConsoleCommands
from drawing_context import DrawingContext
from glyph import Glyph
from iris import Iris
from keyboard_window import GlyphKeyboard
from main import Console
from options_menu import OptionsMenu
from simulator import Dialer
from view_state import CommandInput, GateVisualState, UISettings


class ViewBoundaryTests(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def tearDown(self):
        pygame.quit()

    def test_keyboard_renders_and_dispatches_without_console(self):
        dialer = Dialer()
        dialer.selected = [1, 2, 3, 4, 5, 6]
        dispatch = Mock()
        keyboard = GlyphKeyboard(
            glyph=Glyph(), dialer=dialer, visual=GateVisualState(), iris=Iris(),
            window=Mock(), action=dispatch, stop_gate=Mock(), modal_open=lambda: False)
        keyboard.draw_keyboard()
        self.assertEqual({action for _, action, _ in keyboard.ui.buttons
                          if isinstance(action, int)}, set(range(39)))
        keyboard.keyboard_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), 3)
        dispatch.assert_called_once_with('dial', 3)

    def test_options_mutate_only_explicit_settings(self):
        ui = DrawingContext(pygame.Surface((1280, 960)), Glyph())
        settings = UISettings()
        menu = OptionsMenu(ui=ui, settings=settings, gate_audio=Mock(),
                           viewport=lambda: pygame.Rect(0, 0, 1280, 960))
        menu.draw_options()
        rect = next(rect for rect, action, _ in ui.buttons if action == 'toggle_sizing')
        menu.options_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        self.assertFalse(settings.uniform_glyph_sizing)

    def test_command_controller_needs_no_window_or_renderer(self):
        dialer = Dialer()
        input_state = CommandInput(text='dial Abydos')
        dispatch = Mock()
        commands = ConsoleCommands(
            dialer=dialer, visual=GateVisualState(), input_state=input_state,
            iris=Iris(), action=dispatch, stop_gate=Mock(), reset_gate=Mock(), set_iris=Mock())
        commands.execute_command(10)
        self.assertEqual(dialer.destination, 'ABYDOS')
        self.assertEqual(input_state.text, '')
        dispatch.assert_called_once_with('dial', 10)

    def test_main_event_loop_uses_component_interfaces(self):
        app = Console()
        with patch('pygame.event.get', return_value=[pygame.event.Event(pygame.QUIT)]):
            app.run()
