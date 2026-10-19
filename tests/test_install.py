import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = 'emberbox-audio'


class InstallerTests(unittest.TestCase):
    def test_isolated_install_and_uninstall_keep_preferences(self):
        with tempfile.TemporaryDirectory(prefix='emberbox-install-') as folder:
            folder = Path(folder)
            env = dict(os.environ, XDG_CONFIG_HOME=str(folder/'config'), XDG_DATA_HOME=str(folder/'data with spaces'))
            command = [sys.executable, str(ROOT/'tools/install.py')]
            options = ['--no-systemd', '--bin-dir', str(folder/'bin')]
            result = subprocess.run(command+['install', '--skip-check', *options], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            target=folder/'data with spaces'/APP
            self.assertTrue((target/'src/widget.py').exists())
            self.assertTrue((target/'src/apple_web_host/main.cjs').exists())
            self.assertTrue((target/'tools/apple_player.py').exists())
            self.assertTrue((target/'docs/APPLE_MUSIC.ru.md').exists())
            self.assertTrue((target/'.emberbox-install.json').exists())
            self.assertNotIn('__pycache__', [p.name for p in target.rglob('*')])
            preference=folder/'config'/APP/'prefs.json'
            preference.parent.mkdir(parents=True)
            preference.write_text('{"keep": true}')
            result=subprocess.run(command+['uninstall', *options],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertFalse(target.exists())
            self.assertFalse((folder/'bin'/APP).exists())
            self.assertTrue(preference.exists())

    def test_unmanaged_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='emberbox-unmanaged-') as folder:
            folder=Path(folder)
            target=folder/'data'/APP
            target.mkdir(parents=True)
            sentinel=target/'mine.txt';sentinel.write_text('keep')
            env=dict(os.environ,XDG_DATA_HOME=str(folder/'data'),XDG_CONFIG_HOME=str(folder/'config'))
            result=subprocess.run([sys.executable,str(ROOT/'tools/install.py'),'install','--skip-check','--no-systemd','--bin-dir',str(folder/'bin')],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(sentinel.read_text(),'keep')
