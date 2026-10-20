"""A session-only KWin bridge for XWayland's missing all-desktops request.

The script only touches Emberbox's desktop-widget role. It writes no KWin
configuration or rules and unloads when that window closes, including crashes.
"""
import json
import os
from pathlib import Path
import time
from gi.repository import Gio, GLib
from paths import APP_ID, CACHE_DIR


def script_source(plugin):
    return '''function apply(window) {
      if (String(window.resourceName).toLowerCase() !== "emberbox-audio" ||
          String(window.windowRole) !== "desktop-widget") return;
      window.onAllDesktops = true;
      window.closed.connect(function() {
        callDBus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting",
                 "unloadScript", PLUGIN);
      });
    }
    workspace.windowAdded.connect(apply);
    workspace.windowList().forEach(apply);
    '''.replace('PLUGIN', json.dumps(plugin))


class KWinDesktop:
    def __init__(self):
        self.closed = False
        self.loaded = False
        self.error = ''
        self.connection = None
        self.cancellable = Gio.Cancellable()
        self.plugin = f'emberbox-audio-desktop-{os.getpid()}-{time.time_ns()}'
        self.path = Path(os.environ.get('XDG_RUNTIME_DIR', CACHE_DIR))/APP_ID/(self.plugin+'.js')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(self.path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as target:
                target.write(script_source(self.plugin))
        except OSError:
            self.error = 'KWin workspace integration unavailable'
            return
        Gio.bus_get(Gio.BusType.SESSION, self.cancellable, self._connected)

    def _connected(self, _source, result):
        try:
            self.connection = Gio.bus_get_finish(result)
            if self.closed:
                return
            self.connection.call('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting',
                'loadScript', GLib.Variant('(ss)', (str(self.path), self.plugin)),
                GLib.VariantType.new('(i)'), Gio.DBusCallFlags.NO_AUTO_START, 1500,
                self.cancellable, self._loaded)
        except GLib.Error:
            self.error = 'KWin workspace integration unavailable'

    def _loaded(self, connection, result):
        try:
            identifier = connection.call_finish(result).unpack()[0]
            if self.closed:
                self._unload()
                return
            if identifier < 0:
                self.error = 'KWin workspace integration unavailable'
                return
            self.loaded = True
            connection.call('org.kde.KWin', '/Scripting/Script'+str(identifier),
                'org.kde.kwin.Script', 'run', None, None,
                Gio.DBusCallFlags.NO_AUTO_START, 1500, self.cancellable, self._running)
        except GLib.Error:
            self.error = 'KWin workspace integration unavailable'

    def _running(self, connection, result):
        try:
            connection.call_finish(result)
        except GLib.Error:
            self.error = 'KWin workspace integration unavailable'

    def _unload(self):
        if self.connection:
            self.connection.call('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting',
                'unloadScript', GLib.Variant('(s)', (self.plugin,)), None,
                Gio.DBusCallFlags.NO_AUTO_START, 1000, None, None)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.cancellable.cancel()
        self._unload()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
