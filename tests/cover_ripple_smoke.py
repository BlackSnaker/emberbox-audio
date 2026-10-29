"""Offline GTK lifecycle checks for the cover-local playback transition.

Run on an isolated X display. Mesa is explicitly allowed here; neither playback,
the user's desktop, network access nor account profiles are involved.
"""
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import gi
gi.require_version('Gtk','3.0')
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf,GLib,Gtk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import cover_ripple


SIZE=144


def pixels(colour):
    image=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,True,8,SIZE,SIZE)
    image.fill(colour)
    return image


def settle(seconds=.025):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        # A live frame clock can always have another event ready. Bound each
        # drain so test deadlines do not depend on emptying its event queue.
        for _ in range(8):
            if not GLib.MainContext.default().pending():break
            GLib.MainContext.default().iteration(False)
        time.sleep(.002)


def wait(predicate,message,limit=4):
    deadline=time.monotonic()+limit
    while not predicate() and time.monotonic()<deadline:settle(.012)
    assert predicate(),message


class Rig:
    def __init__(self):
        self.window=Gtk.Window(title='Ember cover · isolated lifecycle fixture')
        self.window.set_decorated(False);self.window.set_resizable(False)
        self.window.set_default_size(SIZE,SIZE)
        self.overlay=Gtk.Overlay();self.window.add(self.overlay)
        self.backdrop=Gtk.Image.new_from_pixbuf(pixels(0x28352bff))
        self.overlay.add(self.backdrop)
        self.surface=cover_ripple.CoverRipple();self.surface.resize(SIZE,18)
        self.surface.REVEAL=.20
        self.overlay.add_overlay(self.surface)
        self.overlay.set_overlay_pass_through(self.surface,True)
        self.window.show_all()
        wait(self.window.get_mapped,'The isolated fixture window did not map')

    def close(self):self.window.destroy();settle(.015)


def idle(surface):
    assert not surface.active and not surface.tick and not surface.get_visible(),\
        'A completed or cancelled cover must be hidden with no frame-clock callback'
    assert surface.old is None and surface.new is None and surface.get_pixbuf() is None
    assert surface.old_image.get_pixbuf() is None and surface.new_image.get_pixbuf() is None
    assert surface.last_now is None and surface.wait_start is None and surface.reveal_start is None
    assert not surface.ready and surface.age==0 and surface.progress==0
    if surface.driver:
        assert surface.driver.uploaded is None and surface.driver.room_uploaded is None,\
            'Hidden covers must release CPU artwork snapshots, retaining only bounded GL storage'


