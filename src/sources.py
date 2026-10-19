"""Source selection and nonblocking MPRIS discovery. No browser credentials."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from gi.repository import Gio, GLib
import control

BROWSERS = {
    'firefox': ('firefox', 'firefox-esr', 'librewolf', 'zen'),
    'chromium': ('chromium',), 'chrome': ('google-chrome', 'chrome'),
    'brave': ('brave',), 'edge': ('microsoft-edge', 'msedge'),
    'vivaldi': ('vivaldi',), 'opera': ('opera',),
}


def browser_family(*values):
    text = ' '.join(str(value).lower() for value in values)
    for family, aliases in BROWSERS.items():
        if any(alias in text for alias in aliases):
            return family
    return ''


@dataclass(frozen=True)
class Session:
    name: str
    identity: str = ''
    desktop: str = ''
    pid: int = 0
    properties: dict = field(default_factory=dict)

    @property
    def metadata(self):
        return self.properties.get('Metadata') or {}

    @property
    def family(self):
        # The embedded Apple engine publishes the runtime's Chromium MPRIS
        # identity. It is already exposed by our native Apple Music source.
        try:
            if self.pid and Path(f'/proc/{self.pid}/exe').readlink().name in ('EmberboxApple','EmberboxYandex'):
                return ''
        except OSError:
            pass
        return browser_family(self.desktop, self.identity, self.name)

    @property
    def binding(self):
        # Instance suffixes and PIDs change on every browser launch.
        return self.desktop or self.identity or self.name.split('.instance')[0]

    @property
    def youtube(self):
        host = (urlparse(str(self.metadata.get('xesam:url', ''))).hostname or '').lower()
        return host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be')

    @property
    def apple(self):
        host = (urlparse(str(self.metadata.get('xesam:url', ''))).hostname or '').lower()
        return host == 'music.apple.com'


def choose_session(sessions, source, binding='', current=''):
    if source == 'spotify':
        candidates = [s for s in sessions if s.name.startswith(control.PREFIX)]
    elif source in ('apple-music', 'youtube'):
        is_site = lambda session: session.youtube if source == 'youtube' else session.apple
        candidates = [s for s in sessions if s.family and is_site(s)]
        if binding:
            bound = [s for s in sessions if s.family and s.binding == binding]
            # A known non-Apple URL must never be treated as Apple Music.
            bound = [s for s in bound if not s.metadata.get('xesam:url') or is_site(s)]
            candidates = bound
    else:
        return None
    if not candidates:
        return None
    if len(candidates) > 1:
        return next((s for s in candidates if s.name == current), None)
    return candidates[0]


def scan(connection):
    names = connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
        'org.freedesktop.DBus', 'ListNames', None, GLib.VariantType.new('(as)'),
        Gio.DBusCallFlags.NONE, 500, None).unpack()[0]
    sessions = []
    for name in names:
        if not name.startswith('org.mpris.MediaPlayer2.'):
            continue
        try:
            def properties(interface):
                return connection.call_sync(name, control.PATH,
                    'org.freedesktop.DBus.Properties', 'GetAll',
                    GLib.Variant('(s)', (interface,)), GLib.VariantType.new('(a{sv})'),
                    Gio.DBusCallFlags.NONE, 400, None).unpack()[0]
            root = properties('org.mpris.MediaPlayer2')
            player = properties(control.PLAYER)
            pid = connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'GetConnectionUnixProcessID',
                GLib.Variant('(s)', (name,)), GLib.VariantType.new('(u)'),
                Gio.DBusCallFlags.NONE, 400, None).unpack()[0]
            sessions.append(Session(name, root.get('Identity', name),
                                    root.get('DesktopEntry', ''), pid, player))
        except GLib.Error:
            continue
    return sessions


class Monitor:
    def __init__(self, connection, changed):
        self.connection, self.changed = connection, changed
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='mpris-scan')
        self.actions = ThreadPoolExecutor(max_workers=1, thread_name_prefix='mpris-action')
        self.busy = self.closed = False

    def poll(self):
        if self.closed or self.busy:
            return
        self.busy = True
        self.pool.submit(scan, self.connection).add_done_callback(
            lambda future: GLib.idle_add(self._done, future))

    def _done(self, future):
        self.busy = False
        if not self.closed:
            try:
                self.changed(future.result())
            except GLib.Error as error:
                print(f'MPRIS discovery: {error}', flush=True)
                self.changed([])
        return False

    def call(self, session, method, args=None, root=False):
        def work():
            try:
                self.connection.call_sync(session.name, control.PATH,
                    'org.mpris.MediaPlayer2' if root else control.PLAYER,
                    method, args, None, Gio.DBusCallFlags.NONE, 900, None)
            except GLib.Error as error:
                print(f'MPRIS {method}: {error.message}', flush=True)
        if not self.closed:
            self.actions.submit(work)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.actions.shutdown(wait=False, cancel_futures=True)
