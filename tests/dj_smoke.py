"""Offline DJ room: real keyboard events, asynchronous selection and cancellation."""
import os,threading,time
from pathlib import Path
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from dj_intent import local_intent
from gi.repository import Gdk,Gtk
from widget_settings import SettingsMenu

tracks=[{'uri':'spotify:track:'+str(i),'id':str(i),'title':name,'artist':'Ember Sessions '+str(i),
         'image':'fixture:cover','duration_ms':180000,'_personal':True,'genres':['ambient']}
        for i,name in enumerate(('Amber Air','Evening Orbit','Quiet Voltage','Warm Horizons','Still Here','After the Rain','A New Room','Soft Signal'))]
entered,release=threading.Event(),threading.Event();plays=[];slow=[False]
def collect(source,intent,affinity,alive=lambda:True,progress=lambda *_:None):
    entered.set();progress('personal')
    if slow[0]:release.wait(2)
    return tracks,[],[]
def wait(predicate,seconds=4):
    until=time.monotonic()+seconds
    while not predicate() and time.monotonic()<until:f.settle(.03)
    assert predicate(),'DJ did not finish';f.settle(.08)
def fits(stage,widgets):
    width,height=stage.window.get_allocated_width(),stage.window.get_allocated_height()
    for widget in widgets:
        assert widget.get_mapped(),type(widget).__name__
        x,y=widget.translate_coordinates(stage.window,0,0);a=widget.get_allocation()
        assert x>=0 and y>=0 and x+a.width<=width+2 and y+a.height<=height+2,(type(widget).__name__,(x,y,a.width,a.height),(width,height))
def shot(stage,name):
    target=os.environ.get('EMBERBOX_DJ_PREVIEW')
    if target:
        f.settle(.2);p=Path(target);p.mkdir(parents=True,exist_ok=True)
        width,height=stage.window.get_allocated_width(),stage.window.get_allocated_height();Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(p/(name+'.png')),'png',[],[])

host=f.FixtureHost()
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network')),patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host)
    s=stage.dj;v=stage.dj_view;host.fullscreen=stage
    s.memory.settings['voice']=False;s.probed=True;s.catalog.collect=collect
    s.brain.interpret=lambda prompt,previous,*_args:(local_intent(prompt,previous),'local')
    stage.music.repository.play=lambda item,alive:plays.append(item['uri']) if alive() else None
    try:
        stage.open();f.wait_transition(stage);stage.page_tabs['dj'].clicked();f.settle(.2)
        assert stage.page=='dj'
        assert isinstance(v.entry,Gtk.Entry) and v.entry.get_max_length()==500
        before=list(host.calls);v.entry.grab_focus();v.entry.set_text('Relaxing music')
        f.key(stage.window,'space');f.key(stage.window,'Left');assert host.calls==before,'Keyboard typing triggered transport'
        slow[0]=True;painted=[0];stage.window.get_frame_clock().connect('after-paint',lambda *_:painted.__setitem__(0,painted[0]+1))
        stage.music.add([dict(tracks[0],uri='spotify:track:Manual',title='Manual selection')])
        v.entry.emit('activate');wait(entered.is_set);assert s.busy and not v.entry.get_text()
        frames=painted[0];f.settle(.2);assert painted[0]>frames,'DJ blocked GTK'
        release.set();slow[0]=False;wait(lambda:not s.busy and len(v.rows)>0);wait(lambda:not stage.music.loading)
        assert plays and s.session and any(i['uri']=='spotify:track:Manual' for _,i in stage.music.book.upcoming('spotify'))
        assert s.prompt=='Relaxing music';shot(stage,'dj-1920')
        # Keyboard and microphone send into the same request pipeline.
        with patch.object(s,'ask') as ask:
            s.voice.transcript('Хочу спокойную музыку');ask.assert_called_once_with('Хочу спокойную музыку')
        with patch('dj_service.ready',return_value=True),patch.object(s.voice,'launch') as launch:
            v.mic.clicked();launch.assert_called_once_with('listen',s.language)
        s.voice.mode='listen';s.voice.phase='listening';s.changed();assert v.mic_caption.get_text() in ('FINISH RECORDING','ЗАКОНЧИТЬ ЗАПИСЬ')
        stage.page_tabs['playing'].clicked();assert not s.voice.mode,'Leaving DJ did not close microphone'
        f.settle(.2);assert s.session and not v.signal.tick,'Hidden DJ kept drawing'
        stage.page_tabs['dj'].clicked();v.toggle_settings();f.settle(.3)
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.unfullscreen();stage.window.resize(width,height);f.settle(.3)
            assert stage.window.get_size()==(width,height),stage.window.get_size()
            fits(stage,[stage.play_button,stage.knob,stage.page_tabs['dj'],v.entry,v.mic,v.send,v.scroll])
            if width==1024:shot(stage,'dj-1024-settings')
        v.toggle_settings();f.settle(.3)
        menu=SettingsMenu(lambda:None,lambda:None,lambda:None,fullscreen=host.show_accounts)
        with patch.object(stage,'open_dj') as launch:menu.dj();launch.assert_called_once_with()
        # A cancelled late result must not replace the queue or start a new track.
        slow[0]=True;release.clear();entered.clear();count=len(plays)
        v.entry.set_text('Energetic music');v.send.clicked();wait(entered.is_set)
        v.cancel_button.clicked();release.set();f.settle(.35);assert len(plays)==count
        assert not s.busy
        s.stop();assert all(i.get('origin')!='dj' for _,i in stage.music.book.upcoming('spotify'))
        assert any(i['uri']=='spotify:track:Manual' for _,i in stage.music.book.upcoming('spotify'))
        stage.close();assert s.closed and not s.voice.process
        print('PASS DJ keyboard Enter/button, microphone routing, live GTK, stale requests, preserved queue and responsive settings')
    finally:release.set();stage.close();host.window.destroy()
