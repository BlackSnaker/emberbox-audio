"""The podcast wall and content-language filters."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from paths import CONFIG_DIR
from podcast_catalog import APPLE, PublicRedirect, apple_shows, fetch, public_network
from source_picker import text


LANGUAGES = {
    'ru': ('Русский', 'ru'),
    'en': ('English', 'us'),
    'pl': ('Polski', 'pl'),
    'de': ('Deutsch', 'de'),
    'fr': ('Français', 'fr'),
    'es': ('Español', 'es'),
    'all': (text('All languages', 'Все языки'), ''),
}
CATEGORIES = {
    'all': (text('All categories', 'Все категории'), ''),
    'history': (text('History', 'История'), '1487'),
    'science': (text('Science', 'Наука'), '1533'),
    'technology': (text('Technology', 'Технологии'), '1318'),
    'culture': (text('Culture', 'Культура'), '1324'),
    'news': (text('News', 'Новости'), '1489'),
    'comedy': (text('Comedy', 'Комедия'), '1303'),
}
PREFERENCES = CONFIG_DIR / 'podcast-discovery.json'
SHELF = Path(__file__).with_name('podcast_showcase.json')
LOCALE_LANGUAGE = re.split('[-_.]', os.environ.get('EMBERBOX_LANGUAGE', os.environ.get('LANG', 'en')).lower())[0]
DEFAULT_LANGUAGE = LOCALE_LANGUAGE if LOCALE_LANGUAGE in LANGUAGES else 'en'
WALL_LIMIT = 24


def preferences(path=PREFERENCES):
    try:
        data = json.loads(path.read_text())
        language, category = data.get('language'), data.get('category')
        return (language if language in LANGUAGES else DEFAULT_LANGUAGE,
                category if category in CATEGORIES else 'all')
    except (OSError, ValueError, AttributeError, TypeError):
        return DEFAULT_LANGUAGE, 'all'


def save_preferences(language, category, path=PREFERENCES):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.next')
        temporary.write_text(json.dumps({'language': language, 'category': category}) + '\n')
        temporary.replace(path)
    except OSError:
        pass


@lru_cache(maxsize=1)
def sample():
    return tuple(json.loads(SHELF.read_text(encoding='utf-8')))


def native_show(value, provider):
    if provider == APPLE:
        return {**value, 'kind': 'show'}
    identifier = value.get(provider)
    if not identifier:
        return None
    native = {key: value[key] for key in ('title', 'artist', 'image', 'language', 'categories')}
    native.update(id=identifier,kind='show')
    if provider == 'spotify':
        native['uri'] = 'spotify:show:' + identifier
    return native


def showcase(provider, language, category):
    values = []
    for value in sample():
        if category != 'all' and category not in value['categories']:
            continue
        if language != 'all' and value['language'] != language:
            continue
        if item := native_show(value, provider):
            values.append(item)
    if language == 'all':
        # Interleave languages so the first screen is not all one market.
        by_language = {key: [] for key in LANGUAGES if key != 'all'}
        for value in values:
            by_language[value['language']].append(value)
        values = [group[index] for index in range(WALL_LIMIT) for group in by_language.values()
                  if index < len(group)]
    return values[:WALL_LIMIT]


def language_code(value):
    return re.split('[-_]', str(value or '').lower(), maxsplit=1)[0].strip()


@lru_cache(maxsize=500)
def feed_language(url):
    try:
        request = Request(public_network(url), headers={'User-Agent': 'Emberbox Podcast Reader'})
        with build_opener(PublicRedirect).open(request, timeout=5) as response:
            prefix = response.read(52_000).replace(b'\x00', b'')
        # Only the channel metadata describes the show's spoken language.
        prefix = re.split(br'<item(?:\s|>)', prefix, maxsplit=1, flags=re.I)[0]
        found = re.search(br'<language(?:\s+[^>]*)?>\s*(?:<!\[CDATA\[)?([a-z]{2,3})(?=[\s<\]_-])',
                          prefix, re.I)
        return found[1].decode('ascii').lower() if found else ''
    except (OSError, ValueError):
        return ''


def unique(values):
    by_id = {}
    for item in values:
        by_id.setdefault((item['kind'], item['id']), item)
    return list(by_id.values())


class PodcastDiscovery:
    def __init__(self, catalogue):
        self.catalogue = catalogue
        self.cache = {}

    def browse(self, provider, language, category):
        initial = showcase(provider, language, category)
        if provider != APPLE or language == 'all':
            return initial
        key = (language, category)
        if key in self.cache:
            return self.cache[key]
        country = LANGUAGES[language][1]
        genre = CATEGORIES[category][1]
        route = '/genre=' + genre if genre else ''
        raw = fetch(f'https://itunes.apple.com/{country}/rss/toppodcasts/limit=25{route}/json', 1_500_000)
        entries = json.loads(raw).get('feed', {}).get('entry', [])
        ids = [str(item.get('id', {}).get('attributes', {}).get('im:id', '')) for item in entries]
        query = urlencode({'id': ','.join(identifier for identifier in ids if identifier.isdecimal()),
                           'country': country, 'entity': 'podcast'})
        if not any(identifier.isdecimal() for identifier in ids):
            return initial
        raw = fetch('https://itunes.apple.com/lookup?' + query, 1_500_000)
        items = apple_shows(json.loads(raw))
        position = {identifier: index for index, identifier in enumerate(ids)}
        items.sort(key=lambda item: position.get(item['id'], len(ids)))
        selected = self.filter(APPLE, items, language, 'all')
        if genre:
            for item in selected:
                item['categories'] = list(dict.fromkeys([category, *item.get('categories', [])]))
        values = unique(initial + selected)[:WALL_LIMIT]
        self.cache[key] = values
        return values

    def search(self, provider, term, language, category):
        country = LANGUAGES[language][1]
        options = {'country': country} if provider == APPLE and country else {}
        items = self.catalogue.load(provider, term, **options)
        return self.filter(provider, items, language, category)

    def filter(self, provider, items, language, category):
        base = {v['id']: v for item in sample() if (v := native_show(item, provider))}
        items = [dict(item) for item in items]
        for item in items:
            known = base.get(item['id']) or (base.get(item.get('showId') or item.get('albumId'))
                                             if item['kind'] == 'episode' else None)
            if known:
                for key in ('language', 'categories'):
                    if not item.get(key):
                        item[key] = known[key]
            if provider == APPLE and not item.get('categories'):
                item['categories'] = [key for key, (_, genre) in CATEGORIES.items()
                                      if genre and genre in item.get('genre_ids', [])]
        if category != 'all':
            items = [item for item in items if category in item.get('categories', [])]
        if language == 'all':
            return items
        if provider == APPLE:
            pending = [item for item in items[:24] if not item.get('language')]
            with ThreadPoolExecutor(max_workers=6, thread_name_prefix='podcast-language') as pool:
                for item, spoken in zip(pending, pool.map(feed_language, (item['feed'] for item in pending))):
                    item['language'] = spoken
        return [item for item in items if language in
                {language_code(mark) for mark in [item.get('language'), *(item.get('languages') or [])]}]
