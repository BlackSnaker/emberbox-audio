"""Keep launched desktop applications independent of the widget service."""
import os
from pathlib import Path
import shutil
import subprocess
import time
from gui_session import systemd_environment


def launch(command):
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/nonexistent'))
    if shutil.which('systemd-run') and (runtime/'systemd/private').exists():
        command = ['systemd-run','--user','--collect',
                   f'--unit=emberbox-launch-{time.time_ns()}',*systemd_environment(),*command]
    return subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
