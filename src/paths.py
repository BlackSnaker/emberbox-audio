"""Per-user paths. No machine-specific files or shared application state."""
import fcntl
import os
from pathlib import Path

APP_ID = 'emberbox-audio'
CONFIG_DIR = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / APP_ID
CACHE_DIR = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / APP_ID


def instance_lock():
    folder = Path(os.environ.get('XDG_RUNTIME_DIR', CACHE_DIR)) / APP_ID
    folder.mkdir(parents=True, exist_ok=True)
    handle = (folder / 'instance.lock').open('a')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise SystemExit('Emberbox is already running.')
    return handle
