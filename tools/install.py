#!/usr/bin/env python3
"""Install this checkout for the current user, with no sudo or downloads."""

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = 'emberbox-audio'
TITLE = APP.replace('-', ' ').title()


def systemd_quote(value):
    return '"' + str(value).replace('%', '%%').replace('\\', '\\\\').replace('"', '\\"') + '"'


def desktop_quote(value):
    return '"' + str(value).replace('%', '%%').replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'uninstall'))
    parser.add_argument('--autostart', action='store_true', help='Start at login (does not start playback)')
    parser.add_argument('--bin-dir', type=Path, default=Path.home() / '.local/bin')
    parser.add_argument('--no-systemd', action='store_true', help='Direct launcher; use XDG autostart if requested')
    parser.add_argument('--skip-check', action='store_true', help='Skip dependency check, for packaging only')
    args = parser.parse_args(argv)
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    target = data / APP
    unit = config / 'systemd/user' / f'{APP}.service'
    desktop = data / 'applications' / f'{APP}.desktop'
    media_desktop = data / 'applications' / 'emberbox-audio-player.desktop'
    launcher = args.bin_dir / APP
    autostart = config / 'autostart' / f'{APP}.desktop'
    manifest = target / '.emberbox-install.json'
    use_systemd = not args.no_systemd
    if target.exists() and not manifest.exists():
        parser.error(f'Refusing to replace an unmanaged directory: {target}')
    if args.action == 'uninstall' and not manifest.exists():
        print(f'{TITLE} is not installed in {target}.')
        return 0

    def service(*command, check=False):
        return subprocess.run(['systemctl', '--user', *command], check=check,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if args.action == 'uninstall':
        previous = json.loads(manifest.read_text())
        if previous['systemd']:
            service('stop', f'{APP}-apple.service')
            service('stop', f'{APP}-yandex.service')
            service('disable', '--now', f'{APP}.service')
        for value in previous['files']:
            Path(value).unlink(missing_ok=True)
        shutil.rmtree(target)
        if previous['systemd']:
            service('daemon-reload')
        print(f'Removed {TITLE}. Your preferences and cache were kept.')
        return 0

    if not args.skip_check:
        result = subprocess.run([sys.executable, str(ROOT / 'tools/check_dependencies.py')])
        if result.returncode:
            return result.returncode
    if use_systemd and not shutil.which('systemctl'):
        parser.error('systemctl is missing. Use --no-systemd for a direct launcher.')
    for file in (unit, desktop, media_desktop, launcher):
        if file.exists() and not manifest.exists():
            parser.error(f'Refusing to overwrite an unmanaged file: {file}')
    was_running = use_systemd and service('is-active', '--quiet', f'{APP}.service').returncode == 0
    if was_running:
        service('stop', f'{APP}.service', check=True)
        service('stop', f'{APP}-apple.service')
        service('stop', f'{APP}-yandex.service')
    target.mkdir(parents=True, exist_ok=True)
    if (target / 'src').exists():
        shutil.rmtree(target / 'src')
    shutil.copytree(ROOT / 'src', target / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if (target / 'browser').exists():
        shutil.rmtree(target / 'browser')
    shutil.copytree(ROOT / 'browser', target / 'browser')
    (target / 'tools').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'tools/apple_browser.py', target / 'tools/apple_browser.py')
    shutil.copy2(ROOT / 'tools/apple_player.py', target / 'tools/apple_player.py')
    shutil.copytree(ROOT / 'docs', target / 'docs', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'assets', target / 'assets', dirs_exist_ok=True)
    for name in ('README.md', 'README.ru.md', 'LICENSE', 'VERSION'):
        shutil.copy2(ROOT / name, target / name)

    direct = f'export GDK_BACKEND=x11\nexec {shlex.quote(sys.executable)} {shlex.quote(str(target / "src/widget.py"))} "$@"\n'
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text('#!/usr/bin/env sh\n' +
                        (f'exec systemctl --user start {APP}.service\n' if use_systemd else direct))
    launcher.chmod(0o755)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop_text = (f'[Desktop Entry]\nType=Application\nName={TITLE}\n'
                    f'Comment=A little warmth for your desktop\nExec={desktop_quote(launcher)}\n'
                    f'Icon={target / "assets/icon.svg"}\nTerminal=false\n'
                    'Categories=AudioVideo;Player;\nStartupNotify=false\n')
    desktop.write_text(desktop_text)
    media_desktop.write_text(desktop_text.replace(f'Name={TITLE}', 'Name=Ember')+'NoDisplay=true\n')
    files = [str(launcher), str(desktop),str(media_desktop)]
    if use_systemd:
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(f'''[Unit]
Description={TITLE} desktop widget
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
Environment=GDK_BACKEND=x11
ExecStart={systemd_quote(sys.executable)} {systemd_quote(target / 'src/widget.py')}
Restart=on-failure
RestartSec=2
TimeoutStopSec=5

[Install]
WantedBy=graphical-session.target
''')
        files.append(str(unit))
        service('daemon-reload', check=True)
        if args.autostart:
            service('enable', f'{APP}.service', check=True)
        if was_running:
            service('start', f'{APP}.service', check=True)
    elif args.autostart:
        autostart.parent.mkdir(parents=True, exist_ok=True)
        autostart.write_text(desktop_text)
        files.append(str(autostart))
    manifest.write_text(json.dumps({'app': APP, 'systemd': use_systemd, 'files': files}, indent=2))
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(desktop.parent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f'Installed {TITLE} in {target}.')
    print(f'Launch it from your applications menu, or run {launcher}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
