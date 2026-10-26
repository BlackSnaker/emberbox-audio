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
from artist_header import portrait_rect
from gi.repository import Gdk,Gtk

tracks=[{'id':str(i),'uri':'spotify:track:'+str(i),'title':name,'artist':'Emberbox Sessions',
         'image':'fixture:cover','duration_ms':(170+i*12)*1000,'playable':i!=3}
        for i,name in enumerate(('Afterglow','The shape of amber','Unavailable recording','A quiet orbit','Slow-burning light'),1)]
albums=[{'id':str(i),'uri':'spotify:album:'+str(i),'kind':'album','title':name,
         'image':'fixture:cover','releaseDate':str(2026-i)+'-10-23','trackCount':12}
        for i,name in enumerate(('Slow Evenings','In the Warm Light','Quiet Hours','Night Drive','Amber Stories','Afterglow'),1)]
latest=dict(albums[0],id='latest-1',uri='spotify:album:latest-1',kind='single',
            title='An ember at dusk',releaseDate='2026-10-23',trackCount=1,isSingle=True)
singles=[dict(albums[i],id='single-'+str(i),uri='spotify:album:single-'+str(i),kind='single',
              title=name,trackCount=2,isSingle=True) for i,name in enumerate(('Soft static','A little longer','Glass and amber'))]
compilations=[dict(albums[i],id='compilation-'+str(i),uri='spotify:album:compilation-'+str(i),kind='compilation',
                   title=name,trackCount=16,isCompilation=True) for i,name in enumerate(('A room of songs','Evenings collected'))]
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
        sections=[{'id':'latest-release','items':[latest]}]
        if ref.get('id')!='SPARSE':
            sections.extend(({'id':'top-songs','items':tracks[:4]}, {'id':'albums','items':albums},
                             {'id':'singles','items':singles}, {'id':'compilations','items':compilations}))
        return {'artist':dict(profile,id=ref.get('id','A'),name='Solstice' if ref.get('id')=='SHORT' else profile['name']),
                'sections':copy.deepcopy(sections)}
    if category=='artist-section':return {'items':copy.deepcopy(albums[:2] if offset else albums),'next':None if offset else 24}
    if category=='release':return {'release':dict(albums[0],id=ref['id'],artist='Emberbox Sessions',
                description='Original demonstration liner notes.\n\nA small collection about warmth, memory and evenings that last a little longer.',
                copyright='Original fixture © Emberbox'),'items':copy.deepcopy(tracks),'next':None}
    return {'items':[]}


def wait(predicate,limit=4):
    until=time.monotonic()+limit
    while not predicate() and time.monotonic()<until:f.settle(.03)
    assert predicate(),'Artist request did not finish'
    while view.entrance.busy and time.monotonic()<until:f.settle(.03)
    assert not view.entrance.busy,'Artist entrance must finish before checking live controls'
    f.settle(.2)


def shot(stage,name):
    target=os.environ.get('EMBERBOX_ARTIST_PREVIEW')
    if target:
        f.settle(.25);folder=Path(target);folder.mkdir(exist_ok=True,parents=True)
        w,h=stage.window.get_size()
        Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,w,h).savev(str(folder/(name+'.png')),'png',[],[])


def rectangle(widget,parent):
    position=widget.translate_coordinates(parent,0,0)
    assert position is not None,'Widget must belong to the visible artist room'
    allocation=widget.get_allocation()
    return (*position,allocation.width,allocation.height)


def visible_in_scroll(widget,view,stage):
    x,y,w,h=rectangle(widget,stage.window)
    sx,sy,sw,sh=rectangle(view.scroll,stage.window)
    return widget.get_mapped() and min(x+w,sx+sw)>max(x,sx) and min(y+h,sy+sh)>max(y,sy)


