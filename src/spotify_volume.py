"""Nonblocking volume and mute for the selected application's PipeWire/PulseAudio streams."""

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from paths import CACHE_DIR, CONFIG_DIR

from gi.repository import GLib
from stream_target import Target, matches


STATE = CONFIG_DIR / 'audio.json'


def source_streams(target):
    result = subprocess.run(['pactl', '-f', 'json', 'list', 'sink-inputs'],
                            capture_output=True, text=True, timeout=2, check=True)
    return [item for item in json.loads(result.stdout)
            if matches(item.get('properties', {}), target)]


class SpotifyVolume:
    def __init__(self, changed):
        self.changed = changed
        self.target = None
        self.volume, self.muted, self.available = 1.0, False, False
        self.configured = False
        try:
            saved = json.loads(STATE.read_text())
            self.saved = saved.get('sources', {'spotify': saved})
        except (OSError, ValueError, TypeError):
            self.saved = {}
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

    def refresh(self, target):
        if target != self.target:
            old = self.target
            if old and old.source != target.source:
                self._remember()
            self.target = target
            self.revision += 1
            self.stream_ids = set()
            if not old or old.source != target.source:
                saved = self.saved.get(target.source, {})
                try:
                    self.volume = max(0., min(1., float(saved.get('volume', 1.))))
                    self.muted = bool(saved.get('muted', False))
                    self.configured = 'volume' in saved
                except (ValueError, TypeError):
                    self.volume, self.muted, self.configured = 1., False, False
            self.dirty = False
        available = bool(target.player)
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

    def _remember(self):
        if self.target and self.configured:
            self.saved[self.target.source] = {'volume': self.volume, 'muted': self.muted}

    def flush(self):
        if self.save_timer:
            GLib.source_remove(self.save_timer)
            self.save_timer = 0
        self._save()

    def _save(self):
        self._remember()
        self.save_timer = 0
        STATE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE.with_suffix('.next.json')
        temporary.write_text(json.dumps({'sources': self.saved}))
        temporary.replace(STATE)
        return False

    def _dispatch(self):
        self.timer = 0
        if self.closed or self.busy:
            return False
        self.busy = True
        revision = self.revision
        future = self.pool.submit(self._sync, self.target, self.volume, self.muted,
                                  self.dirty, self.configured, set(self.stream_ids))
        future.add_done_callback(lambda result: GLib.idle_add(self._done, revision, result))
        return False

    def _sync(self, target, volume, muted, dirty, configured, known):
        streams = source_streams(target)
        ids = {item['index'] for item in streams}
        apply = ids if dirty else ids - known if configured else set()
        for index in apply:
            if self.closed or self.target != target:
                return [], set()
            for command, value in [('set-sink-input-volume', f'{volume * 100:.1f}%'),
                                   ('set-sink-input-mute', '1' if muted else '0')]:
                if self.closed or self.target != target:
                    return [], set()
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
            print(f'Audio volume: {error}', flush=True)
            return False
        if revision != self.revision:
            self._dispatch()
            return False
        self.stream_ids = {item['index'] for item in streams}
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
        self._save()
        self.pool.shutdown(wait=False, cancel_futures=True)
