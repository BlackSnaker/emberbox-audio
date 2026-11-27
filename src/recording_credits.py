"""Normalize explicitly attributed recording and release participants."""
import re


def people(value):
    if isinstance(value, (str, dict)):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    result = {}
    for person in value:
        name = person.get('name') if isinstance(person, dict) else person
        if not isinstance(name, str) or not (name := ' '.join(name.split())[:300]):
            continue
        identifier = str(person.get('id') or '') if isinstance(person, dict) else ''
        if not re.fullmatch(r'[A-Za-z0-9]{1,64}', identifier):
            identifier = ''
        key = name.casefold()
        portrait = person.get('image') if isinstance(person, dict) else ''
        portrait = portrait if isinstance(portrait, str) and portrait.startswith('https://') else ''
        previous = result.get(key, {})
        result[key] = {'name': previous.get('name', name), 'id': previous.get('id') or identifier,
                       'image': previous.get('image') or portrait}
    return list(result.values())


def album_people(release, tracks):
    artists = people(release.get('artists'))
    if not artists:
        artists = people(release.get('artist'))
    keys = {person['name'].casefold() for person in artists}
    ids = {person['id'] for person in artists if person['id']}
    guests = people([person for track in tracks for person in people(track.get('artists'))])
    return artists, [person for person in guests
                     if person['name'].casefold() not in keys and person['id'] not in ids]


def current_recording(host):
    if getattr(getattr(host, 'podcast_audio', None), 'enabled', False):
        return None
    title = host.title.get_text()
    if not host.length or not title:
        return None
    source = host.source
    native = {'apple-music': ('apple_mode', 'apple_web'), 'spotify': ('spotify_mode', 'spotify_web')}
    web = None
    if source in native:
        mode, player = native[source]
        if getattr(host, mode, None) == 'native':
            web = getattr(host, player, None)
    elif source == 'yandex-music':
        web = getattr(host, 'yandex_web', None)
    data = web.state if web else {}
    if data.get('kind') in ('episode', 'podcast', 'show'):
        return None
    metadata = getattr(getattr(host, 'session', None), 'metadata', {}) if not web else {}
    uri = data.get('uri') or metadata.get('xesam:url') or ''
    if re.search(r'(?::episode:|/episode/)', str(uri)):
        return None
    identifier = str(data.get('catalogId') or data.get('id') or metadata.get('mpris:trackid') or '')
    album, artist = host.album.get_text(), host.artist.get_text()
    roles = {
        'artists': (people(data.get('artists')) or people(metadata.get('xesam:artist')) or people(artist))
        if source != 'youtube' else [],
        'channel': people(artist) if source == 'youtube' else [],
        'composer': people(data.get('composer') or metadata.get('xesam:composer')),
        'lyricist': people(metadata.get('xesam:lyricist')),
    }
    key = (source, identifier, title, album, artist)
    apple = web if source == 'apple-music' and re.fullmatch(r'(?:\d{1,20}|i\.[\w.-]{1,198})', identifier) else None
    return key, roles, apple
