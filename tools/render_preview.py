#!/usr/bin/env python3
"""Render the real GTK interface with original demo media and synthetic PCM.

No Spotify session, browser history or desktop audio is read or changed.
These captures are presentation fixtures, not a connected account demo.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
VIDEO = (ROOT / 'src/youtube.py').exists()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--frames', type=int, default=48)
parser.add_argument('--source', choices=('spotify', 'apple-music'), default='spotify')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
temporary = tempfile.TemporaryDirectory(prefix='emberbox-preview-')
os.environ['XDG_CONFIG_HOME'] = str(Path(temporary.name) / 'config')
os.environ['XDG_CACHE_HOME'] = str(Path(temporary.name) / 'cache')
sys.path.insert(0, str(ROOT / 'src'))

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import numpy as np
import widget
import audio_meter

cover = GdkPixbuf.Pixbuf.new_from_file(str(ROOT / 'assets/demo-cover.png'))


def image_load(self, image, url, size, radius=8, preserve=False, on_loaded=None):
    image.set_size_request(size, size)
    image.set_from_pixbuf(cover.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR))
    if on_loaded:
        on_loaded(cover)


if VIDEO:
    widget.STATE = Path(temporary.name) / 'state.json'
    widget.STATE.write_text(json.dumps({'x': 40, 'y': 30, 'volume': .62, 'compact': False}))
    app = widget.Widget(preview=True)
    app.placeholder.hide()
    scene = GdkPixbuf.Pixbuf.new_from_file(str(ROOT / 'assets/demo-scene.png'))
    screen = Gtk.Image()
    app.overlay.add_overlay(screen)
    app.overlay.set_overlay_pass_through(screen, True)

    def fit_scene(_area, allocation):
        screen.set_from_pixbuf(scene.scale_simple(max(1, allocation.width), max(1, allocation.height), GdkPixbuf.InterpType.BILINEAR))
    app.video.connect('size-allocate', fit_scene)
    fit_scene(app.video, app.video.get_allocation())
    screen.show()
    app.current = {'id': 'demo', 'title': 'The Quiet Hours', 'channel': 'Emberbox Originals'}
    app.title.set_text('The Quiet Hours')
    app.channel.set_text('Emberbox Originals · A moment to slow down')
    app.paused = False
    app.duration, app.position = 322, 82
    app.tint.set_cover(cover)
    app.update_controls()
else:
    class DemoSound:
        def __init__(self, changed):
            self.changed = changed
            self.volume, self.muted, self.available = .62, False, True
        def refresh(self, _player):
            self.changed(self)
        def set_volume(self, value):
            self.volume = value
            self.changed(self)
        def toggle_mute(self):
            self.muted = not self.muted
            self.changed(self)
        def close(self):
            pass

    widget.SpotifyVolume = DemoSound
    widget.SpotifyAudioMeter.start = lambda self: None
    widget.Artwork.load = image_load
    from sources import Session
    class DemoMonitor:
        def __init__(self, connection, changed): self.changed=changed
        def poll(self):
            self.changed([Session('org.mpris.MediaPlayer2.spotify', 'Spotify', 'spotify', properties=values),
                          Session('org.mpris.MediaPlayer2.firefox.instance42', 'Firefox', 'firefox', properties={
                              **values, 'Metadata': {**metadata, 'xesam:url': 'https://music.apple.com/demo'}})])
        def call(self,*args,**kwargs): pass
        def close(self): pass
    widget.Monitor = DemoMonitor
    metadata = {'xesam:title': 'Afterglow', 'xesam:artist': ['Emberbox Sessions'],
                'xesam:album': 'Vol. 01 · Slow Evenings', 'mpris:length': 242_000_000,
                'mpris:trackid': '/demo/afterglow', 'mpris:artUrl': 'demo'}
    values = {'Metadata': metadata, 'PlaybackStatus': 'Playing', 'Position': 82_000_000}
    widget.STATE = Path(temporary.name) / 'state.json'
    widget.STATE.write_text(json.dumps({'x': 40, 'y': 30, 'expanded': False, 'compact': False, 'source': args.source}))
    app = widget.Widget()
    app.panel.open = lambda: None

started = time.monotonic()
counter = 0
phase = 'full'


def capture(path):
    width, height = app.window.get_size()
    Gdk.pixbuf_get_from_window(app.window.get_window(), 0, 0, width, height).savev(str(path), 'png', [], [])


def measure():
    # An original generated signal is measured by the same FFT as live audio.
    elapsed = time.monotonic() - started
    t = np.arange(audio_meter.FRAMES) / audio_meter.RATE + elapsed
    signal = np.zeros_like(t)
    for i, frequency in enumerate((77, 141, 250, 440, 760, 1350, 2400, 4200, 7800)):
        amplitude = (.012 + .014 * (1 + math.sin(elapsed * (2.1+i*.21) + i)) / 2) / (1+i*.11)
        signal += amplitude * np.sin(math.tau * frequency * t)
    stereo = np.column_stack((signal, signal)).astype('<f4')
    app.meter._measure(stereo.tobytes())
    if VIDEO:
        app.position = 82 + elapsed
        app.update_controls()
    return True


def frame():
    global counter, phase
    if phase == 'full':
        capture(args.output / f'frame-{counter:03}.png')
        if counter == 10:
            capture(args.output / 'full.png')
        counter += 1
        if counter >= args.frames:
            phase = 'mini'
            app.toggle_compact() if VIDEO else app.toggle_compact(None)
            GLib.timeout_add(450, mini)
            return False
    return True


def mini():
    capture(args.output / 'mini.png')
    if VIDEO:
        app.quit()
    else:
        app.window.destroy()
    return False


GLib.timeout_add(35, measure)
GLib.timeout_add(1700, lambda: (GLib.timeout_add(60, frame), False)[1])
Gtk.main()
print(args.output)
