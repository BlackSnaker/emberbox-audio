"""Run the 1080p jacket checks on a quiet 60 Hz display or under Xvfb."""
import math
from unittest.mock import patch

import numpy as np
import fullscreen_smoke as fixture
import fullscreen
from gi.repository import GdkPixbuf, GLib, Gtk
from record_inspector import INSPECT_ART_SIZE, RecordInspector


def intervals(jacket, action):
    times = []
    clock = jacket.get_frame_clock()
    handler = clock.connect('after-paint', lambda frame: times.append(frame.get_frame_time()))
    loop = GLib.MainLoop()

    def completed():
        if jacket.tick:
            return True
        loop.quit()
        return False

    def timeout():
        loop.quit()
        return False

    action()
    check_id = GLib.timeout_add(2, completed)
    timeout_id = GLib.timeout_add(2000, timeout)
    loop.run()
    clock.disconnect(handler)
    if jacket.tick:
        GLib.source_remove(check_id)
        raise AssertionError('The record animation stalled')
    GLib.source_remove(timeout_id)
    assert len(times) > 24, len(times)
    return np.diff(times)/1000


with patch('urllib.request.urlopen', side_effect=AssertionError('No fixture network')), \
     patch.object(fullscreen, 'LyricsClient', fixture.FixtureLyrics), \
     patch.object(fullscreen.Artwork, 'load', fixture.image_load):
    host = fixture.FixtureHost()
    stage = fullscreen.FullscreenPlayer(host)
    try:
        stage.open()
        fixture.wait_transition(stage)
        stage.window.unfullscreen()
        stage.window.resize(1920, 1080)
        fixture.settle(.4)
        inspector = RecordInspector(lambda: None, lambda: None)
        stage.pages.add_named(inspector, 'record-benchmark')
        inspector.show_all()
        stage.pages.set_visible_child(inspector)
        stage.page = 'library'
        Gtk.Settings.get_default().set_property('gtk-enable-animations', True)
        size = INSPECT_ART_SIZE
        pixels = fixture.cover.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
        inspector.open({'title': 'Reference record', 'artist': 'Ember'}, pixels)
        fixture.settle(.5)
        jacket = inspector.canvas
        assert jacket.faces['front'][1] == size

        def simultaneous(index):
            jacket.turn_to((index+1)*math.pi)
            jacket.toggle_disc(index % 2 == 0)

        for name, animate in (
            ('turn', lambda index: jacket.turn_to((index+1)*math.pi)),
            ('disc', lambda index: jacket.toggle_disc(index % 2 == 0)),
            ('turn + disc', simultaneous),
        ):
            frames = []
            for index in range(6):
                frames.extend(intervals(jacket, lambda: animate(index)))
                fixture.settle(.04)
            fps = 1000/np.mean(frames)
            p95 = np.percentile(frames, 95)
            missed = sum(frame > 21 for frame in frames)
            print(f'{name}: {fps:.2f} FPS, p95 {p95:.2f} ms, {missed}/{len(frames)} late intervals')
            assert fps >= 58.5 and p95 < 18.5 and missed <= 2, (name, fps, p95, missed)
    finally:
        stage.close()
        host.window.destroy()
