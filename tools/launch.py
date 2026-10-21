#!/usr/bin/env python3
"""Launch using this desktop's display environment, including on KDE Plasma."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

APP='emberbox-audio'
ROOT=Path(__file__).resolve().parents[1]
SESSION_KEYS=('DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE',
              'XDG_SESSION_DESKTOP','DESKTOP_SESSION','DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR',
              'XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME',
              'EMBERBOX_DESKTOP_MODE',
              'LANG','LC_ALL','LC_MESSAGES')


def session_file(environ=None):
    env=os.environ if environ is None else environ
    base=Path(env.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))
    if not base.is_dir() or base.stat().st_uid!=os.getuid():
        raise OSError('A private desktop runtime directory is required')
    folder=base/APP
    if folder.is_symlink():raise OSError('Invalid runtime directory')
    folder.mkdir(mode=0o700,exist_ok=True)
    if folder.stat().st_uid!=os.getuid():raise OSError('Invalid runtime owner')
    values={key:env[key] for key in SESSION_KEYS if env.get(key) and '\n' not in env[key] and '\r' not in env[key]}
    # EnvironmentFile is parsed by systemd, not by a shell. No expansion.
    content=''.join(key+'="'+value.replace('\\','\\\\').replace('"','\\"')+'"\n' for key,value in values.items())
    with tempfile.NamedTemporaryFile(mode='w',dir=folder,prefix='.session-',delete=False) as stream:
        temporary=Path(stream.name);stream.write(content)
    temporary.chmod(0o600);temporary.replace(folder/'session.env')
    return folder/'session.env'


def main():
    sys.path.insert(0,str(ROOT/'src'))
    try:from widget_control import send
    except ImportError:send=lambda _action:False
    action='Hide' if '--hide' in sys.argv[1:] else 'Quit' if '--quit' in sys.argv[1:] else 'Show'
    if send(action):return 0
    if action!='Show':return 0
    try:config=json.loads((ROOT/'.emberbox-install.json').read_text())
    except (OSError,ValueError):config={}
    python=Path(config.get('python',sys.executable))
    if not python.is_file():python=Path(sys.executable)
    env=dict(os.environ,GDK_BACKEND='x11')
    env['PATH']=str(python.parent)+os.pathsep+env.get('PATH','/usr/local/bin:/usr/bin:/bin')
    if not env.get('DISPLAY'):
        print('Open Emberbox Audio from a graphical desktop session with X11/XWayland enabled.',file=sys.stderr)
        return 1
    if config.get('systemd') and shutil.which('systemctl'):
        try:
            # Keep display variables scoped to Emberbox, not the entire user manager.
            session_file(env)
            result=subprocess.run(['systemctl','--user','start',APP+'.service'],env=env,timeout=12)
            if result.returncode==0:return 0
        except (OSError,subprocess.SubprocessError):pass
    os.execve(str(python),[str(python),str(ROOT/'src/widget.py'),*sys.argv[1:]],env)


if __name__=='__main__':raise SystemExit(main())
