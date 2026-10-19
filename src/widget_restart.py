"""Restart this widget only, preserving the desktop player's process."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from paths import APP_ID


def service_restart():
    """An independent systemd unit can replace even a stuck widget process."""
    service = APP_ID + '.service'
    try:
        groups = Path('/proc/self/cgroup').read_text().splitlines()
    except OSError:
        return False
    if not any(line.endswith('/' + service) for line in groups):
        return False
    systemd_run, systemctl = shutil.which('systemd-run'), shutil.which('systemctl')
    if not systemd_run or not systemctl:
        return False
    subprocess.Popen(
        [systemd_run, '--user', '--collect', f'--unit=emberbox-restart-{time.time_ns()}',
         systemctl, '--user', 'restart', service],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def replace_process(script):
    """Source/direct launches keep their PID and release the old instance lock."""
    os.execv(sys.executable, [sys.executable, str(script), *sys.argv[1:]])
