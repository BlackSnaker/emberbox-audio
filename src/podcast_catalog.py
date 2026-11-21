"""Podcast catalogue adapters. Public Apple episodes come from publisher RSS."""
from hashlib import sha256
from ipaddress import ip_address
import json
import os
import re
import socket
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

from source_picker import text


APPLE = 'apple-podcasts'
PROVIDERS = {
    APPLE: 'Apple Podcasts',
    'spotify': 'Spotify',
    'yandex-music': text('Yandex Music', 'Яндекс Музыка'),
}
ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
FEED_LIMIT = 8 * 1024 * 1024


def public_url(value):
    """Keep feeds and enclosures on HTTPS and reject local/literal hosts."""
    try:
        url = urlsplit(str(value or ''))
        host = url.hostname or ''
        if (url.scheme != 'https' or url.username or url.password or url.port not in (None, 443)
                or not re.fullmatch(r'[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z][a-zA-Z0-9-]*', host)
                or host.endswith(('.local', '.localhost', '.internal', '.lan', '.home.arpa'))
                or len(url.geturl()) > 4096):
            return ''
        return url.geturl()
    except ValueError:
        return ''


def public_network(url):
    value = public_url(url)
    if not value:
        raise ValueError(text('The publisher did not provide a public HTTPS address.',
                              'Издатель не предоставил публичный HTTPS-адрес.'))
    host = urlsplit(value).hostname
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError(text('The publisher address is outside the public internet.',
                              'Адрес издателя находится за пределами публичной сети.'))
    return value


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, msg, headers, newurl):
        return super().redirect_request(request, file, code, msg, headers, public_network(newurl))


def fetch(url, limit):
    request = Request(public_network(url), headers={'User-Agent': 'Emberbox Podcast Reader'})
    with build_opener(PublicRedirect).open(request, timeout=9) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(text('The podcast response is too large.', 'Ответ каталога подкастов слишком большой.'))
    return data


def duration_ms(value):
    try:
        parts = str(value or '0').split(':')
        if len(parts) > 3:
            return 0
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        return max(0, min(seconds * 1000, 86400000))
    except ValueError:
        return 0


def apple_shows(data):
    shows = []
    for value in data.get('results', []):
        identifier = str(value.get('collectionId') or '')
        title = str(value.get('collectionName') or '').strip()[:300]
        feed = public_url(value.get('feedUrl'))
        if not title or not identifier.isdecimal() or not feed:
            continue
        shows.append({'kind': 'show', 'id': identifier, 'title': title, 'feed': feed,
                      'artist': str(value.get('artistName') or '')[:300],
                      'genre_ids': [str(mark) for mark in value.get('genreIds', [])],
                      'image': public_url(value.get('artworkUrl600') or value.get('artworkUrl100'))})
    return shows


def apple_episodes(show, data):
    # RSS feeds have no need for DTDs. Avoid entity expansion, including
    # UTF-16 payloads whose markup bytes are interspersed with NULs.
    if b'<!DOCTYPE' in data.replace(b'\x00', b'').upper():
        raise ValueError(text('The publisher feed is not supported.', 'Формат ленты издателя не поддерживается.'))
    root = ElementTree.fromstring(data)
    if root.tag != 'rss':
        raise ValueError(text('The publisher did not return an RSS feed.', 'Издатель не вернул RSS-ленту.'))
    episodes, seen = [], set()
    for item in root.findall('./channel/item'):
        title = (item.findtext('title') or '').strip()[:300]
        streams = (public_url(link.get('url')) for link in item.findall('enclosure')
                   if link.get('type', '').lower().startswith('audio/') or not link.get('type'))
        stream = next((url for url in streams if url), '')
        if not title or not stream or stream in seen:
            continue
        seen.add(stream)
        guid = item.findtext('guid') or stream
        identifier = sha256((show['id'] + ':' + guid).encode()).hexdigest()[:32]
        episodes.append({'kind': 'episode', 'id': identifier, 'uri': APPLE + ':episode:' + identifier,
                         'title': title, 'artist': show['title'], 'album': show['title'],
                         'image': show.get('image', ''), 'url': stream,
                         'duration_ms': duration_ms(item.findtext(ITUNES + 'duration'))})
        if len(episodes) == 200:
            break
    return episodes


class PodcastCatalog:
    def __init__(self, host):
        self.host = host

    def load(self, provider, term, show=None, *, country=None):
        if provider == APPLE:
            if show:
                return apple_episodes(show, fetch(show['feed'], FEED_LIMIT))
            locale = re.search(r'[_-]([A-Z]{2})(?:\.|$)', os.environ.get('LANG', ''))
            country = country or (locale[1] if locale else 'US')
            query = urlencode({'term': term, 'country': country, 'media': 'podcast',
                               'entity': 'podcast', 'limit': 40})
            return apple_shows(json.loads(fetch('https://itunes.apple.com/search?' + query, 1024 * 1024)))
        if provider == 'spotify':
            client = self.host.spotify_web
            result = client.request('tracks', uri=show['uri']) if show else client.request(
                'search', term=term, media='podcasts')
        elif provider == 'yandex-music':
            client = self.host.yandex_web
            result = client.request('podcastEpisodes', id=show['id']) if show else client.request('podcasts', term=term)
        else:
            return []
        values = []
        for item in result.get('items', [])[:200]:
            kind = item.get('kind')
            if not item.get('title') or not item.get('id') or kind not in ('episode', 'show'):
                continue
            values.append({**item, 'image': public_url(item.get('image')) or (show or {}).get('image', ''),
                           'artist': item.get('artist') or item.get('subtitle') or (show or {}).get('title', ''),
                           'duration_ms': item.get('duration_ms') or round((item.get('duration') or 0) * 1000)})
        return values
