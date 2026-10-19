"""Private local transport for the native player and optional Firefox companion."""
import json
import os
from pathlib import Path
import socket
import struct
import threading
import uuid
from paths import APP_ID, CACHE_DIR

MAX_MESSAGE = 2_000_000


def socket_path(app=APP_ID, filename='apple-music.sock'):
    parent = Path(os.environ.get('XDG_RUNTIME_DIR', CACHE_DIR)) / app
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return parent / filename


class BridgeUnavailable(RuntimeError):
    pass


class AppleBridge:
    def __init__(self, filename='apple-music.sock', methods=('browse', 'tracks', 'play', 'status')):
        self.methods = methods
        self.path = socket_path(filename=filename)
        self.path.unlink(missing_ok=True)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.path))
        os.chmod(self.path, 0o600)
        self.server.listen(2)
        self.connection = None
        self.pid = 0
        self.pending = {}
        self.lock = threading.Lock()
        self.closed = False
        threading.Thread(target=self._accept, daemon=True, name='apple-bridge').start()

    @property
    def connected(self):
        return self.connection is not None

    def _accept(self):
        while not self.closed:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            try:
                pid, uid, _gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid():
                    connection.close()
                    continue
            except (OSError, AttributeError):
                pid = 0
            with self.lock:
                old = self.connection
                self.connection = connection
                self.pid = pid
            if old:
                old.close()
            threading.Thread(target=self._read, args=(connection,), daemon=True).start()

    def _read(self, connection):
        try:
            with connection.makefile('rb') as stream:
                while not self.closed:
                    line = stream.readline(MAX_MESSAGE + 1)
                    if not line or len(line) > MAX_MESSAGE:
                        break
                    result = json.loads(line)
                    with self.lock:
                        pending = self.pending.get(str(result.get('id', '')))
                    if pending:
                        pending['result'] = result
                        pending['event'].set()
        except (OSError, ValueError):
            pass
        finally:
            with self.lock:
                if self.connection is connection:
                    self.connection = None
                    self.pid = 0
                    for pending in self.pending.values():
                        pending['result'] = {'error':'Apple Music connection closed'}
                        pending['event'].set()
            connection.close()

    def request(self, method, **params):
        if method not in self.methods:
            raise ValueError('Unsupported Apple Music operation')
        ident = uuid.uuid4().hex
        pending = {'event': threading.Event()}
        with self.lock:
            if not self.connection:
                raise BridgeUnavailable('Connect the Apple Music browser companion first.')
            self.pending[ident] = pending
            try:
                self.connection.sendall(json.dumps({'id': ident, 'method': method, 'params': params}).encode() + b'\n')
            except OSError as error:
                self.pending.pop(ident, None)
                raise BridgeUnavailable('Apple Music browser connection was closed.') from error
        try:
            if not pending['event'].wait(18):
                raise BridgeUnavailable('Apple Music did not reply. Keep its signed-in tab open.')
            response = pending['result']
            if response.get('error'):
                raise BridgeUnavailable(str(response['error'])[:250])
            return response.get('result') or {}
        finally:
            with self.lock:
                self.pending.pop(ident, None)

    def close(self):
        self.closed = True
        if self.connection:
            self.connection.close()
        self.server.close()
        self.path.unlink(missing_ok=True)
        for pending in list(self.pending.values()):
            pending['result'] = {'error': 'Widget closed'}
            pending['event'].set()
