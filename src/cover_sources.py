"""Original-size artwork URLs and optional motion art from public Apple pages.

Only known image CDN size fields are changed. Motion comes from the album
linked by the exact catalog song, never from a name search or another release.
"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import json
import re
import time
import urllib.request
from urllib.parse import urljoin, urlsplit, urlunsplit
from collections import OrderedDict
from gi.repository import GLib


def still_candidates(url, pixels=1200):
    original = str(url or '')
    parsed = urlsplit(original)
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        return [original]
    host, path = (parsed.hostname or '').lower(), parsed.path
    pixels = max(640, min(2400, int(pixels)))
    if host.endswith('.mzstatic.com'):
        path = path.replace('{w}', str(pixels)).replace('{h}', str(pixels)).replace('{f}', 'jpg')
        path = re.sub(r'/\d+x\d+[^/]*\.(?:jpg|jpeg|png|webp)$', f'/{pixels}x{pixels}bb.jpg', path, flags=re.I)
    elif host == 'i.scdn.co':
        path = re.sub(r'/image/ab67616d(?:00004851|00001e02)', '/image/ab67616d0000b273', path)
    elif host in ('avatars.yandex.net', 'avatars.mds.yandex.net'):
        path = re.sub(r'/(?:\d+x\d+|%%)$', '/1000x1000', path)
    elif host in ('i.ytimg.com', 'img.youtube.com') and re.match(r'/vi(?:_webp)?/[\w-]{11}/', path):
        path = re.sub(r'/[^/]+\.(?:jpg|webp)$', '/maxresdefault.jpg', path)
    upgraded = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
    return list(dict.fromkeys((upgraded, original)))


def apple_page(url):
    """Accept only an exact public Apple song/album URL, without credentials."""
    try:
        p = urlsplit(str(url or ''))
        if (p.scheme == 'https' and p.hostname == 'music.apple.com' and not p.port and not p.username and not p.password
                and re.fullmatch(r'/[a-z]{2}/(?:song|album)/(?:[^/]+/)?\d{1,20}', p.path)):
            return urlunsplit(('https', 'music.apple.com', p.path, '', ''))
    except ValueError:
        pass
    return ''


def is_motion_url(url):
    try:
        p = urlsplit(str(url or ''))
        host = (p.hostname or '').lower()
        return bool(p.scheme == 'https' and not p.username and not p.password and not p.port
                    and (host.endswith('.itunes.apple.com') or host.endswith('.mzstatic.com'))
                    and p.path.lower().endswith(('.m3u8', '.mp4', '.mov')))
    except ValueError:
        return False


def motion_rendition(manifest, base, pixels=640):
    """Choose one square SDR rendition, so FFmpeg need not probe every variant."""
    choices = []
    pending = ''
    for line in manifest.splitlines():
        line = line.strip()
        if line.startswith('#EXT-X-STREAM-INF:'):
            pending = line
        elif line and not line.startswith('#') and pending:
            resolution = re.search(r'RESOLUTION=(\d+)x(\d+)', pending)
            candidate = urljoin(base, line)
            if resolution and is_motion_url(candidate):
                width,height = map(int,resolution.groups())
                bitrate = re.search(r'(?:^|,)BANDWIDTH=(\d+)',pending)
                if width and height:
                    choices.append((candidate,width,height,'avc1' in pending,
                                    int(bitrate[1]) if bitrate else 0))
            pending = ''
    if not choices:return base
    return min(choices,key=lambda item:(not item[3],abs(item[1]/item[2]-1)>.05,
        min(item[1:3])<pixels, min(item[1:3]) if min(item[1:3])>=pixels else -min(item[1:3]),-item[4]))[0]


class ApplePage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.motion = ''
        self.album = ''
        self.schema = None
        self.heading = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'h1':self.heading = True
        # Apple's own album header player; ignore music videos and recommendations.
        if not self.heading and tag == 'amp-ambient-video' and 'editorial-video--cover' in attrs.get('class', '').split():
            src = attrs.get('src', '')
            if not self.motion and is_motion_url(src):
                self.motion = src
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.schema = []

    def handle_data(self, value):
        if self.schema is not None:
            self.schema.append(value)

    def handle_endtag(self, tag):
        if tag != 'script' or self.schema is None:
            return
        try:
            record = json.loads(''.join(self.schema))
            recording = record.get('audio', record) if isinstance(record, dict) else {}
            album = recording.get('inAlbum', {})
            if isinstance(album, dict):
                candidate = apple_page(album.get('url'))
                if candidate:self.album = candidate
        except (ValueError, TypeError, AttributeError):
            pass
        self.schema = None


class AppleMotion:
    def __init__(self, changed):
        self.changed = changed
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ember-motion-lookup')
        self.generation = 0
        self.key = None
        self.closed = False
        self.future = None
        self.cache = OrderedDict()

    def set_track(self, page, cover=''):
        page = apple_page(page)
        key = (page, cover) if page else None
        if self.closed or key == self.key:
            return
        self.key = key
        self.generation += 1
        generation = self.generation
        if self.future:
            self.future.cancel()
        if not page:
            self.changed('')
            return
        cache_key = cover or page
        cached = self.cache.get(cache_key)
        if cached and time.monotonic()-cached[0] < (3600 if cached[1] else 60):
            self.cache.move_to_end(cache_key)
            self.changed(cached[1])
            return
        self.changed('')
        self.future = self.pool.submit(self._lookup, page, generation)
        self.future.add_done_callback(lambda future: GLib.idle_add(
            self._deliver, generation, cache_key, future, priority=GLib.PRIORITY_DEFAULT))

    def _page(self, url, generation):
        if self.closed or generation != self.generation:
            return None
        request = urllib.request.Request(url, headers={'User-Agent': 'Emberbox Audio (artwork)', 'Accept': 'text/html'})
        with urllib.request.urlopen(request, timeout=6) as response:
            if not apple_page(response.url):
                return None
            raw = response.read(3_000_001)
        if len(raw) > 3_000_000 or self.closed or generation != self.generation:
            return None
        result = ApplePage()
        result.feed(raw.decode('utf-8', errors='replace'))
        return result

    def _lookup(self, page, generation):
        try:
            result = self._page(page, generation)
            if not result:
                return ''
            if '/song/' in urlsplit(page).path:
                # A song's linked album is authoritative; never take related releases.
                if not result.album:
                    return ''
                result = self._page(result.album, generation)
            return result.motion if result else ''
        except (OSError, ValueError, TypeError):
            return ''

    def _deliver(self, generation, key, future):
        if self.closed or generation != self.generation or future.cancelled():
            return False
        try:
            url = future.result()
        except Exception:
            url = ''
        self.cache[key] = (time.monotonic(), url)
        self.cache.move_to_end(key)
        while len(self.cache) > 32:
            self.cache.popitem(last=False)
        self.changed(url)
        return False

    def close(self):
        self.closed = True
        self.generation += 1
        self.pool.shutdown(wait=False, cancel_futures=True)
