#!/usr/bin/env python3
"""Install Emberbox with dependency checks and a per-user desktop launcher."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid

sys.dont_write_bytecode=True
if sys.version_info<(3,10):
    raise SystemExit('Emberbox needs Python 3.10+. Use a current system Python and retry.')

import dependencies
from installer_ui import Terminal

ROOT=Path(__file__).resolve().parents[1]
APP='emberbox-audio'
TITLE='Emberbox Audio'
PAYLOAD=('src','browser','docs','assets','tools','README.md','README.ru.md','LICENSE','VERSION')
INSTALL_TOOLS=('apple_browser.py','apple_player.py','launch.py','check_dependencies.py','dependencies.py','installer_ui.py')


def systemd_quote(value):
    return '"'+str(value).replace('%','%%').replace('\\','\\\\').replace('"','\\"')+'"'


def desktop_quote(value):
    return '"'+str(value).replace('%','%%').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')+'"'


def service(*command,check=False):
    try:return subprocess.run(['systemctl','--user',*command],check=check,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=12)
    except (OSError,subprocess.TimeoutExpired):
        if check:raise RuntimeError('The user service manager did not respond') from None
        return subprocess.CompletedProcess(command,1)


def absolute(value):
    path=Path(value).expanduser().absolute()
    if any(ord(c)<32 for c in str(path)):raise ValueError('Installation paths cannot contain control characters')
    return path


def desktop_directory():
    try:
        result=subprocess.run(['xdg-user-dir','DESKTOP'],capture_output=True,text=True,timeout=3)
        directory=absolute(result.stdout.strip()) if result.returncode==0 and result.stdout.strip() else None
    except (OSError,ValueError,subprocess.SubprocessError):directory=None
    if directory is None:
        config=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'user-dirs.dirs'
        try:
            for line in config.read_text().splitlines():
                if not line.strip().startswith('XDG_DESKTOP_DIR='):continue
                values=shlex.split(line.strip().split('=',1)[1],comments=True)
                if len(values)!=1:continue
                value=values[0]
                for prefix in ('$HOME','${HOME}'):
                    if value==prefix or value.startswith(prefix+'/'):
                        value=str(Path.home())+value[len(prefix):];break
                if Path(value).is_absolute():directory=absolute(value)
                break
        except (OSError,ValueError):pass
    # A desktop directory equal to HOME means desktop icons were disabled.
    if directory is None or directory==Path.home():
        raise ValueError('No desktop folder is configured. Configure XDG_DESKTOP_DIR before adding a shortcut.')
    return directory


def kde_session(environ=None):
    env=os.environ if environ is None else environ
    names=re.split(r'[:;\s]+',' '.join(env.get(key,'') for key in (
        'XDG_CURRENT_DESKTOP','XDG_SESSION_DESKTOP','DESKTOP_SESSION')).casefold())
    return any(name in ('kde','plasma','plasmawayland','plasma-wayland','plasmax11','plasma-x11') for name in names)


def remove(path):
    if path.is_dir() and not path.is_symlink():shutil.rmtree(path)
    else:path.unlink(missing_ok=True)


def snapshot(paths):
    return {p:(p.read_bytes(),p.stat().st_mode&0o777) if p.is_file() else None for p in paths}


def restore(values):
    for path,value in values.items():
        if value is None:path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value[0]);path.chmod(value[1])


def stage_payload(stage):
    for name in ('src','browser','docs','assets'):
        shutil.copytree(ROOT/name,stage/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (stage/'tools').mkdir()
    for name in INSTALL_TOOLS:shutil.copy2(ROOT/'tools'/name,stage/'tools'/name)
    for name in ('README.md','README.ru.md','LICENSE','VERSION'):shutil.copy2(ROOT/name,stage/name)


def prepare_spatial(ui,python,source):
    """Show bounded optional setup progress without blocking GTK or hiding downloads."""
    ui.note('Apple Atmos · headphones · beta · about 100 MB download',
            'Apple Atmos · наушники · бета · загрузка около 100 МБ')
    messages={
        'Building the native audio adapter':'Сборка нативного аудиоадаптера',
        'Downloading the spatial decoder':'Загрузка пространственного декодера',
        'Verifying the spatial decoder':'Проверка пространственного декодера',
        'Spatial audio runtime ready':'Пространственный декодер готов',
    }
    with subprocess.Popen([python,'-B',str(source/'spatial_setup.py')],stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,text=True) as process:
        timer=threading.Timer(180,process.kill);timer.daemon=True;timer.start();last=''
        try:
            for line in process.stdout:
                last=line.strip().removeprefix('● ')
                translated=messages.get(last,last)
                match=re.fullmatch(r'Downloading the spatial decoder: (\d+) MB',last)
                if match:translated='Загрузка пространственного декодера: '+match[1]+' МБ'
                ui.note(last,translated)
            if process.wait()!=0:raise RuntimeError('Apple spatial setup: '+last[:500])
        finally:timer.cancel()
    ui.item(ui.text('Decoder verified; enable it in player settings','Декодер проверен; включи его в настройках плеера'))


def prepare_lossless(ui,python,source):
    ui.note('Apple Lossless · beta · about 75 MB download','Apple Lossless · бета · загрузка около 75 МБ')
    translations={
        'Verifying the optional Lossless sources':'Проверка исходников Lossless',
        'Downloading and verifying the optional native libraries':'Загрузка и проверка нативных библиотек',
        'Building the isolated Lossless adapter':'Сборка отдельного движка Lossless',
        'Lossless adapter ready; sign in from the player settings':'Движок Lossless готов; вход через настройки плеера',
    }
    with subprocess.Popen([python,'-B',str(source/'fairplay_setup.py')],stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,text=True) as process:
        timer=threading.Timer(420,process.kill);timer.daemon=True;timer.start();last=''
        try:
            for line in process.stdout:
                last=line.strip().removeprefix('● ');ui.note(last,translations.get(last,last))
            if process.wait()!=0:raise RuntimeError('Apple Lossless setup: '+last[:500])
        finally:timer.cancel()


def source_summary(ui,python,target,setup=True):
    spotify=bool(shutil.which('spotify'))
    if not spotify and shutil.which('flatpak'):
        try:spotify=subprocess.run(['flatpak','info','com.spotify.Client'],stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,timeout=4).returncode==0
        except (OSError,subprocess.SubprocessError):pass
    ui.note('Spotify client detected.' if spotify else 'Spotify: sign in inside Ember; the desktop client is optional.',
            'Клиент Spotify найден.' if spotify else 'Spotify: войди прямо в Ember; настольный клиент необязателен.')
    status='not_checked'
    if setup:
        probe='''import json,sys
sys.path.insert(0,sys.argv[1])
import apple_setup
status='needs_components'
if apple_setup.configured():status='configured'
else:
    engines=apple_setup.runtime_candidates();modules=apple_setup.widevine_candidates()
    if engines and modules:
        try:
            apple_setup.prepare(runtime=engines[0],module=modules[0]);status='configured'
        except apple_setup.SetupError:status='incompatible'
print(json.dumps({'status':status}))
'''
        try:
            result=subprocess.run([python,'-B','-c',probe,str(target/'src')],capture_output=True,text=True,timeout=48)
            status=json.loads(result.stdout).get('status','not_checked') if result.returncode==0 else 'not_checked'
        except (OSError,ValueError,subprocess.SubprocessError):pass
    if status=='configured':
        ui.item(ui.text('Spotify / Apple / Yandex playback components configured. Sign in from Accounts.',
                        'Компоненты Spotify / Apple / Яндекс настроены. Войди через раздел Аккаунты.'))
    else:
        ui.warning('Spotify / Apple / Yandex still need a compatible DRM engine. Open Settings → Accounts for setup.',
                   'Spotify / Apple / Яндексу ещё нужен совместимый DRM-движок. Настройка: Настройки → Аккаунты.')
    if setup and os.environ.get('DISPLAY') and shutil.which('pw-dump'):
        try:
            audio=subprocess.run(['pw-dump'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
            if audio.returncode:ui.warning('PipeWire is not reachable in this session; live tubes need a working user audio graph.',
                'PipeWire недоступен в этом сеансе; для живых ламп нужен работающий пользовательский аудиосервер.')
        except (OSError,subprocess.SubprocessError):pass


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('install','uninstall'))
    startup=parser.add_mutually_exclusive_group()
    startup.add_argument('--autostart',dest='autostart',action='store_true',default=None,help='Start at desktop login')
    startup.add_argument('--no-autostart',dest='autostart',action='store_false',help='Disable start at login')
    shortcut_options=parser.add_mutually_exclusive_group()
    shortcut_options.add_argument('--desktop-shortcut',dest='desktop_shortcut',action='store_true',default=None,help='Add a launcher to the XDG desktop folder (default on KDE)')
    shortcut_options.add_argument('--no-desktop-shortcut',dest='desktop_shortcut',action='store_false',help='Remove the managed desktop shortcut')
    parser.add_argument('--bin-dir',type=Path,default=Path.home()/'.local/bin')
    parser.add_argument('--apple-atmos',action='store_true',help='Prepare the optional Apple Atmos headphone decoder (Linux x86_64, about 100 MB download)')
    parser.add_argument('--apple-lossless',action='store_true',help='Prepare optional native Apple Lossless / Hi-Res support and Atmos (Linux x86_64)')
    parser.add_argument('--no-systemd',action='store_true',help='Use a direct desktop launcher')
    parser.add_argument('--skip-check',action='store_true',help='Packaging only: skip dependency installation and validation')
    parser.add_argument('--no-deps',action='store_true',help='Require existing dependencies; never install packages')
    parser.add_argument('--check',action='store_true',help='Show checks and installation plan without changing anything')
    parser.add_argument('--yes',action='store_true',help='Explicitly accept package-manager confirmations')
    parser.add_argument('--lang',choices=('auto','en','ru'),default='auto')
    parser.add_argument('--plain',action='store_true',help='Plain terminal output without color')
    args=parser.parse_args(argv)
    if args.check and (args.skip_check or args.action=='uninstall'):
        parser.error('--check requires an install dependency check; do not combine it with --skip-check or uninstall')
    ui=Terminal(language=args.lang,plain=args.plain)
    if sys.platform!='linux':parser.error('Emberbox requires a Linux desktop')
    if os.geteuid()==0 and args.action=='install' and not (args.skip_check or args.check):
        parser.error('Run this installer as your normal user; sudo is used only for missing system packages')
    config=absolute(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))
    data=absolute(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    target=data/APP
    unit=config/'systemd/user'/f'{APP}.service'
    desktop=data/'applications'/f'{APP}.desktop'
    media_desktop=data/'applications'/'emberbox-audio-player.desktop'
    launcher=absolute(args.bin_dir)/APP
    autostart=config/'autostart'/f'{APP}.desktop'
    manifest=target/'.emberbox-install.json'
    previous={}
    if target.is_symlink():parser.error(f'Refusing a symlink installation directory: {target}')
    if target.exists() and (manifest.is_file() or not args.check):
        if not manifest.is_file():parser.error(f'Refusing to replace an unmanaged directory: {target}')
        try:previous=json.loads(manifest.read_text())
        except (OSError,ValueError):parser.error('The installation manifest is unreadable')
        if previous.get('app')!=APP:parser.error('This directory belongs to another application')
    version=(ROOT/'VERSION').read_text().strip()
    shortcut=None
    old_shortcut=previous.get('desktop_shortcut')
    if old_shortcut and Path(old_shortcut).is_absolute() and Path(old_shortcut).name==APP+'.desktop':
        shortcut=absolute(old_shortcut)
    shortcut_preference=previous.get('desktop_shortcut_enabled')
    if args.desktop_shortcut is None:
        want_shortcut=bool(shortcut_preference) if shortcut_preference is not None else bool(shortcut) or kde_session()
    else:want_shortcut=args.desktop_shortcut
    shortcut_warning=False
    if args.action=='install' and want_shortcut and shortcut is None:
        try:shortcut=desktop_directory()/(APP+'.desktop')
        except ValueError as error:
            if args.desktop_shortcut is True:parser.error(str(error))
            # A disabled desktop folder must not prevent the menu installation.
            want_shortcut=False;shortcut_warning=True
    ui.banner(version)
    if shortcut_warning:
        ui.warning('No desktop folder is configured; the application-menu launcher will still be installed.',
                   'Папка рабочего стола не настроена; ярлык в меню приложений будет установлен.')
    if args.action=='uninstall':
        if not previous:
            ui.note('Emberbox is not installed here.','Emberbox здесь не установлен.');return 0
        if previous.get('systemd'):
            for suffix in ('-apple','-yandex',''):service('stop',APP+suffix+'.service')
            service('disable',APP+'.service')
        allowed={unit,desktop,media_desktop,launcher,autostart}
        if shortcut:allowed.add(shortcut)
        # Previous launcher path may differ from today's --bin-dir.
        old_launcher=Path(previous.get('launcher',str(launcher)))
        if old_launcher.name==APP and old_launcher.is_absolute():allowed.add(old_launcher)
        for name in previous.get('files',[]):
            path=Path(name)
            if path in allowed:path.unlink(missing_ok=True)
        remove(target)
        if previous.get('systemd'):service('daemon-reload')
        ui.success('Removed Emberbox. Your music settings and cache are kept.','Emberbox удалён. Настройки музыки и кеш сохранены.')
        return 0
    for path in (unit,desktop,media_desktop,launcher,autostart,*([shortcut] if shortcut else [])):
        if not args.check and path.exists() and str(path) not in previous.get('files',[]):
            parser.error(f'Refusing to overwrite an unmanaged file: {path}')
    ui.step(1,'Check the system','Проверка системы')
    selected=previous.get('python')
    if not selected or not Path(selected).is_file():selected=None
    plan=None
    fresh_runtime=None
    native_cache=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/APP/'apple-spatial/runtime.json'
    spatial_dependencies=args.apple_atmos or args.apple_lossless or native_cache.is_file()
    if not args.skip_check:
        report=dependencies.inspect(selected,spatial=spatial_dependencies,lossless=args.apple_lossless)
        ui.item(report.distribution.name)
        env=os.environ
        ui.note('Desktop: '+env.get('XDG_CURRENT_DESKTOP','not detected')+' · '+env.get('XDG_SESSION_TYPE','not detected'),
                'Рабочий стол: '+env.get('XDG_CURRENT_DESKTOP','не определён')+' · '+env.get('XDG_SESSION_TYPE','не определён'))
        for key,present in report.checks.items():ui.item(dependencies.LABELS.get(key,key),present)
        runtime=target/'runtime'
        # Never repair Python packages underneath the working installed player.
        # A fresh environment is committed by switching the manifest interpreter.
        if previous and any(key in dependencies.PURE for key in report.missing):
            report=dependencies.inspect(spatial=spatial_dependencies,lossless=args.apple_lossless)
            runtime=target/('runtime-'+version+'-'+uuid.uuid4().hex[:8])
            fresh_runtime=runtime
        plan=dependencies.build_plan(report,venv_dir=runtime,yes=args.yes)
        selected=report.python
    else:
        selected=sys.executable
        ui.warning('Dependency checks skipped for packaging.','Проверки зависимостей пропущены для сборки пакета.')
    use_systemd=not args.no_systemd and bool(shutil.which('systemctl')) and service('show-environment').returncode==0
    old_link=config/'systemd/user/graphical-session.target.wants'/unit.name
    old_autostart=bool(previous.get('autostart',str(autostart) in previous.get('files',[]) or old_link.exists()))
    want_autostart=old_autostart if args.autostart is None else args.autostart
    ui.step(2,'Prepare missing components','Подготовка недостающих компонентов')
    if plan:
        if not report.ready and not plan.supported:
            ui.error(plan.reason,plan.reason);return 1
        if args.check:
            for command in plan.commands:ui.command(command)
            ui.note('App destination: '+str(target),'Каталог приложения: '+str(target))
            ui.note('No files or packages changed.','Файлы и пакеты не изменены.')
            return 0 if report.ready else 1
        if args.no_deps and not report.ready:
            ui.error('Dependencies are missing. Run ./install.sh to install them.','Не хватает компонентов. Запусти ./install.sh для их установки.')
            for command in plan.commands:ui.command(command)
            return 1
        if plan.system_commands and not args.yes and not sys.stdin.isatty():
            for command in plan.commands:ui.command(command)
            ui.error('Run in an interactive terminal, or explicitly pass --yes.','Запусти установку в терминале или явно добавь --yes.')
            return 2
    if not use_systemd:
        ui.note('Direct launcher selected; no user service manager is required.','Будет прямой запуск — служба пользователя не требуется.')
    created=not target.exists()
    was_running=bool(previous.get('systemd')) and service('is-active','--quiet',APP+'.service').returncode==0
    files=(unit,desktop,media_desktop,launcher,autostart,manifest,*([shortcut] if shortcut else []))
    old_files=snapshot(files)
    installed=[];backed=[];stopped=False
    data.mkdir(parents=True,exist_ok=True)
    try:
        target.mkdir(parents=True,exist_ok=True)
        if created:manifest.write_text(json.dumps({'app':APP,'files':[],'partial':True}))
        if plan and not report.ready:
            result=dependencies.provision(plan,yes=args.yes,progress=ui.command)
            selected=result.python
        elif plan:ui.item(ui.text('Everything needed is already installed.','Все необходимые компоненты уже установлены.'))
        with tempfile.TemporaryDirectory(prefix='.emberbox-stage-',dir=data) as directory:
            stage=Path(directory)
            ui.step(3,'Install the player','Установка плеера')
            stage_payload(stage)
            if (args.apple_atmos or args.apple_lossless) and not args.skip_check:
                prepare_spatial(ui,selected,stage/'src')
            if args.apple_lossless and not args.skip_check:
                prepare_lossless(ui,selected,stage/'src')
            if not args.skip_check:
                check_env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
                checked=subprocess.run([selected,'-B','-c','import sys;sys.path.insert(0,sys.argv[1]);import widget',str(stage/'src')],
                    env=check_env,capture_output=True,text=True,timeout=30)
                if checked.returncode:raise RuntimeError('Runtime import check failed:\n'+checked.stderr[-2500:])
            if was_running:
                service('stop',APP+'.service',check=True);stopped=True
                service('stop',APP+'-apple.service');service('stop',APP+'-yandex.service');service('stop',APP+'-spotify.service')
            backup=stage/'previous';backup.mkdir()
            try:
                for name in PAYLOAD:
                    if (target/name).exists():
                        (target/name).replace(backup/name);backed.append(name)
                    (stage/name).replace(target/name);installed.append(name)
                ui.item(str(target))
                ui.step(4,'Connect to your desktop','Интеграция с рабочим столом')
                launcher.parent.mkdir(parents=True,exist_ok=True)
                launcher.write_text('#!/usr/bin/env sh\nexec '+shlex.quote(selected)+' '+shlex.quote(str(target/'tools/launch.py'))+' "$@"\n')
                launcher.chmod(0o755)
                desktop.parent.mkdir(parents=True,exist_ok=True)
                desktop_text=(f'[Desktop Entry]\nType=Application\nName={TITLE}\n'
                    f'Comment=A little warmth for your desktop\nComment[ru]=Немного тепла для рабочего стола\n'
                    f'Exec={desktop_quote(launcher)}\nIcon={target/"assets/icon.svg"}\nTerminal=false\n'
                    'Categories=AudioVideo;Player;\nStartupNotify=false\nStartupWMClass=emberbox-audio\n')
                desktop_text+=('Actions=Show;Hide;Quit;\n\n'
                    '[Desktop Action Show]\nName=Show player\nName[ru]=Показать плеер\n'
                    f'Exec={desktop_quote(launcher)} --show\n\n'
                    '[Desktop Action Hide]\nName=Hide player\nName[ru]=Скрыть плеер\n'
                    f'Exec={desktop_quote(launcher)} --hide\n\n'
                    '[Desktop Action Quit]\nName=Close player\nName[ru]=Закрыть плеер\n'
                    f'Exec={desktop_quote(launcher)} --quit\n')
                desktop.write_text(desktop_text)
                media_desktop.write_text(desktop_text.replace(f'Name={TITLE}', 'Name=Ember\nNoDisplay=true'))
                managed=[str(launcher),str(desktop),str(media_desktop)]
                if use_systemd:
                    unit.parent.mkdir(parents=True,exist_ok=True)
                    unit.write_text('[Unit]\nDescription=Emberbox Audio desktop widget\nAfter=graphical-session.target\nPartOf=graphical-session.target\n\n'
                        '[Service]\nType=simple\nEnvironment=GDK_BACKEND=x11\n'
                        f'Environment={systemd_quote("PATH="+str(Path(selected).parent)+":/usr/local/bin:/usr/bin:/bin")}\n'
                        'EnvironmentFile=-%t/emberbox-audio/session.env\n'
                        f'ExecStart={systemd_quote(selected)} -B {systemd_quote(target/"src/widget.py")}\n'
                        'Restart=on-failure\nRestartSec=2\nTimeoutStopSec=5\n')
                    managed.append(str(unit));service('daemon-reload',check=True)
                elif str(unit) in previous.get('files',[]):unit.unlink(missing_ok=True)
                if want_autostart:
                    autostart.parent.mkdir(parents=True,exist_ok=True);autostart.write_text(desktop_text)
                    managed.append(str(autostart))
                elif str(autostart) in previous.get('files',[]):autostart.unlink(missing_ok=True)
                if want_shortcut:
                    shortcut.parent.mkdir(parents=True,exist_ok=True)
                    shortcut.write_text(desktop_text);shortcut.chmod(0o755)
                    managed.append(str(shortcut))
                    if shutil.which('gio'):
                        try:
                            subprocess.run(['gio','set','-t','string',str(shortcut),'metadata::trusted','true'],
                                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
                        except (OSError,subprocess.SubprocessError):pass
                elif shortcut and str(shortcut) in previous.get('files',[]):shortcut.unlink(missing_ok=True)
                manifest.write_text(json.dumps({'app':APP,'version':version,'systemd':use_systemd,'python':selected,
                    'autostart':bool(want_autostart),'launcher':str(launcher),
                    'desktop_shortcut':str(shortcut) if want_shortcut else None,
                    'desktop_shortcut_enabled':bool(want_shortcut),'files':managed},indent=2)+'\n')
                # XDG autostart supplies the current display before starting the service.
                ui.item(ui.text('Application menu entry','Пункт меню приложений'))
                if want_shortcut:ui.item(ui.text('Desktop shortcut','Ярлык рабочего стола'))
                ui.item(ui.text('Start at login enabled','Запуск при входе включён') if want_autostart else ui.text('Launch whenever you want','Запуск по желанию'))
                if was_running and use_systemd:service('start',APP+'.service',check=True)
                if old_link.is_symlink() and old_link.resolve()==unit.resolve():old_link.unlink()
            except BaseException:
                for name in reversed(installed):remove(target/name)
                for name in backed:(backup/name).replace(target/name)
                raise
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,dependencies.DependencyError,KeyboardInterrupt) as error:
        restore(old_files)
        if created and target.exists():remove(target)
        elif fresh_runtime and fresh_runtime.exists():remove(fresh_runtime)
        if stopped:
            service('daemon-reload')
            if previous.get('systemd'):service('start',APP+'.service')
        ui.error(str(error) or 'Installation cancelled.','Установка остановлена: '+(str(error) or 'отмена'))
        return 130 if isinstance(error,(KeyboardInterrupt,dependencies.ProvisionCancelled)) else 1
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database',str(desktop.parent)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    ui.step(5,'Ready for music','Можно включать музыку')
    source_summary(ui,selected,target,setup=not args.skip_check)
    ui.note('Open Emberbox Audio from the application menu, or run:','Открой Emberbox Audio в меню приложений или выполни:')
    ui.command([str(launcher)])
    ui.success('Installed. Make yourself at home.','Установлено. Устраивайся поудобнее.')
    return 0


if __name__=='__main__':raise SystemExit(main())
