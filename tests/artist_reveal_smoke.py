"""Real artist entrance: GPU layers, transport, cancellation and plain fallback."""
import os,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import fullscreen_smoke as f
import fullscreen,artist_reveal


def settle(seconds=.03):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        # A software GL paint can take longer than a frame. Keep test deadlines
        # bounded even while the frame clock has another paint ready.
        for _ in range(8):
            if not f.GLib.MainContext.default().pending():break
            f.GLib.MainContext.default().iteration(False)
        time.sleep(.003)


def wait(predicate,limit=5):
    until=time.monotonic()+limit
    while not predicate() and time.monotonic()<until:settle()
    assert predicate(),'Artist entrance did not settle'


def load(_source,_category,term='',collection=None,offset=0):
    image=(f.ROOT/'assets/demo-cover.png').as_uri()
    return {'artist':{'id':'fixture','name':'Solstice','image':image,'genres':['Ambient soul']},
        'sections':[{'id':'albums','items':[{'id':'release','uri':'spotify:album:release','title':'Afterglow','image':image}]},
                    {'id':'top-songs','items':[{'id':'track','uri':'spotify:track:track','title':'Afterglow','artist':'Solstice','image':image}]}]}


host=f.FixtureHost();host.youtube=SimpleNamespace(queue=[],current=None,eof=False,paused=True,mpv=None)
real_image_load=fullscreen.Artwork.load
def local_artwork(loader,image,url,size,radius=8,**options):
    return real_image_load(loader,image,(f.ROOT/'assets/demo-cover.png').as_uri(),size,radius,**options)

with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected network access')),\
     patch.object(fullscreen,'LyricsClient',f.FixtureLyrics),patch.object(fullscreen.Artwork,'load',local_artwork):
    stage=fullscreen.FullscreenPlayer(host);view=stage.artist_view;entrance=view.entrance
    stage.music.repository.load=load
    settings=stage.window.get_settings();animations=settings.get_property('gtk-enable-animations')
    try:
        stage.open();wait(lambda:not stage.reveal.active)
        stage.window.unfullscreen();stage.window.resize(1920,1080);settle(.15)
        entrance.failed=False;entrance.warmup(allow_software=True)
        assert entrance.driver,'The isolated GL smoke test requires Mesa software GL'
        preview=os.environ.get('EMBERBOX_ARTIST_REVEAL_PREVIEW');shots=[]
        def shot(name):
            folder=Path(preview);folder.mkdir(exist_ok=True,parents=True)
            w,h=stage.window.get_size()
            f.Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,w,h).savev(str(folder/(name+'.png')),'png',[],[])
        def after_paint(*_args):
            if preview and entrance.active and len(shots)<3 and entrance.progress>=(.2,.5,.8)[len(shots)]:
                shots.append(entrance.progress);shot('artist-opening-'+str(len(shots)))
        stage.window.get_frame_clock().connect('after-paint',after_paint)
        frames=[];captures=[];original=entrance.driver.draw_artist
        def draw(*args):
            frames.append((args[-1],view.scroll.get_mapped(),id(args[2]),id(args[3]),id(args[4])))
            return original(*args)
        entrance.driver.draw_artist=draw
        real_snapshot=artist_reveal.snapshot
        def capture(*args):
            captures.append(time.monotonic());return real_snapshot(*args)
        with patch.object(artist_reveal,'snapshot',capture):
            stage.open_artist();wait(lambda:entrance.active)
            assert view.hero_banner.atmosphere and entrance.frame
            assert (entrance.pixels.get_width(),entrance.pixels.get_height())==entrance.hero[2:],\
                'Do not stretch the narrower loading-page portrait into the final masthead'
            assert stage.layout.get_mapped() and not view.scroll.get_mapped()
            stage.play_button.clicked();assert host.calls[-1]==('spotify','toggle')
            frame=entrance.frame;view.render()
            assert view.render_queued and entrance.frame is frame,'Catalogue arrivals must not rebuild a running entrance'
            settle(.16)
            wait(lambda:not entrance.busy)
        assert len(frames)>=3 and all(not row[1] for row in frames),frames
        assert all(a[0]<=b[0] for a,b in zip(frames,frames[1:])),frames
        assert len({row[2:] for row in frames})==1,'Upload fixed textures, not new full-page frames on every tick'
        assert len(captures)==2,'Capture loading and destination once, never per frame'
        assert entrance.frame is None and view.scroll.get_mapped() and not entrance.tick
        assert stage.play_button.get_mapped() and host.calls==[('spotify','toggle')]
        if preview:settle(.05);shot('artist-open')

        # Navigation and resize cancel immediately, including before the photo is ready.
        stage.open_artist();wait(lambda:entrance.busy)
        view.back();settle(.05)
        assert stage.page=='playing' and not entrance.busy and not entrance.wait and not entrance.tick
        stage.open_artist();wait(lambda:entrance.active)
        view.resize(1024,600);settle(.05)
        assert not entrance.busy and view.scroll.get_mapped()
        stage.open_artist();wait(lambda:entrance.active)
        host.source='youtube';stage.update();settle(.05)
        assert not entrance.busy or view.source=='youtube'
        view.cancel_intro();assert entrance.frame is None
        host.source='spotify';stage.update()

        # Reduced motion opens the live page immediately without snapshots/ticks.
        settings.set_property('gtk-enable-animations',False)
        stage.open_artist();wait(lambda:view.profile is not None)
        assert not entrance.busy and not entrance.tick and view.scroll.get_mapped()
        settings.set_property('gtk-enable-animations',True)

        # A shader failure hands off to the live controls instead of stranding a frame.
        stage.open_artist();wait(lambda:entrance.active)
        with patch.object(entrance.driver,'draw_artist',side_effect=RuntimeError('fixture context lost')):
            entrance.area.queue_render();wait(lambda:not entrance.busy)
        assert view.scroll.get_mapped() and entrance.frame is None

        # Exercise the short single-image fallback without a GL context.
        entrance.release(entrance.area);entrance.failed=True
        stage.open_artist();wait(lambda:entrance.active)
        assert entrance.driver is None and entrance.hold.get_visible()
        stage.next_button.clicked();assert host.calls[-1]==('spotify','next')
        wait(lambda:not entrance.busy)
        stage.open_artist();wait(lambda:entrance.busy);stage.hide()
        assert not entrance.busy and entrance.frame is None and not entrance.wait and not entrance.tick
        print('PASS layered GPU artist entrance, fixed textures, no live page paints, transport, deferred catalogue, cancel, resize, source change, reduced motion, lost context and cached fade')
    finally:
        settings.set_property('gtk-enable-animations',animations)
        stage.close();host.window.destroy()
