"""Play publisher audio with the existing asynchronous libmpv transport."""
from concurrent.futures import ThreadPoolExecutor
import os

from gi.repository import GLib

from podcast_catalog import public_network, public_url
from source_picker import text
from youtube_audio import YouTubeAudio
from youtube_search import mpv_quoted


class PodcastAudio(YouTubeAudio):
    client_name = 'Emberbox Apple Podcasts'
    source_name = 'Apple Podcasts'
    media_tags = False

    def __init__(self, changed):
        super().__init__(changed, persistent=False)
        self.resolver = ThreadPoolExecutor(max_workers=2, thread_name_prefix='podcast-stream')
        self.resolve_generation = 0
        self.resolve_job = None

    def player_options(self):
        return dict(ytdl=False, network_timeout=12,
                    demuxer_lavf_o='protocol_whitelist='+mpv_quoted('https,http,tls,tcp,crypto'))

    def media_url(self, item):
        return public_url(item.get('url'))

    def play(self, item, queue=None, start=0):
        if not self.enabled or self.closed:
            return
        self.resolve_generation += 1
        if self.resolve_job:
            self.resolve_job.cancel()
        generation = self.resolve_generation
        self.current = item
        if queue is not None:
            self.queue = list(queue)[:200]
        self.index = next((i for i, value in enumerate(self.queue) if value['id'] == item['id']), -1)
        self.position, self.duration = start, float(item.get('duration_ms') or 0) / 1000
        self.loading, self.loaded, self.eof, self.paused, self.failed = True, False, False, False, False
        self.error = ''
        self.quality = {}
        if self.watchdog:
            GLib.source_remove(self.watchdog)
            self.watchdog = 0
        if self.mpv:
            self.mpv.command_async('set', 'pause', 'yes')
        self.changed()
        self.resolve_job = self.resolver.submit(public_network, item.get('url'))
        self.resolve_job.add_done_callback(lambda future: GLib.idle_add(
            self._resolved, generation, item, start, future, priority=GLib.PRIORITY_DEFAULT))

    def _resolved(self, generation, item, start, future):
        if self.closed or not self.enabled or generation != self.resolve_generation:
            return False
        self.resolve_job = None
        try:
            url = future.result()
        except (OSError, ValueError):
            return self._failure(text('Could not reach the podcast publisher.', 'Не удалось подключиться к издателю подкаста.'))
        paused = self.paused
        episodes = self.queue
        # The music transport normally retains 50 items. Keep the publisher's
        # entire visible episode list in the podcast session.
        super().play(dict(item, url=url, duration=self.duration), None, start)
        self.queue = episodes or [self.current]
        self.index = next((i for i, value in enumerate(self.queue) if value['id'] == item['id']), 0)
        self.paused = paused or self.failed
        return False

    def _loaded(self):
        if self.resolve_job is not None or not self.enabled:
            return False
        return super()._loaded()

    def set_enabled(self, enabled):
        if not enabled:
            self.resolve_generation += 1
            if self.resolve_job:
                self.resolve_job.cancel()
                self.resolve_job = None
            if self.watchdog:
                GLib.source_remove(self.watchdog)
                self.watchdog = 0
            self.loading = False
        super().set_enabled(enabled)

    @property
    def connected(self):
        return bool(self.mpv)

    @property
    def pid(self):
        return os.getpid()

    @property
    def state(self):
        item = self.current or {}
        return {**item, 'url': '', 'ready': True, 'authorized': True, 'kind': 'episode',
                'duration': self.duration, 'position': self.position, 'ended': self.eof,
                'playing': bool(self.loaded and not self.paused and not self.eof),
                'canNext': bool(item and self.index + 1 < len(self.queue)),
                'canPrevious': bool(item and (self.index > 0 or self.position > 3)),
                'canSeek': bool(self.loaded and self.duration)}

    def action(self, method, **values):
        if method == 'seek':
            self.seek(values['position'])
        elif method == 'transport':
            action = values.get('action')
            if action == 'toggle':
                if self.loading:
                    self.paused = not self.paused
                else:
                    self.toggle()
            elif action in ('previous', 'next'):
                self.skip(-1 if action == 'previous' else 1)
            elif action == 'pause' and not self.paused:
                self.paused = True
                if self.mpv:
                    self.mpv.command_async('set', 'pause', 'yes')

    def restart(self):
        if self.current:
            self.play(self.current, start=self.position)

    def close(self):
        self.set_enabled(False)
        self.resolver.shutdown(wait=False, cancel_futures=True)
        super().close()
