"""Optional LRCLIB lyrics, fetched off the GTK thread without service credentials.

Call ``set_track`` on the GTK thread when metadata changes. ``changed`` runs on
the GLib main context; ``state`` always belongs to that track, even if an older
network request finishes later. No request is made until a caller asks for it.
API contract: https://lrclib.net/docs
"""
from bisect import bisect_right
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from gi.repository import GLib
from paths import CACHE_DIR

API = 'https://lrclib.net/api/'
MAX_BYTES = 512_000
MAX_TEXT = 120_000
STAMP = re.compile(r'\[(\d{1,3}):([0-5]\d)(?:[.:](\d{1,3}))?\]')
OFFSET = re.compile(r'^\[offset:([+-]?\d+)\]$', re.I)
FEATURE = re.compile(r'\s*(?:[([](?:feat\.?|ft\.?|featuring)\s+[^)\]]+[)\]]|[-–—]\s*(?:feat\.?|ft\.?|featuring)\s+.+)$', re.I)
WORD_STAMP = re.compile(r'<\d{1,3}:[0-5]\d(?:\.\d{1,3})?>')
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


@dataclass(frozen=True)
class LyricLine:
    seconds: float
    text: str


@dataclass(frozen=True)
class LyricsState:
    status: str = 'idle'
    lines: tuple = ()
    plain: str = ''
    source_url: str = 'https://lrclib.net'

    @property
    def synced(self):
        return bool(self.lines)


def parse_lrc(value):
    """Parse line-level LRC, including repeated timestamps and silent gaps.

    Empty timed lines deliberately remain: an instrumental passage must stop
    highlighting the preceding sung line. Enhanced word timings are stripped;
    the player advertises line synchronization rather than invented karaoke.
    """
    if not isinstance(value, str):
        return ()
    lines, offset = [], 0.
    for raw in _body(value).lstrip('\ufeff').splitlines()[:4000]:
        raw = raw.strip()
        shift = OFFSET.fullmatch(raw)
        if shift:
            offset = max(-60., min(60., int(shift[1]) / 1000))
            continue
        matches = list(STAMP.finditer(raw))
        if not matches or matches[0].start() != 0:
            continue
        # Only leading tags count. A bracket in the actual lyric is text.
        end, stamps = 0, []
        for match in matches:
            if match.start() != end:
                break
            end = match.end()
            stamps.append(int(match[1])*60 + int(match[2]) +
                          (int(match[3]) / 10**len(match[3]) if match[3] else 0))
        content = WORD_STAMP.sub('', raw[end:]).strip()
        lines.extend((stamp, content) for stamp in stamps)
    # LRC's positive offset advances the lyric relative to the audio.
    result = []
    for stamp, content in sorted(lines, key=lambda row: row[0]):
        line = LyricLine(max(0., stamp-offset), content)
        if result and result[-1].seconds == line.seconds:
            if line.text and line.text != result[-1].text:
                result[-1] = LyricLine(line.seconds, '\n'.join(filter(None, (result[-1].text, line.text))))
        else:
            result.append(line)
    return tuple(result)


def active_line(lines, position):
    """Return the timed line index, or -1 during the introduction."""
    try:
        seconds = float(position)
    except (TypeError, ValueError):
        return -1
    if not math.isfinite(seconds):
        return -1
    return bisect_right(lines, seconds, key=lambda line: line.seconds)-1


def _text(value):
    return _body(str(value or ''))[:512].strip()


def _body(value):
    return CONTROL.sub('', value[:MAX_TEXT].encode('utf-8', errors='replace').decode('utf-8'))


def _normalized(value):
    return ' '.join(''.join(character if character.isalnum() else ' '
                           for character in unicodedata.normalize('NFKC', value).casefold()).split())


def _record(record):
    if not isinstance(record, dict):
        raise ValueError('Invalid lyric response')
    if record.get('instrumental') is True:
        return LyricsState('instrumental')
    lines = parse_lrc(record.get('syncedLyrics'))
    value = record.get('plainLyrics')
    plain = _body(value).strip() if isinstance(value, str) else ''
    if not plain and lines:
        plain = '\n'.join(line.text for line in lines)
    return LyricsState('ready' if lines or plain else 'missing', lines, plain)


