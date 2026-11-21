"""Shared desktop icon and a short ignition drawn on the GTK frame clock."""
from functools import lru_cache
from pathlib import Path

from gi.repository import GdkPixbuf, Gtk


@lru_cache(maxsize=8)
def logo(size, warm=True):
    source = Path(__file__).resolve().parent
    icon = source.parent / 'assets' / 'icon.svg'
    if not icon.is_file():
        icon = source / 'player-icon.svg'  # Existing desktop-theme installations.
    if warm:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon), size, size, True)
    svg = icon.read_bytes().replace(b'id="ignition" opacity="1"', b'id="ignition" opacity=".11"')
    loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
    loader.set_size(size, size)
    loader.write(svg)
    loader.close()
    return loader.get_pixbuf()


class BrandIgnition(Gtk.Overlay):
    """A pass-through launch overlay, or a mark that stays lit in the tour."""

    DURATION = 1_080_000  # Frame-clock microseconds.

    def __init__(self, persistent=False):
        super().__init__()
        self.persistent = persistent
        self.tick = 0
        self.size = 0
        base = Gtk.Box()
        self.add(base)
        base.show()
        self.plate, self.filament = Gtk.Image(), Gtk.Image()
        for layer in (self.plate, self.filament):
            layer.set_halign(Gtk.Align.CENTER)
            layer.set_valign(Gtk.Align.CENTER)
            self.add_overlay(layer)
            layer.show()
        self.connect('unmap', lambda *_: self.stop())

    def resize_mark(self, size):
        if size == self.size:
            return
        self.size = size
        self.plate.set_from_pixbuf(logo(size, False))
        self.filament.set_from_pixbuf(logo(size))

    def ignite(self, size):
        self.stop()
        if self.persistent:
            self.resize_mark(size)
        if not self.get_settings().get_property('gtk-enable-animations'):
            return
        self.resize_mark(size)
        self.filament.set_opacity(0.)
        self.set_opacity(1. if self.persistent else 0.)
        self.show()
        start = None

        def update(_widget, clock):
            nonlocal start
            now = clock.get_frame_time()
            if start is None:
                start = now
            elapsed = min(1., (now - start) / self.DURATION)
            if elapsed < 1. and self.get_settings().get_property('gtk-enable-animations'):
                heat = min(1., elapsed / .52)
                self.filament.set_opacity(heat * heat * (3. - 2. * heat))
                if not self.persistent:
                    visibility = min(1., elapsed / .15, (1. - elapsed) / .43)
                    self.set_opacity(visibility * visibility * (3. - 2. * visibility))
                return True
            self.tick = 0
            self.stop()
            return False

        self.tick = self.add_tick_callback(update)

    def stop(self):
        if self.tick:
            self.remove_tick_callback(self.tick)
            self.tick = 0
        self.filament.set_opacity(1.)
        self.set_opacity(1.)
        if not self.persistent and self.get_visible():
            self.hide()