old,new,third=pixels(0x9f533aff),pixels(0x3e7862ff),pixels(0x7287a3ff)
settings=Gtk.Settings.get_default()
animations=settings.get_property('gtk-enable-animations')
settings.set_property('gtk-enable-animations',True)
rigs=[]
try:
    with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network access')):
        # Exercise a real unavailable-driver path rather than substituting a
        # mock renderer. GTK's two image layers provide the compositor fallback.
        fallback=Rig();rigs.append(fallback);surface=fallback.surface
        with patch.object(cover_ripple,'CoverRippleGL',side_effect=RuntimeError('Isolated unavailable GL fixture')):
            surface.warmup()
        assert surface.failed and surface.driver is None
        assert surface.begin(old) and surface.tick
        wait(surface.get_mapped,'The waiting cover did not appear')
        surface.supply(new);fallback.backdrop.set_from_pixbuf(new)
        settle(.28)
        assert surface.active and surface.progress==0 and surface.get_pixbuf() is old,\
            'Artwork arrival alone must not pretend playback is ready'
        assert surface.old_image.get_mapped() and surface.new_image.get_opacity()==0
        assert not surface.area.get_mapped(),'The failed GLArea must remain hidden'
        surface.resolve()
        wait(lambda:surface.progress>.05,'The compositor reveal did not start')
        assert 0<surface.progress<1 and 0<surface.new_image.get_opacity()<1
        assert abs(surface.new_image.get_opacity()-surface.progress)<.012
        wait(lambda:not surface.active,'The compositor reveal did not complete')
        idle(surface)

        # A new manual selection cancels the previous reveal and starts from its
        # chosen visible artwork; stale incoming metadata must not survive it.
        assert surface.begin(old)
        surface.supply(new);surface.resolve()
        wait(lambda:surface.progress>.55,'The first retarget fixture did not reach its new cover')
        snapshot=surface.get_pixbuf();assert snapshot is new
        assert surface.begin(snapshot)
        assert surface.old is snapshot and surface.new is None and not surface.ready
        assert surface.progress==0 and surface.age==0
        settle(.08)
        assert surface.active and surface.get_pixbuf() is snapshot and surface.progress==0
        surface.supply(third);surface.resolve()
        wait(lambda:not surface.active,'The retargeted compositor reveal did not complete')
        idle(surface)

        assert surface.begin(old)
        fallback.window.hide();settle(.025);idle(surface)
        fallback.window.show_all();settle(.025)
        assert surface.begin(new)
        surface.MAX_WAIT=.04
        wait(lambda:not surface.active,'A stalled track preparation did not relinquish its overlay')
        idle(surface)

        assert surface.begin(old)
        surface.close();idle(surface)
        assert surface.closed and not surface.begin(new),'A closed transition must not reactivate'

        # Warm the actual OpenGL renderer on Mesa and reuse it across waiting,
        # readiness, cancellation and later transitions. No mock GL calls here.
        gpu=Rig();rigs.append(gpu);surface=gpu.surface
        surface.warmup(allow_software=True)
        assert surface.driver is not None and not surface.failed,\
            'The isolated GL lifecycle check requires a working Mesa context'
        driver=surface.driver;program=driver.program
        textures=(driver.texture,driver.room_texture,driver.previous_texture)
        draws=[];draw=driver.draw
        def traced_draw(*args):
            draws.append((args[0],args[1],args[-1],args[2],args[3]))
            return draw(*args)
        driver.draw=traced_draw
        assert surface.begin(old)
        wait(lambda:len(draws)>1,'The GL waiting cover did not render')
        assert surface.area.get_mapped() and not surface.old_image.get_mapped()
        scale=surface.area.get_scale_factor()
        assert scale==int(os.environ.get('GDK_SCALE','1'))
        assert all((row[0],row[1])==(SIZE*scale,SIZE*scale) for row in draws),\
            'The ripple viewport must use physical dimensions on HiDPI displays'
        assert all(row[2]==18*scale for row in draws),\
            'Rounded optical corners must scale with the physical viewport'
        surface.supply(new);gpu.backdrop.set_from_pixbuf(new)
        settle(.26)
        assert surface.active and surface.progress==0 and surface.get_pixbuf() is old
        surface.resolve()
        wait(lambda:.05<surface.progress<.95,'The GL reveal skipped its intermediate state')
        assert surface.active and driver.room_uploaded is new
        wait(lambda:not surface.active,'The GL reveal did not complete')
        idle(surface)
        assert surface.driver is driver and driver.program==program
        assert textures==(driver.texture,driver.room_texture,driver.previous_texture),\
            'Settling a transition must not rebuild its bounded GPU storage'

        assert surface.begin(old)
        surface.supply(new);surface.resolve()
        wait(lambda:surface.progress>.55,'The GPU retarget fixture did not progress')
        snapshot=surface.get_pixbuf();assert snapshot is new
        assert surface.begin(snapshot)
        assert surface.new is None and not surface.ready and surface.progress==0
        assert driver.uploaded is None and driver.room_uploaded is None
        surface.supply(third)
        wait(lambda:driver.uploaded is snapshot and driver.room_uploaded is third,\
             'A rapid GPU retarget retained the wrong source texture identity')
        surface.cancel();idle(surface)
        assert surface.driver is driver and driver.program==program

        # A long frame must not jump an entire reveal after a short UI stall.
        assert surface.begin(old)
        wait(lambda:surface.last_now is not None,'The frame-clock fixture did not tick')
        previous=surface.age
        surface.last_now=GLib.get_monotonic_time()-2_000_000
        surface.advance(surface,None)
        assert 0<=surface.age-previous<=.050001,'A UI stall must clamp its animation time step'
        surface.cancel();idle(surface)

        assert surface.begin(old)
        gpu.window.hide();settle(.025);idle(surface)
        assert surface.driver is driver,'Unmapping should retain reusable GPU resources'
        gpu.window.show_all();settle(.025)
        assert surface.begin(new)
        settings.set_property('gtk-enable-animations',False)
        wait(lambda:not surface.active,'Disabling animations did not cancel the active transition')
        idle(surface)
        assert not surface.begin(old) and not surface.tick,\
            'Reduced motion must show the live cover immediately, without a waiting overlay'

        reduced=Rig();rigs.append(reduced)
        with patch.object(cover_ripple,'CoverRippleGL',side_effect=AssertionError('Reduced motion compiled a shader')):
            reduced.surface.warmup(allow_software=True)
        assert reduced.surface.driver is None and not reduced.surface.failed
        assert not reduced.surface.begin(new);idle(reduced.surface)
        settings.set_property('gtk-enable-animations',True)

        assert surface.begin(old)
        gpu.window.destroy();settle(.025)
        assert surface.closed and surface.driver is None
        idle(surface)
        assert driver.program==0 and driver.texture==0 and driver.room_texture==0,\
            'Destroying the transition must release its GL renderer with the context current'
        assert driver.uploaded is None and driver.room_uploaded is None
        print('PASS cover ripple GTK: pending hold, readiness reveal, retarget, cancellation, timeout, reduced motion, compositor fallback, real reusable GL and HiDPI scale='+str(scale))
finally:
    settings.set_property('gtk-enable-animations',animations)
    for rig in rigs:rig.close()