def overview_first_screen(view,stage):
    """One latest release must share the first screen with useful music content."""
    feature=view.overview_panels['feature'];songs=view.overview_panels['songs']
    fx,fy,fw,fh=rectangle(feature,stage.window);sx,sy,sw,sh=rectangle(songs,stage.window)
    assert visible_in_scroll(feature,view,stage) and visible_in_scroll(songs,view,stage)
    assert fx+fw<=sx+2 and min(fy+fh,sy+sh)>max(fy,sy),'Wide artist overview must use both columns'
    assert len([value for _,value in view.album_buttons if value['id']=='latest-1'])==1
    assert any(visible_in_scroll(play,view,stage) for play,_,_ in view.song_buttons),'Popular songs must appear immediately'
    assert len({value['id'] for _,value in view.album_buttons})>=7,'Overview must expose the catalogue beyond one latest release'
    assert view.shelf_widgets,'The overview must retain its real discography shelves'
    heading=view.shelf_widgets[0].get_children()[0]
    _,hy,_,hh=rectangle(heading,stage.window);_,scroll_y,_,scroll_h=rectangle(view.scroll,stage.window)
    assert heading.get_mapped() and hy>=max(fy+fh,sy+sh) and hy>=scroll_y and hy+hh<=scroll_y+scroll_h+1,\
        ('The first discography heading must fit fully below the useful music panels, without being clipped at the viewport edge',
         {'heading':(hy,hh),'scroll':(scroll_y,scroll_h),'feature':(fy,fh),'songs':(sy,sh),
          'masthead':rectangle(view.hero_banner,stage.window)})


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
        stage.window.unfullscreen();stage.window.resize(1920,1080);f.settle(.4)
        block[0]=True;painted=[0]
        stage.window.get_frame_clock().connect('after-paint',lambda *_:painted.__setitem__(0,painted[0]+1))
        stage.artist_button.clicked();wait(entered.is_set)
        before=painted[0];f.settle(.25);assert painted[0]>before,'Artist loading blocked the frame clock'
        stage.play_button.clicked();assert host.calls[-1]==('spotify','toggle'),'Transport must stay available'
        release.set();block[0]=False;wait(lambda:view.profile is not None)
        assert stage.page=='artist' and view.album_buttons and not plays
        assert all(b.get_mapped() for b in view.filters.values()),'Artist categories must be visible, not just programmatically clickable'
        overview_first_screen(view,stage)
        for b,_ in view.album_buttons:
            assert b.get_accessible().get_name(),'Every release must have an accessible name'
        shot(stage,'artist')
        # An eight-letter artist uses the largest poster typography in one line.
        view.set_reference({'id':'SHORT','name':'Solstice'});view.load('artist',view.reference)
        wait(lambda:view.profile is not None and view.profile['id']=='SHORT')
        banner=view.hero_banner
        title=next(child for box in banner.content.get_children() for child in box.get_children()
                   if isinstance(child,Gtk.Label) and child.get_text()=='Solstice')
        assert title.get_style_context().has_class('stage-artist-display')
        assert title.get_layout().get_line_count()==1,'The largest display name must fit without accidental wrapping'
        bx,by,bw,bh=rectangle(banner,stage.window);tx,ty,tw,th=rectangle(title,stage.window)
        assert tx>=bx and ty>=by and tx+tw<=bx+bw-banner.photo_area_width+2 and ty+th<=by+bh+1,\
            'The large display name must fit inside the reading area, clear of the complete photograph'
        overview_first_screen(view,stage)
        shot(stage,'artist-display')
        # A source may really have only one release. Show its story, never cloned cards.
        view.set_reference({'id':'SPARSE','name':profile['name']});view.load('artist',view.reference)
        wait(lambda:view.profile is not None and view.profile['id']=='SPARSE')
        assert set(view.overview_panels)>={'feature','story'}
        assert len(view.album_buttons)==1 and not view.song_buttons,'Sparse catalogues must not fabricate or repeat releases'
        feature=view.overview_panels['feature'];story=view.overview_panels['story']
        fx,fy,fw,fh=rectangle(feature,stage.window);sx,sy,sw,sh=rectangle(story,stage.window)
        assert fx+fw<=sx+2 and min(fy+fh,sy+sh)>max(fy,sy),'A lone release and real artist story must share the editorial row'
        assert visible_in_scroll(story,view,stage)
        assert any('Original demonstration biography.' in value for value in f.labels(story))
        shot(stage,'artist-sparse')
        view.set_reference({'id':'A','name':profile['name']});view.load('artist',view.reference)
        wait(lambda:view.profile is not None and view.profile['id']=='A')
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
        view.filters['overview'].clicked();f.settle(.2)
        for width,height in ((1024,600),(1280,720),(1920,1080)):
            stage.window.unfullscreen();stage.window.resize(width,height);f.settle(.3)
            assert stage.window.get_size()==(width,height)
            for child in (view.back_button,view.refresh_button,view.scroll,stage.knob,stage.play_button,view.play_all_button,*view.filters.values()):
                x,y=child.translate_coordinates(stage.window,0,0);a=child.get_allocation()
                assert child.get_mapped() and x>=0 and y>=0 and x+a.width<=width+2 and y+a.height<=height+2,(type(child).__name__,(x,y,a.width,a.height),(width,height))
            assert view.content.get_allocation().width<=view.scroll.get_allocation().width+2,'Artist page overflowed horizontally'
            banner=view.hero_banner
            bx,by,bw,bh=rectangle(banner,stage.window);cx,cy,cw,ch=rectangle(banner.content,stage.window)
            assert banner.photo_area_width>0,'Reserve the full portrait before painting the heading'
            assert cx+cw<=bx+bw-banner.photo_area_width+2,('Artist text must not overlap the complete photo',(width,height),(bx,by,bw,bh),(cx,cy,cw,ch),banner.photo_area_width)
            assert cy>=by and cy+ch<=by+bh+2,('The heading and controls must stay inside the masthead',(width,height),(bx,by,bw,bh),(cx,cy,cw,ch))
            wait(lambda:banner.pixels is not None)
            px,py,pw,ph=portrait_rect(banner.pixels[1],bw,bh)
            assert ph>=(320 if width==1920 else 160),('The full artist photograph must be substantial',(width,height),(bw,bh),(px,py,pw,ph))
            assert cx+cw<=bx+px and py>=0 and py+ph<=bh,('Artist text and actions must not cover the large photograph',(width,height),(cx,cy,cw,ch),(bx+px,by+py,pw,ph))
            adjustment=view.scroll.get_vadjustment()
            assert adjustment.get_upper()>adjustment.get_page_size(),'The complete artist catalogue must remain scrollable'
            adjustment.set_value(adjustment.get_upper()-adjustment.get_page_size());f.settle(.1)
            assert adjustment.get_value()>0,'Artist catalogue scrolling must work at every supported size'
            adjustment.set_value(0);f.settle(.1)
            if width==1920:overview_first_screen(view,stage)
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
        print('PASS dense artist overview, sparse real catalogue, in-room navigation, prose, background loading, accessible controls, queue continuation, choices, source guards and three screen sizes')
    finally:
        release.set();stage.close();host.window.destroy()
