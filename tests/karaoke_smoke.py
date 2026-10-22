"""Offline real GTK: karaoke timing, mode lifecycle and small-screen layout."""
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fullscreen_smoke import (FixtureHost,FixtureLyrics,image_load,settle,
                              wait_transition)
from gi.repository import Gdk
from lyrics import LyricLine,LyricWord,LyricsState
from stream_target import Target
import fullscreen
import karaoke


class FixtureAudio:
    def __init__(self,changed):
        self.changed=changed;self.available=True;self.active=self.starting=False
        self.error='';self.amount=.7;self.target=None;self.calls=[]
        self.engine='ai';self.model_ready=True;self.pulse_available=True;self.setup_process=None
    def enable(self,target):
        self.target=target;self.active=True;self.calls.append(('on',target));self.changed()
    def disable(self):
        self.active=False;self.target=None;self.calls.append(('off',));self.changed()
    def set_amount(self,value):self.amount=value;self.calls.append(('amount',value))
    def check_target(self,target):
        if self.active and target!=self.target:self.disable()
    def close(self):self.disable()
    def set_engine(self,engine):
        self.disable();self.engine=engine;self.available=self.model_ready or engine=='stereo';self.changed()
    def prepare(self):self.calls.append(('prepare',))
    def set_muted(self,muted):self.muted=muted


with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network')), \
     patch.object(fullscreen,'LyricsClient',FixtureLyrics), \
     patch.object(fullscreen.Artwork,'load',image_load), \
     patch.object(karaoke,'KaraokeAudio',FixtureAudio):
    host=FixtureHost();host.sound.target=Target('spotify',0,'','fixture')
    stage=fullscreen.FullscreenPlayer(host)
    try:
        stage.open();settle();wait_transition(stage)
        before=list(host.calls)
        stage.page_tabs['karaoke'].clicked();settle(.4)
        assert stage.page=='karaoke' and stage.karaoke.active
        assert host.calls==before,'Entering karaoke must not seek or play'
        client=stage.lyrics
        word_state=LyricsState('ready',(
            LyricLine(4,'Let the warm light stay',(
                LyricWord(4,5,0,4),LyricWord(5,6,4,8),LyricWord(6,7,8,13),LyricWord(7,9,13,18),LyricWord(9,10,18,23))),
            LyricLine(14,'And let the evening drift away'),
            LyricLine(24,'Another quiet day'),
        ))
        client.state=word_state
        host.playing=False;host.position=1_000_000;stage.update()
        view=stage.karaoke
        assert view.countdown.get_text().count('●')==3
        host.position=6_500_000;stage.update();settle(.35)
        assert view.labels[view.scene_index][1].get_text()=='Let the warm light stay'
        assert view.labels[view.scene_index][1].get_attributes() is not None
        assert 'word' in view.timing_note.get_text().lower() or 'слов' in view.timing_note.get_text()
        view.frame(time.monotonic()+10,force=True)
        assert view.labels[view.scene_index][1].get_text()=='Let the warm light stay','Pause must stop karaoke time'
        host.position=12_000_000;stage.update()
        assert view.labels[view.scene_index][1].get_text()=='♪','Real word end must allow instrumental gaps'
        assert view.countdown.get_text().count('●')==2
        host.position=1_000_000;stage.update()
        assert view.countdown.get_text().count('●')==3,'Backward seek must restore introduction'
        view.toggle_audio();assert view.audio.active
        view.set_amount(.35);assert view.audio.amount==.35
        host.sound.target=Target('apple-music',123,'','fixture')
        stage.update();assert not view.audio.active,'Source switch must bypass the filter'
        view.toggle_audio();assert view.audio.active
        stage.page_tabs['queue'].clicked();settle()
        assert not view.active and not view.audio.active,'Leaving karaoke must restore dry audio'
        stage.page_tabs['karaoke'].clicked();settle()
        client.state=word_state
        host.position=6_500_000;stage.update()
        view.audio.model_ready=False;view.audio.available=False;view.audio_changed()
        assert view.prepare_button.get_visible() and not view.voice_toggle.get_sensitive()
        view.prepare_button.clicked();assert view.audio.calls[-1]==('prepare',)
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.3)
            assert stage.window.get_size()==(width,height),(stage.window.get_size(),(width,height))
            for child in (view.import_button,view.voice_knob,view.voice_toggle,view.prepare_button,view.engine_choice,stage.page_tabs['karaoke'],
                          stage.exit_button,stage.progress,stage.play_button,stage.knob,stage.mute):
                assert child.get_mapped(),type(child).__name__
                point=child.translate_coordinates(stage.window,0,0);area=child.get_allocation()
                assert point and point[0]>=0 and point[1]>=0
                assert point[0]+area.width<=width and point[1]+area.height<=height,(type(child).__name__,point,area,width,height)
        view.engine_choice.set_active_id('stereo');assert view.voice_toggle.get_sensitive()
        view.engine_choice.set_active_id('ai');assert not view.voice_toggle.get_sensitive()
        view.audio.model_ready=True;view.audio.available=True;view.audio_changed()
        assert not view.prepare_button.get_visible()
        client.state=LyricsState('ready',word_state.lines,'', '')
        view.update();settle(.3)
        if '--screenshot' in sys.argv:
            pixbuf=Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,1920,1080)
            pixbuf.savev('/tmp/emberbox-karaoke.png','png',[],[])
        stage.hide();assert not view.active and not view.audio.active
    finally:stage.close();host.window.destroy()
print('PASS karaoke exact words, gaps, seek/pause, source switching, filter lifecycle and responsive GTK')
