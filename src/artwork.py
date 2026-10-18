"""Small, rounded artwork thumbnails loaded without blocking GTK."""

import hashlib
import io
import time
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from paths import CACHE_DIR, CONFIG_DIR

from gi.repository import GdkPixbuf, GLib
from PIL import Image, ImageDraw, ImageOps


class Artwork:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='spotify-art')
        self.folder = CACHE_DIR / 'thumbnails'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.placeholder = Path(__file__).parent / 'placeholder.png'
        self.placeholders = {}

    def load(self, widget, url, size, radius=8, preserve=False, on_loaded=None):
        existing = widget.get_pixbuf() if preserve else None
        widget.set_size_request(size, size)
        token = (url, size, radius)
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
        url, size, radius = token
        name = hashlib.sha256(repr(token).encode()).hexdigest() + '.png'
        path = self.folder / name
        try:
            if not path.exists() or time.time() - path.stat().st_mtime > 86400:
                if url.startswith('https://'):
                    with urllib.request.urlopen(url, timeout=7) as response:
                        raw = response.read(5_000_000)
                    source = Image.open(io.BytesIO(raw))
                else:
                    source = Image.open(self.placeholder)
                image = ImageOps.fit(source.convert('RGBA'), (size, size), Image.Resampling.LANCZOS)
                mask = Image.new('L', (size, size))
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=255)
                image.putalpha(mask)
                temp = path.with_suffix(f'.{threading.get_ident()}.next.png')
                image.save(temp)
                temp.replace(path)
            GLib.idle_add(self._apply, widget, token, str(path), on_loaded)
        except Exception:
            pass

    @staticmethod
    def _apply(widget, token, path, on_loaded):
        if widget and getattr(widget, '_art_token', None) == token:
            widget.set_from_file(path)
            if on_loaded:
                on_loaded(widget.get_pixbuf())
        return False
