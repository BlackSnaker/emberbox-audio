"""Offline GTK checks for listening mode: geometry, routing and track changes.

Uses original demo media and fixture text. No player, account or desktop audio
is read; all network access is rejected even if a fixture is incomplete.
"""
import os
import math
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixture = tempfile.TemporaryDirectory(prefix='emberbox-fullscreen-')
for variable, folder in (('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'),
                         ('XDG_RUNTIME_DIR', 'runtime')):
    target = Path(fixture.name)/folder
    target.mkdir(mode=0o700)
    os.environ[variable] = str(target)
sys.path.insert(0, str(ROOT/'src'))

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
from lyrics import LyricLine, LyricsState
from lyrics import LyricsClient as RealLyricsClient
import numpy as np
from audio_meter import FRAMES, RATE, SpotifyAudioMeter


def settle(seconds=.2):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def wait_transition(stage,limit=2):
    deadline=time.monotonic()+limit
    while stage.reveal.active and time.monotonic()<deadline:
        settle(.03)
    assert not stage.reveal.active,'Transition must finish without a stuck overlay'
    settle(.05)


def labels(container):
    if isinstance(container, Gtk.Label):
        yield container.get_text()
    if isinstance(container, Gtk.Container):
        for child in container.get_children():
            yield from labels(child)


def key(window, name):
    event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    event.keyval = Gdk.keyval_from_name(name)
    event.state = Gdk.ModifierType(0)
    return window.emit('key-press-event', event)


class FixtureLyrics:
    instances = []

    def __init__(self, changed, **_options):
        self.changed, self.closed, self.key = changed, False, None
        self.calls = []
        self.state = LyricsState()
        self.instances.append(self)

    def set_track(self, title, artist, album='', duration=0, **_options):
        identity = title, artist, album, duration
        if self.closed or identity == self.key:
            return
        self.key = identity
        self.calls.append(identity)
        self.state = LyricsState('ready', (
            LyricLine(0, 'Original fixture: the warm light stays'),
            LyricLine(12, 'Original fixture: the evening drifts away'),
            LyricLine(24, 'Original fixture: another quiet day'),
        ))
        GLib.idle_add(self.notify)

    def notify(self):
        if not self.closed:
            self.changed()
        return False

    def close(self):
        self.closed = True


cover = GdkPixbuf.Pixbuf.new_from_file(str(ROOT/'assets/demo-cover.png'))


def image_load(_loader, image, url, size, radius=8, preserve=False, on_loaded=None, **_options):
    image.set_size_request(size, size)
    image.set_from_pixbuf(cover.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR))
    if on_loaded:
        on_loaded(cover)


class FixtureSound:
    def __init__(self):
        self.available, self.volume, self.muted = True, .6, False
        self.calls = []

    def set_volume(self, value):
        self.volume = value
        self.calls.append(('volume', value))

    def toggle_mute(self):
        self.muted = not self.muted
        self.calls.append(('mute', self.muted))


class FixtureHost:
    def __init__(self):
        self.window = Gtk.Window(title='Fixture desktop widget')
        self.window.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.window.set_keep_below(True)
        self.window.set_default_size(320, 180)
        self.window.move(45, 60)
        self.drawer = Gtk.Revealer()
        self.drawer.set_reveal_child(True)
        self.cover=Gtk.Image.new_from_pixbuf(cover.scale_simple(96,96,GdkPixbuf.InterpType.BILINEAR))
        self.drawer.add(self.cover)
        self.window.add(self.drawer)
        self.window.show_all()
        self.compact, self.expanded = True, True
        self.title = Gtk.Label(label='Afterglow')
        self.artist = Gtk.Label(label='Emberbox Sessions')
        self.album = Gtk.Label(label='Vol. 01 · Slow Evenings')
        self.source, self.playing = 'spotify', True
        self.length, self.position = 180_000_000, 12_000_000
        self.art_url = 'fixture:afterglow'
        self.visual_levels = [.12, .4, .6, .35, .8, .3, .5, .2, .1]
        self.meter = SimpleNamespace(last_sample=time.monotonic(), levels=self.visual_levels)
        self.previous, self.play, self.next = Gtk.Button(), Gtk.Button(), Gtk.Button()
        self.progress_event = Gtk.EventBox()
        self.sound = FixtureSound()
        self.calls = []
        self.sessions = []
        self.browser_binding = self.youtube_binding = ''
        self.youtube_mode = 'native'
        self.apple_mode = 'native'
        self.apple_web=SimpleNamespace(state={})
        self.yandex_web=SimpleNamespace(state={})
        self.youtube=SimpleNamespace(current=None,eof=False)

    def on_action(self, _button, action):
        self.calls.append((self.source, action))

    def seek_to(self, seconds):
        self.calls.append((self.source, 'seek', seconds))

    def select_source(self, source, _session=None):
        self.source = source
        self.calls.append(('source', source))

    def show_accounts(self, *_args):
        self.calls.append(('accounts',))

    def system_volume(self, value):
        if self.sound.muted and value > 0:
            self.sound.toggle_mute()
        self.sound.set_volume(value)


