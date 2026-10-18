"""Read personal music and control background playback in the local Spotify client.

Only music metadata is returned. No cookies, passwords or session tokens are read.
"""

import json
import re
import time
import threading
import urllib.request
from pathlib import Path
from paths import CACHE_DIR, CONFIG_DIR

import websocket


PORT = 43827
CACHE = CACHE_DIR / 'discovery.json'
CLIENT_LOCK = threading.RLock()

PLAYER_SCRIPT = r'''(() => {
  const el = document.querySelector('main') || document.querySelector('#main');
  if (!el) return null;
  let fiber = el[Object.keys(el).find(k => k.startsWith('__reactFiber'))];
  function resolvePlayer(registry, seen = new Set()) {
    if (!registry || seen.has(registry)) return null;
    seen.add(registry);
    const key = Array.from(registry._map?.keys() || [])
      .find(k => String(k) === 'Symbol(PlayerAPI)');
    if (key) return registry.resolve(key);
    for (const parent of registry._parents || []) {
      const player = resolvePlayer(parent, seen);
      if (player) return player;
    }
    return null;
  }
  for (let depth = 0; fiber && depth < 300; depth++, fiber = fiber.return) {
    const values = [fiber.memoizedProps?.value];
    for (let context = fiber.dependencies?.firstContext; context; context = context.next)
      values.push(context.memoizedValue);
    for (const value of values) {
      if (typeof value?.getRegistry !== 'function') continue;
      const player = resolvePlayer(value.getRegistry());
      if (typeof player?.play === 'function') return player;
    }
  }
  return null;
})()'''

HOME_SCRIPT = r'''(() => {
  if (!document.querySelector('[data-testid="home-page"]')) return null;
  const shelves = Array.from(document.querySelectorAll('main section[data-testid="component-shelf"]'));
  return shelves.map((s, index) => ({
    title: index === 0 ? 'Миксы дня и открытия' : (s.querySelector('h2')?.innerText || ''),
    items: Array.from(s.querySelectorAll('[data-encore-id="card"]')).map(c => {
      const a = c.querySelector('a[href]');
      return {
        title: c.querySelector('[data-encore-id="cardTitle"]')?.textContent?.trim() || '',
        subtitle: c.querySelector('[data-encore-id="cardSubtitle"]')?.textContent?.trim() || '',
        href: a?.getAttribute('href') || '',
        image: c.querySelector('img')?.getAttribute('src') || ''
      };
    }).filter(c => /^\/(playlist|album)\/[A-Za-z0-9]+$/.test(c.href) && c.title)
  })).filter(s => s.items.length);
})()'''

TRACKS_SCRIPT = r'''(() => {
  const rows = Array.from(document.querySelectorAll('main [data-testid="tracklist-row"]'));
  if (!rows.length) return null;
  function fiber(el) { return el[Object.keys(el).find(k => k.startsWith('__reactFiber'))]; }
  let context = '', cache = null;
  for (let f = fiber(rows[0]), depth = 0; f && depth < 65; f = f.return, depth++) {
    const p = f.memoizedProps || {};
    if (!context && typeof p.contextUri === 'string') context = p.contextUri;
    if (p.itemsCache?.getItems) { cache = p.itemsCache; break; }
  }
  if (context && context !== EXPECTED) return null;
  const total = Number(cache?.nrValidItems || rows.length);
  let items = cache ? cache.getItems(0, Math.min(99, total - 1), {cachedOnly: true}) : [];
  if (!cache) {
    items = rows.map(row => {
      for (let f = fiber(row), n = 0; f && n < 35; f = f.return, n++) {
        if (f.memoizedProps?.item?.uri) return f.memoizedProps.item;
      }
      return null;
    });
  }
  if (cache && items.filter(Boolean).length < Math.min(total, 100)) {
    cache.getItems(0, Math.min(99, total - 1));
  }
  return {
    title: document.querySelector('main h1')?.innerText || '',
    context, total,
    tracks: items.filter(Boolean).map(t => t.track || t).filter(t => t.uri?.startsWith('spotify:track:')).map(t => ({
      uri: t.uri, title: t.name || '',
      artist: (t.artists || []).map(a => a.name).join(', '),
      album: t.album?.name || '',
      image: t.album?.images?.find(i => i.label === 'small')?.url || t.album?.images?.[0]?.url || '',
      duration_ms: t.duration?.milliseconds || 0,
      playable: t.isPlayable !== false
    }))
  };
})()'''