class LyricsClient:
    """One sequential, bounded HTTP worker and a small private per-user cache."""
    def __init__(self, changed, cache_dir=None):
        self.changed = changed
        self.state = LyricsState()
        self.closed = False
        self.key = None
        self.generation = 0
        self.future = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ember-lyrics')
        self.stop = threading.Event()
        self.next_request = 0.
        self.cache = OrderedDict()
        self.cache_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR/'lyrics'
        version = '0.7.0'
        for directory in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
            try:
                version = (directory/'VERSION').read_text().strip()
                break
            except OSError:
                pass
        self.user_agent = f'Emberbox Audio/{version} (https://github.com/BlackSnaker/emberbox-audio)'

    def set_track(self, title, artist, album='', duration=0, force=False):
        if self.closed:
            return
        title, artist, album = map(_text, (title, artist, album))
        try:
            seconds = float(duration)
            seconds = round(seconds) if math.isfinite(seconds) and 1 <= seconds <= 3600 else 0
        except (TypeError, ValueError, OverflowError):
            seconds = 0
        key = (title, artist, album, seconds) if title and artist else None
        if key == self.key and not force:
            return
        self.generation += 1
        generation, self.key = self.generation, key
        if self.future:
            self.future.cancel()
        if key is None:
            self.state = LyricsState()
        elif not force and key in self.cache and self.cache[key][0] > time.time():
            self.state = self.cache[key][1]
            self.cache.move_to_end(key)
        else:
            self.state = LyricsState('loading')
            self.future = self.pool.submit(self._lookup, key, generation, force)
            self.future.add_done_callback(lambda future: GLib.idle_add(self._deliver, generation, key, future, priority=GLib.PRIORITY_DEFAULT))
        GLib.idle_add(self._notify, generation, priority=GLib.PRIORITY_DEFAULT)

    def _notify(self, generation):
        if not self.closed and generation == self.generation:
            self.changed()
        return False

    def _current(self, generation):
        return not self.closed and generation == self.generation

    def _path(self, key):
        return self.cache_dir/(hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()+'.json')

    def _cached(self, key):
        try:
            path = self._path(key)
            if path.stat().st_size > MAX_BYTES:
                return None
            data = json.loads(path.read_text())
            if data['expires'] <= time.time() or data.get('version') != 1:
                return None
            state = _record(data['record'])
            if state.status in ('ready', 'missing', 'instrumental'):
                return state
        except (OSError, KeyError, TypeError, ValueError):
            pass
        return None

    def _save(self, key, state):
        if state.status not in ('ready', 'missing', 'instrumental'):
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            record = {'instrumental': state.status == 'instrumental', 'plainLyrics': state.plain,
                      'syncedLyrics': '\n'.join(f'[{int(line.seconds)//60:02}:{line.seconds%60:06.3f}]{part}'
                                                for line in state.lines for part in line.text.split('\n'))}
            data = {'version': 1, 'expires': time.time()+self._ttl(state), 'record': record}
            path = self._path(key)
            temporary = path.with_suffix('.next.json')
            with temporary.open('w', encoding='utf-8') as target:
                os.chmod(temporary, 0o600)
                json.dump(data, target, ensure_ascii=False)
            temporary.replace(path)
            cached = sorted(self.cache_dir.glob('*.json'), key=lambda item: item.stat().st_mtime, reverse=True)
            for old in cached[128:]:
                old.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _ttl(state):
        return 7*86400 if state.status in ('ready', 'instrumental') else 3600 if state.status == 'missing' else 120

    def _request(self, endpoint, params, generation):
        while self._current(generation) and time.monotonic() < self.next_request:
            self.stop.wait(min(.1, self.next_request-time.monotonic()))
        if not self._current(generation):
            return None
        self.next_request = time.monotonic()+.35
        request = urllib.request.Request(API+endpoint+'?'+urllib.parse.urlencode(params),
                                         headers={'User-Agent': self.user_agent, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
                if content_type != 'application/json':
                    raise ValueError('Unexpected lyric response')
                raw = response.read(MAX_BYTES+1)
                if len(raw) > MAX_BYTES:
                    raise ValueError('Lyric response too large')
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            try:
                if error.code == 404:
                    return None
                if error.code in (429, 503):
                    retry = error.headers.get('Retry-After', '60')
                    try:
                        delay = float(retry)
                    except ValueError:
                        try:
                            delay = parsedate_to_datetime(retry).timestamp()-time.time()
                        except (TypeError, ValueError, OverflowError):
                            delay = 60.
                    self.next_request = time.monotonic()+max(1., delay if math.isfinite(delay) else 60.)
                raise
            finally:
                error.close()

    def _lookup(self, key, generation, force=False):
        if not self._current(generation):
            return LyricsState()
        if not force:
            cached = self._cached(key)
            if cached:
                return cached
        title, artist, album, seconds = key
        params = {'track_name': title, 'artist_name': artist}
        if album:
            params['album_name'] = album
        if seconds:
            params['duration'] = seconds
        try:
            record = self._request('get', params, generation)
            if not record and self._current(generation):
                search_title = FEATURE.sub('', title).strip() or title
                records = self._request('search', {'track_name': search_title, 'artist_name': artist}, generation)
                candidates = []
                for item in records[:20] if isinstance(records, list) else ():
                    if not isinstance(item, dict):
                        continue
                    if (_normalized(FEATURE.sub('', _text(item.get('trackName')))) != _normalized(search_title) or
                            _normalized(_text(item.get('artistName'))) != _normalized(artist)):
                        continue
                    length = item.get('duration')
                    if not isinstance(length, (int, float)) or not math.isfinite(length):
                        continue
                    if seconds and abs(length-seconds)>2:
                        continue
                    candidates.append(item)
                # Precise album, then synchronized text, then closest duration.
                if candidates:
                    record = min(candidates, key=lambda item: (
                        _normalized(_text(item.get('albumName'))) != _normalized(album),
                        not bool(item.get('syncedLyrics')), abs(float(item.get('duration') or 0)-seconds)))
            state = _record(record) if record else LyricsState('missing')
            if self._current(generation):
                self._save(key, state)
            return state
        except (OSError, ValueError, TypeError, OverflowError):
            return LyricsState('error')

    def _deliver(self, generation, key, future):
        if not self._current(generation) or future.cancelled():
            return False
        try:
            state = future.result()
        except Exception:
            state = LyricsState('error')
        self.state = state
        self.cache[key] = (time.time()+self._ttl(state), state)
        self.cache.move_to_end(key)
        while len(self.cache)>64:
            self.cache.popitem(last=False)
        self.changed()
        return False

    def close(self):
        self.closed = True
        self.generation += 1
        self.stop.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
