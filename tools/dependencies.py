"""Inspect and provision only Emberbox's missing runtime dependencies.

Inspection never installs anything. The caller displays Plan.commands before
provisioning; system package managers retain their own confirmations unless the
caller explicitly requests yes=True. No audio services or repositories change.

Package references: https://archlinux.org/packages/extra/x86_64/libpulse/files/
https://packages.ubuntu.com/noble/pipewire-bin
https://packages.fedoraproject.org/pkgs/pipewire/pipewire-utils/
https://api.opensuse.org/public/source/openSUSE:Factory/pulseaudio/pulseaudio.spec
https://github.com/yt-dlp/yt-dlp/wiki/EJS
https://pypi.org/project/deno/ (Deno-owned binary wheels)
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


LABELS = {
    'python': 'Python ≥ 3.10', 'gi': 'PyGObject', 'gtk3': 'GTK 3',
    'gdkx11': 'GdkX11', 'svg': 'SVG image loader',
    'numpy': 'NumPy ≥ 1.24', 'pillow': 'Pillow ≥ 10',
    'websocket': 'websocket-client ≥ 1.6', 'pipewire': 'PipeWire command-line tools',
    'pactl': 'PulseAudio control client', 'xwayland': 'XWayland',
    'libmpv': 'libmpv', 'python_mpv': 'python-mpv', 'yt_dlp': 'yt-dlp',
    'ejs': 'YouTube JavaScript challenge scripts', 'js_runtime': 'Deno ≥ 2.3 / Node ≥ 22',
    'ffmpeg': 'FFmpeg',
}
PURE = {'numpy': 'numpy>=1.24', 'pillow': 'Pillow>=10',
        'websocket': 'websocket-client>=1.6', 'python_mpv': 'python-mpv',
        'yt_dlp': 'yt-dlp[default]>=2025.11.12', 'ejs': 'yt-dlp[default]>=2025.11.12', 'js_runtime': 'deno>=2.3'}
PACKAGES = {
    'arch': {'gi': ('python-gobject',), 'gtk3': ('gtk3',), 'gdkx11': ('gtk3',),
             'svg': ('librsvg',), 'pipewire': ('pipewire',), 'pactl': ('libpulse',),
             'xwayland': ('xorg-xwayland',), 'libmpv': ('mpv',), 'ffmpeg': ('ffmpeg',)},
    'debian': {'gi': ('python3-gi',), 'gtk3': ('gir1.2-gtk-3.0',), 'gdkx11': ('gir1.2-gtk-3.0',),
               'svg': ('librsvg2-common',), 'pipewire': ('pipewire-bin',),
               'pactl': ('pulseaudio-utils',), 'xwayland': ('xwayland',),
               'libmpv': ('libmpv2',), 'ffmpeg': ('ffmpeg',)},
    'fedora': {'gi': ('python3-gobject',), 'gtk3': ('gtk3',), 'gdkx11': ('gtk3',),
               'svg': ('rsvg-pixbuf-loader',), 'pipewire': ('pipewire-utils',),
               'pactl': ('pulseaudio-utils',), 'xwayland': ('xorg-x11-server-Xwayland',),
               'libmpv': ('mpv-libs',), 'ffmpeg': ('ffmpeg-free',)},
    'opensuse': {'gi': ('python3-gobject',), 'gtk3': ('typelib-1_0-Gtk-3_0',),
                 'gdkx11': ('typelib-1_0-Gtk-3_0',), 'svg': ('gdk-pixbuf-loader-rsvg',),
                 'pipewire': ('pipewire-tools',), 'pactl': ('pulseaudio-utils',),
                 'xwayland': ('xwayland',), 'libmpv': ('libmpv2',), 'ffmpeg': ('ffmpeg',)},
}
BOOTSTRAP = {'arch': ('python-pip',), 'debian': ('python3-venv',),
             'fedora': ('python3-pip',), 'opensuse': ('python3-pip',)}
MANAGERS = {'arch': 'pacman', 'debian': 'apt-get', 'fedora': 'dnf', 'opensuse': 'zypper'}
IMMUTABLE = {'silverblue', 'kinoite', 'sericea', 'onyx', 'sway-atomic', 'budgie-atomic',
             'cosmic-atomic', 'bazzite', 'bluefin', 'aurora', 'aeon', 'kalpa', 'microos',
             'opensuse-microos', 'opensuse-aeon', 'opensuse-kalpa', 'steamos'}
MARKER = '.emberbox-runtime.json'


class DependencyError(RuntimeError):
    pass


class ProvisionCancelled(DependencyError):
    pass


@dataclass(frozen=True)
class Distribution:
    id: str
    name: str
    family: str = ''
    supported: bool = False
    reason: str = ''
    version: str = ''
    codename: str = ''


@dataclass
class Report:
    python: str
    distribution: Distribution
    checks: dict
    versions: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)
    wayland: bool = False
    youtube: bool = True
    venv_available: bool = False
    ensurepip_available: bool = False
    installed_packages: tuple | None = None
    os_release: str = '/etc/os-release'
    environ: dict = field(default_factory=dict, repr=False)
    immutable_paths: tuple = ()
    apt_indexes: bool | None = True

    @property
    def missing(self):
        return tuple(key for key, present in self.checks.items() if not present)

    @property
    def ready(self):
        return not self.missing


@dataclass
class Plan:
    report: Report
    packages: tuple = ()
    system_commands: tuple = ()
    python_commands: tuple = ()
    pip_requirements: tuple = ()
    venv_dir: Path | None = None
    python: str = ''
    supported: bool = True
    reason: str = ''
    sudo: bool = True

    @property
    def commands(self):
        return self.system_commands+self.python_commands

    @property
    def ready(self):
        return self.report.ready


@dataclass
class ProvisionResult:
    python: str
    report: Report


def read_os_release(path='/etc/os-release'):
    """Read os-release as data; never source arbitrary shell syntax."""
    result = {}
    try:
        for line in Path(path).read_text().splitlines():
            if not re.match(r'^[A-Z][A-Z0-9_]*=', line):
                continue
            key, value = line.split('=', 1)
            try:
                parts = shlex.split(value, comments=True)
            except ValueError:
                continue
            result[key] = parts[0] if len(parts) == 1 else ''
    except OSError:
        pass
    return result


def detect_distribution(os_release='/etc/os-release', immutable_paths=None):
    release = read_os_release(os_release)
    identity = release.get('ID', '').lower()
    name = release.get('PRETTY_NAME', identity or 'Unknown Linux')
    variant = release.get('VARIANT_ID', '').lower()
    markers = tuple(immutable_paths) if immutable_paths is not None else ('/run/ostree-booted', '/usr/share/ublue-os/image-info.json')
    immutable = identity in IMMUTABLE or variant in IMMUTABLE or any(Path(path).exists() for path in markers)
    family = ''
    for item in (identity, *release.get('ID_LIKE', '').lower().split()):
        if item in ('arch', 'archlinux'):family = 'arch'
        elif item in ('debian', 'ubuntu'):family = 'debian'
        elif item == 'fedora':family = 'fedora'
        elif item in ('opensuse', 'opensuse-tumbleweed', 'opensuse-leap', 'opensuse-slowroll', 'suse'):family = 'opensuse'
        if family:break
    reason = ('Automatic package installation is unsupported on immutable systems. Use the system image or a packaged build.'
              if immutable else 'Automatic package installation supports Arch, Debian/Ubuntu, Fedora and openSUSE.' if not family else '')
    return Distribution(identity, name, family, bool(family and not immutable), reason,
                        release.get('VERSION_ID', ''), release.get('UBUNTU_CODENAME', release.get('VERSION_CODENAME', '')))


PROBE = r'''
import ctypes, ctypes.util, importlib, importlib.util, importlib.metadata, json, re, sys
result = {'checks': {'python': sys.version_info >= (3,10)}, 'versions': {'python': '.'.join(map(str,sys.version_info[:3]))}, 'details': {}}
def probe(name, function):
    try: result['checks'][name] = bool(function())
    except Exception as error:
        result['checks'][name] = False
        result['details'][name] = type(error).__name__
def module(name, key, minimum=()):
    value = importlib.import_module(name)
    version = str(getattr(value, '__version__', ''))
    result['versions'][key] = version
    parts = tuple(map(int, re.findall(r'\d+', version)[:3]))
    return not minimum or parts >= minimum
probe('gi', lambda: module('gi','gi'))
def namespace(name):
    import gi
    gi.require_version(name, '3.0')
    importlib.import_module('gi.repository.'+name)
    return True
probe('gtk3', lambda: namespace('Gtk'))
probe('gdkx11', lambda: namespace('GdkX11'))
def svg():
    from gi.repository import GdkPixbuf
    loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
    loader.write(b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
    loader.close()
    return loader.get_pixbuf() is not None
probe('svg', svg)
probe('numpy', lambda: module('numpy','numpy',(1,24)))
probe('pillow', lambda: module('PIL','pillow',(10,)))
probe('websocket', lambda: module('websocket','websocket',(1,6)))
def libmpv():
    for value in (ctypes.util.find_library('mpv'), 'libmpv.so.2', 'libmpv.so.1'):
        if value:
            try:ctypes.CDLL(value);return True
            except OSError:pass
    return False
probe('libmpv', libmpv)
probe('python_mpv', lambda: importlib.util.find_spec('mpv') is not None)
def ejs():
    if importlib.util.find_spec('yt_dlp_ejs') is None:
        return False
    supplied = importlib.metadata.version('yt-dlp-ejs')
    requirements = [item.split(';')[0] for item in importlib.metadata.requires('yt-dlp') or ()
                    if item.lower().startswith('yt-dlp-ejs')]
    if not requirements:return False
    def version(value):return tuple(map(int, re.findall(r'\d+',value)))
    actual = version(supplied)
    for requirement in requirements:
        for operator, wanted in re.findall(r'(===|==|!=|>=|<=|>|<|~=)\s*([\d.]+)',requirement):
            expected=version(wanted)
            if not {'===':actual==expected,'==':actual==expected,'!=':actual!=expected,
                    '>=':actual>=expected,'<=':actual<=expected,'>':actual>expected,
                    '<':actual<expected,'~=':actual>=expected and actual[:max(1,len(expected)-1)]==expected[:max(1,len(expected)-1)]}[operator]:
                return False
    return True
probe('ejs', ejs)
result['venv'] = importlib.util.find_spec('venv') is not None
result['ensurepip'] = importlib.util.find_spec('ensurepip') is not None
result['prefix'] = sys.prefix
result['base_prefix'] = sys.base_prefix
print(json.dumps(result))
'''


def probe_python(python, runner=None):
    run = runner or subprocess.run
    try:
        result = run([str(python), '-I', '-B', '-c', PROBE], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError('Python probe failed')
        value = json.loads(result.stdout)
        if not isinstance(value.get('checks'), dict):
            raise ValueError('Invalid Python probe')
        return value
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'checks': {key: False for key in ('python', 'gi', 'gtk3', 'gdkx11', 'svg', 'numpy', 'pillow', 'websocket', 'libmpv', 'python_mpv', 'ejs')},
                'versions': {}, 'details': {'python': 'Python could not run its dependency probe.'}, 'venv': False, 'ensurepip': False}


def _installed(family, runner=None):
    command = {'arch': ['pacman', '-Qq'], 'debian': ['dpkg-query', '-W', '-f=${binary:Package}\t${db:Status-Status}\n'],
               'fedora': ['rpm', '-qa', '--qf', '%{NAME}\n'], 'opensuse': ['rpm', '-qa', '--qf', '%{NAME}\n']}.get(family)
    if not command:return None
    try:
        result = (runner or subprocess.run)(command, capture_output=True, text=True, timeout=15)
        if result.returncode:return None
        if family == 'debian':
            return tuple(line.split('\t')[0].split(':')[0] for line in result.stdout.splitlines() if line.endswith('\tinstalled'))
        return tuple(result.stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        return None


def _runtime(path, runner=None):
    for name, minimum in (('deno', (2,3)), ('node', (22,))):
        executable = shutil.which(name, path=path)
        if not executable:continue
        try:
            result = (runner or subprocess.run)([executable, '--version'], capture_output=True, text=True, timeout=5)
            match = re.search(r'(?:^deno\s+|^v)(\d+)\.(\d+)', result.stdout)
            if result.returncode == 0 and match and tuple(map(int, match.groups())) >= minimum:
                return True, name+' '+'.'.join(match.groups())
        except (OSError, subprocess.SubprocessError):pass
    return False, ''


def apt_indexes_available(directory='/var/lib/apt/lists'):
    """False only when the normal apt index directory is provably empty.

    Sources/InRelease files and the partial/ directory cannot resolve package
    names. Treat unreadable state as unknown rather than scheduling an update.
    """
    folder=Path(directory)
    try:
        folder.stat()
    except FileNotFoundError:
        return False
    except OSError:
        return None
    try:
        return any('Packages' in item.name and item.is_file() and item.stat().st_size>0
                   for item in folder.iterdir())
    except OSError:
        return None


def inspect(python=None, *, youtube=True, os_release='/etc/os-release', environ=None, immutable_paths=None):
    env = dict(os.environ if environ is None else environ)
    selected = str(python or ('/usr/bin/python3' if Path('/usr/bin/python3').is_file() else sys.executable))
    distribution = detect_distribution(os_release, immutable_paths)
    probe = probe_python(selected)
    checks = {key: bool(probe['checks'].get(key)) for key in ('python', 'gi', 'gtk3', 'gdkx11', 'svg', 'numpy', 'pillow', 'websocket')}
    path = os.pathsep.join((str(Path(selected).absolute().parent), env.get('PATH', os.defpath)))
    checks['pipewire'] = all(shutil.which(name, path=path) for name in ('pw-record', 'pw-play', 'pw-link', 'pw-dump'))
    checks['pactl'] = all(shutil.which(name,path=path) for name in ('pactl','pacat'))
    wayland = env.get('XDG_SESSION_TYPE', '').lower() == 'wayland' or bool(env.get('WAYLAND_DISPLAY'))
    if wayland:checks['xwayland'] = bool(shutil.which('Xwayland', path=path))
    versions = dict(probe.get('versions', {}))
    if youtube:
        checks.update({key: bool(probe['checks'].get(key)) for key in ('libmpv', 'python_mpv', 'ejs')})
        checks['yt_dlp'] = bool(shutil.which('yt-dlp', path=path))
        checks['js_runtime'], versions['js_runtime'] = _runtime(path)
    checks['ffmpeg'] = bool(shutil.which('ffmpeg', path=path))
    kept_env = {key: env[key] for key in ('PATH', 'XDG_SESSION_TYPE', 'WAYLAND_DISPLAY') if key in env}
    markers = tuple(immutable_paths) if immutable_paths is not None else ('/run/ostree-booted', '/usr/share/ublue-os/image-info.json')
    return Report(selected, distribution, checks, versions, dict(probe.get('details', {})), wayland, youtube,
                  bool(probe.get('venv')), bool(probe.get('ensurepip')), _installed(distribution.family),
                  str(os_release), kept_env, markers,
                  apt_indexes_available() if distribution.family=='debian' else None)


def package_command(family, packages, *, yes=False, sudo=True):
    command = {'arch': ['pacman', '-S', '--needed'],
               'debian': ['apt-get', 'install', '--no-install-recommends'],
               'fedora': ['dnf', 'install', '--setopt=install_weak_deps=False'],
               'opensuse': ['zypper', 'install', '--no-recommends']}.get(family)
    if not command:raise DependencyError('Unsupported package manager.')
    if yes:
        if family == 'arch':command.append('--noconfirm')
        elif family == 'opensuse':command.insert(1, '--non-interactive')
        else:command.append('-y')
    return tuple((['sudo'] if sudo else [])+command+list(packages))


def build_plan(report, *, venv_dir, yes=False, sudo=None):
    directory = Path(venv_dir).absolute()
    plan = Plan(report, venv_dir=directory, python=report.python, sudo=os.geteuid()!=0 if sudo is None else sudo)
    if report.ready:return plan
    if not report.distribution.supported:
        plan.supported=False;plan.reason=report.distribution.reason;return plan
    if not report.checks.get('python'):
        plan.supported=False;plan.reason='Python 3.10 or newer is required. Upgrade the distribution Python before installing Emberbox.';return plan
    family = report.distribution.family
    mapping = dict(PACKAGES[family])
    if family == 'debian' and (report.distribution.codename == 'jammy' or report.distribution.id == 'ubuntu' and report.distribution.version == '22.04'):
        mapping['libmpv'] = ('libmpv1',)
    needed = tuple(dict.fromkeys(package for key in report.missing for package in mapping.get(key, ())))
    requirements = tuple(dict.fromkeys(PURE[key] for key in report.missing if key in PURE))
    if requirements and not (report.venv_available and report.ensurepip_available):
        needed = tuple(dict.fromkeys((*needed, *BOOTSTRAP[family])))
    packages = tuple(package for package in needed if report.installed_packages is None or package not in report.installed_packages)
    stuck = [key for key in report.missing if key in mapping and all(package not in packages for package in mapping[key])]
    if stuck:
        plan.supported=False;plan.reason='Installed packages do not expose '+', '.join(LABELS.get(key,key) for key in stuck)+'. Repair these system packages before retrying.';return plan
    if packages and not shutil.which(MANAGERS[family]):
        plan.supported=False;plan.reason=f'{MANAGERS[family]} is unavailable; install the listed dependencies with your distribution tools.';return plan
    if requirements:
        if directory.exists() and not (directory/MARKER).is_file():
            plan.supported=False;plan.reason=f'Refusing to change an unmanaged Python environment: {directory}';return plan
        runtime = str(directory/'bin/python')
        commands = []
        if not (directory/'pyvenv.cfg').is_file():
            commands.append((report.python, '-I', '-m', 'venv', '--system-site-packages', str(directory)))
        commands.append((runtime, '-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--only-binary=:all:', *requirements))
        plan.python_commands=tuple(commands);plan.python=runtime;plan.pip_requirements=requirements
    plan.packages=packages
    if packages:
        commands=[]
        if family=='debian' and report.apt_indexes is False:
            commands.append(tuple((['sudo'] if plan.sudo else [])+['apt-get','update']))
        commands.append(package_command(family, packages, yes=yes, sudo=plan.sudo))
        plan.system_commands=tuple(commands)
    return plan


def _run(command, runner, progress):
    if progress:progress(tuple(command))
    try:
        result = runner(list(command))
    except KeyboardInterrupt:
        raise ProvisionCancelled('Dependency installation cancelled.') from None
    except (OSError, subprocess.SubprocessError) as error:
        raise DependencyError(f'Could not run {command[0]}: {error}') from None
    if result.returncode in (-2, 130):
        raise ProvisionCancelled('Dependency installation cancelled.')
    if result.returncode:
        hint=''
        executable=command[1] if command[0]=='sudo' and len(command)>1 else command[0]
        if result.returncode==100 and Path(executable).name=='apt-get':
            hint='\nRefresh package indexes with sudo apt-get update, then run the installer again.'
        raise DependencyError(f'Dependency command failed with exit code {result.returncode}: {shlex.join(command)}'+hint)


def provision(plan, *, yes=False, runner=None, progress=None):
    """Run the displayed plan, rechecking before pip to avoid unnecessary installs."""
    if not plan.supported:raise DependencyError(plan.reason)
    if plan.ready:return ProvisionResult(plan.python, plan.report)
    run = runner or subprocess.run
    if plan.system_commands:
        for command in plan.system_commands[:-1]:
            _run(command,run,progress)
        _run(package_command(plan.report.distribution.family, plan.packages, yes=yes, sudo=plan.sudo), run, progress)
    report = inspect(plan.report.python, youtube=plan.report.youtube, os_release=plan.report.os_release,
                     environ=plan.report.environ, immutable_paths=plan.report.immutable_paths)
    if report.ready:return ProvisionResult(report.python, report)
    native = [key for key in report.missing if key not in PURE]
    if native:
        raise DependencyError('System dependencies are still missing: '+', '.join(LABELS.get(key,key) for key in native))
    # An installed native library can make a previously unimportable Python
    # extension usable. Only install extras that are still missing now.
    requirements = tuple(dict.fromkeys(PURE[key] for key in report.missing if key in PURE))
    if any(item not in plan.pip_requirements for item in requirements):
        raise DependencyError('Dependency state changed. Inspect and review a new plan before continuing.')
    directory = plan.venv_dir
    if directory is None:raise DependencyError('An isolated runtime directory is required.')
    if directory.exists() and not (directory/MARKER).is_file():
        raise DependencyError(f'Refusing to change an unmanaged Python environment: {directory}')
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory/MARKER).write_text(json.dumps({'app':'emberbox-audio','system_site_packages':True})+'\n')
    except OSError as error:
        raise DependencyError(f'Could not prepare the isolated runtime: {error}') from None
    if not (directory/'pyvenv.cfg').is_file():
        _run((report.python, '-I', '-m', 'venv', '--system-site-packages', str(directory)), run, progress)
    runtime = str(directory/'bin/python')
    cfg = directory/'pyvenv.cfg'
    if not cfg.is_file() or 'include-system-site-packages = true' not in cfg.read_text().lower():
        raise DependencyError('The isolated runtime was not created with system GTK bindings.')
    if not (directory/'bin/python').is_file():
        raise DependencyError('The isolated runtime interpreter is missing.')
    isolated = probe_python(runtime, runner=run)
    prefix, base = isolated.get('prefix'), isolated.get('base_prefix')
    if not prefix or Path(prefix).absolute() != directory or prefix == base:
        raise DependencyError('Refusing pip outside the isolated Emberbox runtime.')
    _run((runtime, '-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--only-binary=:all:', *requirements), run, progress)
    final = inspect(runtime, youtube=report.youtube, os_release=report.os_release,
                    environ=report.environ, immutable_paths=report.immutable_paths)
    if not final.ready:
        raise DependencyError('Dependency verification failed: '+', '.join(LABELS.get(key,key) for key in final.missing))
    return ProvisionResult(runtime, final)
