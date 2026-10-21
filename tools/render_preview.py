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
parser.add_argument('--library', action='store_true')
parser.add_argument('--settings', action='store_true')
parser.add_argument('--accounts', action='store_true')
parser.add_argument('--fullscreen', action='store_true')
parser.add_argument('--language', choices=('en','ru'), default='en')
parser.add_argument('--source', choices=('spotify', 'apple-music', 'youtube','yandex-music'), default='spotify')
args = parser.parse_args()
os.environ['EMBERBOX_LANGUAGE']=args.language
args.output.mkdir(parents=True, exist_ok=True)
temporary = tempfile.TemporaryDirectory(prefix='emberbox-preview-')
os.environ['XDG_CONFIG_HOME'] = str(Path(temporary.name) / 'config')
os.environ['XDG_CACHE_HOME'] = str(Path(temporary.name) / 'cache')
os.environ['XDG_RUNTIME_DIR'] = str(Path(temporary.name) / 'runtime')
Path(os.environ['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
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


def image_load(self, image, url, size, radius=8, preserve=False, on_loaded=None, **_options):
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
    class DemoAppleWeb:
        native = True
        connected, enabled, pid, error = True, True, 0, ''
        def __init__(self, changed):
            self.state = {'ready':True,'authorized':True,'title':'Afterglow','artist':'Emberbox Sessions',
                          'album':'Vol. 01 · Slow Evenings','duration':242,'position':82,'image':'demo',
                          'playing':True,'subscribed':True,'wave':True,'canNext':True,'canPrevious':True}
        def set_enabled(self, enabled): self.enabled=enabled
        def ensure_started(self): pass
        def poll(self): pass
        def action(self,*args,**kwargs): pass
        def request(self,*args,**kwargs): return {'items':[],'tracks':[],'next':None}
        def close(self): pass
    widget.AppleWeb = DemoAppleWeb
    widget.YandexWeb = DemoAppleWeb
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
    if args.accounts:
        app.accounts.refresh = lambda:None
        app.accounts.spotify_checked = True
        app.accounts.spotify = ['fixture-spotify']
        app.show_accounts()
    if args.source == 'youtube':
        item={'id':'jNQXAC9IVRw','url':'https://www.youtube.com/watch?v=jNQXAC9IVRw',
              'title':'Afterglow · Evening Session','channel':'Emberbox Sessions','duration':242}
        queue=[dict(item,id=ident,title=title) for ident,title in (
            ('jNQXAC9IVRw','Afterglow · Evening Session'),('mNLJMTRvyj8','Warm Frequencies · Live'),
            ('p5qSg2wjCZA','The Quiet Hours · Jazz'),('hMbf-VPD3ck','Golden Hour · Acoustic'))]
        app.youtube.current=item
        app.youtube.queue=queue
        app.youtube.index=0
        app.youtube.loaded=True
        app.youtube.paused=False
        app.youtube.duration=242
        app.youtube.position=82
        app.youtube_panel.entry.set_text('Emberbox evening sessions')
        app.youtube_panel.on_results(queue,None)
        app.expanded=True
        app.apply_layout()
        app.render_youtube()
    if args.source=='yandex-music':
        app.expanded=True
        app.apply_layout()
        app.render_apple()
        app.yandex_panel.open()
    if args.library:
        from types import SimpleNamespace
        items=[{'id':'p.demo'+str(n),'kind':'library-playlists','title':title,'subtitle':'Emberbox Sessions',
                'uri':'apple:library-playlists:p.demo'+str(n),'image':'demo'}
               for n,title in enumerate(('Slow Evenings','Warm Frequencies','After Midnight','Golden Hour'))]
        app.apple_panel.bridge=SimpleNamespace(connected=True,native=True,state={'authorized':True},request=lambda *a,**k:{'items':items,'next':None})
        app.expanded=True
        app.apply_layout()
        app.apple_panel.open()

if args.fullscreen and not VIDEO:
    import fullscreen
    from lyrics import LyricsState,LyricLine
    class DemoLyrics:
        def __init__(self,changed):self.changed=changed;self.state=LyricsState();self.key=None
        def set_track(self,title,artist,album='',duration=0,**options):
            if self.key==(title,artist):return
            self.key=title,artist
            # Original demonstration verse, never lyrics from an existing song.
            verses=(
                ('The city slows beyond the glass.','Тише город за окном.'),
                ('Let the evening find us here.','Тёплый свет касается ладоней.'),
                ('Leave the hurry in the past.','Мы оставим шум на потом.'),
                ('Only music, warm and clear.','Пусть сегодня музыка нас помнит.'),
                ('Golden threads across the night.','В этом свете время не спешит.'),
                ('Every note a place to stay.','Ночь рисует золотые нити.'),
                ('We are carried by the light.','Всё, что нужно, рядом и звучит.'),
                ('Let the last sound drift away.','Оставайся. Просто послушай.'))
            self.state=LyricsState('ready',tuple(LyricLine(t,verse[1 if args.language=='ru' else 0])
                for t,verse in zip((0,30,60,90,120,150,180,210),verses))) if title else LyricsState()
            GLib.idle_add(lambda:(self.changed(),False)[1],priority=GLib.PRIORITY_DEFAULT)
        def close(self):pass
    fullscreen.LyricsClient=DemoLyrics
    app.fullscreen=fullscreen.FullscreenPlayer(app)
    app.fullscreen.open()
    app.fullscreen.window.unfullscreen()
    app.fullscreen.window.resize(1920,1080)

started = time.monotonic()
counter = 0
phase = 'full'


def capture(path):
    window=app.fullscreen.window if args.fullscreen and not VIDEO else app.window
    width, height = window.get_size()
    Gdk.pixbuf_get_from_window(window.get_window(), 0, 0, width, height).savev(str(path), 'png', [], [])


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
            if args.fullscreen and not VIDEO:
                app.window.destroy();return False
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


def show_settings():
    app.show_settings(app.settings_button)
    GLib.timeout_add(350, capture_settings)
    return False


def capture_settings():
    x, y = app.window.get_position()
    width, height = app.window.get_size()
    Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), x, y, width, height).savev(
        str(args.output / 'settings.png'), 'png', [], [])
    app.settings.popover.popdown()
    GLib.timeout_add(300, lambda: (GLib.timeout_add(60, frame), False)[1])
    return False


GLib.timeout_add(35, measure)
if args.settings and not VIDEO:
    GLib.timeout_add(1700, show_settings)
else:
    GLib.timeout_add(1700, lambda: (GLib.timeout_add(60, frame), False)[1])
Gtk.main()
print(args.output)
