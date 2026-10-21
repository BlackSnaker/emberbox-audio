"""Actual fullscreen collection/search/queue widgets with original offline media."""
import os
from datetime import datetime
from pathlib import Path
import threading
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
import listening_library
from source_picker import text
from gi.repository import Gdk,Gtk

tracks=[{'uri':'spotify:track:'+name,'id':name,'title':title,'artist':'Emberbox Sessions',
         'album':'Slow Evenings','image':'fixture:cover','duration_ms':(180+i*14)*1000}
        for i,(name,title) in enumerate([('A','Afterglow'),('B','Amber lines'),('C','Night drive'),('D','Тёплый воздух')])]
albums=[{'uri':'spotify:album:'+str(i),'href':'/album/'+str(i),'kind':'album','title':title,
         'subtitle':'Emberbox Sessions','image':'fixture:cover'} for i,title in enumerate(
         ['Slow Evenings','In the Warm Light','Quiet Hours','Night Drive','Amber Stories','Afterglow'])]
entered,release=threading.Event(),threading.Event();calls=[];plays=[]
block=[False]
def load(source,category,term='',collection=None,offset=0):
    calls.append((source,category,term,collection,offset))
    if block[0]:entered.set();release.wait(2)
    return {'tracks':tracks} if collection else {'items':tracks if category=='search' else albums}


def wait(predicate,seconds=3):
    import time
    until=time.monotonic()+seconds
    while not predicate() and time.monotonic()<until:f.settle(.03)
    assert predicate(),'GUI request never completed'
    f.settle(.2)


def fits(stage,widgets):
    width,height=stage.window.get_size()
    for child in widgets:
        assert child.get_mapped(),type(child).__name__
        x,y=child.translate_coordinates(stage.window,0,0);a=child.get_allocation()
        assert 0<=x and 0<=y and x+a.width<=width+2 and y+a.height<=height+2,(type(child).__name__,(x,y,a.width,a.height),(width,height))


def shot(stage,name):
    target=os.environ.get('EMBERBOX_LIBRARY_PREVIEW')
    if target:
        f.settle(.22)
        path=Path(target);path.mkdir(exist_ok=True,parents=True)
        width,height=stage.window.get_size()
        Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height).savev(str(path/(name+'.png')),'png',[],[])


host=f.FixtureHost()
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network access')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',f.image_load):
    stage=fullscreen.FullscreenPlayer(host);service=stage.music
    service.repository.load=load;service.repository.play=lambda item,alive:plays.append(item['uri']) if alive() else None
    try:
        stage.open();f.wait_transition(stage)
        assert not calls,'The default cover must not start collection requests'
        stage.page_tabs['library'].clicked();view=stage.library_view
        wait(lambda:len(view.album_buttons)==6)
        assert stage.page=='library' and stage.window.get_visible()
        shot(stage,'collection-1920')
        # A slow backend leaves the GTK frame clock and transport responsive.
        block[0]=True;painted=[0]
        stage.window.get_frame_clock().connect('after-paint',lambda *_:painted.__setitem__(0,painted[0]+1))
        view.album_buttons[0][0].clicked();wait(entered.is_set)
        before=painted[0];f.settle(.25)
        assert painted[0]>before,'Album loading blocked GTK'
        release.set();block[0]=False;wait(lambda:len(view.song_buttons)==4)
        assert view.play_all_button.get_mapped() and view.add_all_button.get_mapped()
        stage.window.unfullscreen();stage.window.resize(1024,600);f.settle(.25)
        fits(stage,[view.play_all_button,view.add_all_button,view.entry,stage.knob])
        stage.window.resize(1920,1080);f.settle(.25)
        view.song_buttons[0][1].clicked();view.song_buttons[1][1].clicked();view.song_buttons[2][1].clicked()
        assert len(service.book.upcoming('spotify'))==3 and not plays,'Adding must never autoplay'
        shot(stage,'album-1920')
        stage.page_tabs['queue'].clicked();f.settle(.25);queue=stage.queue_view
        assert len(queue.rows)==3
        # Local time changes the heading without rebuilding the queue or touching playback.
        original_rows=list(queue.rows);original_plays=list(plays)
        periods=((0,'Late hours, favourite songs.','Ночь — время любимых треков.'),
                 (4,'Late hours, favourite songs.','Ночь — время любимых треков.'),
                 (5,'Let the morning play.','Пусть утро звучит.'),
                 (11,'Let the morning play.','Пусть утро звучит.'),
                 (12,'A soundtrack for your day.','Музыка для твоего дня.'),
                 (17,'A soundtrack for your day.','Музыка для твоего дня.'),
                 (18,'Let the evening continue.','Пусть вечер продолжается.'),
                 (22,'Let the evening continue.','Пусть вечер продолжается.'),
                 (23,'Late hours, favourite songs.','Ночь — время любимых треков.'))
        with patch.object(listening_library,'datetime') as clock:
            for hour,en,ru in periods:
                clock.now.return_value=datetime(2026,10,21,hour)
                queue.render()
                assert queue.title.get_text()==text(en,ru),(hour,queue.title.get_text())
            assert queue.rows==original_rows and plays==original_plays
        queue.render()
        queue.rows[2][1].clicked()
        assert [i['id'] for _,i in service.book.upcoming('spotify')]==['A','C','B']
        queue.rows[2][3].clicked()
        assert [i['id'] for _,i in service.book.upcoming('spotify')]==['A','C']
        shot(stage,'queue-1920')
        queue.play_button.clicked();wait(lambda:not service.loading)
        assert plays==['spotify:track:A']
        # Search typing must not trigger playback/seek keyboard shortcuts.
        stage.page_tabs['library'].clicked();f.settle(.25);view.entry.set_text('Night Drive');view.entry.grab_focus()
        before=list(host.calls);f.key(stage.window,'space');f.key(stage.window,'Left')
        assert host.calls==before
        view.entry.emit('activate');wait(lambda:len(view.song_buttons)==4 and view.category=='search')
        assert calls[-1][2].strip()=='Night Drive' and stage.window.get_visible()
        stage.page_tabs['queue'].clicked();f.settle(.2)
        event=Gdk.Event.new(Gdk.EventType.KEY_PRESS);event.keyval=Gdk.KEY_f;event.state=Gdk.ModifierType.CONTROL_MASK
        stage.window.emit('key-press-event',event);f.settle(.25)
        assert stage.page=='library' and isinstance(stage.window.get_focus(),Gtk.Entry)
        shot(stage,'search-1920')
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.unfullscreen();stage.window.resize(width,height);f.settle(.3)
            assert stage.window.get_size()==(width,height)
            fits(stage,[view.entry,view.refresh_button,view.scroll,stage.knob,stage.play_button,stage.page_tabs['queue']])
            stage.page_tabs['queue'].clicked();f.settle(.25)
            fits(stage,[queue.play_button,queue.clear_button,queue.scroll,stage.knob,stage.page_tabs['library']])
            if width==1024:shot(stage,'queue-1024')
            stage.page_tabs['library'].clicked();f.settle(.25)
        stage.hide()
        assert service.book.active=='spotify','Leaving fullscreen must preserve queue playback'
        stage.close()
        assert service.closed
        print('PASS fullscreen collection, responsive album loading, in-player search, queue edits/playback and source isolation')
    finally:
        release.set();stage.close();host.window.destroy()
