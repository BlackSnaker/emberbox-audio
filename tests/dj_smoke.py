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
    real_collect=s.catalog.collect
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
        v.entry.emit('activate');wait(entered.is_set);assert s.busy and v.entry.get_text()=='Relaxing music'
        assert v.wish.get_mapped() and 'Relaxing music' in v.wish.get_text()
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
        # The reported case: Beatles gets a full artist block and a visible, specific answer.
        beatles=[dict(tracks[0],uri='spotify:track:B'+str(i),id='B'+str(i),artist='The Beatles',
            title='Original Beatles fixture '+str(i),_requested_artist='The Beatles',_requested_artist_id='136975') for i in range(24)]
        s.catalog.collect=lambda *_a,**_kw:(beatles,[],[])
        v.entry.set_text('Beatles');v.entry.emit('activate');wait(lambda:not s.busy and s.intents.get('spotify').mode=='artist')
        assert len(s.items)==14 and all(i['artist']=='The Beatles' for i in s.items)
        assert v.entry.get_text()=='Beatles' and v.wish.get_mapped() and 'Beatles' in v.wish.get_text()
        assert 'The Beatles' in v.reply.get_text() and '14' in v.reply.get_text()
        assert 'The Beatles' in v.understanding.get_text()
        for width,height in ((1024,600),(1920,1080)):
            stage.window.resize(width,height);f.settle(.3)
            fits(stage,[v.wish,v.reply,v.understanding,v.entry,stage.knob])
        shot(stage,'dj-beatles-1920')
        s.refill();wait(lambda:not s.busy)
        tail=[i for _,i in stage.music.book.upcoming('spotify')]
        assert len(tail)>14 and all(i['artist']=='The Beatles' for i in tail[:-1])
        assert tail[-1]['uri']=='spotify:track:Manual','Artist refill lost the user tail'
        # Real interpreter + catalogue + ranking + asynchronous queue changes:
        # a mood after an artist releases artist scope and loads playlist songs.
        queries=[]
        def load(source,category,term='',collection=None,**_kw):
            if category=='search':
                queries.append(term)
                return {'items':[{'id':term,'kind':'playlist','title':term,'uri':'spotify:playlist:Fixture','href':'/playlist/Fixture'}]}
            assert collection
            return {'tracks':[dict(tracks[0],uri='spotify:track:'+collection['id'].replace(' ','')+str(i),
                artist='Session '+str(i),title='Original '+collection['id']+' recording '+str(i)) for i in range(40)]}
        s.catalog.collect=real_collect
        with patch.object(stage.music.repository,'load',side_effect=load),patch.object(s.catalog,'personal',return_value={'tracks':[]}):
            v.entry.set_text('давай что-нибудь повеселее');v.entry.emit('activate')
            wait(lambda:not s.busy and s.intents['spotify'].mood=='happy')
            assert s.intents['spotify'].mode=='mix' and not s.intents['spotify'].artists
            assert len(s.items)==14 and all(i.get('_dj_mood')=='happy' for i in s.items)
            assert queries[-1]=='feel good' and 'повеселее' in v.wish.get_text()
            v.entry.set_text('а теперь поспокойнее');v.send.clicked()
            wait(lambda:not s.busy and s.intents['spotify'].mood=='relax')
            assert queries[-1]=='chill' and len(s.items)==14
            first={i['uri'] for i in s.items}
            v.entry.set_text('ещё');v.send.clicked();wait(lambda:not s.busy and s.prompt=='ещё')
            assert len(s.items)==14 and not first.intersection(i['uri'] for i in s.items)
            assert queries==['feel good','chill'],'Continuation did not reuse the bounded metadata cache'
            # Preserve the exact visible text, but interpret the entire phrase
            # as a mood: the spaced hyphen must not create a literal song query.
            prompt='что - нибудь погрустнее'
            v.entry.set_text(prompt);v.entry.emit('activate')
            wait(lambda:not s.busy and s.intents['spotify'].mood=='melancholy')
            assert s.intents['spotify'].mode=='mix' and not s.intents['spotify'].query
            assert queries[-1]=='sad' and len(s.items)==14
            assert v.entry.get_text()==prompt and prompt in v.wish.get_text()
            assert 'Точный поиск' not in v.understanding.get_text() and 'Exact search' not in v.understanding.get_text()
            assert all(i.get('_dj_mood')=='melancholy' for i in s.items)
        successful=s.intents['spotify'];s.catalog.collect=lambda *_a,**_kw:([],[],[])
        v.entry.set_text('Unknown recording');v.entry.emit('activate');wait(lambda:not s.busy and s.phase=='empty')
        assert s.intents['spotify']==successful,'Failed lookup poisoned the conversation context'
        s.stop();assert all(i.get('origin')!='dj' for _,i in stage.music.book.upcoming('spotify'))
        assert any(i['uri']=='spotify:track:Manual' for _,i in stage.music.book.upcoming('spotify'))
        stage.close();assert s.closed and not s.voice.process
        print('PASS DJ keyboard Enter/button, microphone routing, live GTK, stale requests, preserved queue and responsive settings')
    finally:release.set();stage.close();host.window.destroy()
