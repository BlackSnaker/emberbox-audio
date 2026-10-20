from pathlib import Path
import json
import os
import sys
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from desktop_window import Area, clamp_position, desktop_mode, usable_area
from gui_session import systemd_environment
import desktop_launch


class DesktopWindowTests(unittest.TestCase):
    def test_kwin_uses_managed_alpha_surface_even_with_missing_desktop_environment(self):
        self.assertEqual(desktop_mode({}, 'KWin'), 'normal')
        self.assertEqual(desktop_mode({'XDG_CURRENT_DESKTOP': 'KDE'}), 'normal')
        self.assertEqual(desktop_mode({'XDG_CURRENT_DESKTOP': 'KDE:Plasma'}), 'normal')
        self.assertEqual(desktop_mode({'DESKTOP_SESSION': 'plasmawayland'}), 'normal')
        self.assertEqual(desktop_mode({'XDG_CURRENT_DESKTOP': 'GNOME'}, 'GNOME Shell'), 'desktop')
        self.assertEqual(desktop_mode({'XDG_CURRENT_DESKTOP': 'notkde'}), 'desktop')
        self.assertEqual(desktop_mode({'EMBERBOX_DESKTOP_MODE': 'desktop'}, 'KWin'), 'desktop')
        self.assertEqual(desktop_mode({'EMBERBOX_DESKTOP_MODE': 'normal'}, 'Mutter'), 'normal')

    def test_panels_and_disconnected_monitor_positions_are_respected(self):
        # A negative-origin secondary monitor has a panel on its left and bottom.
        monitor = SimpleNamespace(get_geometry=lambda: Area(-1920, -160, 1920, 1080),
                                  get_workarea=lambda: Area(-1860, -160, 1860, 1020))
        area = usable_area(monitor)
        self.assertEqual(area, Area(-1860, -160, 1860, 1020))
        self.assertEqual(clamp_position(-2500, -500, 460, 400, area), (-1850, -150))
        self.assertEqual(clamp_position(3000, 3000, 460, 400, area), (-470, 450))
        # An over-height library never gets shoved above the usable desktop.
        self.assertEqual(clamp_position(-1800, -300, 460, 1400, area)[1], -160)
        broken = SimpleNamespace(get_geometry=lambda: Area(0, 0, 1920, 1080),
                                 get_workarea=lambda: Area(-2000, 0, 1000, 1000))
        self.assertEqual(usable_area(broken), Area(0, 0, 1920, 1080))


class GuiSessionTests(unittest.TestCase):
    environment = {'DISPLAY': ':fixture', 'XAUTHORITY': '/private authority/file',
                   'WAYLAND_DISPLAY': 'wayland-fixture', 'XDG_RUNTIME_DIR': '/private/runtime',
                   'XDG_CONFIG_HOME': '/private/config', 'XDG_CACHE_HOME': '/private/cache',
                   'XDG_DATA_HOME': '/private/data',
                   'XDG_CURRENT_DESKTOP': 'KDE', 'GDK_BACKEND': 'x11',
                   'API_TOKEN': 'must-not-be-forwarded', 'AWS_SECRET_ACCESS_KEY': 'also-private'}

    def assert_gui_environment(self, command):
        self.assertIn('--setenv=DISPLAY=:fixture', command)
        self.assertIn('--setenv=XAUTHORITY=/private authority/file', command)
        self.assertIn('--setenv=WAYLAND_DISPLAY=wayland-fixture', command)
        self.assertIn('--setenv=XDG_CURRENT_DESKTOP=KDE', command)
        self.assertIn('--setenv=XDG_CONFIG_HOME=/private/config', command)
        self.assertIn('--setenv=XDG_CACHE_HOME=/private/cache', command)
        self.assertIn('--setenv=XDG_DATA_HOME=/private/data', command)
        self.assertFalse(any('must-not-be-forwarded' in item or 'also-private' in item for item in command))

    def test_only_display_variables_are_forwarded_as_individual_arguments(self):
        flags = systemd_environment(self.environment)
        self.assert_gui_environment(flags)
        self.assertEqual(systemd_environment({'DISPLAY': ':1\nINJECT=bad'}), [])

    def test_independent_application_gets_the_callers_session_without_shell_interpolation(self):
        with patch.dict(os.environ, self.environment, clear=True), \
             patch('desktop_launch.shutil.which', return_value='/usr/bin/systemd-run'), \
             patch.object(Path, 'exists', return_value=True), \
             patch('desktop_launch.subprocess.Popen') as launch:
            desktop_launch.launch(['/fixture/app', 'a b', '$(not-a-shell)'])
        command = launch.call_args.args[0]
        self.assert_gui_environment(command)
        self.assertEqual(command[-3:], ['/fixture/app', 'a b', '$(not-a-shell)'])

    def test_apple_and_yandex_engines_get_the_same_current_display(self):
        import apple_web
        import yandex_web
        config = {'runtime': '/fixture/engine', 'cdm_module': '/fixture/cdm'}
        for module, cls in ((apple_web, apple_web.AppleWeb), (yandex_web, yandex_web.YandexWeb)):
            with self.subTest(engine=module.__name__):
                app = cls.__new__(cls)
                app.start_lock = threading.Lock()
                app.bridge = SimpleNamespace(path=Path('/private/player.sock'))
                with patch.dict(os.environ, self.environment, clear=True), \
                     patch.object(Path, 'read_text', return_value=json.dumps(config)), \
                     patch.object(module.subprocess, 'run', side_effect=[SimpleNamespace(returncode=1),
                                                                          SimpleNamespace(returncode=0)]) as launch:
                    app._start_engine()
                self.assert_gui_environment(launch.call_args.args[0])


class KWinBridgeTests(unittest.TestCase):
    def test_script_only_changes_our_desktop_role_and_unloads_with_its_window(self):
        from kwin_desktop import script_source
        fixture = '''const calls=[]; let added;
          function window(name,role){return {resourceName:name,windowRole:role,
            onAllDesktops:false,closed:{connect(fn){this.callback=fn;}}};}
          const own=window('emberbox-audio','desktop-widget');
          const fullscreen=window('emberbox-audio','');
          const other=window('another-app','desktop-widget');
          const workspace={windowAdded:{connect(fn){added=fn;}},windowList(){return [own,fullscreen,other];}};
          function callDBus(...args){calls.push(args);}
        '''
        checks = '''
          if (!own.onAllDesktops || fullscreen.onAllDesktops || other.onAllDesktops) throw Error('Scope exceeded');
          const later=window('emberbox-audio','desktop-widget');added(later);
          if (!later.onAllDesktops) throw Error('Remapped widget missed');
          own.closed.callback();
          if (calls.length!==1 || calls[0][3]!=='unloadScript' || calls[0][4]!=='fixture-plugin') throw Error('Missing cleanup');
        '''
        subprocess.run(['node', '-e', fixture+script_source('fixture-plugin')+checks], check=True,
                       capture_output=True, text=True, timeout=5)

    def test_runtime_script_is_private_and_cleaned_when_kwin_is_unavailable(self):
        import kwin_desktop
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'XDG_RUNTIME_DIR': folder}), \
                 patch('kwin_desktop.Gio.bus_get'):
                bridge = kwin_desktop.KWinDesktop()
            self.assertEqual(bridge.path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(bridge.loaded)
            bridge.close()
            self.assertFalse(bridge.path.exists())
