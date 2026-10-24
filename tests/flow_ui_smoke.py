"""Offline checks for EmberFlow's switch, mirrored controls and small screens."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import time
import fullscreen_smoke as f
import fullscreen
from flow_control import FlowControl
from gi.repository import Gdk,Gtk

host=f.FixtureHost();host.source='youtube'
host.youtube=SimpleNamespace(current=None,queue=[],eof=False,quality={},error='')
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network')), \
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.music=stage.music
    try:
        stage.open();f.wait_transition(stage)
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.unfullscreen();stage.window.resize(width,height);f.settle(.3)
            f.assert_controls_fit(stage)
            control=stage.flow_control;x,y=control.translate_coordinates(stage.window,0,0);a=control.get_allocation()
            assert x>=0 and y>=0 and x+a.width<=width and y+a.height<=height
        second=FlowControl(stage.music.flow)
        beats=FlowControl(stage.music.flow,beats=True)
        assert beats.get_active()
        beats.clicked();f.settle(.3);assert not stage.music.flow.beat_sync and second.get_active()==stage.music.flow.enabled
        beats.clicked();f.settle(.3);assert stage.music.flow.beat_sync
        beats.destroy()
        stage.flow_control.clicked();f.settle(.95)
        assert stage.music.flow.enabled and second.get_active() and stage.flow_control.shown==1 and not stage.flow_control.tick
        host.meter.last_sample=time.monotonic();host.meter.rms_level=.68;f.settle(.16)
        path=Path('/tmp/emberflow-ui.png');a=stage.console.get_allocation();x,y=stage.console.translate_coordinates(stage.window,0,0)
        Gdk.pixbuf_get_from_window(stage.window.get_window(),x,y,a.width,a.height).savev(str(path),'png',[],[])
        second.destroy();stage.flow_control.clicked();f.settle(1.5);assert not stage.music.flow.enabled
        print('PASS EmberFlow geometry, mirrored settings and finite switch animation; screenshot:',path)
    finally:stage.close();host.window.destroy()
