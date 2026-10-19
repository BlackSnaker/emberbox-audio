"""Account connection flow. Authentication stays in the services' official UI."""
from concurrent.futures import ThreadPoolExecutor
import shutil
import subprocess
import time
from gi.repository import GLib
import apple_setup
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
    def __init__(self, apple, changed, open_spotify, open_picks, choose_source):
        self.apple,self.changed = apple,changed
        self.open_spotify,self.open_picks,self.choose_source = open_spotify,open_picks,choose_source
        self.pool = ThreadPoolExecutor(max_workers=2,thread_name_prefix='accounts')
        self.spotify = None
        self.spotify_checked = False
        self.sessions = []
        self.pending = {'spotify':False,'apple-music':False}
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
        if self.pending['apple-music'] and self.apple.connected and self.apple.state.get('authorized'):
            self.pending['apple-music'] = False
            self.apple.action('hide')
        elif self.pending['apple-music'] and not self.apple.connected and time.monotonic()-self.waiting_since>30:
            self.pending['apple-music'] = False
            self.error = 'START_FAILED'
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
        ready = bool(self.apple.connected and self.apple.state.get('authorized'))
        errors = {
            'NEEDS_ENGINE':text('Choose a compatible playback engine below.','Выбери совместимый движок воспроизведения ниже.'),
            'NEEDS_DRM':text('Choose an installed Widevine module below.','Выбери установленный модуль Widevine ниже.'),
            'INCOMPATIBLE_ENGINE':text('This engine cannot play protected audio. Choose another engine.',
                                       'Этот движок не воспроизводит защищённую музыку. Выбери другой.'),
            'START_FAILED':text('Could not open Apple Music. Check the playback setup and retry.',
                                'Не удалось открыть Apple Music. Проверь настройку воспроизведения и повтори.')}
        return {'ready':ready,'busy':self.preparing,'status':text('Connected','Подключён') if ready else
                text('Preparing…','Подготавливаю…') if self.preparing else
                text('Finish sign-in','Заверши вход') if self.pending[source] else text('Not connected','Не подключён'),
                'description':errors.get(self.error) or (text('Your library, search and music are ready inside Emberbox.',
                    'Медиатека, поиск и музыка доступны внутри Emberbox.') if ready else
                    text('Sign in to your Apple Account. Your library will appear here. A subscription is needed for full songs.',
                         'Войди в Apple Account — медиатека появится здесь. Для полных треков нужна подписка.')),
                'button':text('Apple Music account','Аккаунт Apple Music') if ready else
                text('Retry connection','Повторить подключение') if self.error else text('Sign in to Apple Music','Войти в Apple Music'),
                'details':bool(self.error)}

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
        if self.apple.connected:
            self.pending[source] = not bool(self.apple.state.get('authorized'))
            self.waiting_since = time.monotonic()
            self.apple.action('show')
            self.changed()
            return
        self.preparing = True
        self.error = ''
        self.changed()
        self.pool.submit(apple_setup.prepare,self.runtime,self.module).add_done_callback(
            lambda item:GLib.idle_add(self._prepared,item))

    def _prepared(self,future):
        self.preparing = False
        if self.closed:
            return False
        try:
            future.result()
            self.pending['apple-music'] = True
            self.waiting_since = time.monotonic()
            self.apple.error = ''
            self.apple.action('show')
        except apple_setup.SetupError as error:self.error = str(error)
        except Exception:self.error = 'START_FAILED'
        self.changed()
        return False

    def listen(self,source):
        self.choose_source(source)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False,cancel_futures=True)
