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
    if existing and not runtime and not module:
        return existing
    shared=apple_setup.configured()
    if shared and not runtime and not module:
        config={key:shared[key] for key in ('runtime','cdm_module')}
        config['profile']=str(CONFIG_DIR/'yandex-web-profile')
        apple_setup.save(config,ENGINE_CONFIG)
        return config
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
        try:return self.bridge.request(method,**params)
        except BridgeUnavailable as error:
            messages={
                'SIGN_IN_REQUIRED':text('Sign in with Yandex ID in Accounts.','Войди в Яндекс ID в разделе аккаунтов.'),
                'SUBSCRIPTION_REQUIRED':text('Yandex Plus is required for My Wave.','Для Моей волны нужен Яндекс Плюс.'),
                'REGION_UNAVAILABLE':text('Yandex Music is unavailable in this region.','Яндекс Музыка недоступна в этом регионе.'),
                'ADAPTER_UNAVAILABLE':text('The website controls have changed. Open Yandex Music to continue.',
                    'Элементы сайта изменились. Открой окно Яндекс Музыки для продолжения.'),
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
            try:self.state=future.result();self.error=''
            except Exception:self.state={}
            self.changed()
        return False
