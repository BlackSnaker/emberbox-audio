"""Read artist photographs from Spotify's public, identity-checked metadata.

No signed-in browser state or account headers are used. Decorative CSS images
and images belonging to a different artist must never become the masthead.
"""
from collections import OrderedDict
from html.parser import HTMLParser
from http.client import HTTPException
import re
import threading
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_HEAD = 128 * 1024
CACHE_SIZE = 64
_cache = OrderedDict()
_lock = threading.Lock()


def artist_id(url):
    try:
        parsed = urlsplit(str(url))
        if (parsed.scheme != 'https' or parsed.hostname != 'open.spotify.com'
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)):
            return ''
        match = re.fullmatch(r'/(?:intl-[a-z]{2}/)?artist/([A-Za-z0-9]{1,64})/?', parsed.path)
        return match[1] if match else ''
    except ValueError:
        return ''


def image_url(value, portrait=False):
    try:
        parsed = urlsplit(str(value))
        host = parsed.hostname or ''
        if (parsed.scheme != 'https' or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment
                or not (host == 'i.scdn.co' or host.endswith('.spotifycdn.com'))
                or not re.fullmatch(r'/image/[A-Za-z0-9]{20,100}', parsed.path)):
            return ''
        if portrait and not parsed.path.startswith(('/image/ab676161', '/image/ab676186')):
            return ''
        return str(value)
    except ValueError:
        return ''


class ArtistMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.url = self.image = ''
        self.finished = False

    def handle_starttag(self, tag, attrs):
        if self.finished or tag != 'meta':
            return
        attrs = dict(attrs)
        if attrs.get('property') == 'og:url':
            self.url = attrs.get('content', '')
        elif attrs.get('property') == 'og:image':
            self.image = attrs.get('content', '')

    def handle_endtag(self, tag):
        if tag == 'head':
            self.finished = True


class ArtistRedirect(HTTPRedirectHandler):
    def __init__(self, ident):
        super().__init__()
        self.ident = ident

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if artist_id(newurl) != self.ident:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def public_image(ident):
    parser = ArtistMetadata()
    deadline = time.monotonic() + 3
    request = Request('https://open.spotify.com/artist/' + ident,
                      headers={'User-Agent': 'EmberboxAudio/1.0', 'Accept': 'text/html'})
    with build_opener(ArtistRedirect(ident)).open(request, timeout=2.5) as response:
        if artist_id(response.geturl()) != ident:
            return ''
        # The image and canonical identity are in the public page's head. Stop
        # there, rather than retaining the application's serialized body.
        for _ in range(MAX_HEAD // 8192):
            if time.monotonic() >= deadline:
                break
            block = response.read(8192)
            if not block:
                break
            parser.feed(block.decode('utf-8', 'replace'))
            if parser.finished or parser.url and parser.image:
                break
    return image_url(parser.image) if artist_id(parser.url) == ident else ''


def artist_image(ident, fallback=''):
    ident = str(ident or '')
    fallback = image_url(fallback, portrait=True)
    if not re.fullmatch(r'[A-Za-z0-9]{1,64}', ident):
        return ''
    now = time.monotonic()
    with _lock:
        cached = _cache.get(ident)
        if cached and now - cached[0] < cached[2]:
            _cache.move_to_end(ident)
            return cached[1] or fallback
    try:
        value = public_image(ident)
    except (OSError, ValueError, HTTPException):
        value = ''
    with _lock:
        # Successful photographs are reused for an hour; failed lookups can
        # recover quickly without hammering a temporarily unavailable website.
        _cache[ident] = (time.monotonic(), value, 3600 if value else 20)
        _cache.move_to_end(ident)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return value or fallback
