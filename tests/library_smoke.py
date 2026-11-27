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
from gi.repository import Gdk,GdkPixbuf,Gtk

tracks=[{'uri':'spotify:track:'+name,'id':name,'title':title,'artist':'Emberbox Sessions',
         'album':'Slow Evenings','image':'fixture:cover','duration_ms':(180+i*14)*1000}
        for i,(name,title) in enumerate([('A','Afterglow'),('B','Amber lines'),('C','Night drive'),('D','Тёплый воздух')])]
albums=[{'uri':'spotify:album:'+str(i),'href':'/album/'+str(i),'kind':'album','title':title,
         'subtitle':'Emberbox Sessions','image':f'fixture:album:{i}'} for i,title in enumerate(
         ['Slow Evenings','In the Warm Light','Quiet Hours','Night Drive','Amber Stories','Afterglow'])]


def album_covers():
    source=(f.ROOT/'assets/demo-cover.svg').read_text()
    colors=('#222e29','#66705a','#ffda84','#c8793e','#25392f','#1b2b24')
    variations=(('#2e241e','#8f5742','#efc78a','#bd692d','#543124','#3c2722'),
                ('#1e222d','#536f81','#bce5e2','#517fc3','#2e424b','#1f3340'),
                ('#2b1b27','#6e4658','#f6a8a8','#bc6e89','#512e48','#362439'),
                ('#211c27','#615c76','#e7d1ff','#8880b0','#443750','#342b44'),
                ('#252c1e','#5f784b','#e3d99c','#a9a65b','#344d32','#28382b'),colors)
    result={}
    for album,palette in zip(albums,variations):
        image=source.replace('AFTERGLOW',album['title'].upper())
        for old,new in zip(colors,palette):image=image.replace(old,new)
        loader=GdkPixbuf.PixbufLoader.new_with_type('svg')
        loader.write(image.encode());loader.close()
        result[album['image']]=loader.get_pixbuf()
    return result


covers=album_covers()


def image_load(loader,image,url,size,radius=8,preserve=False,on_loaded=None,**options):
    if url not in covers:
        return f.image_load(loader,image,url,size,radius,preserve,on_loaded,**options)
    pixels=covers[url].scale_simple(size,size,GdkPixbuf.InterpType.BILINEAR)
    image.set_size_request(size,size);image.set_from_pixbuf(pixels)
    if on_loaded:on_loaded(pixels)


entered,release=threading.Event(),threading.Event();calls=[];plays=[]
block=[False]
failure=set()
def load(source,category,term='',collection=None,offset=0):
    calls.append((source,category,term,collection,offset))
    if block[0]:entered.set();release.wait(2)
    if category in failure:
        error=RuntimeError('Fixture timeout')
        error.code='TIMEOUT'
        raise error
    if category=='whole-album':return {'items':tracks}
    if category=='albums' and not collection:
        return {'items':[dict(album,id=str(i),uri=f'spotify:album:{i}',title=album['title']+f' · {i+1}')
                         for i,album in enumerate(albums*10)]}
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


def check_spines(stage,shelf):
    wait(lambda:bool(shelf.spines) and all(spine.get_allocated_width()>1 for spine,_item in shelf.spines))
    faces=[]
    fits(stage,[spine for spine,_item in shelf.spines])
    width,height=shelf.canvas.get_allocated_width(),shelf.canvas.get_allocated_height()
    for spine,_item in shelf.spines:
        x,y=spine.translate_coordinates(shelf.canvas,0,0)
        area=spine.get_allocation()
        assert 0<=x and 0<=y and x+area.width<=width and y+area.height<=height,(
            x,y,area.width,area.height,width,height)
        if spine.print.face:faces.append(spine.print.art)
    assert faces and all(pixels is not None for pixels in faces),'Nearby sleeves must show their artwork'