def assert_controls_fit(stage):
    width, height = stage.window.get_size()
    for child in (stage.exit_button, stage.lyrics_button, stage.progress, stage.play_button,
                  stage.volume_meter, stage.knob, stage.mute,
                  stage.previous_button, stage.next_button):
        assert child.get_mapped(), f'{type(child).__name__} is not mapped'
        point = child.translate_coordinates(stage.window, 0, 0)
        assert point is not None
        x, y = point
        area = child.get_allocation()
        assert x >= 0 and y >= 0, (type(child).__name__, x, y)
        assert x+area.width <= width and y+area.height <= height, (
            type(child).__name__, x, y, area.width, area.height, width, height)


def assert_long_titles_fit(stage,host):
    """Wrapped metadata must never displace or clip the complete console."""
    original=[w.get_text() for w in (host.title,host.artist,host.album)]
    playback_calls=list(host.calls)
    titles=('Afterglow',
            'Instant Crush (Drumless Edition) (feat. Julian Casablancas)',
            'Очень длинное название композиции с участием нескольких исполнителей и расширенной версией альбома',
            'Original recording · '+('Unabridged anniversary edition / '*30))
    def rectangle(widget):
        x,y=widget.translate_coordinates(stage.window,0,0);area=widget.get_allocation()
        return x,y,area.width,area.height
    try:
        for lyrics in (False,True):
            stage.set_lyrics_visible(lyrics)
            for width,height in ((1920,1080),(1366,768),(1280,720),(1024,600)):
                stage.window.unfullscreen();stage.window.resize(width,height);settle(.25)
                anchor=None
                for title in titles:
                    host.title.set_text(title);stage.update();settle(.12)
                    assert stage.window.get_size()==(width,height)
                    assert_controls_fit(stage)
                    for widget in (stage.footer,stage.console,stage.title,stage.artist_button,stage.album,stage.quality):
                        x,y,w,h=rectangle(widget)
                        assert y>=0 and y+h<=height,(lyrics,(width,height),title[:40],type(widget).__name__,(x,y,w,h))
                    console=rectangle(stage.console);progress=rectangle(stage.progress)
                    if anchor is None:anchor=(console,progress)
                    assert (console,progress)==anchor,('The console moved when metadata wrapped',lyrics,(width,height),anchor,(console,progress))
                    lx,ly,lw,lh=rectangle(stage.left);fx,fy,fw,fh=rectangle(stage.footer)
                    assert ly+lh<=fy,('Artwork/metadata overlapped the fixed console',lyrics,(width,height),ly+lh,fy)
                    assert stage.title.get_layout().get_line_count()<=2
                    if title!=titles[0]:assert stage.title.get_layout().get_line_count()==2,'The regression fixture must actually wrap'
        assert host.calls==playback_calls,'Layout-only metadata changes must not send playback commands'
    finally:
        for widget,value in zip((host.title,host.artist,host.album),original):widget.set_text(value)
        stage.set_lyrics_visible(False);stage.update();settle(.15)


