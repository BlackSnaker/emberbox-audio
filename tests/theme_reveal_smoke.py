"""Theme changes must not turn fullscreen/lyrics transitions into a window blink."""
import os,time
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from seasonal_theme import Appearance
from stage_reveal_paint import RevealPaint
from gi.repository import GLib,Gdk


def settle(seconds=.1):
    deadline=time.monotonic()+seconds;context=GLib.MainContext.default()
    while time.monotonic()<deadline:
        for _ in range(3):
            if context.pending():context.iteration(False)
        time.sleep(.002)


host=f.FixtureHost();host.appearance=Appearance()
gpu=os.environ.get('EMBERBOX_REVEAL_TEST_GL')=='1'
opacity=[];native_opacity=Gdk.Window.set_opacity
painted=[];real_draw=RevealPaint.draw
def set_opacity(window,value):
    opacity.append(value);return native_opacity(window,value)
def draw(painter,*args):
    owner=painter.owner()
    if owner and owner.active and owner.fallback:painted.append(owner.progress)
    return real_draw(painter,*args)

with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',f.image_load),\
     patch.object(Gdk.Window,'set_opacity',set_opacity),patch.object(RevealPaint,'draw',draw):
    stage=fullscreen.FullscreenPlayer(host)
    try:
        with patch('stage_reveal.RevealGL',side_effect=RuntimeError('Fixture compatibility renderer')):
            stage.prewarm()
        if gpu:
            stage.reveal.error='';stage.reveal.warmup(host.cover.get_pixbuf(),allow_software=True)
            assert stage.reveal.driver,'The GPU test must exercise the real shader'
        maps=[];unmaps=[];samples=[]
        stage.window.connect('map',lambda *_:maps.append(True))
        stage.window.connect('unmap',lambda *_:unmaps.append(True))
        def transition():
            deadline=time.monotonic()+5;start=len(samples)
            while stage.reveal.active and time.monotonic()<deadline:
                settle(.025)
                if stage.reveal.active:
                    assert stage.window.get_mapped(),'The native window disappeared during a transition'
                    samples.append(stage.reveal.progress)
            assert not stage.reveal.active,'Transition did not settle'
            assert any(0<t<1 for t in samples[start:]),'Transition skipped its intermediate frames'
            assert not stage.reveal.paint.frames and stage.reveal.paint.art is None and stage.reveal.paint.base is None,'Retained frames leaked'
            settle(.06)

        stage.open();transition()
        for theme in ('nocturne','mirrorball','classic','christmas','mirrorball','nocturne'):
            assert host.appearance.set_theme(theme);settle(.15)
            before=(len(maps),len(unmaps));native=stage.window.get_window()
            for _ in range(2):
                stage.toggle_lyrics()
                assert stage.reveal.active and stage.reveal.room is not None
                assert stage.reveal.fallback is not gpu
                transition()
                assert stage.window.get_window()==native
                assert (len(maps),len(unmaps))==before,'Lyrics remapped the player after a theme change'
                assert stage.layout.get_mapped() and stage.background.get_mapped()
            stage.dismiss();transition()
            assert not stage.visible and not stage.window.get_mapped()
            stage.open();transition()
        assert opacity and all(value==1. for value in opacity),('A transition made the native window transparent',opacity)
        if not gpu:assert sum(0<t<1 for t in painted)>20,'The compatibility animation never painted its intermediate frames'
        assert not host.calls and not host.sound.calls,'Visual transitions changed playback'
        settings=stage.window.get_settings();settings.set_property('gtk-enable-animations',False)
        try:
            stage.toggle_lyrics()
            assert not stage.reveal.active and stage.layout.get_mapped()
        finally:settings.set_property('gtk-enable-animations',True)
        print('PASS repeated theme changes, continuous mapped/opaque window, lyrics, fullscreen, reverse, reduced motion and retained-frame cleanup; '+('GPU' if gpu else 'Cairo'))
    finally:
        stage.close();host.appearance.close();host.window.destroy()
