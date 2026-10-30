"""A complete album cover and a quiet pool of its reflected light.

Artwork decoding and the static atmospheric field run outside GTK.  Layout is
changed only by ``resize``; allocation merely requests a matching background.
"""
from collections import OrderedDict
import weakref

import gi
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, GLib, Gtk, Pango

from source_picker import text


CSS = b'''
.album-header {
  background-image: linear-gradient(to bottom right,#383d2d,#19241d);
  border: 1px solid rgba(235,219,178,.085); border-radius: 25px;
  box-shadow: inset 0 1px rgba(251,241,199,.07), 0 12px 30px rgba(4,10,6,.13);
}
.album-header-content { padding: 20px 30px; }
.album-cover-mount {
  padding: 7px; border-radius: 12px;
  background-image: linear-gradient(to bottom right,rgba(240,224,183,.16),rgba(10,17,12,.65));
  border: 1px solid rgba(248,231,195,.19);
  box-shadow: 0 12px 22px rgba(3,9,5,.38),inset 0 1px rgba(255,244,216,.11);
}
.album-header-kicker { color: #cdbb8b; font-size: 10px; letter-spacing: 1.5px; }
.album-header-title { color: #fbf1c7; font-size: 68px; font-weight: bold; letter-spacing: -2px; }
.album-header-title.album-title-long { font-size: 52px; letter-spacing: -1.4px; }
.album-header-title.album-title-very-long { font-size: 44px; letter-spacing: -1px; }
.album-header-artist { color: #dfd5b5; font-size: 23px; }
.album-header-metadata { color: #c6baa0; font-size: 12px; }
.ember-stage button.album-artist-button, button.album-artist-button {
  background: transparent; border: none; box-shadow: none; padding: 0;
  min-height: 0; min-width: 0; border-radius: 4px;
}
.ember-stage button.album-artist-button:hover .album-header-artist,
button.album-artist-button:hover .album-header-artist { color: #f6d58c; }
.ember-stage button.album-play-button, button.album-play-button {
  background-image: linear-gradient(to bottom right,#f6d68b,#d8ac56);
  background-color: #e6bd6a; color: #252b20; border: 1px solid rgba(255,236,175,.25);
  border-radius: 21px; min-height: 20px; padding: 10px 23px;
  font-size: 13px; font-weight: bold;
  box-shadow: 0 4px 13px rgba(5,12,7,.23),inset 0 1px rgba(255,248,207,.42);
}
.ember-stage button.album-play-button:hover, button.album-play-button:hover {
  background-image: linear-gradient(to bottom right,#ffe4a7,#e8bd68);
}
.ember-stage button.album-queue-button, button.album-queue-button {
  background-image: linear-gradient(to bottom right,rgba(210,216,173,.10),rgba(135,151,112,.035));
  background-color: rgba(15,24,17,.30); color: #e0d2ab;
  border: 1px solid rgba(235,219,178,.17); border-radius: 21px;
  min-height: 20px; padding: 10px 19px; font-size: 13px; box-shadow: inset 0 1px rgba(246,237,199,.04);
}
.ember-stage button.album-queue-button:hover, button.album-queue-button:hover {
  background-color: rgba(201,189,136,.09); border-color: rgba(235,219,178,.29);
}
.ember-stage button.album-notes-button, button.album-notes-button {
  background: transparent; color: #c9bc99; border: none; box-shadow: none;
  padding: 9px 6px; min-height: 20px; font-size: 12px;
}
.ember-stage button.album-notes-button:hover, button.album-notes-button:hover { color: #f3d58f; }
.ember-stage button.album-play-button:disabled, button.album-play-button:disabled {
  background-image: none; background-color: #666344; color: #a9a383; box-shadow: none; border-color: transparent;
}
.ember-stage button.album-queue-button:disabled, button.album-queue-button:disabled { color: #767b65; }
.album-header.album-medium .album-header-content { padding: 20px 24px; }
.album-medium .album-header-title { font-size: 43px; letter-spacing: -1.1px; }
.album-medium .album-header-title.album-title-long { font-size: 36px; }
.album-medium .album-header-title.album-title-very-long { font-size: 32px; }
.album-medium .album-header-artist { font-size: 19px; }
.album-medium .album-header-kicker { font-size: 9px; letter-spacing: 1px; }
.album-medium .album-header-metadata { font-size: 11px; }
.ember-stage .album-medium button.album-play-button, .album-medium button.album-play-button,
.ember-stage .album-medium button.album-queue-button, .album-medium button.album-queue-button { padding: 8px 17px; font-size: 12px; min-height: 18px; }
.album-header.album-compact { border-radius: 19px; }
.album-header.album-compact .album-header-content { padding: 8px 18px; }
.album-compact .album-cover-mount { padding: 5px; border-radius: 9px; }
.album-compact .album-header-title { font-size: 28px; letter-spacing: -.7px; }
.album-compact .album-header-title.album-title-long { font-size: 23px; }
.album-compact .album-header-title.album-title-very-long { font-size: 21px; }
.album-compact .album-header-artist { font-size: 14px; }
.album-compact .album-header-kicker { font-size: 9px; letter-spacing: .4px; }
.ember-stage .album-compact button.album-play-button, .album-compact button.album-play-button,
.ember-stage .album-compact button.album-queue-button, .album-compact button.album-queue-button { padding: 6px 13px; font-size: 11px; min-height: 16px; border-radius: 17px; }
.ember-stage .album-compact button.album-notes-button, .album-compact button.album-notes-button { padding: 6px 4px; font-size: 11px; min-height: 16px; }
'''


