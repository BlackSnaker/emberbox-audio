"""Album facts, static light, whole-cover geometry and async disposal."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from album_header import AlbumHeader, CSS, album_backdrop, album_metrics, release_metadata, release_type


def pixels(image):
    return image.tobytes(), image.size, image.mode == 'RGBA', image.width * len(image.getbands())


def luminance(rgb):
    value = np.asarray(rgb, dtype=np.float32) / 255
    return np.where(value <= .04045, value / 12.92, ((value + .055) / 1.055) ** 2.4) @ np.array((.2126, .7152, .0722))


class AlbumFacts(unittest.TestCase):
    def test_runtime_requires_complete_known_durations(self):
        tracks = [{'duration_ms': 180000}, {'duration_ms': 240000}]
        partial = dict(trackCount=12, tracks=tracks)
        self.assertNotIn('min', release_metadata(partial))
        self.assertNotIn('мин', release_metadata(partial))
        self.assertNotIn('min', release_metadata(dict(partial, tracks_complete=True)))
        self.assertNotIn('мин', release_metadata(dict(partial, tracks_complete=True)))
        complete = dict(trackCount=2, tracks=tracks)
        self.assertIn('7', release_metadata(complete))
        self.assertNotIn('min', release_metadata(dict(complete, partial=True)))
        self.assertNotIn('мин', release_metadata(dict(complete, partial=True)))
        self.assertNotIn('7', release_metadata(dict(complete, tracks=[tracks[0], {}])))
        self.assertIn('45', release_metadata(dict(partial, duration_ms=2700000)))

    def test_unknown_paginated_count_does_not_become_album_total(self):
        tracks = [{'duration_ms': 180000} for _ in range(3)]
        self.assertEqual(release_metadata(dict(tracks=tracks)), '')
        complete = release_metadata(dict(tracks=tracks, tracks_complete=True))
        self.assertIn('3', complete)
        self.assertIn('9', complete)
        self.assertIn('2026-10-23', release_metadata(dict(releaseDate='2026-10-23T12:00:00Z')))
        self.assertEqual(release_metadata(dict(trackCount='unavailable', duration_ms='bad')), '')

    def test_provider_release_types_survive(self):
        self.assertEqual(release_type(dict(kind='ep')), 'EP')
        self.assertNotEqual(release_type(dict(isSingle=True)), release_type(dict(kind='album')))
        self.assertNotEqual(release_type(dict(isCompilation=True)), release_type(dict(kind='album')))

    def test_cover_and_mount_fit_inside_every_requested_header(self):
        for width, height in ((1744, 1080), (1104, 720), (928, 600)):
            cover, header, *_ = album_metrics(width, height)
            inset = 16 if height < 680 else 40
            mount = 12 if height < 680 else 16
            self.assertLessEqual(cover + mount + inset, header)
        self.assertGreaterEqual(album_metrics(1744, 1080)[0], 260)
        self.assertEqual(album_metrics(928, 600)[:2], (108, 140))


class AlbumAtmosphere(unittest.TestCase):
    def test_white_artwork_cannot_wash_out_the_title(self):
        source = pixels(Image.new('RGB', (320, 320), 'white'))
        for width, height, reading_x in ((1744, 324, 348), (1104, 242, 242), (928, 176, 176)):
            with self.subTest(width=width):
                data = np.asarray(Image.frombytes('RGBA', (width, height), album_backdrop(source, width, height)))
                contrast = (luminance((251, 241, 199)) + .05) / (luminance(data[20:-20, reading_x:-24, :3]) + .05)
                self.assertGreaterEqual(float(contrast.min()), 4.5)
                self.assertEqual(int(data[0, 0, 3]), 0)
                self.assertEqual(int(data[height // 2, width // 2, 3]), 255)

    def test_light_retains_cover_colour_and_never_shimmers(self):
        fields = []
        for colour in ('red', 'blue'):
            source = pixels(Image.new('RGB', (320, 320), colour))
            first = album_backdrop(source, 928, 176)
            self.assertEqual(first, album_backdrop(source, 928, 176))
            fields.append(np.asarray(Image.frombytes('RGBA', (928, 176), first))[24:-24, 24:176, :3].mean(axis=(0, 1)))
        self.assertGreater(fields[0][0] - fields[0][2], 25)
        self.assertGreater(fields[1][2] - fields[1][0], 25)


def settle(seconds=.05):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.002)


class FixtureArtwork:
    def __init__(self, source):
        alpha = source.mode == 'RGBA'
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(source.tobytes()),
            GdkPixbuf.Colorspace.RGB, alpha, 8, source.width, source.height, source.width * (4 if alpha else 3))
        self.options = None
        self.callback = None

    def load(self, widget, _uri, _size, _radius, **options):
        self.options = options
        self.callback = options['on_loaded']
        widget.set_from_pixbuf(self.pixbuf)
        self.callback(self.pixbuf)


@unittest.skipUnless(Gtk.init_check()[0], 'GTK requires a display; run this file under Xvfb')
class AlbumHeaderLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = Gtk.CssProvider()
        cls.provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), cls.provider,
                                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def test_whole_cover_and_long_titles_fit_all_viewports(self):
        source = Image.new('RGB', (320, 480), (80, 110, 120))
        draw = ImageDraw.Draw(source)
        for rectangle, colour in (((0, 0, 40, 60), 'red'), ((279, 0, 319, 60), 'green'),
                                   ((0, 419, 40, 479), 'blue'), ((279, 419, 319, 479), 'yellow')):
            draw.rectangle(rectangle, fill=colour)
        with ThreadPoolExecutor(max_workers=2) as pool:
            for width, height in ((1744, 1080), (1104, 720), (928, 600)):
                with self.subTest(viewport=(width, height)):
                    art = FixtureArtwork(source)
                    hero = AlbumHeader(dict(title='Letters from the Observatory / Письма из старой обсерватории (Anniversary Edition)',
                        artist='The Paper Satellites', image='fixture:cover', releaseDate='2026-10-23', trackCount=12),
                        'Apple Music', art, pool, lambda: None, lambda: None,
                        artist=lambda: None, notes=lambda: None, width=width, height=height)
                    window = Gtk.Window()
                    window.set_default_size(width, hero.header_height)
                    window.add(hero)
                    window.show_all()
                    settle(.12)
                    self.assertTrue(art.options['high_quality'])
                    self.assertTrue(art.options['keep_aspect'])
                    image = hero.cover.get_pixbuf()
                    self.assertAlmostEqual(image.get_width() / image.get_height(), 2 / 3, delta=.015)
                    allocation = hero.cover.get_allocation()
                    self.assertGreaterEqual(allocation.width, image.get_width())
                    self.assertGreaterEqual(allocation.height, image.get_height())
                    for child in (hero.cover, hero.title_label, hero.artist_button, hero.controls):
                        x, y = child.translate_coordinates(hero, 0, 0)
                        allocation = child.get_allocation()
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertLessEqual(x + allocation.width, hero.get_allocated_width() + 1)
                        self.assertLessEqual(y + allocation.height, hero.get_allocated_height() + 1)
                    clear = np.asarray(Image.frombytes('RGB', (image.get_width(), image.get_height()),
                        bytes(image.get_pixels()), 'raw', 'RGB', image.get_rowstride()))
                    for colour in ((255, 0, 0), (0, 128, 0), (0, 0, 255), (255, 255, 0)):
                        self.assertTrue(np.any(np.all(clear == colour, axis=2)), 'A clear cover edge was cropped or tinted')
                    window.destroy()
                    settle()

    def test_destroy_during_background_work_rejects_late_artwork(self):
        entered = threading.Event()
        release = threading.Event()
        original = album_backdrop
        def delayed(*args):
            entered.set()
            release.wait(2)
            return original(*args)
        with ThreadPoolExecutor(max_workers=1) as pool, patch('album_header.album_backdrop', delayed):
            art = FixtureArtwork(Image.new('RGBA', (320, 320), (0, 0, 0, 0)))
            hero = AlbumHeader(dict(title='Quiet Light', image='fixture:transparent'), 'Spotify', art, pool,
                lambda: None, lambda: None, width=928, height=600)
            self.assertIsNone(hero.notes_button)
            self.assertIsNone(hero.artist_button)
            window = Gtk.Window()
            window.set_default_size(928, 140)
            window.add(hero)
            window.show_all()
            settle()
            self.assertTrue(entered.wait(1))
            window.destroy()
            art.callback(art.pixbuf)
            release.set()
            pool.shutdown(wait=True)
            settle()
            self.assertTrue(hero.closed)
            self.assertIsNone(hero.pixels)
            self.assertFalse(hero._frames)
            self.assertFalse(hero._pending)


if __name__ == '__main__':
    unittest.main()
