"""Audio-only YouTube transport. No browser window, account or cookie import."""
import json
from pathlib import Path
import threading
from gi.repository import GLib
from paths import CONFIG_DIR
from source_picker import text
from youtube_search import yt_dlp_executable, ytdl_raw_options, mpv_quoted

STATE = CONFIG_DIR / 'youtube.json'
CLIENT_NAME = 'Emberbox Audio YouTube'


class YouTubeAudio:
    def __init__(self, changed, *, persistent=True):
        self.changed = changed
        self.persistent=persistent;self.flow_cancel=None
        self.mpv = None
        self.closed = False
        self.enabled = False
        self.current = None
        self.queue = []
        self.index = -1
        self.position = self.duration = 0.
        self.paused, self.loaded, self.loading = True, False, False
        self.failed = self.eof = False
        self.error = ''
        self.watchdog = 0
        self.save_timer = 0
        self.open_request = 0
        self.quality = {}
        try:
            if not persistent:return
            saved = json.loads(STATE.read_text())
            from youtube_search import video_url
            for item in saved.get('queue', [])[:50]:
                parsed = video_url(str(item.get('url', '')))
                if parsed:
                    self.queue.append({**item, 'url': parsed[0]})
            index = int(saved.get('index', -1))
            if 0 <= index < len(self.queue):
                self.index = index
                self.current = self.queue[index]
                self.position = max(0., float(saved.get('position', 0)))
                self.duration = float(self.current.get('duration') or 0)
        except (OSError, ValueError, TypeError, KeyError):
            pass

    def _ensure_player(self):
        if self.mpv:
            return True
        try:
            import mpv
            self.mpv = mpv.MPV(
                config=False, idle=True, keep_open=True, vid='no', vo='null',
                audio_display='no', force_window=False, input_default_bindings=False,
                input_vo_keyboard=False, osc=False, terminal=False, osd_level=0,
                ao='pulse', volume=100, volume_max=100, mute=False,
                audio_client_name=CLIENT_NAME,
                demuxer_max_bytes=16*1024*1024,demuxer_max_back_bytes=1024*1024,
                ytdl=True, ytdl_format='bestaudio/best',
                script_opts='ytdl_hook-ytdl_path='+mpv_quoted(yt_dlp_executable()),
                ytdl_raw_options=ytdl_raw_options())
            for name in ('time-pos', 'duration', 'pause', 'eof-reached',
                         'paused-for-cache', 'media-title', 'metadata',
                         'audio-codec-name','audio-params','audio-bitrate'):
                self.mpv.observe_property(name, self._property)
            @self.mpv.event_callback('file-loaded')
            def file_loaded(_event):
                GLib.idle_add(self._loaded)
            @self.mpv.event_callback('end-file')
            def end_file(event):
                if event.data and event.data.reason == mpv.MpvEventEndFile.ERROR:
                    GLib.idle_add(self._failure, text(
                        'This video could not be played. Try another public video.',
                        'Не удалось включить ролик. Попробуй другой общедоступный ролик.'))
            return True
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.mpv = None
            self.error = text('YouTube needs libmpv and python-mpv. See installation notes.',
                              'Для YouTube нужны libmpv и python-mpv. См. инструкцию установки.')
            self.failed = True
            self.changed()
            return False

    def set_enabled(self, enabled):
        if not enabled and self.flow_cancel:self.flow_cancel()
        self.enabled = enabled
        if not enabled:
            self.paused = True
            if self.mpv:
                self.mpv.command_async('set', 'pause', 'yes')
            self.save()

    def play(self, item, queue=None, start=0):
        if self.flow_cancel:self.flow_cancel()
        from youtube_search import video_url
        parsed = video_url(str(item.get('url', '')))
        if not parsed:
            return
        self.open_request += 1
        self.current = dict(item, url=parsed[0])
        if queue is not None:
            self.queue = [dict(entry) for entry in queue][:50]
        if not any(entry.get('id') == item.get('id') for entry in self.queue):
            self.queue = [self.current]
        self.index = next((i for i, entry in enumerate(self.queue)
                           if entry.get('id') == self.current.get('id')), 0)
        self.position, self.duration = float(start), float(item.get('duration') or 0)
        self.loaded, self.loading, self.failed, self.eof = False, True, False, False
        self.quality = {}
        self.paused = not self.enabled
        self.error = ''
        self.save()
        if not self._ensure_player():
            self.loading = False
            return
        args = ['loadfile', self.current['url'], 'replace']
        if self.mpv.mpv_version_tuple >= (0, 38, 0):
            args.append(-1)
        # Extraction can finish after a source switch: start paused, then let
        # _loaded use the current source choice before enabling any sound.
        args.append(f'start={max(0., float(start))},pause=yes')
        self.mpv.command_async(*args)
        if self.watchdog:
            GLib.source_remove(self.watchdog)
        self.watchdog = GLib.timeout_add_seconds(50, self._load_timeout, self.open_request)
        self.changed()

    def _loaded(self):
        if self.closed:
            return False
        self.loading, self.loaded, self.failed = False, True, False
        if self.watchdog:
            GLib.source_remove(self.watchdog)
            self.watchdog = 0
        # Initial 'pause=yes' notifications are ignored while loading.
        self.mpv.command_async('set', 'pause', 'yes' if self.paused or not self.enabled else 'no')
        self.changed()
        return False

    def _property(self, name, value):
        GLib.idle_add(self._on_property, name, value)

    def _on_property(self, name, value):
        if self.closed:
            return False
        if name in ('audio-codec-name','audio-params','audio-bitrate'):
            if not (self.loading or self.loaded) or self.failed:return False
            self.quality['evidence']='mpv'
            if name=='audio-codec-name':self.quality['codec']=str(value or '').lower()
            elif name=='audio-params':
                params=value if isinstance(value,dict) else {}
                self.quality.update(sampleRate=params.get('samplerate',0),channels=params.get('channel-count',0))
            else:self.quality['bitrate']=value or 0
        if name == 'time-pos' and value is not None:
            self.position = max(0., float(value))
            if not self.save_timer:
                self.save_timer = GLib.timeout_add_seconds(5, self.save)
        elif name == 'duration' and value:
            self.duration = float(value)
        elif name == 'pause' and not self.loading:
            self.paused = bool(value)
        elif name == 'eof-reached':
            self.eof = bool(value)
            if value and self.enabled and not self.loading and not self.failed:
                if self.index + 1 < len(self.queue):
                    self.play(self.queue[self.index+1])
                else:
                    self.paused = True
        elif name == 'media-title' and value and self.current:
            self.current['title'] = str(value)
        elif name == 'metadata' and value and self.current:
            metadata = {key.lower(): item for key, item in value.items()}
            channel = metadata.get('uploader') or metadata.get('artist') or metadata.get('channel')
            if channel:
                self.current['channel'] = str(channel)
        self.changed()
        return False

    def _load_timeout(self, request):
        self.watchdog = 0
        if not self.closed and request == self.open_request and self.loading:
            self.mpv.command_async('stop')
            self._failure(text('YouTube took too long. Try this track again.',
                               'YouTube долго отвечает. Попробуй включить трек ещё раз.'))
        return False

    def _failure(self, message):
        if self.closed:
            return False
        self.error = message
        self.loading, self.loaded, self.paused, self.failed = False, False, True, True
        self.quality = {}
        if self.watchdog:
            GLib.source_remove(self.watchdog)
            self.watchdog = 0
        self.changed()
        return False

    def toggle(self):
        if self.flow_cancel:self.flow_cancel()
        if not self.current:
            return
        if not self.loaded or self.failed:
            self.play(self.current, start=0 if self.failed else self.position)
        elif self.eof:
            self.seek(0)
            self.paused = False
            self.mpv.command_async('set', 'pause', 'no')
        else:
            self.paused = not self.paused
            self.mpv.command_async('set', 'pause', 'yes' if self.paused else 'no')
        self.changed()

    def skip(self, direction):
        if direction < 0 and self.position > 3 and self.loaded:
            self.seek(0)
        elif 0 <= self.index+direction < len(self.queue):
            self.play(self.queue[self.index+direction])

    def seek(self, position):
        if self.flow_cancel:self.flow_cancel()
        if self.mpv and self.loaded and self.duration:
            self.mpv.command_async('seek', max(0.,min(self.duration,float(position))), 'absolute+exact')

    def save(self):
        self.save_timer = 0
        if not self.persistent:return False
        STATE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE.with_suffix('.next.json')
        temporary.write_text(json.dumps({'queue':self.queue,'index':self.index,'position':self.position}))
        temporary.replace(STATE)
        return False

    def close(self):
        self.closed = True
        for timer in (self.watchdog, self.save_timer):
            if timer:
                GLib.source_remove(timer)
        self.watchdog = self.save_timer = 0
        self.save()
        if self.mpv:
            player, self.mpv = self.mpv, None
            # libmpv shutdown may wait for an extractor; never block GTK.
            threading.Thread(target=player.terminate, daemon=True).start()