def album_metrics(width, height):
    """Cover size, masthead height, and spacing for a viewport, not an image."""
    if height < 680 or width < 1000:
        return 108, 140, 18, 2, 'album-compact'
    if height < 900 or width < 1400:
        return 176, 242, 26, 6, 'album-medium'
    return 264, 324, 38, 8, ''


def _number(value):
    try:
        return max(0, int(value or 0))
    except (ValueError, TypeError, OverflowError):
        return 0


def release_type(release):
    if release.get('isCompilation') or release.get('kind') == 'compilation':
        return text('COMPILATION', 'СБОРНИК')
    kind = str(release.get('albumType') or release.get('releaseType') or release.get('kind') or '').lower()
    if kind == 'ep':
        return 'EP'
    if release.get('isSingle') or kind == 'single':
        return text('SINGLE', 'СИНГЛ')
    return text('ALBUM', 'АЛЬБОМ')


def release_metadata(release):
    """Only provider facts; a partially loaded album has no invented runtime."""
    tracks = release.get('tracks') or release.get('items') or []
    if isinstance(tracks, dict):
        tracks = tracks.get('items') or []
    count = _number(release.get('trackCount') or release.get('total_tracks'))
    values = []
    date = str(release.get('releaseDate') or release.get('release_date') or '')[:10]
    if date:
        values.append(date)
    if count:
        values.append(text(f'{count} '+('track' if count == 1 else 'tracks'), f'Треков: {count}'))
    elif tracks:
        # Loaded tracks can be an incomplete page.  Only use a loaded count
        # when the caller explicitly supplies completeness.
        if release.get('tracks_complete') and not release.get('partial'):
            count = len(tracks)
            values.append(text(f'{count} '+('track' if count == 1 else 'tracks'), f'Треков: {count}'))
    milliseconds = _number(release.get('duration_ms'))
    complete = not release.get('partial') and (len(tracks) >= count if count else release.get('tracks_complete'))
    if not milliseconds and tracks and complete:
        durations = [_number(item.get('duration_ms')) for item in tracks if isinstance(item, dict)]
        if len(durations) == len(tracks) and all(durations):
            milliseconds = sum(durations)
    if milliseconds:
        minutes = max(1, milliseconds // 60000)
        hours, minutes = divmod(minutes, 60)
        values.append(text(f'{hours} hr {minutes} min' if hours else f'{minutes} min',
                           f'{hours} ч {minutes} мин' if hours else f'{minutes} мин'))
    return '  ·  '.join(values)


def album_backdrop(pixels, width, height):
    """A static cover-derived light field with a dark, readable right side."""
    raw, size, alpha, stride = pixels
    photo = Image.frombytes('RGBA' if alpha else 'RGB', size, raw, 'raw',
                            'RGBA' if alpha else 'RGB', stride).convert('RGBA')
    base = Image.new('RGBA', photo.size, (27, 33, 25, 255))
    base.alpha_composite(photo)
    # Most work happens at half resolution; the visible cover stays crisp in
    # its separate Gtk.Image and never receives this field's tint or blur.
    scale = min(1., 960 / width)
    small = max(1, round(width * scale)), max(1, round(height * scale))
    field = ImageOps.fit(base.convert('RGB'), small, Image.Resampling.LANCZOS)
    field = ImageEnhance.Color(field).enhance(.78)
    near = field.filter(ImageFilter.GaussianBlur(max(18, height * .14) * scale))
    far = field.filter(ImageFilter.GaussianBlur(max(45, height * .29) * scale))
    rgb = np.asarray(Image.blend(near, far, .46), dtype=np.float32)
    yy, xx = np.mgrid[0:small[1], 0:small[0]].astype(np.float32)
    xx /= max(1, small[0] - 1)
    yy /= max(1, small[1] - 1)
    exposure = (.10 + .31 * np.exp(-((xx + .025) / .19) ** 2)) * (1 - .15 * yy)
    ink = np.array((19, 28, 22), dtype=np.float32)
    rgb = ink + (rgb - ink) * exposure[:, :, None]
    palette = np.asarray(base.convert('RGB').resize((1, 1), Image.Resampling.BOX), dtype=np.float32)[0, 0]
    light = palette / max(1, float(palette.max())) * .64 + np.array((.30, .22, .10))
    glow = np.exp(-.5 * (((xx - .10) / .30) ** 2 + ((yy + .35) / .70) ** 2)) * .085
    rgb += (255 - rgb) * light[None, None, :] * glow[:, :, None]
    bounce = np.exp(-.5 * (((xx - .78) / .65) ** 2 + ((yy - 1.4) / .55) ** 2)) * .035
    rgb += (255 - rgb) * np.array((.52, .54, .34))[None, None, :] * bounce[:, :, None]
    image = Image.fromarray(np.clip(rgb, 0, 255).astype('uint8'), 'RGB').resize((width, height), Image.Resampling.BICUBIC)
    rgb = np.asarray(image, dtype=np.float32)
    grain = np.random.default_rng(41).normal(0, .55, (height, width, 1)).astype(np.float32)
    image = Image.fromarray(np.clip(rgb + grain, 0, 255).astype('uint8'), 'RGB').convert('RGBA')
    # GTK3 does not clip overlay children to the CSS radius.
    from PIL import ImageDraw
    mask = Image.new('L', (width, height))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1),
                                           18 if height < 210 else 24, fill=255)
    image.putalpha(mask)
    return image.tobytes()