class ConnectionUnavailable(Exception):
    pass


def image_url(url):
    if url.startswith('spotify:image:'):
        return 'https://i.scdn.co/image/' + url.rsplit(':', 1)[-1]
    return url if url.startswith('https://') else ''


class LocalSpotify:
    def __enter__(self):
        CLIENT_LOCK.acquire()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=2) as response:
                targets = json.load(response)
            target = next(t for t in targets if t.get('type') == 'page'
                          and t.get('url', '').startswith('https://xpui.app.spotify.com/'))
            self.ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=12,
                                                  suppress_origin=True)
            self.sequence = 0
            return self
        except Exception as error:
            CLIENT_LOCK.release()
            raise ConnectionUnavailable('Connect Spotify to see your personal picks.') from error

    def __exit__(self, *_args):
        self.ws.close()
        CLIENT_LOCK.release()

    def evaluate(self, expression):
        self.sequence += 1
        self.ws.send(json.dumps({'id': self.sequence, 'method': 'Runtime.evaluate',
                                'params': {'expression': expression, 'returnByValue': True,
                                           'awaitPromise': True}}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get('id') != self.sequence:
                continue
            result = reply.get('result', {})
            if reply.get('error') or result.get('exceptionDetails'):
                raise RuntimeError('Spotify has not returned the list yet. Try refreshing.')
            return result.get('result', {}).get('value')

    def home(self):
        if not self.evaluate("!!document.querySelector('[data-testid=\"home-page\"]')"):
            self.evaluate("document.querySelector('[data-testid=\"home-button\"]')?.click()")
        for _ in range(35):
            shelves = self.evaluate(HOME_SCRIPT)
            if shelves:
                first = shelves[0]['items']
                first.sort(key=lambda item: 0 if item['title'] == 'Открытия недели'
                           else 1 if item['title'] == 'Радар новинок' else 2)
                for shelf in shelves:
                    for item in shelf['items']:
                        item['uri'] = 'spotify:' + item['href'].strip('/').replace('/', ':')
                        item['image'] = image_url(item['image'])
                data = {'updated': time.time(), 'shelves': shelves}
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                temporary = CACHE.with_suffix('.next.json')
                temporary.write_text(json.dumps(data, ensure_ascii=False))
                temporary.chmod(0o600)
                temporary.replace(CACHE)
                return data
            time.sleep(0.2)
        raise RuntimeError('Spotify Home is still loading. Try refreshing in a moment.')

    def play(self, uri):
        if not re.fullmatch(r'spotify:(track|playlist|album):[A-Za-z0-9]+', uri):
            raise ValueError('Could not play this track.')
        script = f'''(async () => {{
          const player = {PLAYER_SCRIPT};
          if (!player) return false;
          await player.play({{uri: {json.dumps(uri)}}},
                            {{featureIdentifier: 'gruvbox-widget'}});
          return true;
        }})()'''
        try:
            played = self.evaluate(script)
        except Exception as error:
            raise RuntimeError('Could not play this track. Try again.') from error
        if not played:
            raise ConnectionUnavailable('Connect Spotify to play tracks in the background.')

    def tracks(self, item):
        href = item.get('href', '')
        if not re.fullmatch(r'/(playlist|album)/[A-Za-z0-9]+', href):
            raise ValueError('Could not open this collection.')
        expected = 'spotify:' + href.strip('/').replace('/', ':')
        script = TRACKS_SCRIPT.replace('EXPECTED', json.dumps(expected))
        current = self.evaluate(script)
        if not current:
            self.home()
            found = self.evaluate(f'''(() => {{
              const a = Array.from(document.querySelectorAll('main a[href]'))
                .find(a => a.getAttribute('href') === {json.dumps(href)});
              a?.click(); return !!a;
            }})()''')
            if not found:
                raise RuntimeError('This collection changed. Go back and refresh your picks.')
        best = None
        for _ in range(40):
            data = self.evaluate(script)
            if data and data.get('tracks'):
                best = data
                if len(data['tracks']) >= min(data.get('total', 0), 100):
                    break
            time.sleep(0.2)
        if not best:
            raise RuntimeError('Could not load tracks. Open this collection in Spotify, then refresh.')
        for track in best['tracks']:
            track['image'] = image_url(track['image'])
        return best


def cached_home():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return None
