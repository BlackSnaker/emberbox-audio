"""Account connection flow. Authentication stays in the services' official UI."""
from concurrent.futures import ThreadPoolExecutor
import shutil
import subprocess
import time
from gi.repository import GLib
import apple_setup
import yandex_web
from desktop_launch import launch
from source_picker import text


def spotify_command():
    executable = shutil.which('spotify')
    if executable:
        return [executable]
    flatpak = shutil.which('flatpak')
    if flatpak:
        try:
            result = subprocess.run([flatpak,'info','com.spotify.Client'],timeout=4,
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                return [flatpak,'run','--command=spotify','com.spotify.Client']
        except (OSError,subprocess.SubprocessError):
            pass
    return None


class Accounts:
    def __init__(self, apple, changed, open_spotify, open_picks, choose_source, yandex=None):
        self.apple,self.yandex,self.changed = apple,yandex,changed
        self.open_spotify,self.open_picks,self.choose_source = open_spotify,open_picks,choose_source
        self.pool = ThreadPoolExecutor(max_workers=2,thread_name_prefix='accounts')
        self.spotify = None
        self.spotify_checked = False
        self.sessions = []
        self.pending = {'spotify':False,'apple-music':False,'yandex-music':False}
        self.preparing_source = self.error_source = ''
        self.error = ''
        self.preparing = False
        self.closed = False
        self.checking = False
        self.runtime,self.module = None,None
        self.waiting_since = 0.

    def refresh(self):
        if not self.checking and not self.closed:
            self.checking = True
            future = self.pool.submit(spotify_command)
            future.add_done_callback(lambda item:GLib.idle_add(self._checked,item))

    def _checked(self,future):
        self.checking = False
        if not self.closed:
            try:self.spotify = future.result()
            except Exception:self.spotify = None
            self.spotify_checked = True
            self.changed()
        return False

    def update(self,sessions):
        self.sessions = sessions
        spotify = self.spotify_session()
        if spotify and spotify.metadata.get('xesam:title'):
            self.pending['spotify'] = False
        for source,service in (('apple-music',self.apple),('yandex-music',self.yandex)):
            if not service:continue
            if self.pending[source] and service.connected and service.state.get('authorized'):
                self.pending[source] = False
                service.action('hide')
            elif self.pending[source] and not service.connected and time.monotonic()-self.waiting_since>30:
                self.pending[source] = False
                self.error,self.error_source = 'START_FAILED',source
        self.changed()

    def spotify_session(self):
        return next((s for s in self.sessions if s.name.startswith('org.mpris.MediaPlayer2.spotify')),None)

    def state(self,source):
        if source == 'spotify':
            session = self.spotify_session()
            ready = bool(session and session.metadata.get('xesam:title'))
            installed = bool(self.spotify or session)
            return {'ready':ready,'busy':not self.spotify_checked and not installed,'status':text('Connected','Подключён') if ready else
                    text('Finish sign-in','Заверши вход') if self.pending[source] else
                    text('Client found','Клиент найден') if installed else
                    text('Install Spotify','Нужен Spotify') if self.spotify_checked else text('Checking…','Проверяю…'),
                    'description':text('Music controls and your personal picks, together.','Управление музыкой и личные подборки рядом.') if ready else
                    text('Sign in in the Spotify window, then play a song. Emberbox will connect automatically.',
                         'Войди в окне Spotify и включи трек. Emberbox подключится автоматически.') if installed else
                    text('Install the official Spotify app, then return here to sign in.',
                         'Установи официальный Spotify, затем вернись сюда для входа.'),
                    'button':text('Open Spotify','Открыть Spotify') if ready else
                    text('Sign in to Spotify','Войти в Spotify') if installed else text('Get Spotify','Установить Spotify'),
                    'details':False}
        service = self.yandex if source=='yandex-music' else self.apple
        is_yandex = source=='yandex-music'
        name = text('Yandex Music','Яндекс Музыка') if is_yandex else 'Apple Music'
        ready = bool(service and service.connected and service.state.get('authorized'))
        preparing = self.preparing and self.preparing_source==source
        error = self.error if not self.error_source or self.error_source==source else ''
        errors = {
            'NEEDS_ENGINE':text('Choose a compatible playback engine below.','Выбери совместимый движок воспроизведения ниже.'),
            'NEEDS_DRM':text('Choose an installed Widevine module below.','Выбери установленный модуль Widevine ниже.'),
            'INCOMPATIBLE_ENGINE':text('This engine cannot play protected audio. Choose another engine.',
                                       'Этот движок не воспроизводит защищённую музыку. Выбери другой.'),
            'START_FAILED':text('Could not open '+name+'. Check the playback setup and retry.',
                                'Не удалось открыть '+name+'. Проверь настройку воспроизведения и повтори.')}
        return {'ready':ready,'busy':preparing,'status':text('Connected','Подключён') if ready else
                text('Preparing…','Подготавливаю…') if preparing else
                text('Finish sign-in','Заверши вход') if self.pending[source] else text('Not connected','Не подключён'),
                'description':errors.get(error) or (text('Your library, search and music are ready inside Emberbox.',
                    'Медиатека, поиск и музыка доступны внутри Emberbox.') if ready else
                    text('Sign in with Yandex ID to listen to My Wave. A Yandex Plus subscription is required.',
                         'Войди в Яндекс ID, чтобы слушать Мою волну. Нужна подписка Яндекс Плюс.') if is_yandex else
                    text('Sign in to your Apple Account. Your library will appear here. A subscription is needed for full songs.',
                         'Войди в Apple Account — медиатека появится здесь. Для полных треков нужна подписка.')),
                'button':text('Yandex Music account','Аккаунт Яндекс Музыки') if is_yandex and ready else
                text(name+' account','Аккаунт '+name) if ready else
                text('Retry connection','Повторить подключение') if error else text('Sign in to Yandex Music','Войти в Яндекс Музыку') if is_yandex else text('Sign in to '+name,'Войти в '+name),
                'details':bool(error)}

    def connect(self,source):
        if self.closed:
            return
        if source == 'spotify':
            if not self.spotify and not self.spotify_session():
                launch(['xdg-open','https://www.spotify.com/download/linux/'])
                return
            self.pending[source] = True
            self.open_spotify()
            self.changed()
            return
        if self.preparing:
            return
        service=self.yandex if source=='yandex-music' else self.apple
        if not service:return
        if service.connected:
            self.pending[source] = not bool(service.state.get('authorized'))
            self.waiting_since = time.monotonic()
            service.action('show')
            self.changed()
            return
        self.preparing = True
        self.preparing_source = self.error_source = source
        self.error = ''
        self.changed()
        self.pool.submit(yandex_web.prepare if source=='yandex-music' else apple_setup.prepare,self.runtime,self.module).add_done_callback(
            lambda item:GLib.idle_add(self._prepared,item,source))

    def _prepared(self,future,source='apple-music'):
        self.preparing = False
        if self.closed:
            return False
        try:
            future.result()
            self.pending[source] = True
            self.waiting_since = time.monotonic()
            service=self.yandex if source=='yandex-music' else self.apple
            service.error = ''
            service.action('show')
        except apple_setup.SetupError as error:self.error = str(error)
        except Exception:self.error = 'START_FAILED'
        self.changed()
        return False

    def listen(self,source):
        self.choose_source(source)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False,cancel_futures=True)
