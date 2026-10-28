"""Spotify's official web player in an Ember-owned, isolated profile."""
import json
from pathlib import Path
import subprocess
import sys
import time
import threading
from gi.repository import GLib
from apple_web import AppleWeb
from apple_bridge import BridgeUnavailable
import apple_setup
from paths import APP_ID,CONFIG_DIR
from source_picker import text
from gui_session import systemd_environment

ENGINE_CONFIG=CONFIG_DIR/'spotify-engine.json'


def prepare(runtime=None,module=None):
    existing=apple_setup.configured(ENGINE_CONFIG)
    shared=apple_setup.configured()
    if shared and not runtime and not module:
        config={key:shared[key] for key in ('runtime','cdm_module')}
        config['profile']=(existing or {}).get('profile',str(CONFIG_DIR/'spotify-web-profile'))
        apple_setup.save(config,ENGINE_CONFIG)
        return config
    if existing and not runtime and not module:return existing
    return apple_setup.prepare(runtime,module,config_path=ENGINE_CONFIG,profile_name='spotify-web-profile')


class SpotifyWeb(AppleWeb):
    socket_filename='spotify-player.sock'

    def __init__(self,changed):
        self.browse_lock=threading.RLock()
        super().__init__(changed)

    def _start_engine(self):
        unit=APP_ID+'-spotify.service'
        with self.start_lock:
            if subprocess.run(['systemctl','--user','is-active','--quiet',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:return
            config=json.loads(ENGINE_CONFIG.read_text())
            command=[sys.executable,str(Path(__file__).with_name('apple_engine_launcher.py')),
                '--service','spotify','--runtime',config['runtime'],'--cdm-module',config['cdm_module'],
                '--profile',config.get('profile',str(CONFIG_DIR/'spotify-web-profile')),'--socket',str(self.bridge.path)]
            subprocess.run(['systemd-run','--user','--collect','--service-type=exec','--unit='+APP_ID+'-spotify',
                *systemd_environment(),*command],check=True,timeout=5,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def _started(self,future):
        self.starting=False
        if not self.closed:
            try:future.result();self.error=''
            except Exception:self.error=text('Connect Spotify in Accounts to prepare playback.','Подключи Spotify в Аккаунтах для подготовки воспроизведения.')
            self.changed()
        return False

    def request(self,method,**params):
        if method in ('browse','tracks','search','artist','artistSection','release'):
            with self.browse_lock:return self._request(method,**params)
        return self._request(method,**params)

    def _request(self,method,**params):
        self.ensure_started()
        until=time.monotonic()+20
        while not self.connected and not self.closed and time.monotonic()<until:
            if self.error:raise BridgeUnavailable(self.error)
            time.sleep(.1)
        try:return self.bridge.request(method,**params)
        except BridgeUnavailable as error:
            messages={
                'SIGN_IN_REQUIRED':text('Sign in to Spotify in Accounts.','Войди в Spotify в разделе Аккаунты.'),
                'PREMIUM_REQUIRED':text('Spotify requires Premium for this playback action.','Для этого действия Spotify требует Premium.'),
                'PLAYBACK_RESTRICTED':text('Spotify does not allow this action right now. Try again after playback starts.','Spotify сейчас не разрешает это действие. Повтори после начала воспроизведения.'),
                'REGION_UNAVAILABLE':text('Spotify is unavailable for this account or region.','Spotify недоступен для этого аккаунта или региона.'),
                'ADAPTER_UNAVAILABLE':text('Open Spotify from Accounts and check its web player.','Открой Spotify через Аккаунты и проверь веб-плеер.'),
                'NOT_READY':text('Spotify is loading. Try again shortly.','Spotify загружается. Попробуй чуть позже.'),
                'TIMEOUT':text('Spotify took too long. Retry.','Spotify долго отвечает. Повтори попытку.')}
            raise BridgeUnavailable(messages.get(str(error),text('Spotify could not complete this request.','Spotify не смог выполнить запрос.'))) from None

    def _action_done(self,future):
        if not self.closed:
            try:future.result();self.error=''
            except Exception as error:self.error=str(error)
            self.poll();self.changed()
        return False

    def _status_done(self,future):
        self.busy=False
        if not self.closed:
            try:self.state=self._seek_state(future.result())
            except Exception:self.state={}
            self.changed()
        return False


class SpotifyClient:
    """Typed compatibility interface for existing shelves and DJ browsing."""
    def __init__(self,player):self.player=player
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def home(self,deadline=None):return self.player.request('browse',category='home')
    def search(self,term):return self.player.request('search',term=str(term)[:200])
    def tracks(self,item,deadline=None):
        uri=str(item.get('uri') or 'spotify:'+str(item.get('href','')).strip('/').replace('/',':'))
        return self.player.request('tracks',uri=uri)
    def play(self,uri):return self.player.request('play',uri=uri)


def client_for(host):
    if getattr(host,'spotify_mode','desktop')=='native' and getattr(host,'spotify_web',None):return SpotifyClient(host.spotify_web)
    from discovery import LocalSpotify
    return LocalSpotify()
