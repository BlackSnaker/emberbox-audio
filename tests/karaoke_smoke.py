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
        self.phase='';self.delay=0.
    def enable(self,target):
        self.target=target;self.active=True;self.starting=False;self.error='';self.calls.append(('on',target));self.changed()
    def disable(self):
        self.active=self.starting=False;self.phase='';self.error='';self.target=None;self.calls.append(('off',));self.changed()
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
            card=view.control_card.get_allocation()
            card_at=view.control_card.translate_coordinates(stage.window,0,0)
            assert 740<=card.width<=800,(width,card.width)
            assert abs(card_at[0]+card.width/2-width/2)<=1,(width,card_at,card.width)
            for child in (view.voice_toggle,view.engine_choice,view.voice_knob,view.prepare_button):
                at=child.translate_coordinates(view.control_card,0,0);area=child.get_allocation()
                assert at and at[0]>=0 and at[1]>=0
                assert at[0]+area.width<=card.width and at[1]+area.height<=card.height
                assert not child.get_has_tooltip()
            engine_at=view.engine_choice.translate_coordinates(view.control_card,0,0)
            knob_at=view.voice_knob.translate_coordinates(view.control_card,0,0)
            assert knob_at[0]-(engine_at[0]+view.engine_choice.get_allocated_width())>=12
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
        settle(.1);card_height=view.control_card.get_allocated_height()
        before=list(host.calls)
        view.audio.target=host.sound.target
        view.audio.active=False;view.audio.starting=True;view.audio.phase='model';view.audio_changed();settle(.1)
        assert view.control_card.get_allocated_height()==card_height,'Buffering should not move the controls'
        assert view.scenes.get_visible_child_name()=='startup' and view.startup.waiting
        assert not view.startup.progress.get_show_text(),'Waiting has no made-up percentage'
        levels=tuple(dot.get_opacity() for dot in view.startup.dots)
        settle(.25)
        assert levels!=tuple(dot.get_opacity() for dot in view.startup.dots),'Warm embers should move while work is pending'
        view.audio.phase='buffering';view.audio_changed();settle(.1)
        assert view.startup.state=='buffering' and view.scenes.get_visible_child_name()=='startup'
        settings=stage.window.get_settings();old_motion=settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations',False)
        levels=tuple(dot.get_opacity() for dot in view.startup.dots)
        view.startup.advance(time.monotonic()+1)
        assert levels==tuple(dot.get_opacity() for dot in view.startup.dots),'Reduced motion keeps a readable static status'
        settings.set_property('gtk-enable-animations',old_motion)
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.unfullscreen();stage.window.resize(width,height);settle(.25)
            for child in (view.startup,view.startup.progress,view.control_card,stage.mute):
                point=child.translate_coordinates(stage.window,0,0);area=child.get_allocation()
                assert point and point[0]>=0 and point[1]>=0
                assert point[0]+area.width<=width and point[1]+area.height<=height,(type(child).__name__,point,area,width,height)
        view.audio.starting=False;view.audio.active=True;view.audio.phase='';view.audio_changed();settle(.1)
        assert view.control_card.get_allocated_height()==card_height,'AI status should not move the controls'
        assert view.startup.state=='ready' and view.scenes.get_visible_child_name()!='startup','Only real readiness returns to lyrics'
        assert view.startup.progress.get_fraction()==1.
        assert host.calls==before,'Startup decoration never controls playback'
        view.audio.active=False;view.audio.starting=True;view.audio.phase='buffering';view.audio_changed()
        view.toggle_audio();settle(.1)
        assert not view.startup.waiting and view.startup.state=='idle' and view.scenes.get_visible_child_name()!='startup'
        view.audio.starting=True;view.audio_changed()
        view.audio.error='output-lost';view.audio_changed();settle(.1)
        assert view.control_card.get_allocated_height()==card_height,'A normal error should not move the controls'
        assert view.startup.state=='idle' and view.scenes.get_visible_child_name()!='startup'
        view.audio.error='';view.audio.starting=False
        view.toggle_audio()
        client.state=LyricsState('ready',word_state.lines,'', '')
        view.update();settle(.3)
        if '--screenshot' in sys.argv:
            view.set_amount(.7);view.audio.delay=1.8;view.toggle_audio();settle(2.5)
            pixbuf=Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,1920,1080)
            pixbuf.savev('/tmp/emberbox-karaoke.png','png',[],[])
        if '--startup-screenshot' in sys.argv:
            view.audio.active=False;view.audio.starting=True;view.audio.phase='buffering';view.audio_changed();settle(.75)
            pixbuf=Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,1920,1080)
            pixbuf.savev('/tmp/emberbox-karaoke-startup.png','png',[],[])
        view.audio.active=False;view.audio.starting=True;view.audio.phase='buffering';view.audio_changed()
        stage.hide();assert not view.active and not view.audio.active
        assert not view.startup.waiting and view.startup.last_pulse is None,'Hidden pages never keep startup animation running'
        assert view.scenes.get_visible_child_name()!='startup','Reopening must not flash an old startup scene'
    finally:stage.close();host.window.destroy()
print('PASS karaoke exact words, gaps, seek/pause, source switching, filter lifecycle and responsive GTK')