def check_sleeve(stage,shelf):
    request_count,play_count=len(calls),len(plays)
    shelf.preview_key.clicked()
    inspector=shelf.inspector
    canvas=inspector.canvas
    wait(lambda:shelf.inspector_open and canvas.get_mapped())
    fits(stage,[canvas,inspector.front_button,inspector.back_button,inspector.disc_button,inspector.close_button])
    assert canvas.face=='front'
    shot(stage,'shelf-sleeve-front')

    angle=canvas.angle
    x,y=canvas.get_allocated_width()/2,canvas.get_allocated_height()/2
    canvas.drag_begin(None,x,y)
    canvas.drag_update(None,68.,0.)
    assert canvas.angle!=angle,'Dragging must turn the sleeve before release'
    shot(stage,'shelf-sleeve-turning')
    canvas.drag_end(None,68.,0.)
    wait(lambda:canvas.face=='back' and not canvas.tick)

    canvas.grab_focus()
    assert f.key(stage.window,'Right')
    wait(lambda:canvas.face=='front' and not canvas.tick)
    inspector.back_button.grab_focus()
    assert f.key(stage.window,'space')
    wait(lambda:canvas.face=='back' and not canvas.tick)
    shot(stage,'shelf-sleeve-back')
    inspector.front_button.clicked()
    wait(lambda:canvas.face=='front' and not canvas.tick)
    inspector.disc_button.clicked()
    wait(lambda:canvas.disc_position>.95)
    shot(stage,'shelf-sleeve-disc')
    inspector.disc_button.clicked()
    wait(lambda:canvas.disc_position<.05)
    f.key(stage.window,'Escape')
    wait(lambda:not shelf.inspector_open and shelf.preview_key.get_mapped())
    assert stage.page=='library' and stage.window.get_visible()
    assert len(calls)==request_count and len(plays)==play_count,'Inspecting must leave playback and browsing alone'


