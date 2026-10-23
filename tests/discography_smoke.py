"""Real GTK: complete background catalogue, resume, cancellation and bounded covers."""
import copy
import threading
from types import SimpleNamespace
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen
from gi.repository import GLib,Gtk

releases=[{'id':str(2000+i),'uri':'apple:albums:'+str(2000+i),'kind':'albums',
    'title':'Original edition','image':'fixture:cover','releaseDate':f'{2026-i%30}-01-01',
    'isSingle':i%3==0,'isCompilation':i%3==1} for i in range(317)]
calls=[];failed=[False];blocked=[False];entered=threading.Event();resume=threading.Event()
def load(source,category,term='',collection=None,offset=0):
    ref=collection or {};calls.append((category,dict(ref),offset))
    if category=='artist':
        return {'artist':{'id':'100','name':'Emberbox Sessions','image':'fixture:artist','bio':'Original biography.'},
                'sections':[{'id':'latest-release','items':[releases[0]]}]}
    if category=='artist-section':
        assert source=='apple-music' and ref['section']=='discography'
        if offset==100 and not failed[0]:failed[0]=True;raise RuntimeError('Fixture network interruption')
        if offset==200 and not blocked[0]:blocked[0]=True;entered.set();assert resume.wait(4)
        values=copy.deepcopy(releases[offset:offset+100])
        if offset:values.append(copy.deepcopy(releases[0]))
        return {'catalog':True,'storefront':'us','items':values,'next':offset+100 if offset+100<len(releases) else None}
    if category=='release':return {'release':dict(ref),'items':[]}
    raise AssertionError(category)

def wait(predicate,limit=5):
    import time
    until=time.monotonic()+limit
    while not predicate() and time.monotonic()<until:f.settle(.02)
    assert predicate(),'Discography request did not finish'
    f.settle(.05)

host=f.FixtureHost();host.source='apple-music';host.apple_web=SimpleNamespace(state={'id':'123'})
host.youtube=SimpleNamespace(queue=[],current=None,eof=False,paused=True,mpv=None)
real_load=fullscreen.Artwork.load
def artwork(loader,image,url,size,radius=8,**options):
    return real_load(loader,image,(f.ROOT/'assets/demo-cover.png').as_uri(),size,radius,**options)
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network access')), \
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',artwork):
    stage=fullscreen.FullscreenPlayer(host);view=stage.artist_view;stage.music.repository.load=load
    try:
        stage.open();f.wait_transition(stage);stage.window.unfullscreen();stage.window.resize(1920,1080);f.settle(.2)
        stage.artist_button.clicked();wait(lambda:bool(view.catalog.error))
        assert len(view.catalog.items)==100 and not view.catalog.complete
        assert view.catalog.offset==100 and not view.busy
        view.filters['discography'].clicked();wait(entered.is_set)
        assert len(view.catalog.items)==200 and len(view.album_buttons)<=48
        assert all(b.get_mapped() for b in view.filters.values())
        painted=[0]
        stage.window.get_frame_clock().connect('after-paint',lambda *_:painted.__setitem__(0,painted[0]+1))
        f.settle(.2);assert painted[0]>0,'A waiting catalogue page blocked GTK'
        stage.play_button.clicked();assert host.calls[-1]==('apple-music','toggle')
        # Leave while an API call is outstanding. Its late page must not commit.
        view.filters['about'].clicked();resume.set();f.settle(.3)
        assert len(view.catalog.items)==200 and not view.catalog.complete and not view.busy
        view.filters['discography'].clicked();wait(lambda:view.catalog.complete)
        assert len(view.catalog.items)==317 and len(view.catalog.seen)==317
        assert len(view.album_buttons)==48 and view.catalog.storefront=='us'
        assert '317' in view.notice.get_text()
        assert sum(len(view.catalog.selection(k)) for k in ('albums','singles','compilations'))==317
        while view.catalog_next_button.get_sensitive():
            view.catalog_next_button.clicked();f.settle(.03)
            assert len(view.album_buttons)<=48
        assert view.album_buttons[-1][1]['id']=='2316','The final release must be reachable'
        count=len(calls);view.album_buttons[-1][0].clicked();wait(lambda:bool(view.release_ref) and not view.busy)
        view.back_button.clicked();f.settle(.2)
        assert view.section=='discography' and len(calls)==count+1,'Returning must reuse the completed catalogue'
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.resize(width,height);f.settle(.25)
            assert stage.window.get_size()==(width,height)
            for widget in (*view.filters.values(),view.refresh_button,stage.play_button):
                x,y=widget.translate_coordinates(stage.window,0,0);a=widget.get_allocation()
                assert x>=0 and y>=0 and x+a.width<=width+2 and y+a.height<=height+2,(width,height,widget.get_label(),x,a.width)
        view.set_reference({'id':'200','name':'Another artist'})
        assert not view.catalog.items and not view.catalog.complete
        print('PASS 317 editions, automatic paging, interrupted-page resume, stale replies, live transport, 48-cover window and three GTK sizes')
    finally:
        resume.set();stage.close();host.window.destroy()
