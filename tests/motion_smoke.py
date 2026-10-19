"""Decode an original local cover loop in GTK, with no network or audio output."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
from motion_artwork import MotionCover


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
print('PASS original silent cover loop, decoded frames, rounded corners, pause, resume and nonblocking cleanup')
