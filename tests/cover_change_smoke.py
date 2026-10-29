"""A delayed track changes the real fullscreen artwork without delaying transport."""
import os
import time
from pathlib import Path
from unittest.mock import patch
import fullscreen_smoke as fixture
import fullscreen
from gi.repository import Gdk,GdkPixbuf
from gi.repository import GLib
from PIL import Image,ImageDraw


def settle(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        for _ in range(2):
            if not GLib.MainContext.default().pending():break
            GLib.MainContext.default().iteration(False)
        time.sleep(.002)


host=fixture.FixtureHost()
host.source='apple-music'
host.apple_web.state={'id':'old','spatial':{'enabled':True,'phase':'playing','switching':False}}
host.art_url='fixture:old'
deferred=[]


def load(loader,image,url,size,radius=8,preserve=False,on_loaded=None,**options):
    if image is stage.cover and url=='fixture:new':
        deferred.append((image,size,on_loaded));return
    fixture.image_load(loader,image,url,size,radius,preserve,on_loaded,**options)


with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network')),\
     patch.object(fullscreen,'LyricsClient',fixture.FixtureLyrics),\
     patch.object(fullscreen.Artwork,'load',fixture.image_load):
    stage=fullscreen.FullscreenPlayer(host);host.fullscreen=stage
    try:
        stage.prewarm();stage.open();fixture.wait_transition(stage)
        surface=stage.cover_change.surface
        if surface.failed:surface.failed=False
        surface.warmup(allow_software=True)
        assert surface.driver,'The fixture needs Mesa for the real cover overlay'
        stage.cover_change.reset();stage.update();settle(.15)
        old=stage.cover.get_pixbuf()
        commands=list(host.calls)
        stage.next_button.clicked()
        assert host.calls==commands+[('apple-music','next')]
        assert surface.active and surface.old is old,'The ripple must begin inside the click, before metadata changes'
        settle(.25)
        assert surface.progress==0 and surface.age>0,('A slow response should keep the outgoing artwork alive',surface.active,surface.age,surface.progress,surface.get_mapped(),stage.cover_change.pending,stage.visible,stage.page)
        host.apple_web.state={'id':'new','spatial':{'enabled':True,'phase':'preparing','switching':True}}
        host.title.set_text('Another original evening');host.art_url='fixture:new'
        with patch.object(fullscreen.Artwork,'load',load):stage.update()
        assert deferred and stage.cover_change.confirmed
        settle(.2)
        assert surface.progress==0,'playing=True during native preparation must not finish the cover transition'
        image,size,callback=deferred[-1]
        rgba=Image.new('RGBA',(size,size))
        ImageDraw.Draw(rgba).rounded_rectangle((0,0,size-1,size-1),22,fill='#51928b')
        new=GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgba.tobytes()),GdkPixbuf.Colorspace.RGB,True,8,size,size,size*4)
        image.set_from_pixbuf(new);callback(new)
        settle(.15)
        assert surface.new is new and surface.progress==0,'An image response alone must not claim playback is ready'
        host.apple_web.state['spatial'].update(phase='playing',switching=False)
        stage.update()
        until=time.monotonic()+4
        while surface.progress<.35 and surface.active and time.monotonic()<until:settle(.02)
        assert 0<surface.progress<1 and surface.get_mapped(),'The incoming artwork needs a real intermediate wave frame'
        if os.environ.get('EMBERBOX_RIPPLE_PREVIEW'):
            folder=Path(os.environ['EMBERBOX_RIPPLE_PREVIEW']);folder.mkdir(parents=True,exist_ok=True)
            width,height=stage.window.get_size()
            pixels=Gdk.pixbuf_get_from_window(stage.window.get_window(),0,0,width,height)
            pixels.savev(str(folder/'fullscreen-ripple.png'),'png',[],[])
        until=time.monotonic()+4
        while surface.active and time.monotonic()<until:settle(.05)
        stage.update()
        assert not surface.active and not surface.tick and not surface.get_visible()
        assert not stage.cover_change.pending and stage.cover.get_pixbuf() is new
        assert host.calls==commands+[('apple-music','next')],'The visual must not play, seek, pause or repeat the request'
        stage.next_button.clicked();settle(.1)
        assert surface.active
        held=surface.old
        image.set_from_pixbuf(old)
        stage.dismiss()
        assert stage.reveal.cover_pixels is held,'Collapsing must use the artwork visible above the incoming image'
        fixture.wait_transition(stage)
        settle(.1)
        assert not surface.tick and surface.old is None and surface.new is None
        assert surface.driver.uploaded is None and surface.driver.room_uploaded is None
        print('PASS fullscreen ripple: immediate request, delayed native readiness and artwork, real intermediate frame, exact cover, unchanged transport and hide cleanup')
    finally:
        stage.close();host.window.destroy()