def assert_lyrics_under_repaint(stage, host):
    """Metadata delivery must beat continuous GTK work at idle priorities.

    Large software-rendered windows can keep GTK's frame work pending. Normal
    idle callbacks then starve; lyric completion must still update the scene.
    The PCM is generated here and never comes from an application or microphone.
    """
    old_lyrics, old_meter = stage.lyrics, host.meter
    meter = SpotifyAudioMeter()
    host.meter = meter
    samples = np.arange(FRAMES)/RATE
    signal = (.1*np.sin(math.tau*440*samples)).astype('<f4')
    pcm = np.column_stack((signal, signal)).astype('<f4').tobytes()
    state = LyricsState('ready', (LyricLine(0, 'Original fixture under active painting'),
                                  LyricLine(20, 'The words arrive while sound is measured')))
    client = RealLyricsClient(stage.on_lyrics, cache_dir=Path(fixture.name)/'lyrics')
    stage.lyrics = client
    busy_calls, measures = [0], [0]

    def repaint():
        busy_calls[0] += 1
        stage.window.queue_draw()
        return True

    def measure():
        meter._measure(pcm)
        measures[0] += 1
        return True

    busy = GLib.idle_add(repaint, priority=GLib.PRIORITY_HIGH_IDLE+50)
    measure_timer = GLib.timeout_add(25, measure)
    try:
        # Establish the continuously pending repaint work before completing the
        # worker. With DEFAULT_IDLE delivery, its callback cannot run at all.
        context = GLib.MainContext.default()
        deadline = time.monotonic()+1
        while busy_calls[0] < 3 and time.monotonic() < deadline:
            context.iteration(False)
        assert busy_calls[0] >= 3, 'Repaint load did not start'
        with patch.object(client, '_lookup', return_value=state):
            client.set_track(host.title.get_text(), host.artist.get_text(),
                             host.album.get_text(), host.length/1e6)
            deadline = time.monotonic()+.35
            while time.monotonic() < deadline:
                context.iteration(False)
                time.sleep(.001)
        assert busy_calls[0] >= 3 and measures[0] > 0, (busy_calls[0], measures[0])
        assert client.state.status == 'ready', 'Lyric completion starved behind repaint work'
        assert len(stage.line_buttons) == 2, 'Completed lyrics were not rendered under load'
        assert stage.line_labels[0].get_text() == state.lines[0].text
        GLib.source_remove(busy);busy=0
        assert stage.volume_meter.level > .3, 'VU must react to measured PCM'
        sound_calls=list(host.sound.calls)
        measured=stage.volume_meter.level
        host.sound.volume=.05
        stage.update();settle(.1)
        assert stage.volume_meter.level > measured*.8, 'VU must not display the knob position'
        assert host.sound.calls == sound_calls, 'Passive VU must not change volume'
        host.sound.muted=True
        settle(.85)
        assert stage.volume_meter.level < .01, 'Muted sound must fade to rest'
        host.sound.muted=False
        settle(.3)
        assert stage.volume_meter.level > .3
        GLib.source_remove(measure_timer);measure_timer=0
        settle(1.2)
        assert stage.volume_meter.level < .01, 'A stalled audio stream must fade to rest'
    finally:
        if busy:GLib.source_remove(busy)
        if measure_timer:GLib.source_remove(measure_timer)
        client.close()
        stage.lyrics, host.meter = old_lyrics, old_meter
        stage.on_lyrics()


