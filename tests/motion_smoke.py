"""Decode an original local cover loop in GTK, with no network or audio output."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit,unquote
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
gi.require_version('Gdk','3.0')
from gi.repository import Gdk,Gtk,GLib
from motion_artwork import MotionCover
from motion_surface import MotionSurface
from motion_cache import cached_clip


def settle(predicate, timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        if predicate():return True
        time.sleep(.01)
    return False


with tempfile.TemporaryDirectory(prefix='ember-motion-fixture-') as folder:
    path=Path(folder)/'original-loop.mp4'
    assert shutil.which('ffmpeg'),'Install ffmpeg to run this check'
    subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-filter_threads','1',
        '-f','lavfi','-i','testsrc2=size=96x96:rate=30','-t','0.8',
        '-an','-c:v','mpeg4','-threads','1','-y',str(path)],check=True,timeout=10)
    # Exercise the real remux/cache command against our own file. Only its
    # network input is substituted, so this test never reads a music account.
    popen=subprocess.Popen
    def local_remux(command,**options):
        command=list(command)
        command[command.index('-i')+1]=path.as_uri()
        command[command.index('-protocol_whitelist')+1]='file'
        return popen(command,**options)
    with patch('motion_cache.subprocess.Popen',side_effect=local_remux):
        prepared=cached_clip('ffmpeg','https://mvod.itunes.apple.com/fixture/loop.mp4',
                             threading.Event(),lambda _:None,Path(folder)/'cache')
    assert prepared,'Real silent clip preparation failed'
    path=Path(unquote(urlsplit(prepared).path))
    window=Gtk.Window();image=Gtk.Image();window.add(image);window.show_all()
    cover=MotionCover(image)
    with patch('motion_artwork.is_motion_url',lambda url:url==path.as_uri()):
        cover.set_source(path.as_uri(),160)
        run=cover.run
        assert run
        def painted():
            cover.tick()
            return cover.frames>3
        try:
            assert settle(painted),'Animated cover never produced frames'
            first=bytes(image.get_pixbuf().get_pixels())
            initial=cover.frames
            assert settle(lambda:(cover.tick(),cover.frames>initial+30)[1]),'Video did not loop past its duration'
            assert first!=bytes(image.get_pixbuf().get_pixels()),'Cover stayed on its first frame'
            assert image.get_pixbuf().get_pixels()[3]==0,'Rounded glass corners were lost'
            assert '-an' in run.process.args and run.process.args.count('-map')==1
            cover.set_playing(False)
            frozen=bytes(image.get_pixbuf().get_pixels())
            settle(lambda:False,.2);cover.tick()
            assert frozen==bytes(image.get_pixbuf().get_pixels()),'Paused track still animated'
            cover.set_playing(True)
            initial=cover.frames
            assert settle(lambda:(cover.tick(),cover.frames>initial+2)[1]),'Loop failed to resume'
            started=time.monotonic();cover.stop()
            assert time.monotonic()-started<.1,'GTK waited for the video process'
            assert not image.get_visible() and cover.run is None
            assert settle(lambda:run.finished),'Decoder did not stop'
            assert run.process.poll() is not None,'Video process leaked'
            cover.set_source('https://example.invalid/not-artwork.mp4',160)
            assert cover.run is None,'Untrusted video was accepted'
        finally:cover.stop();window.destroy()
        surface=MotionSurface();surface.resize(320)
        window=Gtk.Window();window.add(surface);window.show_all()
        surface.warmup()
        if not surface.driver:
            surface.failed=False;surface.warmup(allow_software=True)
        cover=MotionCover(surface)
        tick=window.add_tick_callback(lambda _window,clock:(cover.tick(clock.get_frame_time()/1e6),True)[1])
        try:
            cover.set_source(path.as_uri(),320)
            assert settle(lambda:cover.frames>8),'Display clock did not present the prepared frames'
            run=cover.run;allocations=[]
            surface.connect('size-allocate',lambda *_args:allocations.append(1))
            first=cover.frames
            assert settle(lambda:cover.frames>first+40),'Display-paced loop stopped'
            assert run.queue.rebuffers==0,'Local loops must decode ahead of presentation'
            assert len(run.queue.frames)<=run.queue.capacity
            assert '-re' not in run.process.args,'Network/decoder pacing must not set presentation time'
            if surface.driver:
                assert surface.area.get_mapped() and not surface.still.get_visible()
                assert len(allocations)<=2,'Motion frames must not reallocate the GTK layout'
                rendered=Gdk.pixbuf_get_from_window(window.get_window(),10,10,280,280).get_pixels()
                assert max(rendered)-min(rendered)>100,'The GPU layer rendered an empty cover'
            cover.set_source(path.as_uri(),240)
            assert cover.run is run,'Resizing artwork must preserve the running loop'
            window.resize(240,240)
            assert settle(lambda:surface.get_allocated_width()==240)
            cover.set_playing(False);paused=cover.frames
            settle(lambda:False,.15)
            assert cover.frames==paused
            cover.set_playing(True)
            assert settle(lambda:cover.frames>paused+3)
        finally:
            window.remove_tick_callback(tick);cover.stop();window.destroy()
            assert settle(lambda:run.finished),'Buffered decoder leaked after cleanup'
print('PASS silent 60fps loop, bounded preroll, display pacing, stable GPU layout, resize, pause/resume and cleanup')
