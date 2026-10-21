import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import json
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = 'emberbox-audio'
sys.path.insert(0,str(ROOT/'tools'))
import install as installer
import dependencies
import launch as app_launch
from installer_ui import Terminal


class InstallerTests(unittest.TestCase):
    def test_desktop_shortcut_actions_survive_update_and_are_removed_on_uninstall(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            options=['--skip-check','--no-systemd','--bin-dir',str(base/'bin')]
            with patch.dict(os.environ,{'XDG_DATA_HOME':str(base/'data'),'XDG_CONFIG_HOME':str(base/'config')}),\
                 patch.object(installer,'desktop_directory',return_value=base/'Desktop with spaces'),\
                 redirect_stdout(io.StringIO()):
                self.assertEqual(installer.main(['install',*options,'--desktop-shortcut']),0)
                shortcut=base/'Desktop with spaces'/f'{APP}.desktop'
                self.assertTrue(shortcut.stat().st_mode&0o111)
                for action in ('Show','Hide','Quit'):self.assertIn('[Desktop Action '+action+']',shortcut.read_text())
                self.assertEqual(installer.main(['install',*options]),0)
                self.assertTrue(shortcut.exists())
                self.assertEqual(installer.main(['uninstall',*options]),0)
                self.assertFalse(shortcut.exists())

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

    def test_conflicting_read_only_options_are_rejected_before_changes(self):
        with patch.object(installer,'stage_payload') as stage,patch.object(installer,'remove') as remove:
            for options in (['install','--check','--skip-check'],['uninstall','--check']):
                with redirect_stdout(io.StringIO()),patch('sys.stderr',new_callable=io.StringIO),self.assertRaises(SystemExit) as error:
                    installer.main(options)
                self.assertEqual(error.exception.code,2)
            stage.assert_not_called();remove.assert_not_called()

    def test_read_only_check_does_not_create_directories_or_install_anything(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            report=SimpleNamespace(python=sys.executable,distribution=SimpleNamespace(name='Fixture Linux'),
                                   checks={'python':True,'gtk3':False},ready=False)
            plan=SimpleNamespace(supported=True,system_commands=(('package-manager','install','gtk'),),
                                 commands=(('package-manager','install','gtk'),))
            env={'XDG_DATA_HOME':str(base/'data'),'XDG_CONFIG_HOME':str(base/'config')}
            with patch.dict(os.environ,env),patch.object(dependencies,'inspect',return_value=report),\
                 patch.object(dependencies,'build_plan',return_value=plan),patch.object(dependencies,'provision') as provision,redirect_stdout(io.StringIO()):
                code=installer.main(['install','--check','--no-systemd','--bin-dir',str(base/'bin')])
            self.assertEqual(code,1);provision.assert_not_called()
            self.assertFalse((base/'data').exists());self.assertFalse((base/'config').exists())

    def test_failed_dependency_install_leaves_no_partial_application(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            report=SimpleNamespace(python=sys.executable,distribution=SimpleNamespace(name='Fixture Linux'),
                                   checks={'python':True,'numpy':False},ready=False)
            plan=SimpleNamespace(supported=True,system_commands=(),commands=())
            with patch.dict(os.environ,{'XDG_DATA_HOME':str(base/'data'),'XDG_CONFIG_HOME':str(base/'config')}),\
                 patch('install.os.geteuid',return_value=1000),\
                 patch.object(dependencies,'inspect',return_value=report),patch.object(dependencies,'build_plan',return_value=plan),\
                 patch.object(dependencies,'provision',side_effect=dependencies.ProvisionCancelled('Cancelled')),redirect_stdout(io.StringIO()):
                code=installer.main(['install','--no-systemd','--bin-dir',str(base/'bin')])
            self.assertEqual(code,130)
            self.assertFalse((base/'data'/APP).exists());self.assertFalse((base/'bin').exists())

    def test_failed_update_restores_working_player_and_desktop_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            env={'XDG_DATA_HOME':str(base/'data'),'XDG_CONFIG_HOME':str(base/'config')}
            options=['install','--skip-check','--no-systemd','--autostart','--bin-dir',str(base/'bin')]
            with patch.dict(os.environ,env),redirect_stdout(io.StringIO()):
                self.assertEqual(installer.main(options),0)
                target=base/'data'/APP
                player=target/'src/widget.py';player.write_text('# Previous working version\n'+player.read_text())
                original=player.read_bytes()
                desktop=base/'data/applications'/f'{APP}.desktop';desktop_before=desktop.read_bytes()
                manifest=(target/'.emberbox-install.json').read_bytes()
                write=Path.write_text
                def fail_desktop(path,*args,**kwargs):
                    if path==desktop:raise OSError('Disk full during desktop integration')
                    return write(path,*args,**kwargs)
                with patch.object(Path,'write_text',fail_desktop):self.assertEqual(installer.main(options),1)
                self.assertEqual(player.read_bytes(),original)
                self.assertEqual(desktop.read_bytes(),desktop_before)
                self.assertEqual((target/'.emberbox-install.json').read_bytes(),manifest)
                self.assertTrue((base/'config/autostart'/f'{APP}.desktop').exists())

    def test_dependency_failure_during_update_preserves_previous_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            env={'XDG_DATA_HOME':str(base/'data'),'XDG_CONFIG_HOME':str(base/'config')}
            options=['install','--no-systemd','--bin-dir',str(base/'bin')]
            with patch.dict(os.environ,env),redirect_stdout(io.StringIO()):
                self.assertEqual(installer.main([*options,'--skip-check']),0)
                target=base/'data'/APP
                runtime=target/'runtime';runtime.mkdir()
                sentinel=runtime/'working-package';sentinel.write_text('keep')
                manifest=(target/'.emberbox-install.json').read_bytes()
                player=(target/'src/widget.py').read_bytes()
                report=SimpleNamespace(python=sys.executable,distribution=SimpleNamespace(name='Fixture Linux'),
                    checks={'numpy':False},missing=('numpy',),ready=False)
                def plan_report(report,*,venv_dir,**kwargs):
                    self.assertNotEqual(venv_dir,runtime)
                    self.assertTrue(venv_dir.name.startswith('runtime-'))
                    return SimpleNamespace(supported=True,system_commands=(),commands=(),venv_dir=venv_dir)
                def fail_provision(plan,**kwargs):
                    plan.venv_dir.mkdir();(plan.venv_dir/'partial').write_text('incomplete')
                    raise dependencies.DependencyError('Download interrupted')
                with patch.object(dependencies,'inspect',return_value=report),\
                     patch.object(dependencies,'build_plan',side_effect=plan_report),\
                     patch.object(dependencies,'provision',side_effect=fail_provision),\
                     patch('install.os.geteuid',return_value=1000):
                    self.assertEqual(installer.main(options),1)
                self.assertEqual(sentinel.read_text(),'keep')
                self.assertEqual((target/'.emberbox-install.json').read_bytes(),manifest)
                self.assertEqual((target/'src/widget.py').read_bytes(),player)
                self.assertEqual(list(target.glob('runtime-*')),[])

    def test_session_environment_is_private_scoped_and_not_shell_expanded(self):
        with tempfile.TemporaryDirectory() as folder:
            env={'XDG_RUNTIME_DIR':folder,'DISPLAY':':73','XAUTHORITY':'/tmp/a "quoted" file',
                 'LANG':'ru_RU.UTF-8','UNRELATED_SECRET':'must-not-copy'}
            path=app_launch.session_file(env)
            value=path.read_text()
            self.assertIn('DISPLAY=":73"',value)
            self.assertIn('\\"quoted\\"',value)
            self.assertNotIn('UNRELATED_SECRET',value)
            self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_service_failure_falls_back_to_same_python_and_runtime_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'app';root.mkdir()
            (root/'.emberbox-install.json').write_text(json.dumps({'python':sys.executable,'systemd':True}))
            with patch.object(app_launch,'ROOT',root),patch.dict(os.environ,{'DISPLAY':':73','XDG_RUNTIME_DIR':folder}),\
                 patch.object(app_launch.shutil,'which',return_value='/usr/bin/systemctl'),\
                 patch.object(app_launch.subprocess,'run',return_value=SimpleNamespace(returncode=1)),\
                 patch.object(app_launch.os,'execve',side_effect=SystemExit(0)) as execute:
                with self.assertRaises(SystemExit):app_launch.main()
            executable,argv,environment=execute.call_args.args
            self.assertEqual(executable,sys.executable)
            self.assertEqual(argv[1],str(root/'src/widget.py'))
            self.assertEqual(environment['GDK_BACKEND'],'x11')
            self.assertTrue(environment['PATH'].startswith(str(Path(sys.executable).parent)+os.pathsep))

    def test_terminal_respects_no_color_plain_and_russian_locale(self):
        class TTY(io.StringIO):
            def isatty(self):return True
        for options in ({'environ':{'TERM':'xterm','NO_COLOR':'1'}},{'plain':True,'environ':{'TERM':'xterm'}}):
            stream=TTY();ui=Terminal(stream=stream,language='ru',**options);ui.banner('test');ui.item('GTK 3')
            self.assertNotIn('\x1b',stream.getvalue());self.assertIn('Немного тепла',stream.getvalue())
        stream=TTY();ui=Terminal(stream=stream,environ={'TERM':'xterm','LANG':'ru_RU.UTF-8'})
        ui.banner('test');self.assertIn('\x1b[38;2;',stream.getvalue())
