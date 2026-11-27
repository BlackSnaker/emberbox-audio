"""Small direct Yandex Music API client. OAuth credentials never reach media URLs."""
import base64
import hashlib
import hmac
import json
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from xml.etree import ElementTree


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Never forward OAuth headers or fetch an unvalidated media redirect.
        return None


def urlopen(request, timeout):
    return build_opener(NoRedirect).open(request, timeout=timeout)


class YandexError(RuntimeError):
    pass


def token_store(token=None):
    """Use the desktop Secret Service; never fall back to plaintext files."""
    command = ['secret-tool', 'lookup' if token is None else 'store',
               *([] if token is None else ['--label=Emberbox Yandex Music']),
               'application', 'emberbox', 'service', 'yandex-music']
    try:
        result = subprocess.run(command, input=None if token is None else token,
                                text=True, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise YandexError('Yandex token storage requires secret-tool and an unlocked desktop keyring.') from None
    if result.returncode and token is not None:
        raise YandexError('Could not save the token in the desktop keyring.')
    return result.stdout.strip() if token is None else token


def safe_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    if parsed.scheme != 'https' or parsed.username or parsed.password or not any(
            host == root or host.endswith('.' + root) for root in ('yandex.net', 'yandex.ru')):
        raise YandexError('Invalid Yandex media URL.')
    return url


class API:
    def __init__(self, token):
        self.token = token.strip()
        if not self.token or any(c.isspace() for c in self.token):
            raise YandexError('Enter a valid Yandex Music OAuth token.')

    def call(self, path, data=None, json_body=None, *, timeout=15, **query):
        url = 'https://api.music.yandex.net/' + path
        if query:
            url += '?' + urlencode(query)
        payload = json.dumps(json_body).encode() if json_body is not None else None if data is None else urlencode(data).encode()
        request = Request(url, data=payload, headers={
            'Authorization': 'OAuth ' + self.token,
            'Content-Type': 'application/json' if json_body is not None else 'application/x-www-form-urlencoded',
            'X-Yandex-Music-Client': 'YandexMusicAndroid/24024312', 'User-Agent': 'Emberbox'})
        try:
            with urlopen(request, timeout=timeout) as response:
                body = json.load(response)
            if body.get('error'):
                raise YandexError('Yandex Music rejected the request.')
            return body.get('result')
        except HTTPError as error:
            messages = {401: 'Yandex token expired or invalid. Reconnect in Accounts.',
                        403: 'Yandex Music access denied. Check your subscription and region.'}
            raise YandexError(messages.get(error.code, 'Yandex Music request failed.')) from None
        except (URLError, OSError, ValueError):
            raise YandexError('Yandex Music could not be reached. Retry shortly.') from None

    def tracks(self, ids):
        return self.call('tracks', {'track-ids': ','.join(map(str, ids))}) or []

    def lyrics(self, identifier, fmt, *, timeout=2):
        """Fetch one lyric format using the signed API flow documented by yamusic-rs."""
        identifier = str(identifier).partition(':')[0]
        if not identifier.isascii() or not identifier.isdecimal() or fmt not in ('LRC', 'TEXT'):
            raise ValueError('Invalid Yandex lyrics request.')
        deadline = time.monotonic() + timeout
        timestamp = str(int(time.time()))
        digest = hmac.digest(b'p93jhgh689SBReK6ghtw62', (identifier + timestamp).encode(), 'sha256')
        result = self.call(f'tracks/{identifier}/lyrics', format=fmt, timeStamp=timestamp,
                           sign=base64.b64encode(digest).decode('ascii'), timeout=timeout)
        url = result.get('downloadUrl') if isinstance(result, dict) else None
        if not isinstance(url, str) or not url:
            return ''
        limit = 512_000
        # No OAuth headers on the download, and no unvalidated redirects.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Yandex lyrics lookup timed out.')
        with urlopen(safe_url(url), timeout=remaining) as response:
            raw = response.read(limit + 1)
        if len(raw) > limit:
            raise YandexError('Yandex lyrics response is too large.')
        return raw.decode('utf-8-sig')

    def stream(self, identifier):
        variants = self.call('tracks/' + quote(str(identifier), safe='') + '/download-info') or []
        variants = sorted((v for v in variants if v.get('codec') == 'mp3' and not v.get('preview')),
                          key=lambda v: v.get('bitrateInKbps', 0), reverse=True)
        if not variants:
            raise YandexError('No playable full-length stream. Check Yandex Plus access.')
        url = safe_url(variants[0]['downloadInfoUrl'])
        try:
            with urlopen(url, timeout=15) as response:
                root = ElementTree.fromstring(response.read(65536))
            host, path, ts, salt = (root.findtext(k) for k in ('host', 'path', 'ts', 's'))
            signature = hashlib.md5(('XGRlBW9FXlekgbPrRHuSiA' + path[1:] + salt).encode()).hexdigest()
            return safe_url('https://' + host + '/get-mp3/' + signature + '/' + ts + path)
        except (OSError, ValueError, TypeError, ElementTree.ParseError):
            raise YandexError('Yandex Music stream is unavailable.') from None


def artist_credit(artist):
    cover = artist.get('cover')
    uri = (cover.get('uri') if isinstance(cover, dict) else '') or artist.get('coverUri')
    image = ''
    if isinstance(uri, str) and uri:
        try:
            image = safe_url('https://' + uri.replace('%%', '200x200'))
        except (ValueError, YandexError):
            pass
    return {'id': str(artist.get('id', '')), 'name': artist.get('name', ''), 'image': image}


def track(item):
    item = item.get('track', item)
    albums = item.get('albums') or [{}]
    artists = item.get('artists') or []
    image = item.get('coverUri') or albums[0].get('coverUri') or ''
    return dict(id=str(item.get('id', '')), uri='yandex:track:' + str(item.get('id', '')),
                kind='song', title=item.get('title', ''), artist=', '.join(a.get('name', '') for a in artists),
                artists=[artist_credit(a) for a in artists],
                artistId=str(artists[0].get('id', '')) if artists else '', album=albums[0].get('title', ''),
                albumId=str(albums[0].get('id', '')), duration=item.get('durationMs', 0) / 1000,
                image=('https://' + image.replace('%%', '400x400')) if image else '')
