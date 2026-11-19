#!/usr/bin/env python3
"""Capture real GTK product fixtures in an isolated Xvfb display.

Uses the original media and offline transports from render_preview.py. Nothing
is read from an account, a browser profile or the desktop's sound output.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--language', choices=('ru', 'en'), default='ru')
parser.add_argument('--clip-seconds', type=float, default=3)
parser.add_argument('--pcm', type=Path, help='Original soundtrack to measure for the live tubes')
parser.add_argument('--pcm-offset', type=float, default=24)
options = parser.parse_args()
# The promotional fixture must never start a user-enabled Quest bridge.
os.environ['EMBERBOX_QUEST']='0'
output = options.output.resolve()
output.mkdir(parents=True, exist_ok=True)

# Reuse only the initialisation section, before its fullscreen/capture driver.
source = (ROOT/'tools/render_preview.py').read_text()
marker = '\nif args.fullscreen and not VIDEO:'
assert marker in source, 'Preview fixture entry point changed'
sys.argv = ['render_preview.py', '--output', str(output), '--language', options.language,
            '--theme', 'nocturne', '--source', 'spotify']
fixture = {'__file__': str(ROOT/'tools/render_preview.py'), '__name__': '__promo_fixture__'}
exec(compile(source.split(marker, 1)[0], str(ROOT/'tools/render_preview.py'), 'exec'), fixture)
assert not fixture['VIDEO'], 'These captures target Emberbox Audio'
app, widget = fixture['app'], fixture['widget']
Gtk, Gdk, GLib, np = (fixture[name] for name in ('Gtk', 'Gdk', 'GLib', 'np'))
cover = fixture['cover']
blank_cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.BLANK_CURSOR)
Gdk.get_default_root_window().set_cursor(blank_cursor)
app.window.get_window().set_cursor(blank_cursor)
import audio_meter
import fullscreen
from lyrics import LyricLine, LyricsState


def settle(seconds=.3):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        for _ in range(12):
            if not GLib.MainContext.default().pending():
                break
            GLib.MainContext.default().iteration(False)
        time.sleep(.003)


def snapshot(window, name, popup=None):
    settle(.25)
    if popup:
        windows = (window, popup)
        x = min(w.get_position()[0] for w in windows)
        y = min(w.get_position()[1] for w in windows)
        right = max(w.get_position()[0]+w.get_size().width for w in windows)
        bottom = max(w.get_position()[1]+w.get_size().height for w in windows)
        pixels = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), x, y, right-x, bottom-y)
    else:
        width, height = window.get_size()
        pixels = Gdk.pixbuf_get_from_window(window.get_window(), 0, 0, width, height)
    path = output/(name+'.png')
    pixels.savev(str(path), 'png', [], [])
    print(json.dumps({'file': str(path), 'width': pixels.get_width(), 'height': pixels.get_height()}), flush=True)


started = time.monotonic()
clip_started = None
soundtrack = None
if options.pcm:
    raw = subprocess.check_output(['ffmpeg','-v','error','-i',str(options.pcm),
        '-f','f32le','-ar',str(audio_meter.RATE),'-ac','2','-'])
    soundtrack = np.frombuffer(raw,dtype='<f4').reshape(-1,2)


def measure():
    elapsed = time.monotonic()-started
    if soundtrack is not None:
        seconds = options.pcm_offset+(time.monotonic()-clip_started if clip_started else elapsed)
        start = int(seconds*audio_meter.RATE)%len(soundtrack)
        indices = (np.arange(audio_meter.FRAMES)+start)%len(soundtrack)
        app.meter._measure(soundtrack[indices].astype('<f4').tobytes())
        return True
    t = np.arange(audio_meter.FRAMES)/audio_meter.RATE+elapsed
    signal = np.zeros_like(t)
    for i, frequency in enumerate((77,141,250,440,760,1350,2400,4200,7800)):
        amplitude = (.025+.025*(1+math.sin(elapsed*(2.1+i*.21)+i))/2)/(1+i*.11)
        signal += amplitude*np.sin(math.tau*frequency*t)
    stereo = np.column_stack((signal, signal)).astype('<f4')
    app.meter._measure(stereo.tobytes())
    return True


class DemoLyrics:
    def __init__(self, changed):
        self.changed, self.state, self.key = changed, LyricsState(), None
    def set_track(self, title, artist, album='', duration=0, **options):
        if self.key == (title, artist):
            return
        self.key = title, artist
        verses = ('Тише город за окном.', 'Тёплый свет касается ладоней.',
                  'Мы оставим шум на потом.', 'Пусть сегодня музыка нас помнит.')
        if options_language == 'en':
            verses = ('The city slows beyond the glass.', 'Let the evening find us here.',
                      'Leave the hurry in the past.', 'Only music, warm and clear.')
        self.state = LyricsState('ready', tuple(LyricLine(t, value) for t, value in zip((0,30,60,90), verses))) if title else LyricsState()
        GLib.idle_add(lambda: (self.changed(), False)[1])
    def close(self):
        pass


options_language = options.language
fullscreen.LyricsClient = DemoLyrics
app.accounts.refresh = lambda: None
app.accounts.spotify_checked = True
app.accounts.spotify = None
app.spotify_mode = 'native'
app.source = 'spotify'
app.spotify_web.set_enabled(True)
app.render_apple()
measure_timer = GLib.timeout_add(33, measure)

tracks = [dict(uri='spotify:track:'+str(i+1), id=str(i+1), title=title,
               artist='Emberbox Sessions', album='Slow Evenings', image='demo',
               duration_ms=(180+i*14)*1000) for i, title in enumerate(
    ('Afterglow', 'Amber Lines', 'Night Drive', 'The Quiet Hours', 'Golden Hour', 'Slow Evenings'))]
albums = [dict(uri='spotify:playlist:demo'+str(i), id='demo'+str(i), kind='playlist',
               title=title, subtitle='Emberbox Sessions', image='demo') for i, title in enumerate(
    ('Slow Evenings', 'Warm Frequencies', 'After Midnight', 'Golden Hour', 'Quiet Hours', 'Night Drive'))]


def catalogue(source, category, term='', collection=None, offset=0):
    return {'tracks': tracks} if collection else {'items': tracks if category == 'search' else albums}


try:
    deadline = time.monotonic()+35
    while not app.equalizer.frames_ready and time.monotonic() < deadline:
        settle(.05)
    assert app.equalizer.frames_ready, 'Lamp atlas did not finish'
    app.startup_pending = False
    app.update_loading()
    settle(1)
    snapshot(app.window, 'desktop')
    shutil.copy2(output/'desktop.png',output/'widget.png')
    app.show_sources(app.source_button)
    snapshot(app.window, 'sources', app.source_picker.popover)
    app.source_picker.popover.dismiss()
    app.show_settings(app.settings_button)
    app.settings.select_section('player')
    snapshot(app.window, 'settings', app.settings.popover)
    app.settings.popover.dismiss()
    app.show_accounts()
    settle(.5)
    snapshot(app.window, 'accounts')
    services = (app.spotify_web,app.apple_web,app.yandex_web)
    for client in services:
        client.connected=False
        client.state['authorized']=False
    app.account_panel.update()
    settle(.5)
    child=app.account_panel
    x,y=child.translate_coordinates(app.window,0,0)
    Gdk.pixbuf_get_from_window(app.window.get_window(),x,y,child.get_allocated_width(),child.get_allocated_height()).savev(
        str(output/'accounts-signin.png'),'png',[],[])
    shutil.copy2(output/'accounts-signin.png',output/'accounts-detail.png')
    for client in services:
        client.connected=True
        client.state['authorized']=True
    app.account_panel.update()
    app.hide_accounts()
    app.expanded = False
    app.drawer.set_reveal_child(False)
    app.apply_layout()
    settle(.8)
    app.toggle_compact(None)
    settle(.9)
    snapshot(app.window, 'mini')
    app.toggle_compact(None)
    settle(.7)
    if not app.fullscreen:
        app.fullscreen = fullscreen.FullscreenPlayer(app)
    stage = app.fullscreen
    # Widget prewarming may have already instantiated the real lyric client.
    stage.lyrics.close()
    stage.lyrics=DemoLyrics(stage.on_lyrics)
    stage.music.repository.load = catalogue
    stage.music.repository.play = lambda *_args: None
    stage.open()
    stage.window.unfullscreen()
    stage.window.resize(1920,1080)
    settle(2)
    stage.window.get_window().set_cursor(blank_cursor)
    snapshot(stage.window, 'fullscreen')
    if options.clip_seconds > 0:
        clip_started=time.monotonic()
        process = subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y',
            '-f','x11grab','-draw_mouse','0','-framerate','30','-video_size','1920x1080','-i',os.environ['DISPLAY'],
            '-t',str(options.clip_seconds),'-an','-c:v','libx264','-preset','veryfast',
            '-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(output/'fullscreen-live.mp4')])
        while process.poll() is None:
            settle(.03)
        assert process.returncode == 0, 'Recording failed'
    stage.show_page('library')
    settle(1.2)
    snapshot(stage.window, 'collection')
    view = stage.library_view
    view.select('search')
    view.entry.set_text('Emberbox Sessions')
    view.search()
    settle(1)
    snapshot(stage.window, 'search')
    stage.show_page('playing')
    settle(.9)
    stage.set_lyrics_visible(True)
    stage.lyrics.set_track('Afterglow','Emberbox Sessions','Slow Evenings',242)
    settle(1.5)
    stage.on_lyrics(force=True)
    settle(.8)
    assert stage.line_labels, 'Original fixture lyrics must be visible'
    assert not stage.lyric_stack.get_transition_running(), 'Lyrics crossfade must settle before capture'
    snapshot(stage.window, 'lyrics')
finally:
    GLib.source_remove(measure_timer)
    app.close_resources()
    app.window.disconnect_by_func(app.on_destroy)
    app.window.destroy()
    fixture['temporary'].cleanup()
