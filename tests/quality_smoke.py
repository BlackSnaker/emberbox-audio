"""Actual GTK badge/popover with fictional tracks and decoder fixtures."""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from gi.repository import Gdk,Gtk

host=f.FixtureHost();host.source='apple-music'
host.apple_web=SimpleNamespace(state={'audioQuality':{'codec':'aac','sampleRate':44100,'channels':2,'evidence':'decoder'},
    'availableFormats':['dolby-atmos','hi-res-lossless','lossless'],
    'qualityPreference':{'mode':'maximum','applied':True}})
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network access')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host)
    try:
        stage.open();f.wait_transition(stage)
        assert stage.quality.get_mapped() and 'AAC' in stage.quality.get_label()
        assert not stage.quality.get_has_tooltip()
        stage.quality.clicked();f.settle(.3)
        assert stage.quality.popover.get_visible()
        assert 'Atmos' not in stage.quality.get_label()
        target=os.environ.get('EMBERBOX_QUALITY_PREVIEW')
        if target:
            width,height=stage.window.get_size()
            Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(Path(target)),'png',[],[])
        # An open detail panel follows an actual stream change and source switch.
        host.apple_web.state['audioQuality']={'codec':'alac','sampleRate':96000,'evidence':'decoder'}
        stage.update();assert 'Hi‑Res Lossless' in stage.quality.get_label()
        host.source='spotify';stage.update()
        assert not stage.quality.model['known'] and not stage.quality.model['available']
        stage.quality.popover.popdown()
        stage.window.unfullscreen();stage.window.resize(1024,600);f.settle(.3)
        f.assert_controls_fit(stage)
        print('PASS actual quality badge, click-only details, catalogue separation, source changes and compact fullscreen layout')
    finally:stage.close();host.window.destroy()
