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
    if not VIDEO:
        print('  OK  Optional motion covers: FFmpeg' if shutil.which('ffmpeg') else
              '  --  Optional animated Apple Music covers need ffmpeg; still artwork remains available.')
        try:
            importlib.import_module('mpv')
            if not shutil.which('yt-dlp') and not (Path.home()/'.local/bin/yt-dlp').is_file():
                raise ImportError('yt-dlp')
            print('  OK  Optional YouTube audio: libmpv / python-mpv / yt-dlp')
        except (ImportError, OSError):
            print('  --  Optional YouTube search/playback needs libmpv, python-mpv and yt-dlp.')
    print('\nDependencies found. A running desktop session and PipeWire are required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
