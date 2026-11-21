"""Direct Yandex Music transport (the historical module name is kept for callers)."""
from concurrent.futures import ThreadPoolExecutor
import threading
from urllib.parse import quote
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk
from source_picker import text
from yandex_api import API, YandexError, token_store, track


class YandexWeb:
    native = True

    def __init__(self, changed):
        self.changed = changed
        self.state = {}
        self.enabled = self.closed = self.starting = False
        self.error = ''
        self.api = None
        self.mpv = None
        self.queue = []
        self.index = -1
        self.session = self.batch = ''
        self.lock = threading.RLock()
        self.playback_lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='yandex-api')
        self.timer = GLib.timeout_add(500, self.poll)
        self.pool.submit(self._restore).add_done_callback(self._done)

    @property
    def connected(self):
        return self.api is not None

    @property
    def pid(self):
        import os
        return os.getpid()

    def _restore(self):
        # Retire only the previous Yandex website engine; keep its profile and
        # leave Apple/Spotify services untouched during this migration.
        import subprocess
        from paths import APP_ID
        try:
            active = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', APP_ID + '-yandex.service'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            if active.returncode == 0:
                subprocess.run(['systemctl', '--user', 'stop', APP_ID + '-yandex.service'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=True)
        except (OSError, subprocess.SubprocessError):
            raise YandexError(text('Could not stop the old Yandex Music engine. Stop emberbox-audio-yandex.service and reconnect.',
                                   'Не удалось остановить старый движок Яндекса. Останови emberbox-audio-yandex.service и подключись снова.')) from None
        token = token_store()
        if token:
            self._connect(token)

    def _connect(self, token):
        api = API(token)
        status = api.call('account/status') or {}
        account = status.get('account') or {}
        if not account.get('uid'):
            raise YandexError(text('Invalid Yandex Music account.', 'Неверный аккаунт Яндекс Музыки.'))
        self.api = api
        self.uid = str(account['uid'])
        self.state.update(authorized=True, ready=True, account=account.get('displayName', ''),
                          subscribed=bool((status.get('plus') or {}).get('hasPlus') or
                                          (status.get('subscription') or {}).get('autoRenewable')))

    def _save_token(self, token):
        with self.lock:
            # Validate before replacing the stored credential or current account.
            old_api = self.api
            old_state = dict(self.state)
            old_uid = getattr(self, 'uid', '')
            try:
                self._connect(token)
                token_store(token)
            except Exception:
                self.api, self.state, self.uid = old_api, old_state, old_uid
                raise
            if self.mpv:
                self.mpv.command('stop')
            self.queue = []
            self.index = -1
            self.session = self.batch = ''
            self.state = {k: v for k, v in self.state.items() if k in ('authorized', 'ready', 'account', 'subscribed')}

    def show(self):
        from yandex_auth import authorize, DEVICE_URL
        if getattr(self, 'login_dialog', None):
            self.login_dialog.present()
            return
        cancel = self.login_cancel = threading.Event()
        dialog = self.login_dialog = Gtk.Dialog(title=text('Sign in to Yandex Music', 'Вход в Яндекс Музыку'))
        dialog.add_button(text('Close', 'Закрыть'), Gtk.ResponseType.CLOSE)
        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_border_width(18)
        label = Gtk.Label(label=text(
            'Sign in on ya.ru/device using the code below.\nYour password stays on Yandex’s website.\nThe token is saved in your desktop keyring. Yandex Plus is required.',
            'Войди на ya.ru/device по коду ниже.\nПароль вводится только на сайте Яндекса.\nТокен сохранится в системной связке ключей. Нужен Яндекс Плюс.'))
        label.set_line_wrap(True)
        box.add(label)
        code_label = Gtk.Label(label=text('Requesting a code…', 'Получаю код…'))
        code_label.set_selectable(True)
        box.add(code_label)
        link = Gtk.LinkButton.new_with_label(DEVICE_URL, text('Open ya.ru/device', 'Открыть ya.ru/device'))
        link.set_sensitive(False)
        box.add(link)

        def closed(*_args):
            cancel.set()
            if self.login_dialog is dialog:
                self.login_dialog = None
            dialog.destroy()

        def issued(code):
            if not cancel.is_set() and not self.closed:
                code_label.set_text(code)
                link.set_sensitive(True)
                # Gtk.LinkButton uses the desktop URI handler, not a shell.
                link.activate()
            return False

        def finished(error):
            if cancel.is_set() or self.closed:
                return False
            if error:
                code_label.set_text(error)
                self.error = error
            else:
                code_label.set_text(text('Connected. You can close this window.', 'Подключено. Можно закрыть окно.'))
                self.error = ''
            link.set_sensitive(False)
            self.changed()
            return False

        def login():
            try:
                token = authorize(cancel, lambda code: GLib.idle_add(issued, code))
                if token is None or cancel.is_set() or self.closed:
                    return
                # Serialize account replacement with playback/API operations.
                with self.lock:
                    if cancel.is_set() or self.closed:
                        return
                    self._save_token(token)
                GLib.idle_add(finished, '')
            except Exception as error:
                message = str(error) if isinstance(error, YandexError) else text('Yandex sign-in failed.', 'Не удалось войти в Яндекс.')
                GLib.idle_add(finished, message)

        dialog.connect('response', closed)
        dialog.show_all()
        threading.Thread(target=login, name='yandex-sign-in', daemon=True).start()

    def ensure_started(self):
        pass  # No browser, CDM, socket or background service is needed.

    def set_enabled(self, enabled):
        with self.playback_lock:
            self.enabled = bool(enabled)
            if not enabled and self.mpv:
                self.mpv.pause = True
                self.state['playing'] = False
        self.changed()

    def _player(self):
        if self.mpv is None:
            try:
                import mpv
                self.mpv = mpv.MPV(config=False, idle=True, vid='no', vo='null',
                                   audio_display='no', terminal=False, ytdl=False,
                                   input_default_bindings=False, input_vo_keyboard=False,
                                   audio_client_name='Emberbox Yandex Music', volume=100)
                @self.mpv.event_callback('end-file')
                def ended(event):
                    if event.data and event.data.reason == mpv.MpvEventEndFile.EOF:
                        self.action('_ended')
                    elif event.data and event.data.reason == mpv.MpvEventEndFile.ERROR:
                        GLib.idle_add(self._playback_error)
            except (ImportError, OSError, RuntimeError, ValueError):
                raise YandexError(text('Yandex Music needs libmpv and python-mpv.',
                                       'Для Яндекс Музыки нужны libmpv и python-mpv.')) from None
        return self.mpv

    def _playback_error(self):
        if not self.closed:
            self.error = text('Could not play the Yandex Music stream.', 'Не удалось воспроизвести поток Яндекс Музыки.')
            self.state['playing'] = False
            self.changed()
        return False

    def _play(self, item):
        url = self.api.stream(item['id'])
        with self.playback_lock:
            if not self.enabled or self.closed:
                return {'skipped': True}
            player = self._player()
            player.pause = True
            player.play(url)
            self.state.update(item, playlistId=item.get('playlistId', ''), position=0, playing=True, ended=False, wave=bool(self.session),
                              canNext=bool(self.session or item.get('playlistId') or self.index + 1 < len(self.queue)),
                              canPrevious=self.index > 0, canSeek=True,
                              artwork=item.get('image', ''), url='https://music.yandex.ru/track/' + item['id'])
            player.pause = False
        if self.session:
            self._feedback('trackStarted')
        return dict(self.state)

    def _feedback(self, event):
        if not self.session:
            return
        from datetime import datetime, timezone
        current = self.state
        ident = current.get('id', '')
        if current.get('albumId'):
            ident += ':' + current['albumId']
        self.api.call('rotor/session/' + quote(self.session, safe='') + '/feedback', json_body={
            'from': 'web-home-rup_main-radio-default', 'batchId': self.batch,
            'event': {'type': event, 'timestamp': datetime.now(timezone.utc).isoformat(),
                      'trackId': ident, 'totalPlayedSeconds': current.get('position', 0),
                      'trackLengthSeconds': current.get('duration', 0)}})

    def _wave_batch(self, new=False, seed='user:onyourwave'):
        if new:
            result = self.api.call('rotor/session/new', json_body={
                'includeTracksInResponse': True, 'includeWaveModel': False,
                'interactive': True, 'seeds': [seed]})
        else:
            result = self.api.call('rotor/session/' + quote(self.session, safe='') + '/tracks',
                                   json_body={'feedbacks': [], 'queue': []})
        self.session = str(result.get('radioSessionId') or result.get('sessionId') or self.session)
        self.batch = str(result.get('batchId') or '')
        self.queue = [track(v) for v in result.get('sequence', []) if (v.get('track') or {}).get('available', True)]
        self.index = 0
        if not self.session or not self.queue:
            raise YandexError(text('My Wave returned no tracks. Check Yandex Plus.', 'Моя волна не вернула треки. Проверь Яндекс Плюс.'))

    def request(self, method, **params):
        if method in ('podcasts', 'podcastEpisodes'):
            # Podcast catalogue requests do not hold the transport lock
            # during network I/O, so pause and seek remain responsive.
            api = self.api if not self.closed else None
            if not api:
                raise YandexError(text('Sign in to Yandex Music in Accounts.', 'Войди в Яндекс Музыку в разделе Аккаунты.'))
            return self._podcasts(api, method, params)
        with self.lock:
            if self.closed:
                raise YandexError('Yandex Music is closed.')
            if method == 'enable':
                self.set_enabled(params.get('enabled', False))
                return {}
            if method == 'status':
                return dict(self.state)
            if not self.api:
                raise YandexError(text('Sign in to Yandex Music in Accounts.', 'Войди в Яндекс Музыку в разделе Аккаунты.'))
            if method == 'search':
                result = self.api.call('search', text=params.get('term', ''), type='track', page=0) or {}
                return {'items': [track(v) for v in (result.get('tracks') or {}).get('results', [])]}
            if method == 'browse':
                if params.get('category') == 'queue':
                    # Playlist playback is owned by MusicService, not this
                    # transport's single-track fallback or Rotor batch.
                    provider = getattr(self, 'queue_provider', None)
                    managed = provider() if provider and not self.session else None
                    return {'items': list(self.queue) if managed is None else managed}
                if params.get('category') == 'personal':
                    result = self.api.call('landing3', blocks='personalplaylists') or {}
                    items = []
                    seen = set()
                    for block in result.get('blocks', []):
                        for entity in block.get('entities', []):
                            data = entity.get('data') or {}
                            if data.get('ready') is False:
                                continue
                            value = playlist(data.get('data') or data)
                            if value and value['id'] not in seen:
                                seen.add(value['id'])
                                items.append(value)
                    return {'items': items, 'note': '' if items else text(
                        'Yandex has not supplied personal playlists yet.', 'Яндекс пока не предоставил персональные плейлисты.')}
                items = self.api.call('users/' + self.uid + '/playlists/list') or []
                return {'items': [value for v in items if (value := playlist(v, self.uid))]}
            if method == 'tracks':
                owner, kind = str(params['id']).split(':', 1)
                result = self.api.call('users/' + quote(owner, safe='') + '/playlists/' + quote(kind, safe='')) or {}
                values = result.get('tracks') or []
                missing = [v['id'] for v in values if not v.get('track')]
                resolved = {}
                for start in range(0, len(missing), 100):
                    resolved.update((str(v['id']), v) for v in self.api.tracks(missing[start:start + 100]))
                return {'items': [dict(track(v.get('track') or resolved.get(str(v.get('id')), v)),
                                       playlistId=str(params['id'])) for v in values]}
            if method in ('artist', 'artistSection', 'release'):
                return self._catalog(method, params)
            if method in ('favorite', 'feedback'):
                ident = str(params.get('id') or self.state.get('id') or '')
                if not ident:
                    raise YandexError('No track selected.')
                action = params.get('action', 'like')
                category = 'dislikes' if action == 'dislike' else 'likes'
                value = params.get('value', True)
                self.api.call('users/' + self.uid + '/' + category + '/tracks/' + ('add-multiple' if value else 'remove'), {'track-ids': ident})
                if self.session:
                    self._feedback('dislike' if action == 'dislike' else 'like' if value else 'unlike')
                if action == 'dislike':
                    self._step(1, 'skip')
                return {'confirmed': True, 'favorite': value}
            if method == 'seek':
                if self.mpv:
                    self.mpv.seek(max(0, min(float(params['position']), self.state.get('duration', 0))), 'absolute+exact')
                return {}
            if method in ('play', 'wave', 'transport', '_ended'):
                if not self.enabled:
                    return {'skipped': True}
                if method == 'wave':
                    seed = 'user:onyourwave'
                    wave_kind = 'personal'
                    wave_id = ''
                    if params.get('trackId'):
                        wave_id = str(params['trackId'])
                        if not wave_id.isdigit():
                            raise YandexError('Invalid track for My Wave.')
                        seed = 'track:' + wave_id
                        wave_kind = 'track'
                    elif params.get('id'):
                        owner, kind = str(params['id']).split(':', 1)
                        if not owner.isdigit() or not kind.isdigit():
                            raise YandexError('Invalid playlist for My Wave.')
                        seed = 'playlist:' + owner + '_' + kind
                        wave_kind = 'playlist'
                        wave_id = str(params['id'])
                    self._wave_batch(new=True, seed=seed)
                    self.state.update(waveKind=wave_kind, waveId=wave_id, waveTitle=str(params.get('title') or ''))
                    self._feedback('radioStarted')
                    return self._play(self.queue[0])
                if method == 'play':
                    ident = str(params['id']).removeprefix('yandex:track:')
                    self.session = self.batch = ''
                    self.state.update(wave=False, waveKind='', waveId='', waveTitle='')
                    found = next((i for i, v in enumerate(self.queue) if v['id'] == ident), None)
                    if found is None:
                        values = self.api.tracks([ident])
                        if not values:
                            raise YandexError('Track not found.')
                        self.queue = [track(values[0])]
                        found = 0
                    self.index = found
                    item = self.queue[self.index]
                    if params.get('episode') is True:
                        item = dict(item, kind='episode')
                    return self._play(dict(item, playlistId=params.get('playlistId', '')))
                action = params.get('action', 'next')
                if method == '_ended':
                    return self._step(1, 'trackFinished')
                if action in ('next', 'previous'):
                    return self._step(1 if action == 'next' else -1, 'skip')
                with self.playback_lock:
                    if self.mpv:
                        self.mpv.pause = not self.enabled or action == 'pause' or (action == 'toggle' and not self.mpv.pause)
                        self.state['playing'] = not self.mpv.pause
                return {}
            raise YandexError('Unsupported Yandex Music operation: ' + method)

    def _step(self, delta, event):
        self._feedback(event)
        index = self.index + delta
        if index >= len(self.queue) and self.session:
            self._wave_batch()
            index = 0
        if 0 <= index < len(self.queue):
            self.index = index
            return self._play(self.queue[index])
        if delta > 0 and event == 'skip' and self.state.get('playlistId') and not self.session:
            return self.request('wave', id=self.state['playlistId'])
        if event == 'trackFinished':
            self.state.update(playing=False, ended=True)
        return {}

    def _podcasts(self, api, method, params):
        if method == 'podcastEpisodes':
            ident = str(params.get('id', ''))
            if not ident.isdecimal() or len(ident) > 20:
                raise YandexError('Invalid podcast ID.')
            show = api.call('albums/' + ident + '/with-tracks') or {}
            episodes = [value for volume in show.get('volumes', []) for value in volume]
            return {'items': [dict(track(value), kind='episode', album=show.get('title', ''))
                              for value in episodes[:200] if value.get('available', True)]}
        result = api.call('search', text=params.get('term', ''), type='podcast', page=0) or {}
        shows = (result.get('podcasts') or {}).get('results', [])
        episodes = (result.get('podcastEpisodes') or {}).get('results', [])
        if not shows:
            shows = [value for value in (result.get('albums') or {}).get('results', [])
                     if value.get('type') == 'podcast' or value.get('genre') == 'podcasts']
        return {'items': [dict(album(value), kind='show') for value in shows[:100]]
                + [dict(track(value), kind='episode') for value in episodes[:100] if value.get('available', True)]}

    def _catalog(self, method, params):
        ident = str(params.get('id') or '')
        if not ident and params.get('songId'):
            values = self.api.tracks([params['songId']])
            item = track(values[0]) if values else {}
            ident = item.get('albumId' if method == 'release' else 'artistId', '')
        if not ident:
            raise YandexError('Artist or album could not be identified.')
        ident = quote(ident, safe='')
        page = int(params.get('offset', 0)) // 50
        if method == 'release':
            result = self.api.call('albums/' + ident + '/with-tracks') or {}
            values = [track(v) for volume in result.get('volumes', []) for v in volume]
            offset = max(0, int(params.get('offset', 0)))
            return {'release': album(result), 'items': values[offset:offset + 100],
                    'next': offset + 100 if len(values) > offset + 100 else None}
        result = self.api.call('artists/' + ident + '/brief-info') or {}
        artist = result.get('artist') or {}
        info = {'id': str(artist.get('id', ident)), 'name': artist.get('name', ''),
                'image': cover(artist.get('cover')), 'bio': (artist.get('description') or {}).get('text', '')}
        if method == 'artistSection':
            section = params.get('section', 'discography')
            if section == 'appears':
                return {'artist': info, 'items': [], 'note': text('Guest releases are not exposed by this connection.', 'Это подключение не предоставляет гостевые релизы.')}
            result = self.api.call('artists/' + ident + '/direct-albums', page=page, pageSize=50) or {}
            values = result.get('albums', [])
            selected = values
            if section == 'singles':
                selected = [v for v in values if v.get('type') in ('single', 'ep')]
            elif section == 'compilations':
                selected = [v for v in values if v.get('type') == 'compilation']
            elif section == 'albums':
                selected = [v for v in values if v.get('type') not in ('single', 'ep', 'compilation')]
            return {'artist': info, 'items': [album(v) for v in selected],
                    'next': (page + 1) * 50 if len(values) == 50 else None}
        return {'artist': info, 'items': [track(v) for v in result.get('popularTracks', [])],
                'sections': [{'id': 'albums', 'title': text('Albums', 'Альбомы'),
                              'items': [album(v) for v in result.get('albums', [])[:30]]}]}

    def action(self, method, **params):
        if self.closed:
            return
        if method == 'show':
            self.show()
        elif method != 'hide':
            self.pool.submit(self.request, method, **params).add_done_callback(self._done)

    def _done(self, future):
        GLib.idle_add(self._completed, future)

    def _completed(self, future):
        if self.closed:
            return False
        try:
            future.result()
            self.error = ''
        except Exception as error:
            self.error = str(error) if isinstance(error, YandexError) else text('Yandex Music request failed.', 'Ошибка запроса Яндекс Музыки.')
        self.changed()
        return False

    def poll(self):
        if self.closed:
            return False
        if self.mpv:
            try:
                self.state.update(position=float(self.mpv.time_pos or 0),
                                  playing=bool(self.enabled and not self.mpv.pause and not self.mpv.eof_reached))
            except (RuntimeError, ValueError):
                pass
        self.changed()
        return True

    def close(self):
        if getattr(self, 'login_cancel', None):
            self.login_cancel.set()
        if getattr(self, 'login_dialog', None):
            self.login_dialog.destroy()
            self.login_dialog = None
        self.closed = True
        self.enabled = False
        GLib.source_remove(self.timer)
        self.pool.shutdown(wait=False, cancel_futures=True)
        if self.mpv:
            self.mpv.pause = True
            player, self.mpv = self.mpv, None
            threading.Thread(target=player.terminate, daemon=True).start()


def cover(value):
    uri = (value or {}).get('uri', '')
    return 'https://' + uri.replace('%%', '400x400') if uri else ''


def album(value):
    return {'id': str(value.get('id', '')), 'kind': 'album', 'title': value.get('title', ''),
            'artist': ', '.join(a.get('name', '') for a in value.get('artists', [])),
            'image': 'https://' + value['coverUri'].replace('%%', '400x400') if value.get('coverUri') else '',
            'year': value.get('year', '')}


def playlist(value, default_owner=''):
    owner = str((value.get('owner') or {}).get('uid') or value.get('uid') or default_owner)
    kind = str(value.get('kind', ''))
    if not owner or not kind:
        return None
    return {'id': owner + ':' + kind, 'kind': 'playlist', 'title': value.get('title', ''),
            'image': cover(value.get('cover')), 'artist': (value.get('owner') or {}).get('name', '')}
