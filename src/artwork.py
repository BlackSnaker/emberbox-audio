"""Small, rounded artwork thumbnails loaded without blocking GTK."""

import hashlib
import io
import time
import threading
import urllib.request
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from paths import CACHE_DIR, CONFIG_DIR

from gi.repository import GdkPixbuf, GLib
from PIL import Image, ImageDraw, ImageOps
from cover_sources import still_candidates


class Artwork:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='spotify-art')
        self.folder = CACHE_DIR / 'thumbnails'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.placeholder = Path(__file__).parent / 'placeholder.png'
        self.placeholders = {}

    def cached_uri(self,widget):
        token = getattr(widget,'_art_token',None)
        if token:
            path = self.folder/(hashlib.sha256(repr(token).encode()).hexdigest()+'.png')
            if path.is_file():
                return path.as_uri()
        return ''

    def load(self, widget, url, size, radius=8, preserve=False, on_loaded=None, high_quality=False, keep_aspect=False):
        existing = widget.get_pixbuf() if preserve else None
        widget.set_size_request(size, size)
        token = (url, size, radius) + (('original-v1',) if high_quality else ())
        if keep_aspect:token+=('aspect-v1',)
        widget._art_token = token
        if not getattr(widget, '_art_destroy_connected', False):
            widget.connect('destroy', lambda target: setattr(target, '_art_token', None))
            widget._art_destroy_connected = True
        path = self.folder / (hashlib.sha256(repr(token).encode()).hexdigest() + '.png')
        if path.exists() and time.time() - path.stat().st_mtime < 86400:
            widget.set_from_file(str(path))
            if on_loaded:
                on_loaded(widget.get_pixbuf())
            return
        if size not in self.placeholders:
            self.placeholders[size] = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(self.placeholder), size, size, True)
        widget.set_from_pixbuf(existing.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
                               if existing else self.placeholders[size])
        self.pool.submit(self._fetch, widget, token, on_loaded)

    def _fetch(self, widget, token, on_loaded):
        if getattr(widget, '_art_token', None) != token:
            return
        url, size, radius = token[:3]
        name = hashlib.sha256(repr(token).encode()).hexdigest() + '.png'
        path = self.folder / name
        try:
            if not path.exists() or time.time() - path.stat().st_mtime > 86400:
                if url.startswith('https://'):
                    source = None
                    candidates = still_candidates(url, max(1200, size*2)) if 'original-v1' in token else [url]
                    for candidate in candidates:
                        if getattr(widget, '_art_token', None) != token:
                            return
                        try:
                            with urllib.request.urlopen(candidate, timeout=7) as response:
                                raw = response.read(15_000_001)
                            if len(raw)>15_000_000:
                                continue
                            item = Image.open(io.BytesIO(raw))
                            if item.width*item.height>20_000_000:
                                continue
                            item.load()
                            # Some CDNs return a tiny placeholder with HTTP 200.
                            # Retain the real larger response rather than stretching it.
                            if source is None or min(item.size)>min(source.size):
                                source = item
                            if min(item.size)>=size:
                                break
                        except (OSError, ValueError, Image.DecompressionBombError):
                            continue
                    if source is None:
                        return
                elif url.startswith('file://') and urlparse(url).netloc in ('', 'localhost'):
                    local = Path(unquote(urlparse(url).path))
                    if local.stat().st_size > 5_000_000:
                        raise ValueError('Artwork too large')
                    source = Image.open(local)
                else:
                    source = Image.open(self.placeholder)
                source = ImageOps.exif_transpose(source).convert('RGBA')
                if 'aspect-v1' in token:
                    # Artist portraits keep their real proportions, without
                    # square padding or a thumbnail crop before composition.
                    image=ImageOps.contain(source,(size,size),Image.Resampling.LANCZOS)
                else:
                    image = (ImageOps.pad if 'original-v1' in token else ImageOps.fit)(source, (size, size), Image.Resampling.LANCZOS)
                    mask = Image.new('L', (size*3, size*3))
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size*3 - 1, size*3 - 1), radius*3, fill=255)
                    mask = mask.resize((size,size),Image.Resampling.LANCZOS)
                    image.putalpha(mask)
                temp = path.with_suffix(f'.{threading.get_ident()}.next.png')
                image.save(temp)
                temp.replace(path)
            GLib.idle_add(self._apply, widget, token, str(path), on_loaded, priority=GLib.PRIORITY_DEFAULT)
        except Exception:
            pass

    @staticmethod
    def _apply(widget, token, path, on_loaded):
        if widget and getattr(widget, '_art_token', None) == token:
            widget.set_from_file(path)
            if on_loaded:
                on_loaded(widget.get_pixbuf())
        return False
