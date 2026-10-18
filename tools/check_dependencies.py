#!/usr/bin/env python3
"""Check requirements without installing packages or changing the desktop."""
import importlib
from pathlib import Path
import shutil
import sys

VIDEO = (Path(__file__).resolve().parents[1] / 'src/youtube.py').exists()


def main():
    missing = []
    modules = ['numpy', 'PIL', 'mpv', 'yt_dlp'] if VIDEO else ['numpy', 'PIL', 'websocket']
    for module in modules:
        try:
            importlib.import_module(module)
            print(f'  OK  Python {module}')
        except (ImportError, OSError):
            missing.append(f'Python {module}')
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gtk, GdkX11  # noqa: F401
        print('  OK  GTK 3 / PyGObject / X11')
    except (ImportError, ValueError):
        missing.append('GTK 3 / PyGObject / X11')
    commands = ['pw-record', 'pw-link', 'pw-dump'] + (['yt-dlp', 'mpv'] if VIDEO else ['pactl'])
    for command in commands:
        if shutil.which(command):
            print(f'  OK  {command}')
        else:
            missing.append(command)
    if missing:
        print('\nMissing: ' + ', '.join(missing))
        print('See docs/INSTALL.md for system packages. Nothing was installed.')
        return 1
    print('\nDependencies found. A running desktop session and PipeWire are required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
