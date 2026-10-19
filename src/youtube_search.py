"""YouTube URLs and cancellable public search, shared with Emberbox Video."""

import json
import re
import subprocess
import shutil
import threading
from urllib.parse import parse_qs, urlparse
from pathlib import Path

from gi.repository import GLib


def yt_dlp_executable():
    # pipx installs the current CLI here; systemd may not inherit the shell PATH.
    found = shutil.which('yt-dlp')
    local = Path.home() / '.local/bin/yt-dlp'
    return found or (str(local) if local.is_file() else 'yt-dlp')


def video_url(text):
    """Return a canonical video URL plus optional start, or None for a search."""
    text = text.strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', text):
        return f'https://www.youtube.com/watch?v={text}', 0
    if text.startswith(('youtube.com/', 'www.youtube.com/', 'm.youtube.com/', 'youtu.be/')):
        text = 'https://' + text
    parsed = urlparse(text)
    host = (parsed.hostname or '').lower()
    if host not in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com',
                    'youtu.be', 'www.youtube-nocookie.com'):
        return None
    query = parse_qs(parsed.query)
    parts = parsed.path.strip('/').split('/')
    video = (parts[0] if host == 'youtu.be' else
             parts[1] if len(parts) > 1 and parts[0] in ('embed', 'shorts', 'live') else
             query.get('v', [''])[0])
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('Paste a link to an individual YouTube video.')
    time = query.get('t', query.get('start', ['0']))[0]
    if time.isdigit():
        seconds = int(time)
    elif re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', time):
        match = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', time)
        seconds = sum(int(n or 0) * factor for n, factor in zip(match.groups(), (3600, 60, 1)))
    else:
        seconds = 0
    return f'https://www.youtube.com/watch?v={video}', min(seconds, 604800)


class Search:
    def __init__(self, done):
        self.done = done
        self.process = None
        self.lock = threading.Lock()
        self.generation = 0
        self.closed = False

    def cancel(self):
        with self.lock:
            self.generation += 1
            if self.process and self.process.poll() is None:
                self.process.terminate()
            self.process = None

    def start(self, query):
        self.cancel()
        with self.lock:
            generation = self.generation
        threading.Thread(target=self._run, args=(query, generation),
                         name='youtube-search', daemon=True).start()

    def _run(self, query, generation):
        error = None
        results = []
        process = None
        try:
            with self.lock:
                if self.closed or generation != self.generation:
                    return
                process = subprocess.Popen([
                    yt_dlp_executable(), '--ignore-config', '--flat-playlist',
                    '--dump-single-json', '--no-warnings', '--socket-timeout', '12',
                    '--retries', '1', '--extractor-retries', '1', '--', f'ytsearch8:{query}'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.process = process
            stdout, stderr = process.communicate(timeout=38)
            if process.returncode:
                raise RuntimeError('Search is unavailable. Check your connection and try again.')
            for item in json.loads(stdout).get('entries', []):
                video = item.get('id', '')
                if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
                    continue
                results.append({'id': video, 'url': f'https://www.youtube.com/watch?v={video}',
                                'title': item.get('title') or 'Видео YouTube',
                                'channel': item.get('channel') or item.get('uploader') or '',
                                'duration': item.get('duration') or 0,
                                'live': item.get('live_status') == 'is_live'})
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            error = 'YouTube is taking a while. Try again.'
        except Exception as exc:
            error = str(exc) if isinstance(exc, RuntimeError) else 'Could not search YouTube.'
        finally:
            with self.lock:
                if self.process is process:
                    self.process = None
        GLib.idle_add(self._deliver, generation, results, error)

    def _deliver(self, generation, results, error):
        if not self.closed and generation == self.generation:
            self.done(results, error)
        return False

    def close(self):
        self.closed = True
        self.cancel()
