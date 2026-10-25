"""Dependency planning is read-only; provisioning uses only an explicit plan."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import dependencies as deps


def report(*missing, family='arch', installed=(), youtube=True):
    checks = dict.fromkeys(deps.LABELS, True)
    if not youtube:
        for key in ('libmpv','python_mpv','yt_dlp','ejs','js_runtime'):checks.pop(key)
    checks.update(dict.fromkeys(missing, False))
    return deps.Report('/usr/bin/python3', deps.Distribution(family, family.title(), family, True),
                       checks, versions={'python':'3.12.5'}, venv_available=True,
                       ensurepip_available=True, installed_packages=installed, youtube=youtube)


class DependencyTests(unittest.TestCase):
    def test_os_release_is_data_and_derivatives_keep_arch_family(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'os-release'
            sentinel = Path(folder)/'must-not-exist'
            source.write_text('ID=lunaos\nID_LIKE="arch"\nPRETTY_NAME="Luna OS"\n'
                              f'HOME_URL="$(touch {sentinel})"\n')
            value = deps.detect_distribution(source, immutable_paths=())
            self.assertEqual((value.id,value.family,value.name), ('lunaos','arch','Luna OS'))
            self.assertTrue(value.supported)
            self.assertFalse(sentinel.exists())

    def test_immutable_and_unknown_never_select_a_guessed_manager(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'os-release'
            for contents in ('ID=fedora\nVARIANT_ID=silverblue\n', 'ID=unlisted\n'):
                source.write_text(contents)
                value = deps.detect_distribution(source, immutable_paths=())
                current = report('gi');current.distribution=value
                plan = deps.build_plan(current, venv_dir=Path(folder)/'runtime')
                self.assertFalse(plan.supported)
                self.assertTrue(plan.reason)
                self.assertEqual(plan.commands, ())
                runner = unittest.mock.Mock()
                with self.assertRaises(deps.DependencyError):deps.provision(plan, runner=runner)
                runner.assert_not_called()
            source.write_text('ID=fedora\n')
            marker = Path(folder)/'ostree-booted';marker.touch()
            self.assertFalse(deps.detect_distribution(source, immutable_paths=(marker,)).supported)

    def test_ready_host_has_no_mutation_even_on_unsupported_distribution(self):
        current = report()
        current.distribution=deps.Distribution('nixos','NixOS',supported=False,reason='Manual packaging')
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)/'runtime'
            plan = deps.build_plan(current, venv_dir=runtime)
            self.assertTrue(plan.ready)
            self.assertEqual(plan.commands, ())
            with patch('dependencies.subprocess.run') as run:
                result=deps.provision(plan)
                run.assert_not_called()
            self.assertEqual(result.python, '/usr/bin/python3')
            self.assertFalse(runtime.exists())

    def test_each_distribution_installs_only_missing_clients_not_audio_daemons(self):
        expected = {'arch': ('pipewire','libpulse'), 'debian': ('pipewire-bin','pulseaudio-utils'),
                    'fedora': ('pipewire-utils','pulseaudio-utils'), 'opensuse': ('pipewire-tools','pulseaudio-utils')}
        for family, packages in expected.items():
            with self.subTest(family=family), patch('dependencies.shutil.which', return_value='/package-manager'):
                plan = deps.build_plan(report('pipewire','pactl',family=family),venv_dir='/unused/runtime',sudo=True)
                self.assertEqual(plan.packages,packages)
                self.assertEqual(plan.python_commands,())
                command=plan.system_commands[0]
                self.assertEqual(command[0],'sudo')
                self.assertNotIn('--noconfirm',command)
                self.assertNotIn('-y',command)
                self.assertNotIn('--non-interactive',command)
                self.assertTrue(all(value not in command for value in ('systemctl','enable','restart','upgrade','pipewire-pulse','pipewire-pulseaudio','spotify','firefox','chromium')))
        # Missing Gtk and GdkX11 share one package; installed PyGObject is kept.
        with patch('dependencies.shutil.which',return_value='/pacman'):
            plan=deps.build_plan(report('gtk3','gdkx11',installed=('python-gobject',)),venv_dir='/unused/runtime')
        self.assertEqual(plan.packages,('gtk3',))

    def test_optional_spatial_compiler_uses_the_distribution_package(self):
        for family,package in (('arch','gcc'),('debian','g++'),('fedora','gcc-c++'),('opensuse','gcc-c++')):
            with patch('dependencies.shutil.which',return_value='/package-manager'):
                plan=deps.build_plan(report('cxx',family=family),venv_dir='/unused/runtime')
            self.assertEqual(plan.packages,(package,))
            self.assertFalse(any('libav' in value for value in plan.packages))
    def test_explicit_yes_is_the_only_way_to_disable_native_confirmation(self):
        for family in deps.MANAGERS:
            ordinary=deps.package_command(family,('fixture-package',),sudo=True)
            unattended=deps.package_command(family,('fixture-package',),sudo=True,yes=True)
            self.assertNotEqual(ordinary,unattended)
            self.assertTrue(any(value in unattended for value in ('-y','--noconfirm','--non-interactive')))
            self.assertTrue(all(value not in ordinary for value in ('-y','--noconfirm','--non-interactive')))
            self.assertEqual(unattended[-1],'fixture-package')

    def test_old_python_blocks_without_major_system_upgrade(self):
        current=report('python','pillow')
        current.versions['python']='3.9.2'
        plan=deps.build_plan(current,venv_dir='/unused/runtime')
        self.assertFalse(plan.supported)
        self.assertIn('3.10',plan.reason)
        self.assertEqual(plan.commands,())

    def test_ubuntu_jammy_uses_its_actual_libmpv_soname_package(self):
        current=report('libmpv',family='debian')
        current.distribution=deps.Distribution('ubuntu','Ubuntu 22.04','debian',True,version='22.04',codename='jammy')
        with patch('dependencies.shutil.which',return_value='/apt-get'):
            plan=deps.build_plan(current,venv_dir='/unused/runtime')
        self.assertEqual(plan.packages,('libmpv1',))

    def test_missing_python_extras_use_only_isolated_binary_wheels(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'runtime'
            plan=deps.build_plan(report('pillow','websocket','ejs','js_runtime'),venv_dir=runtime)
            self.assertEqual(plan.system_commands,())
            self.assertEqual(plan.python,str(runtime/'bin/python'))
            self.assertEqual(plan.pip_requirements,('Pillow>=10','websocket-client>=1.6','yt-dlp[default]>=2025.11.12','deno>=2.3'))
            create,pip=plan.python_commands
            self.assertIn('--system-site-packages',create)
            self.assertEqual(pip[0],str(runtime/'bin/python'))
            self.assertIn('--isolated',pip)
            self.assertIn('--only-binary=:all:',pip)
            self.assertNotIn('--user',pip)
            self.assertNotIn('--break-system-packages',pip)
            self.assertNotIn('sudo',pip)
            self.assertFalse(runtime.exists())

    def test_unmanaged_venv_is_not_overwritten_or_used_for_pip(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'runtime';runtime.mkdir()
            (runtime/'important').write_text('keep')
            plan=deps.build_plan(report('pillow'),venv_dir=runtime)
            self.assertFalse(plan.supported)
            self.assertIn('unmanaged',plan.reason)
            self.assertEqual((runtime/'important').read_text(),'keep')

    def test_installed_but_broken_native_packages_are_not_reinstalled(self):
        current=report('gi',installed=('python-gobject',))
        plan=deps.build_plan(current,venv_dir='/unused/runtime')
        self.assertFalse(plan.supported)
        self.assertIn('Repair',plan.reason)
        self.assertEqual(plan.commands,())

    def test_manager_cancellation_or_failure_stops_before_runtime_creation(self):
        for result,error in ((SimpleNamespace(returncode=130),deps.ProvisionCancelled),
                             (SimpleNamespace(returncode=1),deps.DependencyError),
                             (KeyboardInterrupt(),deps.ProvisionCancelled)):
            with self.subTest(result=result),tempfile.TemporaryDirectory() as folder,patch('dependencies.shutil.which',return_value='/pacman'):
                runtime=Path(folder)/'runtime'
                plan=deps.build_plan(report('gi','pillow'),venv_dir=runtime,sudo=True)
                runner=unittest.mock.Mock(side_effect=result if isinstance(result,BaseException) else None,return_value=result)
                with self.assertRaises(error):deps.provision(plan,runner=runner)
                self.assertEqual(runner.call_count,1)
                self.assertFalse(runtime.exists())

    def test_provision_rechecks_and_drops_extras_satisfied_by_native_packages(self):
        with tempfile.TemporaryDirectory() as folder,patch('dependencies.shutil.which',return_value='/apt-get'):
            before=report('gtk3','pillow',family='debian')
            ready=report(family='debian')
            plan=deps.build_plan(before,venv_dir=Path(folder)/'runtime')
            runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0))
            with patch('dependencies.inspect',return_value=ready):
                result=deps.provision(plan,runner=runner)
            self.assertEqual(result.python,ready.python)
            self.assertEqual(runner.call_count,1)
            self.assertNotIn('pip',runner.call_args.args[0])
            self.assertFalse((Path(folder)/'runtime').exists())

    def test_provision_keeps_system_pip_unreachable_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'runtime'
            before=report('pillow')
            complete=report();complete.python=str(runtime/'bin/python')
            plan=deps.build_plan(before,venv_dir=runtime)
            calls=[]
            def runner(command,**kwargs):
                calls.append(command)
                if 'venv' in command:
                    (runtime/'bin').mkdir(exist_ok=True)
                    (runtime/'bin/python').write_text('fixture interpreter')
                    (runtime/'pyvenv.cfg').write_text('include-system-site-packages = true\n')
                if kwargs.get('capture_output'):
                    return SimpleNamespace(returncode=0,stdout=json.dumps({'checks':{},'prefix':str(runtime),'base_prefix':'/usr'}))
                return SimpleNamespace(returncode=0)
            with patch('dependencies.inspect',side_effect=[before,complete]):
                installed=deps.provision(plan,runner=runner)
            pip=[command for command in calls if 'pip' in command]
            self.assertEqual(len(pip),1)
            self.assertEqual(pip[0][0],str(runtime/'bin/python'))
            self.assertIn('Pillow>=10',pip[0])
            self.assertEqual(installed.python,str(runtime/'bin/python'))
            again=deps.build_plan(complete,venv_dir=runtime)
            self.assertTrue(again.ready)
            self.assertEqual(again.commands,())
            self.assertTrue((runtime/deps.MARKER).is_file())

    def test_fake_venv_never_reaches_system_pip(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'runtime';runtime.mkdir();(runtime/'bin').mkdir()
            (runtime/'bin/python').write_text('fixture')
            (runtime/'pyvenv.cfg').write_text('include-system-site-packages = true\n')
            (runtime/deps.MARKER).write_text('{}')
            before=report('pillow')
            plan=deps.build_plan(before,venv_dir=runtime)
            runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'checks':{},'prefix':'/usr','base_prefix':'/usr'})))
            with patch('dependencies.inspect',return_value=before),self.assertRaisesRegex(deps.DependencyError,'outside'):
                deps.provision(plan,runner=runner)
            self.assertTrue(all('pip' not in call.args[0] for call in runner.call_args_list))

    def test_inspect_is_read_only_preserves_venv_path_and_xwayland_is_conditional(self):
        python='/managed/runtime/bin/python'
        payload={'checks':dict.fromkeys(('python','gi','gtk3','gdkx11','svg','numpy','pillow','websocket','libmpv','python_mpv','ejs'),True),
                 'versions':{'python':'3.12.5','pillow':'10.4'},'details':{},'venv':True,'ensurepip':True}
        with patch('dependencies.probe_python',return_value=payload),patch('dependencies._installed',return_value=()), \
             patch('dependencies._runtime',return_value=(True,'node 22.1')),patch('dependencies.shutil.which',side_effect=lambda name,path=None:None if name=='Xwayland' else '/fixture/'+name), \
             patch('dependencies.subprocess.run') as run:
            x11=deps.inspect(python,environ={'XDG_SESSION_TYPE':'x11'},immutable_paths=())
            wayland=deps.inspect(python,environ={'XDG_SESSION_TYPE':'wayland'},immutable_paths=())
            run.assert_not_called()
        self.assertEqual(x11.python,python)
        self.assertTrue(x11.ready)
        self.assertNotIn('xwayland',x11.checks)
        self.assertEqual(wayland.missing,('xwayland',))

    def test_js_version_gate_rejects_ubuntu_node18_and_accepts_deno23(self):
        for name,version,expected in [('node','v18.20.8\n',False),('node','v22.0.0\n',True),
                                      ('deno','deno 2.2.8\n',False),('deno','deno 2.3.0 (stable)\n',True)]:
            with self.subTest(version=version),patch('dependencies.shutil.which',side_effect=lambda item,path=None:'/usr/bin/'+item if item==name else None):
                runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0,stdout=version))
                actual,_=deps._runtime('/fixture',runner)
                self.assertEqual(actual,expected)
                self.assertEqual(runner.call_args.args[0],['/usr/bin/'+name,'--version'])

    def test_apt_index_probe_ignores_partial_and_release_files(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            self.assertFalse(deps.apt_indexes_available(base/'missing'))
            (base/'partial').mkdir()
            (base/'partial/host_binary-amd64_Packages').write_bytes(b'incomplete')
            (base/'host_InRelease').write_text('release signatures')
            self.assertFalse(deps.apt_indexes_available(base))
            index=base/'host_binary-amd64_Packages.lz4'
            index.touch()  # Empty placeholder is not a usable package index.
            self.assertFalse(deps.apt_indexes_available(base))
            index.write_bytes(b'compressed package metadata')
            self.assertTrue(deps.apt_indexes_available(base))
            with patch.object(Path,'stat',side_effect=PermissionError):
                self.assertIsNone(deps.apt_indexes_available(base))

    def test_apt_refresh_is_shown_only_for_empty_indexes_and_missing_system_packages(self):
        for indexes,expected in ((False,True),(True,False),(None,False)):
            with self.subTest(indexes=indexes),patch('dependencies.shutil.which',return_value='/apt-get'):
                current=report('gi',family='debian');current.apt_indexes=indexes
                plan=deps.build_plan(current,venv_dir='/unused/runtime',sudo=True)
                updates=[command for command in plan.system_commands if command==('sudo','apt-get','update')]
                self.assertEqual(bool(updates),expected)
                if expected:
                    self.assertEqual(plan.system_commands[0],updates[0])
                    self.assertEqual(plan.commands[0],updates[0])
                self.assertIn('install',plan.system_commands[-1])
                self.assertTrue(all('upgrade' not in command for command in plan.commands))
        for current in (report(family='debian'),report('pillow',family='debian'),report('gi',family='arch')):
            current.apt_indexes=False
            with patch('dependencies.shutil.which',return_value='/manager'):
                plan=deps.build_plan(current,venv_dir='/unused/runtime',sudo=True)
            self.assertTrue(all('update' not in command for command in plan.commands))

    def test_provision_apt_refresh_and_install_follow_the_displayed_order(self):
        with tempfile.TemporaryDirectory() as folder,patch('dependencies.shutil.which',return_value='/apt-get'):
            current=report('gi',family='debian');current.apt_indexes=False
            plan=deps.build_plan(current,venv_dir=Path(folder)/'runtime',sudo=True)
            ready=report(family='debian')
            runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0))
            progress=[]
            with patch('dependencies.inspect',return_value=ready):
                deps.provision(plan,runner=runner,progress=progress.append)
            actual=[tuple(call.args[0]) for call in runner.call_args_list]
            self.assertEqual(actual,list(plan.system_commands))
            self.assertEqual(progress,actual)
            self.assertEqual(len(actual),2)

    def test_failed_apt_refresh_stops_without_install_retry_or_runtime_creation(self):
        with tempfile.TemporaryDirectory() as folder,patch('dependencies.shutil.which',return_value='/apt-get'):
            runtime=Path(folder)/'runtime'
            current=report('gi','pillow',family='debian');current.apt_indexes=False
            plan=deps.build_plan(current,venv_dir=runtime,sudo=True)
            runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=100))
            progress=[]
            with patch('dependencies.inspect') as inspect,self.assertRaisesRegex(deps.DependencyError,'sudo apt-get update'):
                deps.provision(plan,runner=runner,progress=progress.append)
            self.assertEqual(runner.call_count,1)
            self.assertEqual(runner.call_args.args[0],['sudo','apt-get','update'])
            self.assertEqual(progress,[('sudo','apt-get','update')])
            inspect.assert_not_called()
            self.assertFalse(runtime.exists())

    def test_apt_install_code100_has_a_recovery_hint_with_existing_indexes(self):
        with tempfile.TemporaryDirectory() as folder,patch('dependencies.shutil.which',return_value='/apt-get'):
            current=report('gi',family='debian');current.apt_indexes=True
            plan=deps.build_plan(current,venv_dir=Path(folder)/'runtime',sudo=True)
            runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=100))
            with self.assertRaisesRegex(deps.DependencyError,'sudo apt-get update.*installer again'):
                deps.provision(plan,runner=runner)
            self.assertEqual(runner.call_count,1)
            self.assertIn('install',runner.call_args.args[0])


if __name__ == '__main__':unittest.main()
