from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import widget_restart


class RestartTests(unittest.TestCase):
    def test_service_restart_runs_in_an_independent_unit(self):
        unit = widget_restart.APP_ID + '.service'
        with patch.object(Path, 'read_text', return_value='0::/app.slice/' + unit + '\n'), \
                patch('widget_restart.shutil.which', side_effect=lambda name: '/usr/bin/' + name), \
                patch('widget_restart.subprocess.Popen') as popen:
            self.assertTrue(widget_restart.service_restart())
            command = popen.call_args.args[0]
            self.assertEqual(command[:3], ['/usr/bin/systemd-run', '--user', '--collect'])
            self.assertTrue(command[3].startswith('--unit=emberbox-restart-'))
            self.assertEqual(command[4:], ['/usr/bin/systemctl', '--user', 'restart', unit])

    def test_direct_launch_never_restarts_an_unrelated_service(self):
        with patch.object(Path, 'read_text', return_value='0::/app.slice/some-other.service\n'), \
                patch('widget_restart.subprocess.Popen') as popen:
            self.assertFalse(widget_restart.service_restart())
            popen.assert_not_called()

    def test_direct_restart_replaces_process_without_starting_a_second_widget(self):
        with patch('widget_restart.os.execv') as execute, patch.object(sys, 'argv', ['widget.py']):
            widget_restart.replace_process(Path('/tmp/example/widget.py'))
            execute.assert_called_once_with(sys.executable, [sys.executable, '/tmp/example/widget.py'])
