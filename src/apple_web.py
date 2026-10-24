"""App-owned Apple Music transport. The signed-in site runs in the background."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from gi.repository import GLib
from apple_bridge import AppleBridge, BridgeUnavailable
from paths import APP_ID, CONFIG_DIR
from source_picker import text
from gui_session import systemd_environment

ENGINE_CONFIG = CONFIG_DIR/'apple-engine.json'


class AppleWeb:
    native = True
    def __init__(self, changed):
        self.changed = changed
        self.bridge = AppleBridge(getattr(self,'socket_filename','apple-player.sock'),
            ('status','browse','tracks','search','play','transport','seek','show','hide','enable','artist','artistSection','release')+getattr(self,'extra_methods',()))
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='apple-player')
        self.state = {}
        self.enabled = False
        self.closed = False
        self.busy = False
        self.starting = False
        self.error = ''
        self.last_enable = None
        self.upgrading = False
        self.upgrade_attempted = False
        self.start_lock = threading.Lock()
        self.timer = GLib.timeout_add(750, self.poll)

    @property
    def connected(self):
        return self.bridge.connected

    @property
    def pid(self):
        return self.bridge.pid

    def ensure_started(self):
        if self.closed or self.starting or self.connected:
            return
        self.starting = True
        self.pool.submit(self._start_engine).add_done_callback(lambda future:GLib.idle_add(self._started, future))

    def _start_engine(self):
        unit = APP_ID+'-apple.service'
        with self.start_lock:
            if subprocess.run(['systemctl','--user','is-active','--quiet',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0:
                return
            config = json.loads(ENGINE_CONFIG.read_text())
            command = [sys.executable, str(Path(__file__).with_name('apple_engine_launcher.py')),
                       '--runtime',config['runtime'], '--cdm-module',config['cdm_module'],
                       '--profile',config.get('profile',str(CONFIG_DIR/'apple-web-profile')),
                       '--socket',str(self.bridge.path)]
            subprocess.run(['systemd-run','--user','--collect','--service-type=exec',
                            '--unit='+APP_ID+'-apple',*systemd_environment(),*command],check=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)

    def _started(self, future):
        self.starting = False
        if self.closed:
            return False
        try:
            future.result()
            self.error = ''
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            self.error = text('Apple Music engine is not configured. See setup instructions.',
                              'Не настроен движок Apple Music. См. инструкцию установки.')
        self.changed()
        return False

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if enabled:
            self.ensure_started()
        if self.connected and self.last_enable != self.enabled:
            self.last_enable = self.enabled
            self.action('enable', enabled=self.enabled)

    def request(self, method, **params):
        self.ensure_started()
        until = time.monotonic()+20
        while not self.connected and not self.closed and time.monotonic()<until:
            if self.error:
                raise BridgeUnavailable(self.error)
            time.sleep(.1)
        try:
            return self.bridge.request(method, **params)
        except BridgeUnavailable as error:
            code = str(error)
            message = text('Apple Music is still loading. Try again shortly.', 'Apple Music ещё загружается. Попробуй чуть позже.')
            if code == 'SIGN_IN_REQUIRED':
                message = text('Sign in to Apple Music to load your library.', 'Войди в Apple Music, чтобы загрузить медиатеку.')
            elif code == 'APPLE_REQUEST_FAILED':
                message = text('Apple Music could not complete this request.', 'Apple Music не смог выполнить запрос.')
            elif code == 'TIMEOUT':
                message = text('Apple Music took too long. Try again.', 'Apple Music долго отвечает. Попробуй ещё раз.')
            elif code in ('CONTENT_UNAVAILABLE','CONTENT_UNSUPPORTED','GEO_BLOCK','NOT_FOUND'):
                message = text('This track is unavailable in Apple Music.', 'Этот трек недоступен в Apple Music.')
            elif code in ('SUBSCRIPTION_ERROR','UNAUTHORIZED_ERROR','TOKEN_EXPIRED'):
                message = text('Check your Apple Music sign-in and subscription.', 'Проверь вход и подписку Apple Music.')
            elif code not in ('NOT_READY',):
                message = text('Apple Music could not complete this request.', 'Apple Music не смог выполнить запрос.')
            raise BridgeUnavailable(message) from None

    def action(self, method, **params):
        if self.closed:
            return
        future = self.pool.submit(self.request, method, **params)
        future.add_done_callback(lambda item:GLib.idle_add(self._action_done,item))

    def _action_done(self, future):
        if self.closed:
            return False
        try:
            future.result()
            self.error = ''
        except Exception:
            self.error = text('Apple Music did not respond. Reconnect in settings.', 'Apple Music не ответил. Переподключи источник в настройках.')
        self.poll()
        self.changed()
        return False

    def poll(self):
        if self.closed:
            return False
        if self.upgrading:
            return True
        if not self.connected:
            self.last_enable = None
            return True
        if self.last_enable != self.enabled:
            self.set_enabled(self.enabled)
        if not self.busy:
            self.busy = True
            self.pool.submit(self.bridge.request,'status').add_done_callback(lambda future:GLib.idle_add(self._status_done,future))
        return True

    def _status_done(self, future):
        self.busy = False
        if self.closed:
            return False
        try:
            self.state = future.result()
            self.error = ''
            if self.state.get('ready') and self.state.get('integrationVersion',0)<8 and not self.upgrade_attempted:
                self.upgrade_attempted = self.upgrading = True
                self.pool.submit(self._upgrade,dict(self.state)).add_done_callback(
                    lambda item:GLib.idle_add(self._upgraded,item))
        except Exception:
            self.state = {}
        self.changed()
        return False

    def _upgrade(self,state):
        # A widget update can meet an older independent playback engine.
        # Replace it once and retain the current song and listening position.
        if not state.get('id') and state.get('title') and state.get('artist'):
            try:
                results = self.bridge.request('search',term=state['title']+' '+state['artist']).get('items',[])
                exact = [item for item in results if item.get('title','').casefold()==state['title'].casefold()
                         and item.get('artist','').casefold()==state['artist'].casefold()]
                if exact:
                    state['id'] = min(exact,key=lambda item:abs(item.get('duration_ms',0)/1000-state.get('duration',0)))['id']
            except BridgeUnavailable:pass
        try:self.bridge.request('transport',action='pause')
        except BridgeUnavailable:pass
        subprocess.run(['systemctl','--user','stop',APP_ID+'-apple.service'],check=True,timeout=8,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self._start_engine()
        until = time.monotonic()+30
        while not self.closed and time.monotonic()<until:
            if self.connected:
                try:
                    current = self.bridge.request('status')
                    if current.get('ready') and current.get('integrationVersion',0)>=8 and (not state.get('authorized') or current.get('authorized')):
                        break
                except BridgeUnavailable:pass
            time.sleep(.3)
        else:raise BridgeUnavailable('Engine upgrade timed out')
        self.bridge.request('enable',enabled=self.enabled)
        if self.enabled and state.get('id') and state.get('authorized'):
            self.bridge.request('play',kind='songs',id=state['id'],position=state.get('position',0),paused=not state.get('playing'))
            if not self.enabled:
                self.bridge.request('transport',action='pause')

    def _upgraded(self,future):
        self.upgrading = False
        if not self.closed:
            try:future.result()
            except Exception:self.error = text('Reconnect Apple Music to finish the update.','Переподключи Apple Music для завершения обновления.')
            self.poll()
            self.changed()
        return False

    def close(self):
        self.closed = True
        GLib.source_remove(self.timer)
        self.bridge.close()
        self.pool.shutdown(wait=False,cancel_futures=True)