host=f.FixtureHost()
with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network access')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',image_load):
    stage=fullscreen.FullscreenPlayer(host);service=stage.music
    service.repository.load=load;service.repository.play=lambda item,alive:plays.append(item['uri']) if alive() else None
    try:
        stage.open();f.wait_transition(stage)
        assert not calls,'The default cover must not start collection requests'
        failure.add('home')
        stage.page_tabs['library'].clicked();view=stage.library_view
        wait(lambda:view.active and not view.busy)
        assert not view.shelf.get_mapped() and view.scroll.get_mapped()
        assert not view.connect_button.get_visible()
        shot(stage,'collection-unavailable')
        failure.clear();view.refresh_button.clicked()
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
        # Returning to a prepared page must reuse its rows, including after
        # playback-only metadata changes. No expensive widget reconstruction.
        original_songs=tuple(view.song_buttons)
        stage.show_page('library');f.settle(.35)
        assert tuple(view.song_buttons)==original_songs,'Cached library rows were recreated'
        stage.show_page('queue');f.settle(.35)
        assert queue.rows==original_rows,'Reopening queue rebuilt every row'
        old_playing=host.playing;host.playing=not old_playing;queue.render();host.playing=old_playing;queue.render()
        assert queue.rows==original_rows,'Playback state alone must not rebuild queue rows'

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
        # A burst never composites a stack of half-faded pages. The indicator
        # follows every click, while the content honours only the latest intent.
        from unittest.mock import patch as watch
        import page_transition
        with watch.object(page_transition,'snapshot',wraps=page_transition.snapshot) as captures:
            stage.show_page('playing')
            assert stage.page_transition.active
            for destination in ('library','queue','library','playing','queue'):
                stage.show_page(destination)
            assert stage.page=='playing' and stage.pending_page=='queue'
            wait(lambda:stage.page=='queue' and not stage.page_transition.active and stage.pending_page is None)
            assert captures.call_count<=4,'A click burst must not build a multi-page ghost image'
            assert stage.pages.get_opacity()==1. and stage.page_transition.canvas is None
        assert host.calls==[],'Visual navigation must not control playback'
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
        # Clicking a search result creates a continuation from that row.
        view.song_buttons[1][0].clicked();wait(lambda:not service.loading)
        assert plays[-1]=='spotify:track:B'
        assert [i['id'] for _,i in service.book.upcoming('spotify')]==['C','D']
        host.title.set_text(tracks[1]['title']);host.artist.set_text(tracks[1]['artist'])
        host.length=tracks[1]['duration_ms']*1000;host.position=12_000_000;host.playing=True
        service.poll();host.position=host.length;host.playing=False;service.poll()
        wait(lambda:not service.loading)
        assert plays[-1]=='spotify:track:C','Search playback stopped after its first song'
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
        failure.add('albums');view.select('albums')
        shelf=view.shelf
        wait(lambda:shelf.get_mapped() and not view.busy)
        assert shelf.status.get_mapped() and shelf.status_retry.get_mapped()
        assert not shelf.scene.get_mapped() and not shelf.play_key.get_mapped()
        fits(stage,[view.tabs['albums'], view.refresh_button, shelf.status, stage.knob, stage.play_button])
        shot(stage,'shelf-unavailable')
        failure.clear();shelf.status_retry.clicked()
        wait(lambda:bool(shelf.spines) and shelf.get_mapped() and not view.busy)
        assert len(shelf.items)==60
        assert shelf.page==0 and shelf.following.get_sensitive() and not shelf.previous.get_sensitive()
        shelf.following.clicked();f.settle(.2)
        assert shelf.page==1 and shelf.previous.get_sensitive()
        assert shelf.current['uri']==shelf.spines[0][1]['uri']==shelf.items[shelf.capacity]['uri']
        shelf.previous.clicked();f.settle(.2)
        assert shelf.page==0 and not shelf.previous.get_sensitive()
        shelf.spines[2][0].clicked();f.settle(.2)
        assert shelf.current['id']=='2'
        assert shelf.sleeve.art is not None
        assert shelf.spines[2][0].get_accessible().get_name()==shelf.current['title']
        assert shelf.spines[2][0].get_style_context().has_class('selected-spine')
        check_spines(stage,shelf)
        shot(stage,'shelf-1920')
        check_sleeve(stage,shelf)
        shelf.want.clicked();shelf.filter_key.clicked()
        assert [item['id'] for item in shelf.items]==['2']
        with patch.object(Gtk,'show_uri_on_window') as open_browser:
            shelf.format.set_active_id('CD');shelf.shops['Discogs'].clicked()
            assert 'format=CD' in open_browser.call_args.args[1]
            assert 'Quiet+Hours' in open_browser.call_args.args[1]
        shelf.filter_key.clicked()
        shelf.details_key.clicked()
        wait(lambda:stage.page=='artist' and not stage.artist_view.busy)
        stage.artist_view.back()
        wait(lambda:stage.page=='library' and shelf.get_mapped())
        stage.window.resize(1024,600);f.settle(.3)
        assert stage.window.get_size()==(1024,600)
        fits(stage,[shelf.canvas,shelf.play_key,shelf.details_key,stage.knob])
        check_spines(stage,shelf)
        shot(stage,'shelf-1024')
        shelf.sleeve_key.grab_focus()
        assert f.key(stage.window,'Return')
        inspector=shelf.inspector
        wait(lambda:shelf.inspector_open and inspector.canvas.get_mapped())
        assert stage.window.get_size()==(1024,600)
        fits(stage,[inspector.canvas,inspector.close_button,inspector.front_button,inspector.back_button,
                    inspector.disc_button,stage.console,stage.knob])
        assert inspector.canvas.face=='front'
        shot(stage,'shelf-sleeve-1024')
        settings=stage.window.get_settings()
        animations=settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations',False)
        try:
            inspector.back_button.clicked()
            assert inspector.canvas.face=='back' and inspector.canvas.angle==inspector.canvas.target
        finally:
            settings.set_property('gtk-enable-animations',animations)
        inspector.close_button.clicked()
        wait(lambda:not shelf.inspector_open and shelf.play_key.get_mapped())
        assert stage.window.get_focus() is shelf.sleeve_key
        normal_book=service.book
        normal_queue=list(normal_book.upcoming('spotify'))
        shelf.play_key.clicked()
        wait(lambda:service.album_listening and not service.loading)
        stage.update()
        assert service.album_title==shelf.current['title']
        assert stage.album_mode.get_mapped()
        assert not stage.progress.get_sensitive() and not stage.next_button.get_sensitive()
        assert [item['id'] for item in service.book.queues['spotify']]==['A','B','C','D']
        before=list(host.calls)
        stage.request_seek(30);stage.action('next')
        assert host.calls==before and service.book.indices['spotify']==0
        stage.hide()
        assert service.book.active=='spotify','Leaving fullscreen must preserve queue playback'
        service.exit_album()
        assert service.book is normal_book and normal_book.upcoming('spotify')==normal_queue
        stage.close()
        assert service.closed
        print('PASS fullscreen collection, responsive album loading, in-player search, queue edits/playback and source isolation')
    finally:
        release.set();stage.close();host.window.destroy()
