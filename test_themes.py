"""Theme boundaries, travel lifecycle and offworld input geometry."""
import unittest
from unittest.mock import Mock
from dataclasses import replace
import pygame
from simulator import Dialer
from themes import EARTH, ABYDOS, DHD_OUTER_RING, DHD_INNER_RING
from offworld import Sector, Dome, point, fitted_dhd_glyph
from main import Console
from glyph_database import glyph_letters
from ring_motion import TILE_ANGLE
from keyboard_window import keyboard_bounds


class ThemeTests(unittest.TestCase):
    def test_instant_offworld_shutdown_plays_failure_once_only_for_interrupted_entry(self):
        for phase in ('idle', 'partial', 'ready', 'activating', 'connected'):
            with self.subTest(phase=phase):
                app = Console()
                self.addCleanup(pygame.quit)
                d = app.dialer
                d.theme = ABYDOS
                d.set_behavior('dhd')
                if phase == 'partial':
                    app.action(27, 0)
                elif phase != 'idle':
                    d.load_destination('Earth', 0)
                    if phase in ('activating', 'connected'):
                        d.activate(0)
                    app.update_gate(d.cycle_elapsed(7))
                    if phase == 'connected':
                        app.update_gate(d.cycle_elapsed(7)+.81)
                app.gate_audio.play = Mock(return_value=1)
                app.stop_gate(6)
                app.stop_gate(6.1)
                app.gate_audio.update(d, None, 7, d.spin_fraction(7))
                names = [c.args[0] for c in app.gate_audio.play.call_args_list]
                self.assertEqual(names.count('fail'), int(phase in ('partial', 'ready', 'activating')))
                self.assertIsNone(app.gate_audio.spin_key)

    def test_offworld_arrival_hides_existing_keyboard_until_manual_open(self):
        app = Console()
        self.addCleanup(pygame.quit)
        app.keyboard.open_keyboard()
        self.assertTrue(app.keyboard.keyboard_visible)
        app.dialer.destination, app.dialer.state = 'ABYDOS', 'connected'
        app.action('travel', 0)
        self.assertFalse(app.keyboard.keyboard_visible)
        app.action('keyboard', 1)
        self.assertTrue(app.keyboard.keyboard_visible)

    def test_offworld_keyboard_fits_small_desktops_and_theme_resize(self):
        for desktop in ((1024, 768), (1920, 1080), (800, 600)):
            bounds = keyboard_bounds((1280, 680), (100, 710), desktop)
            self.assertGreaterEqual(bounds.left, 0)
            self.assertGreaterEqual(bounds.top, 0)
            self.assertLessEqual(bounds.right, desktop[0])
            self.assertLessEqual(bounds.bottom, desktop[1]-40)
        app = Console()
        self.addCleanup(pygame.quit)
        app.keyboard.open_keyboard()
        app.dialer.theme = ABYDOS
        app.keyboard.draw_keyboard()
        w = app.keyboard.keyboard_window
        desktop = pygame.display.get_desktop_sizes()[0]
        self.assertLessEqual(w.position[1]+w.size[1], desktop[1]-40)

    def test_offworld_controls_have_no_undo_or_clear(self):
        app = Console()
        self.addCleanup(pygame.quit)
        app.dialer.theme = ABYDOS
        app.dialer.set_behavior('dhd')
        for entered in (False, True):
            if entered:
                app.action(27, 0)
            app.keyboard.draw_keyboard()
            actions = [action for _, action, _ in app.keyboard.keyboard_buttons]
            self.assertNotIn('undo', actions)
            self.assertNotIn('clear', actions)

    def test_closed_offworld_gate_accepts_new_entry_during_lingering_fade(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.load_destination('Earth', 0)
        d.activate(0)
        app.update_gate(d.cycle_elapsed(7))
        app.update_gate(d.cycle_elapsed(7)+.81)
        app.stop_gate(6)
        now = 6+app.gate_audio.close_duration+.01
        app.update_gate(now)
        app.renderer.draw(now)
        self.assertIsNone(app.visual.horizon_closing)
        self.assertFalse(hasattr(app.visual, 'slot_fade_started'))
        self.assertFalse(app.visual.busy)
        self.assertEqual(app.visual.fade_alpha, 255)
        app.action(27, now)
        self.assertEqual(d.selected, [27])
        self.assertEqual(app.visual.closing_slots, ())
        self.assertEqual(app.visual.closing_dhd, ())

    def test_abydos_origin_uses_glyph_39_font_character_without_changing_earth(self):
        app = Console()
        self.addCleanup(pygame.quit)
        glyph = app.ui.glyph
        earth = pygame.image.tobytes(glyph.image(0, 100), 'RGBA')
        self.assertEqual(glyph_letters[39], 'n')
        glyph.origin_mark = ABYDOS.origin_mark
        origin, abydos = glyph.image(0, 100), glyph.image(39, 100)
        self.assertGreater(origin.get_bounding_rect().width, 0)
        self.assertEqual(pygame.image.tobytes(origin, 'RGBA'), pygame.image.tobytes(abydos, 'RGBA'))
        glyph.origin_mark = EARTH.origin_mark
        self.assertEqual(pygame.image.tobytes(glyph.image(0, 100), 'RGBA'), earth)

    def test_offworld_shutdown_fades_slots_and_dhd_from_shared_timeline(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.load_destination('Earth', 0)
        d.activate(0)
        app.update_gate(d.cycle_elapsed(7))
        app.update_gate(d.cycle_elapsed(7)+.81)
        sequence = tuple(d.sequence)
        app.stop_gate(6)
        v = app.visual
        self.assertEqual(v.closing_slots, sequence)
        self.assertEqual(v.closing_dhd, sequence)
        self.assertEqual(v.fade_alpha, 255)
        starts = v.fade_started
        app.update_gate(starts-.1)
        app.renderer.draw(starts-.1)
        self.assertEqual(v.fade_alpha, 255)
        self.assertIsNone(v.horizon_closing)
        midpoint = starts+v.fade_duration/2
        app.update_gate(midpoint)
        self.assertTrue(0 < v.fade_alpha < 255)
        original = app.renderer.draw_slot_glyph
        app.renderer.draw_slot_glyph = Mock(wraps=original)
        app.renderer.draw(midpoint)
        self.assertEqual(app.renderer.draw_slot_glyph.call_count, 7)
        for call in app.renderer.draw_slot_glyph.call_args_list:
            self.assertEqual(call.kwargs['alpha'], v.fade_alpha)
        app.keyboard.draw_keyboard()
        self.assertEqual(app.keyboard.visual.fade_alpha, v.fade_alpha)
        app.update_gate(starts+v.fade_duration+.01)
        self.assertEqual(v.fade_alpha, 0)
        self.assertEqual(v.closing_slots, ())
        self.assertEqual(v.closing_dhd, ())

    def test_own_address_is_invalid_for_each_dialing_mode(self):
        for theme, behavior, alternate in ((EARTH, 'current', False),
                                            (EARTH, 'dhd', False),
                                            (ABYDOS, 'dhd', False),
                                            (ABYDOS, 'dhd', True)):
            with self.subTest(origin=theme.name, behavior=behavior, alternate=alternate):
                d = Dialer(rotation_rpm=5)
                d.theme = theme
                d.offworld_sgc_dialing = alternate
                d.set_behavior(behavior)
                self.assertTrue(d.load_destination(theme.name, 0))
                d.connection.connect = Mock()
                if behavior == 'current':
                    self.assertTrue(d.start(0))
                else:
                    self.assertTrue(d.activate(0))
                end = d.cycle_elapsed(len(d.sequence))
                d.update(end)
                d.update(end + .8)
                self.assertEqual(d.state, 'failed')
                self.assertEqual(d.message, 'INVALID ADDRESS / NO CONNECTION')
                d.connection.connect.assert_not_called()

    def test_own_address_resets_immediately_in_console(self):
        for theme in (EARTH, ABYDOS):
            with self.subTest(origin=theme.name):
                app = Console()
                self.addCleanup(pygame.quit)
                d = app.dialer
                d.theme = theme
                d.set_behavior('dhd' if theme.offworld else 'current')
                d.load_destination(theme.name, 0)
                app.action('dial', 0)
                end = d.started + d.cycle_elapsed(len(d.sequence))
                app.update_gate(end)
                app.update_gate(end + .8)
                self.assertEqual(d.state, 'idle')
                self.assertEqual(d.sequence, [])
                self.assertIn('INVALID ADDRESS', d.message)

    def test_offworld_abort_centers_nearby_tile_before_failure_sound(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                app = Console()
                self.addCleanup(pygame.quit)
                d = app.dialer
                d.theme = ABYDOS
                d.offworld_sgc_dialing = True
                d.set_behavior('dhd')
                app.gate_audio.play = Mock(return_value=1)
                d.select(26, 0)
                now = 1
                if reverse:
                    end = d.cycle_elapsed(1)
                    app.update_gate(end)
                    d.select(6, end+1)
                    now = end+2
                app.gate_audio.update(d, None, now, d.spin_fraction(now))
                rotation = app.track_rotation(now)
                app.gate_audio.play.reset_mock()
                app.stop_gate(now)
                started, _, duration, _ = app.visual.ring_return
                target = app.visual.ring_stop_target
                self.assertLessEqual(abs(target-rotation), TILE_ANGLE*2)
                self.assertAlmostEqual(target/TILE_ANGLE, round(target/TILE_ANGLE))
                app.renderer.draw(started+duration-.001)
                app.gate_audio.update(d, app.visual.ring_return, started+duration-.001, d.spin_fraction(now))
                self.assertNotIn('fail', [c.args[0] for c in app.gate_audio.play.call_args_list])
                app.renderer.draw(started+duration)
                self.assertIsNone(app.visual.ring_return)
                self.assertAlmostEqual(app.visual.rest_rotation, target)
                app.gate_audio.update(d, None, started+duration, d.spin_fraction(now))
                app.gate_audio.update(d, None, started+duration+1, d.spin_fraction(now))
                self.assertEqual([c.args[0] for c in app.gate_audio.play.call_args_list].count('fail'), 1)
                self.assertIsNone(app.gate_audio.spin_key)

    def test_offworld_rpm_control_requires_alternate_mode_and_idle_gate(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')

        def speed_enabled():
            app.keyboard.draw_keyboard()
            return next(enabled for _, action, enabled in app.keyboard.keyboard_buttons
                        if action == 'cycle_speed')

        self.assertFalse(speed_enabled())
        app.action('cycle_speed', 0)
        self.assertEqual(d.rotation_rpm, 5)
        app.action('toggle_offworld_sgc', 0)
        self.assertTrue(speed_enabled())
        for expected in (10, 15, 20, 30, 5):
            app.action('cycle_speed', 0)
            self.assertEqual(d.rotation_rpm, expected)
        app.action('toggle_offworld_sgc', 0)
        self.assertEqual(d.offworld_dialing_mode, 'rotary')
        app.action(27, 1)
        self.assertFalse(speed_enabled())
        app.action('cycle_speed', 2)
        self.assertEqual(d.rotation_rpm, 5)
        app.stop_gate(3)
        self.assertFalse(speed_enabled())
        app.renderer.draw(5)
        self.assertTrue(speed_enabled())
        app.visual.ring_return = (3, 0, 1, 0)
        self.assertFalse(speed_enabled())

    def test_offworld_center_dome_activates_and_shuts_down_without_extra_button(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')

        def dome():
            app.keyboard.draw_keyboard()
            targets = [(action, enabled) for rect, action, enabled in app.keyboard.keyboard_buttons
                       if isinstance(rect, Dome)]
            self.assertFalse(any(action == 'shutdown' and not isinstance(rect, Dome)
                                 for rect, action, enabled in app.keyboard.keyboard_buttons))
            return targets[0]

        self.assertEqual(dome(), ('shutdown', False))
        app.action(27, 0)
        self.assertEqual(dome(), ('shutdown', True))
        app.action(dome()[0], 1)
        self.assertEqual(d.state, 'idle')
        self.assertTrue(d.load_destination('Earth', 2))
        self.assertEqual(dome(), ('dial', True))
        app.action(dome()[0], 2)
        self.assertEqual(dome(), ('shutdown', True))
        app.update_gate(2+d.cycle_elapsed(7))
        app.update_gate(2+d.cycle_elapsed(7)+.81)
        self.assertEqual(d.state, 'connected')
        self.assertEqual(dome(), ('shutdown', False))
        unlocked = app.visual.activation_unlock_at
        app.update_gate(unlocked)
        self.assertEqual(dome(), ('shutdown', True))
        app.action(dome()[0], unlocked)
        self.assertEqual(d.state, 'idle')

    def test_offworld_dome_waits_for_open_sound_and_one_second(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.load_destination('Earth', 0)
        d.locked = 7
        d.state = 'connected'
        d.connected_at = 10
        app.gate_audio.play = Mock(side_effect=lambda cue, channel, **kw: 2.5 if cue == 'open' else 1)
        app.begin_horizon_open(10)
        self.assertEqual(app.visual.activation_unlock_at, 13.5)
        app.action('shutdown', 12)
        self.assertEqual(d.state, 'connected')
        app.update_gate(13.499)
        app.keyboard.draw_keyboard()
        self.assertFalse(next(enabled for hit, action, enabled in app.keyboard.keyboard_buttons
                              if isinstance(hit, Dome)))
        locked_colors = [app.keyboard.ui.canvas.get_at(point)
                         for point in ((640, 322), (700, 322), (714, 322))]
        self.assertEqual(locked_colors[0], (255, 68, 47, 255))
        app.update_gate(13.5)
        app.keyboard.draw_keyboard()
        self.assertTrue(next(enabled for hit, action, enabled in app.keyboard.keyboard_buttons
                             if isinstance(hit, Dome)))
        self.assertEqual(locked_colors, [app.keyboard.ui.canvas.get_at(point)
                                        for point in ((640, 322), (700, 322), (714, 322))])
        app.action('shutdown', 13.5)
        self.assertEqual(d.state, 'idle')

    def test_offworld_hover_identifies_each_glyph_and_local_origin(self):
        app = Console()
        self.addCleanup(pygame.quit)
        app.dialer.theme = ABYDOS
        app.dialer.set_behavior('dhd')
        for index, glyph_id in enumerate(ABYDOS.keyboard_glyphs):
            radius = 220 if index < 19 else 129.5
            app.keyboard.keyboard_mouse = point(radius, -90+(index % 19)*360/19)
            app.keyboard.draw_keyboard()
            self.assertEqual(app.keyboard.hover, glyph_id)
        app.keyboard.keyboard_mouse = (0, 0)
        app.keyboard.draw_keyboard()
        self.assertIsNone(app.keyboard.hover)

    def test_every_dhd_glyph_pixel_stays_inside_its_own_button(self):
        app = Console()
        self.addCleanup(pygame.quit)
        app.ui.glyph.origin_mark = ABYDOS.origin_mark
        for index, glyph_id in enumerate(ABYDOS.keyboard_glyphs):
            inner, outer = (177, 263) if index < 19 else (88, 171)
            angle = -90+(index % 19)*360/19
            image = fitted_dhd_glyph(app.ui.glyph, glyph_id, (255, 255, 255), inner, outer, angle)
            rect = image.get_rect(center=point((inner+outer)/2, angle))
            button = Sector(inner+3, outer-3, angle)
            for y in range(image.get_height()):
                for x in range(image.get_width()):
                    if image.get_at((x, y)).a:
                        self.assertTrue(button.collidepoint((rect.x+x, rect.y+y)),
                                        f'Glyph {glyph_id} spills outside its button')

    def test_mode_switch_preserves_rendered_ring_orientation(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        for rotation in (23.75, 27*TILE_ANGLE):
            app.visual.rest_rotation = rotation
            app.renderer.draw(10)
            before = pygame.image.tobytes(app.ui.canvas.subsurface((318, 113, 644, 644)), 'RGBA')
            for expected in ('spinning', 'rotary', 'dhd'):
                app.action('toggle_offworld_sgc', 10)
                self.assertEqual(d.offworld_dialing_mode, expected)
                app.renderer.draw(10)
                self.assertAlmostEqual(app.visual.last_ring_rotation, rotation)
                after = pygame.image.tobytes(app.ui.canvas.subsurface((318, 113, 644, 644)), 'RGBA')
                self.assertEqual(before, after)

    def test_spinning_mode_encodes_without_stopping_between_glyphs(self):
        from offworld_state import OffworldVisualState
        d = Dialer(rotation_rpm=10)
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.offworld_dialing_mode = 'spinning'
        v = OffworldVisualState()
        d.select(27, 10)
        self.assertTrue(d.instant_dhd)
        self.assertGreater(v.rotation(d, 10.2), 0)
        self.assertLess(v.rotation(d, 10.2), 12)
        d.update(10.4)
        self.assertEqual((d.locked, d.state), (1, 'dhd_wait'))
        before = v.rotation(d, 11)
        self.assertGreater(before, 0)
        d.select(9, 11)
        self.assertGreater(v.rotation(d, 11.2), before)
        d.update(11.4)
        self.assertEqual(d.locked, 2)
        v.begin_shutdown(d, 12)
        d.reset()
        stopped = v.rotation(d, 12)
        self.assertGreater(v.rotation(d, 20), stopped)
        self.assertAlmostEqual(v.rest_rotation % TILE_ANGLE, 0, places=6)

    def test_spinning_smoothly_stops_after_final_chevron(self):
        from offworld_state import OffworldVisualState
        d = Dialer(rotation_rpm=10)
        d.theme = ABYDOS
        d.set_behavior('dhd')
        d.offworld_dialing_mode = 'spinning'
        d.load_destination('Earth', 0)
        v = OffworldVisualState()
        end = d.cycle_elapsed(7)
        rotation = v.rotation(d, end)
        self.assertAlmostEqual(rotation, (end-.75)*60)
        self.assertAlmostEqual(v.velocity(d, end), 60)
        self.assertAlmostEqual(v.velocity(d, end+.75), 30)
        d.update(end+1)
        self.assertEqual(d.state, 'ready')
        self.assertAlmostEqual(v.rotation(d, end+10), rotation+45)
        self.assertEqual(v.velocity(d, end+10), 0)
        self.assertEqual(v.rotation(d, end+20), rotation+45)

    def test_optional_offworld_ring_rotation_and_abort_complete(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        app.keyboard.draw_keyboard()
        self.assertFalse(d.offworld_sgc_dialing)
        self.assertTrue(any(action == 'toggle_offworld_sgc' and enabled
                            for _, action, enabled in app.keyboard.keyboard_buttons))
        app.action('toggle_offworld_sgc', 0)
        self.assertEqual(d.offworld_dialing_mode, 'spinning')
        app.action('toggle_offworld_sgc', 0)
        self.assertTrue(d.offworld_sgc_dialing)
        app.action(26, 0)
        app.renderer.draw(1)
        self.assertNotEqual(app.visual.last_ring_rotation, 0)
        self.assertEqual(d.locked, 0)
        self.assertEqual(d.state, 'dialing')
        app.keyboard.draw_keyboard()
        self.assertTrue(any(action == 6 and enabled
                            for _, action, enabled in app.keyboard.keyboard_buttons))
        self.assertTrue(d.select(6, 1))
        spin = d.cycle_durations()[0]-2.8
        app.update_gate(spin+2.8)
        self.assertEqual((d.locked, d.state), (1, 'dialing'))
        app.action('toggle_offworld_sgc', 1)
        self.assertTrue(d.offworld_sgc_dialing)
        app.stop_gate(1)
        self.assertIsNotNone(app.visual.ring_return)
        app.renderer.draw(5)
        self.assertIsNone(app.visual.ring_return)
        app.gate_audio.update(d, app.visual.ring_return, 5, d.spin_fraction(5))
        self.assertIsNone(app.gate_audio.spin_key)
        app.action('toggle_offworld_sgc', 5)
        self.assertFalse(d.offworld_sgc_dialing)

    def test_offworld_dome_lights_only_after_activation_with_center_gradient(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        app.keyboard.draw_keyboard()
        idle_color = app.keyboard.ui.canvas.get_at((640, 322))
        idle_edge = app.keyboard.ui.canvas.get_at((700, 322))
        self.assertGreater(idle_color.r, idle_edge.r)
        d.load_destination('Earth', 0)
        app.keyboard.draw_keyboard()
        self.assertEqual(app.keyboard.ui.canvas.get_at((640, 322)), idle_color)
        self.assertTrue(d.activate(0))
        app.keyboard.draw_keyboard()
        pressed_color = app.keyboard.ui.canvas.get_at((640, 322))
        self.assertGreater(pressed_color.r, idle_color.r)
        self.assertGreater(pressed_color.r, app.keyboard.ui.canvas.get_at((700, 322)).r)
        end = d.cycle_elapsed(len(d.sequence))
        app.update_gate(end)
        app.update_gate(end+1)
        self.assertEqual(d.state, 'connected')
        app.keyboard.draw_keyboard()
        active_color = app.keyboard.ui.canvas.get_at((640, 322))
        self.assertGreater(active_color.r, idle_color.r)
        self.assertGreater(sum(active_color[:3]), sum(idle_color[:3]))
        app.stop_gate(end+2)
        app.keyboard.draw_keyboard()
        self.assertEqual(app.keyboard.ui.canvas.get_at((640, 322)), idle_color)

    def test_offworld_mid_dial_shutdown_stops_roll_and_accepts_new_input(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.theme = ABYDOS
        d.set_behavior('dhd')
        roll = Mock()
        app.gate_audio.channels['roll'] = roll
        self.assertTrue(d.select(26, 0))
        app.gate_audio.update(d, None, 1, d.spin_fraction(1))
        roll.play.assert_called_once()
        roll.stop.reset_mock()
        app.stop_gate(1)
        roll.stop.assert_called_once()
        self.assertIsNone(app.gate_audio.spin_key)
        self.assertIsNone(app.visual.ring_return)
        self.assertFalse(app.visual.busy)
        roll.play.reset_mock()
        for now in (2, 5, 20):
            app.update_gate(now)
            app.renderer.draw(now)
            app.gate_audio.update(d, app.visual.ring_return, now, d.spin_fraction(now))
        roll.play.assert_not_called()
        app.action(6, 21)
        self.assertEqual(d.selected, [6])
        app.gate_audio.update(d, None, 21, d.spin_fraction(21))
        roll.play.assert_called_once()

    def test_offworld_rejects_long_addresses_and_resets_arrival_length(self):
        d = Dialer()
        self.assertTrue(d.set_symbol_count(9))
        d.destination, d.state = 'ABYDOS', 'connected'
        self.assertTrue(d.travel())
        self.assertEqual(d.symbol_count, 7)
        d.update(1.5)
        for count in (8, 9):
            self.assertFalse(d.set_symbol_count(count))
            self.assertEqual(d.symbol_count, 7)
        for name in ('Atlantis', 'Destiny'):
            self.assertFalse(d.load_destination(name))
            self.assertEqual((d.state, d.symbol_count, d.selected), ('idle', 7, []))
        self.assertTrue(d.load_destination('Earth'))

    def test_travel_requires_connection_and_supported_destination(self):
        d = Dialer()
        d.destination = 'ABYDOS'
        self.assertFalse(d.travel())
        d.state = 'connected'
        self.assertTrue(d.travel())
        self.assertEqual(d.theme, ABYDOS)
        self.assertEqual((d.state, d.behavior, d.selected), ('connected', 'dhd', []))
        self.assertFalse(d.travel())
        d.update(1.5)
        self.assertFalse(d.set_behavior('current'))
        self.assertFalse(d.select(ABYDOS.omitted_glyph))
        d.destination, d.state = 'CHULAK', 'connected'
        self.assertFalse(d.travel())
        self.assertEqual(d.theme, ABYDOS)
        d.destination = 'EARTH'
        self.assertTrue(d.travel())
        self.assertEqual((d.theme, d.behavior), (EARTH, 'current'))

    def test_palette_bounds_and_keyboard_inventory(self):
        self.assertEqual(len(DHD_OUTER_RING), 19)
        self.assertEqual(len(DHD_INNER_RING), 19)
        self.assertEqual(set(DHD_OUTER_RING + DHD_INNER_RING), set(range(39)) - {12})
        self.assertEqual(ABYDOS.keyboard_glyphs[:19], DHD_OUTER_RING)
        self.assertEqual(ABYDOS.keyboard_glyphs[15], 0)
        self.assertEqual(ABYDOS.keyboard_glyphs[19:],
                         (27, 9, 32, 38, 25, 22, 17, 13, 16, 1, 24, 35, 7, 26, 30, 14, 34, 29, 15))
        self.assertEqual(ABYDOS.keyboard_glyphs[:19],
                         (37, 5, 28, 23, 33, 11, 36, 10, 20, 2, 3, 19, 8, 4, 31, 0, 18, 21, 6))
        with self.assertRaises(ValueError):
            replace(ABYDOS, dhd_color=(255, 0, 0))
        self.assertEqual(len(set(ABYDOS.keyboard_glyphs)), 38)
        self.assertIn(0, ABYDOS.keyboard_glyphs)

    def test_annular_hit_targets(self):
        for index in range(19):
            angle = -90+index*360/19
            hit = Sector(177, 263, angle)
            self.assertTrue(hit.collidepoint(point(220, angle)))
            self.assertFalse(hit.collidepoint(point(220, angle+360/19)))
            self.assertFalse(hit.collidepoint((640, 322)))
        self.assertTrue(Dome().collidepoint((640, 322)))
        self.assertFalse(Dome().collidepoint((715, 322)))

    def test_arrival_keyboard_and_return_dial(self):
        app = Console()
        self.addCleanup(pygame.quit)
        d = app.dialer
        d.destination, d.state = 'ABYDOS', 'connected'
        app.action('travel', 0)
        self.assertIs(app.renderer.visual, app.visual)
        self.assertFalse(app.keyboard.keyboard_visible)
        self.assertIsNone(app.keyboard.keyboard_window)
        app.keyboard.draw_keyboard()
        self.assertEqual(app.keyboard.ui.canvas.get_size(), (1280, 680))
        modes = {action[1]: enabled for _, action, enabled in app.keyboard.keyboard_buttons
                 if isinstance(action, tuple) and action[0] == 'mode'}
        self.assertEqual(modes, {})
        keys = [(rect, action) for rect, action, enabled in app.keyboard.keyboard_buttons if isinstance(action, int)]
        self.assertEqual(len(keys), 38)
        app.update_gate(1.5)
        entry_time = 1.5+app.gate_audio.close_duration+.01
        app.update_gate(entry_time)
        for glyph_id in (27, 25, 4, 35, 10, 28, 0):
            self.assertTrue(d.select(glyph_id, entry_time))
        self.assertTrue(d.activate(entry_time))
        end = entry_time+d.cycle_elapsed(len(d.sequence))
        d.update(end)
        d.update(end+1)
        self.assertEqual((d.state, d.destination), ('connected', 'EARTH'))
        app.action('travel', end+1)
        self.assertEqual(d.theme, EARTH)
        self.assertEqual(app.ui.glyph.origin_mark, 'earth')
        self.assertEqual(app.keyboard.ui.canvas.get_size(), (1280, 240))


if __name__ == '__main__':
    unittest.main()
