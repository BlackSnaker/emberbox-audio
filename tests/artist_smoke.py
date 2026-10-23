"""Real GTK artist/release navigation; offline fixtures and original media only."""
import copy
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from source_picker import text
from gi.repository import Gdk,Gtk

tracks=[{'id':str(i),'uri':'spotify:track:'+str(i),'title':name,'artist':'Emberbox Sessions',
         'image':'fixture:cover','duration_ms':(170+i*12)*1000,'playable':i!=3}
        for i,name in enumerate(('Afterglow','The shape of amber','A quiet orbit','Unavailable recording','Slow-burning light'),1)]
albums=[{'id':str(i),'uri':'spotify:album:'+str(i),'kind':'album','title':name,
         'image':'fixture:cover','releaseDate':str(2026-i)+'-10-23','trackCount':12}
        for i,name in enumerate(('Slow Evenings','In the Warm Light','Quiet Hours','Night Drive','Amber Stories','Afterglow'),1)]
profile={'id':'A','name':'Emberbox Sessions','image':'fixture:artist','genres':['Alternative','Ambient soul'],
         'bio':'Original demonstration biography.\n\nEmberbox Sessions follows the warm edge between sound and silence. '
               'These fictional releases and words demonstrate the artist room; no account data is used.'}
calls=[];plays=[];block=[False];entered=threading.Event();release=threading.Event()
def load(source,category,term='',collection=None,offset=0):
    ref=collection or {};calls.append((source,category,dict(ref),offset))
    if block[0]:entered.set();release.wait(3)
    if source=='youtube':return {'artist':dict(profile,name='A video channel',id=''),'searchOnly':True,'note':'Video search, not an album catalogue.'}
    if category=='artist':
        if ref.get('name')=='Collaboration' and not ref.get('id'):return {'choices':[dict(profile,id='A'),dict(profile,id='B',name='Another musician')]}
        return {'artist':dict(profile,id=ref.get('id','A')),'sections':[{'id':'latest-release','items':copy.deepcopy(albums[:4])},
                {'id':'top-songs','items':copy.deepcopy(tracks[:4])}]}
    if category=='artist-section':return {'items':copy.deepcopy(albums[:2] if offset else albums),'next':None if offset else 24}
    if category=='release':return {'release':dict(albums[0],id=ref['id'],artist='Emberbox Sessions',
                description='Original demonstration liner notes.\n\nA small collection about warmth, memory and evenings that last a little longer.',
                copyright='Original fixture © Emberbox'),'items':copy.deepcopy(tracks),'next':None}
    return {'items':[]}


def wait(predicate,limit=4):
    until=time.monotonic()+limit
    while not predicate() and time.monotonic()<until:f.settle(.03)
    assert predicate(),'Artist request did not finish'
    f.settle(.2)


def shot(stage,name):
    target=os.environ.get('EMBERBOX_ARTIST_PREVIEW')
    if target:
        f.settle(.25);folder=Path(target);folder.mkdir(exist_ok=True,parents=True)
        w,h=stage.window.get_size()
        Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,w,h).savev(str(folder/(name+'.png')),'png',[],[])


host=f.FixtureHost()
host.youtube=SimpleNamespace(queue=[],current=None,eof=False,paused=True,mpv=None)
real_image_load=fullscreen.Artwork.load
def local_artwork(loader,image,url,size,radius=8,**options):
    return real_image_load(loader,image,(f.ROOT/'assets/demo-cover.png').as_uri(),size,radius,**options)
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network access')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',local_artwork):
    stage=fullscreen.FullscreenPlayer(host);service=stage.music;view=stage.artist_view
    service.repository.load=load;service.repository.play=lambda item,alive:plays.append(item['uri']) if alive() else None
    try:
        stage.open();f.wait_transition(stage);assert not calls
        block[0]=True;painted=[0]
        stage.window.get_frame_clock().connect('after-paint',lambda *_:painted.__setitem__(0,painted[0]+1))
        stage.artist_button.clicked();wait(entered.is_set)
        before=painted[0];f.settle(.25);assert painted[0]>before,'Artist loading blocked the frame clock'
        stage.play_button.clicked();assert host.calls[-1]==('spotify','toggle'),'Transport must stay available'
        release.set();block[0]=False;wait(lambda:view.profile is not None)
        assert stage.page=='artist' and len(view.album_buttons)==4 and not plays
        assert all(b.get_mapped() for b in view.filters.values()),'Artist categories must be visible, not just programmatically clickable'
        shot(stage,'artist')
        view.filters['about'].clicked();f.settle(.2)
        assert any('Original demonstration biography.' in value for value in f.labels(view))
        assert not plays
        shot(stage,'artist-about')
        view.filters['albums'].clicked();wait(lambda:len(view.album_buttons)==6)
        assert calls[-1][2]['section']=='albums'
        view.album_buttons[0][0].clicked();wait(lambda:len(view.song_buttons)==5)
        assert not view.song_buttons[2][0].get_sensitive(),'Unavailable songs must not be playable'
        assert not view.song_buttons[2][1].get_sensitive()
        view.read_button.clicked();f.settle(.4)
        assert any('Original demonstration liner notes.' in value for value in f.labels(view))
        shot(stage,'artist-release')
        view.scroll.get_vadjustment().set_value(0)
        view.song_buttons[0][1].clicked();assert len(service.book.upcoming('spotify'))==1 and not plays
        view.song_buttons[1][0].clicked();wait(lambda:not service.loading)
        assert plays==['spotify:track:2']
        assert [v['id'] for _,v in service.book.upcoming('spotify')]==['1','4','5'],'Release playback must retain explicit queue entries and skip unavailable songs'
        view.back_button.clicked();wait(lambda:view.release_ref is None and len(view.album_buttons)==6)
        assert view.section=='albums' and len(plays)==1,'Back must restore the discography without restarting music'
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.unfullscreen();stage.window.resize(width,height);f.settle(.3)
            assert stage.window.get_size()==(width,height)
            for child in (view.back_button,view.refresh_button,view.scroll,stage.knob,stage.play_button,view.play_all_button,*view.filters.values()):
                x,y=child.translate_coordinates(stage.window,0,0);a=child.get_allocation()
                assert child.get_mapped() and x>=0 and y>=0 and x+a.width<=width+2 and y+a.height<=height+2,(type(child).__name__,(x,y,a.width,a.height),(width,height))
            assert view.content.get_allocation().width<=view.scroll.get_allocation().width+2,'Artist page overflowed horizontally'
            if width==1024:shot(stage,'artist-1024')
        view.back_button.clicked();f.settle(.2);assert stage.page=='playing'
        stage.open_artist({'artist':'Collaboration'});wait(lambda:len(view.choice_buttons)==2)
        view.choice_buttons[1][0].clicked();wait(lambda:view.profile is not None)
        assert view.profile['id']=='B'
        # A late reply cannot replace a new source's page.
        block[0]=True;entered.clear();release.clear();view.refresh();wait(entered.is_set)
        host.source='youtube';stage.update();release.set();block[0]=False
        wait(lambda:view.source=='youtube' and view.profile is not None and view.profile.get('name')=='A video channel')
        assert view.search_only and not view.album_buttons
        stage.hide();assert not view.active
        stage.close();assert view.closed
        print('PASS in-room artist/album navigation, prose, background loading, controls, queue continuation, choices, source guards and three screen sizes')
    finally:
        release.set();stage.close();host.window.destroy()
