"""Release identity, local wishlist and physical-edition search."""
import json
import re
from urllib.parse import urlencode


def release_reference(source, item):
    if not isinstance(item, dict) or not item.get('title'):
        return None
    raw_id = str(item.get('id') or '')
    uri = str(item.get('uri') or '')
    if item.get('kind') not in ('album','albums','library-albums') and not any(
            part in uri for part in (':album:',':albums:',':library-albums:')):
        return None
    if source == 'apple-music':
        catalog = str(item.get('catalogId') or '')
        identifier = catalog if re.fullmatch(r'\d{1,20}', catalog) else raw_id
        if re.fullmatch(r'\d{1,20}', identifier):
            kind = 'albums'
        elif re.fullmatch(r'l\.[\w.-]{1,198}', identifier):
            kind = 'library-albums'
        else:
            return None
        uri = f'apple:{kind}:{identifier}'
    elif source == 'spotify':
        match = re.fullmatch(r'(?:spotify:album:|/album/)([A-Za-z0-9]{1,64})', uri or str(item.get('href') or ''))
        if not match and item.get('kind') == 'album':
            match = re.fullmatch(r'([A-Za-z0-9]{1,64})', raw_id)
        if not match:return None
        identifier = match[1]
        kind, uri = 'album', 'spotify:album:'+identifier
    elif source == 'yandex-music' and re.fullmatch(r'\d{1,20}', raw_id):
        identifier = raw_id
        kind, uri = 'album', 'yandex:album:'+identifier
    else:
        return None
    return {**item, 'id': identifier, 'kind': kind, 'uri': uri,
            'artist': item.get('artist') or item.get('subtitle') or ''}


def edition_links(album, format_name):
    query = ' '.join(str(album.get(key) or '').strip()[:160] for key in ('artist', 'title')).strip()
    if not query or format_name not in ('Vinyl', 'CD'):
        return {}
    return {
        'Discogs': 'https://www.discogs.com/sell/list?' + urlencode({'q': query, 'format': format_name}),
        'eBay': 'https://www.ebay.com/sch/i.html?' + urlencode({'_nkw': f'{query} {format_name}'}),
        'Ozon': 'https://www.ozon.ru/search/?' + urlencode({'text': f'{query} {format_name}'}),
    }


class AlbumWishlist:
    def __init__(self, path):
        self.path = path
        self.items = {}
        try:
            if path.stat().st_size <= 2_000_000:
                for value in json.loads(path.read_text()):
                    source = value.get('source') or ''
                    if ref := release_reference(source, value):
                        self.items[ref['uri']] = dict(ref, source=source)
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def toggle(self, source, album):
        key = album['uri']
        values = dict(self.items)
        if key in values:
            del values[key]
        else:
            fields = ('id', 'kind', 'uri', 'title', 'artist', 'image', 'releaseDate', 'year', 'trackCount')
            values[key] = dict({name: album[name] for name in fields if name in album}, source=source)
        saved = json.dumps(list(values.values()), ensure_ascii=False)
        if len(saved.encode()) > 2_000_000:
            raise OSError('The wishlist is full.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.next.json')
        temporary.write_text(saved)
        temporary.chmod(0o600)
        temporary.replace(self.path)
        self.items = values