def _label(value, style):
    result = Gtk.Label(label=str(value or ''))
    result.set_xalign(0)
    result.get_style_context().add_class(style)
    return result


class AlbumHeader(Gtk.Overlay):
    def __init__(self, release, source_name, artwork, pool, play, queue,
                 artist=None, notes=None, width=1744, height=1080):
        super().__init__()
        self.release = dict(release)
        self.source_name, self.artwork, self.pool = source_name, artwork, pool
        self.closed = False
        self.pixels = None
        self._serial = 0
        self._rendered_key = None
        self._frames = OrderedDict()
        self._pending = {}
        self.cover_size = 0
        self.source_image = Gtk.Image()
        self.get_style_context().add_class('album-header')
        self.base = Gtk.Box()
        self.add(self.base)
        self.background = Gtk.Image()
        self.background.set_halign(Gtk.Align.FILL)
        self.background.set_valign(Gtk.Align.FILL)
        self.add_overlay(self.background)
        self.set_overlay_pass_through(self.background, True)
        self.content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.content.get_style_context().add_class('album-header-content')
        self.add_overlay(self.content)
        self.cover_mount = Gtk.Box()
        self.cover_mount.get_style_context().add_class('album-cover-mount')
        self.cover_mount.set_halign(Gtk.Align.CENTER)
        self.cover_mount.set_valign(Gtk.Align.CENTER)
        self.cover = Gtk.Image()
        self.cover.set_halign(Gtk.Align.CENTER)
        self.cover.set_valign(Gtk.Align.CENTER)
        self.cover_mount.add(self.cover)
        self.content.pack_start(self.cover_mount, False, False, 0)
        self.names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.names.set_valign(Gtk.Align.CENTER)
        self.names.set_hexpand(True)
        self.content.pack_start(self.names, True, True, 0)
        self._kicker = str(source_name).upper() + '  /  ' + release_type(release)
        self.kicker_label = _label(self._kicker, 'album-header-kicker')
        self.kicker_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.names.pack_start(self.kicker_label, False, False, 0)
        name = str(release.get('title') or release.get('name') or text('Album', 'Альбом'))
        self.title_label = _label(name, 'album-header-title')
        self.title_label.set_line_wrap(True)
        self.title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.title_label.set_lines(2)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_max_width_chars(34)
        self.title_label.set_hexpand(True)
        if len(name) > 44:
            self.title_label.get_style_context().add_class('album-title-very-long')
        elif len(name) > 26:
            self.title_label.get_style_context().add_class('album-title-long')
        self.names.pack_start(self.title_label, False, False, 0)
        artist_name = str(release.get('artist') or '')
        self.artist_label = _label(artist_name, 'album-header-artist')
        self.artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist_label.set_max_width_chars(60)
        self.artist_button = None
        if artist and artist_name:
            self.artist_button = Gtk.Button()
            self.artist_button.get_style_context().add_class('album-artist-button')
            self.artist_button.set_halign(Gtk.Align.START)
            self.artist_button.add(self.artist_label)
            self.artist_button.set_has_tooltip(False)
            self.artist_button.get_accessible().set_name(text('Open artist: ', 'Открыть артиста: ') + artist_name)
            self.artist_button.connect('clicked', lambda _button: self._act(artist))
            self.names.pack_start(self.artist_button, False, False, 0)
        elif artist_name:
            self.names.pack_start(self.artist_label, False, False, 0)
        self.metadata = release_metadata(release)
        self.metadata_label = _label(self.metadata, 'album-header-metadata')
        self.metadata_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.metadata_label.set_no_show_all(True)
        self.names.pack_start(self.metadata_label, False, False, 0)
        self.controls = Gtk.Box(spacing=10)
        self.controls.set_halign(Gtk.Align.START)
        self.play_button = self._button('▶  ' + text('Listen', 'Слушать'), 'album-play-button', play,
                                        text('Play album: ', 'Слушать альбом: ') + name)
        self.queue_button = self._button('+  ' + text('Queue', 'В очередь'), 'album-queue-button', queue,
                                         text('Add album to queue: ', 'Добавить альбом в очередь: ') + name)
        self.controls.pack_start(self.play_button, False, False, 0)
        self.controls.pack_start(self.queue_button, False, False, 0)
        self.notes_button = None
        if notes:
            self.notes_button = self._button(text('Liner notes', 'Об альбоме') + '  ⌄', 'album-notes-button', notes,
                                             text('Read the album liner notes', 'Прочесть об альбоме'))
            self.controls.pack_start(self.notes_button, False, False, 0)
        self.names.pack_start(self.controls, False, False, 2)
        self.connect('get-child-position', self._position_child)
        self.connect('size-allocate', lambda *_: self._render_background())
        self.connect('destroy', self.close)
        self.resize(width, height)
        owner = weakref.ref(self)
        def loaded(pixbuf):
            target = owner()
            if target is not None and not target.closed and pixbuf:
                target._set_cover(pixbuf)
        artwork.load(self.source_image, str(release.get('image') or ''), 1000, 0,
                     high_quality=True, keep_aspect=True, on_loaded=loaded)
        # Show the loader's actual placeholder until its async result arrives.
        placeholder = self.source_image.get_pixbuf()
        if self.pixels is None and placeholder:
            self._scale_cover(placeholder)

    def _button(self, caption, style, action, accessible):
        result = Gtk.Button(label=caption)
        result.get_style_context().add_class(style)
        result.set_has_tooltip(False)
        result.get_accessible().set_name(accessible)
        result.connect('clicked', lambda _button: self._act(action))
        return result

    def _act(self, action):
        if not self.closed and action:
            action()

    def _position_child(self, _overlay, widget, area):
        if widget not in (self.background, self.content):
            return False
        area.x = area.y = 0
        area.width = max(1, self.get_allocated_width())
        area.height = max(1, self.get_allocated_height())
        return True

    def resize(self, width, height):
        if self.closed:
            return
        cover, header, gap, spacing, style = album_metrics(width, height)
        context = self.get_style_context()
        for value in ('album-medium', 'album-compact'):
            if value == style:
                context.add_class(value)
            else:
                context.remove_class(value)
        self.header_height = header
        self.base.set_size_request(-1, header)
        self.content.set_spacing(gap)
        self.names.set_spacing(spacing)
        self.controls.set_spacing(7 if style == 'album-compact' else 10)
        self.title_label.set_lines(1 if style == 'album-compact' and len(self.title_label.get_text()) <= 26 else 2)
        self.kicker_label.set_text(self._kicker + ('  ·  ' + self.metadata if style == 'album-compact' and self.metadata else ''))
        self.metadata_label.set_visible(bool(self.metadata) and style != 'album-compact')
        if cover != self.cover_size:
            self.cover_size = cover
            self.cover.set_size_request(cover, cover)
            pixbuf = self.source_image.get_pixbuf()
            if pixbuf:
                self._scale_cover(pixbuf)
        self.queue_resize()

    def _scale_cover(self, pixbuf):
        scale = min(self.cover_size / pixbuf.get_width(), self.cover_size / pixbuf.get_height())
        width = max(1, round(pixbuf.get_width() * scale))
        height = max(1, round(pixbuf.get_height() * scale))
        self.cover.set_from_pixbuf(pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.HYPER))

    def _set_cover(self, pixbuf):
        if self.closed:
            return
        self._scale_cover(pixbuf)
        self.pixels = (bytes(pixbuf.get_pixels()), (pixbuf.get_width(), pixbuf.get_height()),
                       pixbuf.get_has_alpha(), pixbuf.get_rowstride())
        self._serial += 1
        self._rendered_key = None
        self._frames.clear()
        self._render_background()

    def _render_background(self):
        if self.closed or not self.pixels:
            return
        width, height = self.get_allocated_width(), self.get_allocated_height()
        if width < 10 or height < 10:
            return
        key = self._serial, min(3840, width), min(600, height)
        if self._rendered_key == key:
            return
        self._rendered_key = key
        if key in self._frames:
            GLib.idle_add(AlbumHeader._deliver, weakref.ref(self), key, self._frames[key],
                          priority=GLib.PRIORITY_DEFAULT)
            return
        if key in self._pending:
            return
        # Old size work is expendable during a rapid resize.  Running jobs
        # finish harmlessly and their result is checked against this key.
        for pending_key, future in tuple(self._pending.items()):
            if future.cancel():
                self._pending.pop(pending_key, None)
        try:
            future = self.pool.submit(album_backdrop, self.pixels, key[1], key[2])
        except RuntimeError:
            return
        self._pending[key] = future
        owner = weakref.ref(self)
        def done(result):
            try:
                data = result.result()
            except Exception:
                data = None
            GLib.idle_add(AlbumHeader._deliver, owner, key, data, priority=GLib.PRIORITY_DEFAULT)
        future.add_done_callback(done)

    @staticmethod
    def _deliver(owner, key, data):
        target = owner()
        if target is None or target.closed:
            return False
        target._pending.pop(key, None)
        if data is None:
            if target._rendered_key == key:
                target._rendered_key = None
            return False
        if key[0] != target._serial:
            return False
        target._frames[key] = data
        target._frames.move_to_end(key)
        while len(target._frames) > 3:
            target._frames.popitem(last=False)
        target._apply_background(key, data)
        return False

    def _apply_background(self, key, data):
        if not self.closed and key == self._rendered_key:
            self.background.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_bytes(
                GLib.Bytes.new(data), GdkPixbuf.Colorspace.RGB, True, 8,
                key[1], key[2], key[1] * 4))

    def close(self, *_args):
        if self.closed:
            return
        self.closed = True
        for future in self._pending.values():
            future.cancel()
        self._pending.clear()
        self._frames.clear()
        self.pixels = None
        self.source_image.destroy()
