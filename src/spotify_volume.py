"""Nonblocking volume and mute for Spotify's own PipeWire/PulseAudio streams."""

import json
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from paths import CACHE_DIR, CONFIG_DIR

from gi.repository import GLib


STATE = CONFIG_DIR / 'audio.json'


def spotify_streams():
    result = subprocess.run(['pactl', '-f', 'json', 'list', 'sink-inputs'],
                            capture_output=True, text=True, timeout=2, check=True)
    streams = []
    for item in json.loads(result.stdout):
        props = item.get('properties', {})
        names = [str(props.get(key, '')).lower() for key in
                 ('application.name', 'application.process.binary', 'application.id', 'node.name')]
        if any(name in ('spotify', 'com.spotify.client') or re.fullmatch(r'spotify-\d+', name)
               for name in names):
            streams.append(item)
    return streams


class SpotifyVolume:
    def __init__(self, changed):
        self.changed = changed
        self.volume, self.muted, self.available = 1.0, False, False
        self.configured = False
        try:
            saved = json.loads(STATE.read_text())
            self.volume = max(0.0, min(1.0, float(saved['volume'])))
            self.muted = bool(saved.get('muted', False))
            self.configured = True
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='spotify-volume')
        self.stream_ids = set()
        self.revision = 0
        self.dirty = False
        self.busy = False
        self.timer = 0
        self.save_timer = 0
        self.closed = False
        self.event_timer = 0
        self.refresh_again = False
        self.watcher = subprocess.Popen(['pactl', 'subscribe'], stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True)
        threading.Thread(target=self._watch, name='spotify-volume-events', daemon=True).start()

    def _watch(self):
        for event in self.watcher.stdout:
            if self.closed:
                break
            if 'sink-input' in event and not self.event_timer:
                self.event_timer = GLib.timeout_add(30, self._stream_event)

    def _stream_event(self):
        self.event_timer = 0
        if self.closed:
            return False
        if self.busy:
            self.refresh_again = True
        elif not self.timer:
            self._dispatch()
        return False

    def refresh(self, player):
        available = bool(player)
        if available != self.available:
            self.available = available
            self.changed(self)
        if not self.busy and not self.timer:
            self._dispatch()

    def set_volume(self, value):
        value = round(max(0.0, min(1.0, value)), 3)
        if value != self.volume:
            self.volume = value
            self._change()

    def toggle_mute(self):
        self.muted = not self.muted
        self._change()

    def _change(self):
        self.configured = self.dirty = True
        self.revision += 1
        self.changed(self)
        self._schedule_save()
        if not self.timer:
            self.timer = GLib.timeout_add(60, self._dispatch)

    def _schedule_save(self):
        if self.save_timer:
            GLib.source_remove(self.save_timer)
        self.save_timer = GLib.timeout_add(400, self._save)

    def _save(self):
        self.save_timer = 0
        STATE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE.with_suffix('.next.json')
        temporary.write_text(json.dumps({'volume': self.volume, 'muted': self.muted}))
        temporary.replace(STATE)
        return False

    def _dispatch(self):
        self.timer = 0
        if self.closed or self.busy:
            return False
        self.busy = True
        revision = self.revision
        future = self.pool.submit(self._sync, self.volume, self.muted,
                                  self.dirty, self.configured, set(self.stream_ids))
        future.add_done_callback(lambda result: GLib.idle_add(self._done, revision, result))
        return False

    @staticmethod
    def _sync(volume, muted, dirty, configured, known):
        streams = spotify_streams()
        ids = {item['index'] for item in streams}
        apply = ids if dirty else ids - known if configured else set()
        for index in apply:
            for command, value in [('set-sink-input-volume', f'{volume * 100:.1f}%'),
                                   ('set-sink-input-mute', '1' if muted else '0')]:
                subprocess.run(['pactl', command, str(index), value], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        return streams, apply

    def _done(self, revision, future):
        self.busy = False
        if self.closed:
            return False
        try:
            streams, applied = future.result()
        except Exception as error:
            print(f'Spotify volume: {error}', flush=True)
            return False
        self.stream_ids = {item['index'] for item in streams}
        if revision != self.revision:
            self._dispatch()
            return False
        if applied:
            self.dirty = False
        elif streams:
            channels = list(streams[0].get('volume', {}).values())
            if channels:
                volume = max(0.0, min(1.0, sum(c['value'] for c in channels) / (65536 * len(channels))))
                muted = bool(streams[0].get('mute', False))
                if abs(volume - self.volume) > .002 or muted != self.muted:
                    self.volume, self.muted = volume, muted
                    self.changed(self)
                    self._schedule_save()
                self.configured = True
        if self.refresh_again and not self.timer:
            self.refresh_again = False
            self.timer = GLib.timeout_add(60, self._dispatch)
        return False

    def close(self):
        self.closed = True
        if self.timer:
            GLib.source_remove(self.timer)
        if self.save_timer:
            GLib.source_remove(self.save_timer)
        if self.event_timer:
            GLib.source_remove(self.event_timer)
        self.watcher.terminate()
        try:
            self.watcher.wait(timeout=.5)
        except subprocess.TimeoutExpired:
            self.watcher.kill()
            self.watcher.wait(timeout=.5)
        if self.configured:
            self._save()
        self.pool.shutdown(wait=False, cancel_futures=True)
