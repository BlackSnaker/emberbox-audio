"""Yandex Music in an independent official-site playback session."""
import json
from pathlib import Path
import subprocess
import sys
import time
from gi.repository import GLib
from apple_web import AppleWeb
from apple_bridge import BridgeUnavailable
import apple_setup
from paths import APP_ID, CONFIG_DIR
from source_picker import text
from gui_session import systemd_environment

ENGINE_CONFIG = CONFIG_DIR/'yandex-engine.json'


def prepare(runtime=None,module=None):
    existing=apple_setup.configured(ENGINE_CONFIG)
    shared=apple_setup.configured()
    if shared and not runtime and not module:
        config={key:shared[key] for key in ('runtime','cdm_module')}
        config['profile']=(existing or {}).get('profile',str(CONFIG_DIR/'yandex-web-profile'))
        if config==existing:return existing
        apple_setup.save(config,ENGINE_CONFIG)
        return config
    if existing and not runtime and not module:return existing
    return apple_setup.prepare(runtime,module,config_path=ENGINE_CONFIG,profile_name='yandex-web-profile')


class YandexWeb(AppleWeb):
    socket_filename='yandex-player.sock'
    extra_methods=('wave','feedback')

    def _start_engine(self):
        unit=APP_ID+'-yandex.service'
        with self.start_lock:
            if subprocess.run(['systemctl','--user','is-active','--quiet',unit],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
                return
            config=json.loads(ENGINE_CONFIG.read_text())
            command=[sys.executable,str(Path(__file__).with_name('apple_engine_launcher.py')),
                '--service','yandex','--runtime',config['runtime'],'--cdm-module',config['cdm_module'],
                '--profile',config.get('profile',str(CONFIG_DIR/'yandex-web-profile')),
                '--socket',str(self.bridge.path)]
            subprocess.run(['systemd-run','--user','--collect','--service-type=exec',
                '--unit='+APP_ID+'-yandex',*systemd_environment(),*command],check=True,timeout=5,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def _started(self,future):
        self.starting=False
        if not self.closed:
            try:future.result();self.error=''
            except Exception:self.error=text('Connect Yandex Music in Accounts.','Подключи Яндекс Музыку в разделе аккаунтов.')
            self.changed()
        return False

    def request(self,method,**params):
        self.ensure_started()
        until=time.monotonic()+20
        while not self.connected and not self.closed and time.monotonic()<until:
            if self.error:raise BridgeUnavailable(self.error)
            time.sleep(.1)
        try:
            starts_playback=method in ('wave','play') or method=='transport' and params.get('action')!='pause'
            if starts_playback:
                if not self.enabled:return {'skipped':True}
                # Source selection and a first Play can arrive concurrently.
                # Wait for the engine's acknowledgement before starting audio.
                self.bridge.request('enable',enabled=True)
                if not self.enabled:return {'skipped':True}
            return self.bridge.request(method,**params)
        except BridgeUnavailable as error:
            messages={
                'SIGN_IN_REQUIRED':text('Sign in with Yandex ID in Accounts.','Войди в Яндекс ID в разделе аккаунтов.'),
                'SUBSCRIPTION_REQUIRED':text('Yandex Plus is required for My Wave.','Для Моей волны нужен Яндекс Плюс.'),
                'REGION_UNAVAILABLE':text('Yandex Music is unavailable in this region.','Яндекс Музыка недоступна в этом регионе.'),
                'ADAPTER_UNAVAILABLE':text('The website controls have changed. Open Yandex Music to continue.',
                    'Элементы сайта изменились. Открой окно Яндекс Музыки для продолжения.'),
                'TypeError':text('The Yandex Music controls could not be connected. Reconnect in Accounts.',
                    'Не удалось подключить управление Яндекс Музыкой. Переподключи её в Аккаунтах.'),
                'ReferenceError':text('The Yandex Music controls could not be connected. Reconnect in Accounts.',
                    'Не удалось подключить управление Яндекс Музыкой. Переподключи её в Аккаунтах.'),
                'MEDIA_PLAYBACK':text('The site could not start audio. Open Yandex Music and check the playback engine.',
                    'Сайт не смог запустить звук. Открой Яндекс Музыку и проверь движок воспроизведения.'),
                'NOT_READY':text('Yandex Music is loading. Try again shortly.','Яндекс Музыка загружается. Попробуй чуть позже.'),
                'TIMEOUT':text('Yandex Music took too long. Retry.','Яндекс Музыка долго отвечает. Повтори попытку.')}
            raise BridgeUnavailable(messages.get(str(error),text('Yandex Music did not respond. Reconnect in settings.',
                'Яндекс Музыка не ответила. Обнови подключение в настройках.'))) from None

    def _action_done(self,future):
        if self.closed:return False
        try:future.result();self.error=''
        except Exception as error:self.error=str(error)
        self.poll();self.changed()
        return False

    def _status_done(self,future):
        self.busy=False
        if not self.closed:
            try:
                self.state=future.result()
                if self.state.get('integrationVersion') in (1,2,3,4,5) and not self.upgrade_attempted:
                    self.upgrade_attempted=self.upgrading=True
                    self.pool.submit(self._upgrade_adapter,dict(self.state)).add_done_callback(lambda item:GLib.idle_add(self._adapter_upgraded,item))
            except Exception:self.state={}
            self.changed()
        return False

    def _upgrade_adapter(self,previous):
        # Replace only Yandex's older page adapter; its own signed-in profile
        # is kept, and the Apple Music playback process is never restarted.
        prepare()
        subprocess.run(['systemctl','--user','stop',APP_ID+'-yandex.service'],check=True,timeout=8,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self._start_engine()
        until=time.monotonic()+30
        while not self.closed and time.monotonic()<until:
            if self.connected:
                try:
                    status=self.bridge.request('status')
                    if status.get('integrationVersion',0)>=6 and (status.get('ready') or not previous.get('playing')):
                        self.bridge.request('enable',enabled=self.enabled)
                        if self.enabled and previous.get('playing') and status.get('authorized'):
                            if previous.get('wave'):self.bridge.request('wave')
                            else:self.bridge.request('transport',action='play')
                        return
                except BridgeUnavailable:pass
            time.sleep(.3)
        raise BridgeUnavailable('Yandex adapter update timed out')

    def _adapter_upgraded(self,future):
        self.upgrading=False
        if not self.closed:
            try:future.result();self.error=''
            except Exception:self.error=text('Reconnect Yandex Music in Accounts to finish the update.',
                'Переподключи Яндекс Музыку в Аккаунтах для завершения обновления.')
            self.poll();self.changed()
        return False