def run():
    import fullscreen
    host = FixtureHost()
    settle()
    original = (host.window.get_position(), host.window.get_size(), host.compact,
                host.expanded, host.drawer.get_reveal_child())
    with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network access')), \
         patch.object(fullscreen, 'LyricsClient', FixtureLyrics), \
         patch.object(fullscreen.Artwork, 'load', image_load):
        stage = fullscreen.FullscreenPlayer(host)
        stage.prewarm()
        entrance_frames=[]
        advance=stage.reveal.advance
        def record_entrance(now):
            advance(now)
            entrance_frames.append(stage.reveal.progress)
        stage.reveal.advance=record_entrance
        try:
            assert not stage.visible
            stage.open()
            assert stage.reveal.active
            settle()
            if stage.reveal.active:
                assert stage.reveal.cover_pixels is not None, 'Cover must travel from the widget'
            assert stage.visible and stage.window.get_visible()
            assert stage.window.get_type_hint() != Gdk.WindowTypeHint.DESKTOP
            assert host.calls == [], 'Entering listening mode must not start or seek music'
            assert 'Afterglow' in set(labels(stage.window))
            assert stage.cover.get_pixbuf() is not None
            paints = [0]
            stage.window.get_frame_clock().connect(
                'after-paint', lambda *_args: paints.__setitem__(0, paints[0]+1))
            for width, height in ((1280, 720), (1024, 600), (1366,768), (1920,1080)):
                # Xvfb has no window manager; force actual fixture allocations.
                stage.window.unfullscreen()
                stage.window.resize(width, height)
                settle()
                assert stage.window.get_size() == (width,height), 'Controls must not force a wider window'
                assert_controls_fit(stage)
            assert not stage.reveal.active and not stage.reveal.get_visible()
            assert any(0 < value < 1 for value in entrance_frames), 'Entrance must animate across frames'
            assert stage.layout.get_opacity()==stage.background.get_opacity()==1.
            assert stage.knob.get_allocated_width() >= 88
            assert not hasattr(stage,'volume'), 'Fullscreen volume slider must be removed'
            assert not stage.lyrics_visible and not stage.right.get_visible()
            assert not any(call[0] for call in stage.lyrics.calls), 'Artwork mode must not request lyrics'
            stage.lyrics_button.clicked();wait_transition(stage)
            assert stage.lyrics_visible and stage.right.get_visible()
            assert stage.current_line == 1
            assert stage.line_buttons[1].get_style_context().has_class('stage-line-active')
            stage.line_buttons[2].clicked()
            assert host.calls[-1] == ('spotify', 'seek', 24)
            stage.play_button.clicked()
            stage.next_button.clicked()
            stage.previous_button.clicked()
            assert host.calls[-3:] == [('spotify', 'toggle'), ('spotify', 'next'), ('spotify', 'previous')]
            before_seek = stage.position
            key(stage.window, 'Right')
            assert host.calls[-1] == ('spotify', 'seek', before_seek+10)
            key(stage.window, 'Left')
            assert host.calls[-1] == ('spotify', 'seek', max(0, before_seek-10))
            key(stage.window, 'space')
            assert host.calls[-1] == ('spotify', 'toggle')
            key(stage.window, 'Up')
            assert host.sound.volume > .6
            key(stage.window, 'Down')
            assert abs(host.sound.volume-.6) < .001
            host.progress_event.set_sensitive(False)
            stage.update()
            before = list(host.calls)
            key(stage.window, 'Right')
            assert host.calls == before, 'Unavailable seeking must not send transport commands'
            assert not stage.progress.get_sensitive()
            stage.line_buttons[2].clicked()
            assert host.calls == before, 'Timed lyrics must respect unavailable seeking'
            host.progress_event.set_sensitive(True)
            before_transitions = len(host.calls)
            previous_paints = paints[0]
            for source in ('apple-music', 'youtube', 'yandex-music'):
                host.source = source
                host.title.set_text('')
                host.position, host.playing = 0, False
                stage.update()
                host.title.set_text('Next fixture · '+source)
                host.artist.set_text('Другой исполнитель')
                host.art_url = 'fixture:'+source
                host.position, host.playing = 24_000_000, True
                stage.update()
                settle()
                assert host.title.get_text() in set(labels(stage.window))
                assert paints[0] > previous_paints, 'Track changes must continue painting'
                previous_paints = paints[0]
                stage.next_button.clicked()
                assert host.calls[-1] == (source, 'next')
            assert all(call[1] == 'next' for call in host.calls[before_transitions:]), (
                'Refreshing metadata must not seek, play or change the source')
            client = FixtureLyrics.instances[-1]
            client.state = LyricsState('ready', (), 'Original fixture plain lyrics\nA quiet second line')
            client.notify();settle()
            assert any('Original fixture plain lyrics' in value for value in labels(stage.window))
            before = list(host.calls)
            stage.line_buttons[0].clicked()
            assert host.calls == before, 'Plain lyrics must never invent seek positions'
            for status in ('missing', 'instrumental', 'error'):
                client.state = LyricsState(status)
                client.notify();settle(.05)
                assert stage.play_button.get_sensitive()
                assert stage.window.get_visible()
            assert_lyrics_under_repaint(stage, host)
            stage.lyrics_button.clicked();wait_transition(stage)
            assert not stage.lyrics_visible and not stage.right.get_visible()
            assert_controls_fit(stage)
            assert_long_titles_fit(stage,host)
            key(stage.window, 'Escape')
            wait_transition(stage)
            assert not stage.visible and not stage.window.get_visible()
            hidden_calls = len(client.calls)
            host.title.set_text('Hidden fixture must not request lyrics')
            stage.update();settle()
            assert len(client.calls) == hidden_calls
            assert original == (host.window.get_position(), host.window.get_size(), host.compact,
                                host.expanded, host.drawer.get_reveal_child())
            stage.open();settle()
            key(stage.window, 'F11');settle()
            assert not stage.visible
            assert not stage.reveal.active and stage.tick==0
            stage.open()
            stage.hide()
            assert not stage.reveal.active and stage.reveal.cover_pixels is None
            settings=stage.window.get_settings()
            animations=settings.get_property('gtk-enable-animations')
            try:
                settings.set_property('gtk-enable-animations',False)
                stage.open();settle()
                assert not stage.reveal.active and stage.layout.get_opacity()==1.
            finally:
                settings.set_property('gtk-enable-animations',animations)
            stage.exit_button.clicked();wait_transition(stage)
            assert not stage.visible
        finally:
            stage.close()
            host.window.destroy()
    print('PASS fullscreen routing, keyboard controls, track changes, lyrics fallbacks, small screens and desktop restoration')


if __name__ == '__main__':
    run()
