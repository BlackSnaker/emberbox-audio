"""Offline, real-framebuffer checks for the cover's liquid transition.

Run under an isolated X display with Mesa enabled. No desktop windows, account
profiles, audio, or network media are used; both covers are generated here.
"""
import ctypes as C
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, GLib, Gtk
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from cover_ripple_gl import CoverRippleGL
from cover_ripple import CoverRipple,smooth


SIZE=320


def fixture(variant):
    """Opaque original artwork with enough detail to expose optical movement."""
    y,x=np.mgrid[:SIZE,:SIZE]
    rings=((np.sqrt((x-SIZE*.5)**2+(y-SIZE*.5)**2)//11)%2)*30
    stripes=((x//9+y//13)%2)*45
    if variant:
        rgb=np.stack((35+x//4,95+y//4,175+stripes//2-rings),axis=-1)
    else:
        rgb=np.stack((145+stripes,45+x//5,30+y//5+rings),axis=-1)
    rgba=np.concatenate((np.clip(rgb,0,255).astype(np.uint8),
                         np.full((SIZE,SIZE,1),255,dtype=np.uint8)),axis=-1)
    pixels=GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgba.tobytes()),
        GdkPixbuf.Colorspace.RGB,True,8,SIZE,SIZE,SIZE*4)
    return pixels,rgba


def settle(predicate,limit=5):
    deadline=time.monotonic()+limit
    while not predicate() and time.monotonic()<deadline:
        for _ in range(12):
            if not GLib.MainContext.default().pending():break
            GLib.MainContext.default().iteration(False)
        time.sleep(.002)
    assert predicate(),'The isolated GL frame did not arrive'


class Frames:
    def __init__(self):
        self.window=Gtk.Window(title='Ember ripple · isolated fixture')
        self.window.set_decorated(False);self.window.set_resizable(False)
        self.area=Gtk.GLArea();self.area.set_required_version(3,2)
        self.area.set_use_es(False);self.area.set_has_alpha(True)
        self.area.set_auto_render(False);self.area.set_size_request(SIZE,SIZE)
        self.window.add(self.area);self.area.connect('render',self.render)
        self.area.connect('unrealize',self.release)
        self.driver=None;self.request=None;self.result=None;self.error=None
        self.serial=0;self.uploads=0;self.released=False
        self.window.show_all()
        settle(lambda:self.area.get_realized())

    def render(self,area,_context):
        try:
            if area.get_error():raise RuntimeError(str(area.get_error()))
            if self.driver is None:
                self.driver=CoverRippleGL(allow_software=True)
                for name in ('TexImage2D','TexSubImage2D'):
                    original=self.driver.functions[name]
                    def upload(*args,_original=original):
                        self.uploads+=1;return _original(*args)
                    self.driver.functions[name]=upload
            if self.request is None:return True
            old,new,age,reveal=self.request
            width=area.get_allocated_width()*area.get_scale_factor()
            height=area.get_allocated_height()*area.get_scale_factor()
            assert (width,height)==(SIZE,SIZE),'Run this fixture with GDK_SCALE=1'
            self.driver.call('Viewport',0,0,width,height)
            self.driver.draw(width,height,old,new,age,reveal,radius=22)
            self.driver.call('Finish')
            read=self.driver.lib.glReadPixels
            read.restype=None
            read.argtypes=[C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p]
            raw=(C.c_ubyte*(width*height*4))()
            read(0,0,width,height,0x1908,0x1401,raw)
            self.result=np.frombuffer(raw,dtype=np.uint8).reshape(height,width,4)[::-1].copy()
        except Exception as error:self.error=error
        finally:self.serial+=1
        return True

    def capture(self,old,new,age=0.,reveal=0.):
        serial=self.serial;self.request=(old,new,age,reveal)
        self.area.queue_render();settle(lambda:self.serial>serial)
        if self.error:raise self.error
        assert self.result is not None
        return self.result.copy()

    def release(self,area):
        if self.driver is not None:
            area.make_current()
            if not area.get_error():self.driver.close()
            self.driver=None
        self.released=True

    def close(self):self.window.destroy()


def screenshot(name,rgba):
    folder=os.environ.get('EMBERBOX_RIPPLE_PREVIEW')
    if not folder:return
    from PIL import Image
    path=Path(folder);path.mkdir(parents=True,exist_ok=True)
    Image.fromarray(rgba,'RGBA').save(path/(name+'.png'))


with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected fixture network access')):
    frames=Frames()
    old,old_rgba=fixture(False);new,new_rgba=fixture(True)
    inside=np.s_[24:-24,24:-24,:]
    try:
        baseline=frames.capture(old,new)
        assert np.max(np.abs(baseline[inside].astype(int)-old_rgba[inside]))<=1,\
            'The request begins on the actual outgoing cover, without a flash'
        assert baseline[SIZE//2,SIZE//2,0]>baseline[SIZE//2,SIZE//2,2]
        assert baseline[0,0,3]==0 and baseline[-1,-1,3]==0,\
            'The GL overlay must leave rounded corners transparent'
        assert 0<baseline[3,11,3]<255 or np.any((baseline[:22,:22,3]>0)&(baseline[:22,:22,3]<255)),\
            'The rounded optical edge needs partial alpha, not a hard staircase'

        # Keeping both sources identical isolates the ripple from the reveal:
        # a flat crossfade would produce the exact same image at every age.
        calm=frames.capture(old,old,0.,0.)
        wave=frames.capture(old,old,.43,0.)
        movement=np.abs(wave[inside].astype(int)-calm[inside].astype(int))[...,:3]
        assert np.count_nonzero(np.max(movement,axis=-1)>3)>250,\
            'A delayed track should show visible optical movement on its cover'
        assert np.count_nonzero(np.max(movement,axis=-1)<=1)>movement.shape[0]*movement.shape[1]*.35,\
            'The wave must remain local rather than flashing the whole cover'
        later=frames.capture(old,old,.68,0.)
        assert np.mean(np.abs(later[inside].astype(int)-wave[inside].astype(int)))>.10,\
            'Concentric wavefronts must travel rather than remain a static ring'

        halfway=frames.capture(old,new,.68,.50)
        final=frames.capture(old,new,.68,1.)
        assert np.mean(np.abs(halfway[inside].astype(int)-calm[inside].astype(int)))>8,\
            'Readiness should reveal the incoming cover before the final frame'
        assert np.mean(np.abs(halfway[inside].astype(int)-final[inside].astype(int)))>8,\
            'The liquid reveal must have a visible intermediate state'
        assert np.max(np.abs(final[inside].astype(int)-new_rgba[inside]))<=1,\
            'The endpoint must retain original artwork colours and sharpness'
        assert final[0,0,3]==0 and final[SIZE//2,SIZE//2,3]==255
        screenshot('outgoing-cover',baseline);screenshot('waiting-wave',wave)
        screenshot('liquid-handover',halfway);screenshot('incoming-cover',final)

        # A broad liquid front must dissolve each point over many display
        # frames. A sharp wipe can pass the endpoint tests yet feel abrupt.
        warm=old.copy();warm.fill(0xc35032ff)
        cool=new.copy();cool.fill(0x2d82aaff)
        steps=[];previous=None
        count=round(CoverRipple.REVEAL*60)+1
        for index in range(count):
            phase=index/(count-1)
            current=frames.capture(warm,cool,.55+phase*CoverRipple.REVEAL,smooth(phase))
            if previous is not None:
                steps.append(np.max(np.abs(current[inside][...,:3].astype(int)-previous[inside][...,:3].astype(int))))
            previous=current
        assert max(steps)<=24,('The incoming image still has a sharp per-frame colour jump',max(steps))
        assert sum(value>1 for value in steps)>count*.45,'The reveal must use its intermediate frames rather than hold then replace'
        frames.capture(old,new,.68,1.)

        # Animation changes uniforms only: uploading a cover every frame would
        # compete with playback and animated artwork on slower machines.
        assert frames.uploads>=2,'Both source textures must reach the real GL driver'
        uploads=frames.uploads
        for age,reveal in ((.85,.55),(1.,.75),(1.2,1.),(3.8,1.)):
            frames.capture(old,new,age,reveal)
        assert frames.uploads==uploads,'Reuse unchanged old/new textures across animation frames'
        replacement=new.copy()
        replacement.fill(0x479d6bff)
        replaced=frames.capture(old,replacement,0.,1.)
        assert frames.uploads==uploads+1,'A new artwork object uploads once, without rebuilding the old texture'
        assert np.max(np.abs(replaced[SIZE//2,SIZE//2].astype(int)-np.array([71,157,107,255])))<=1,\
            'A rapid second selection must not leave the previous incoming cover'

        # No-art and one-art states occur while switching sources or on a
        # metadata error; they must not reuse an unrelated cached texture.
        empty=frames.capture(None,None)
        assert np.max(empty)==0,'Missing artwork must yield a transparent overlay'
        one=frames.capture(None,new,0.,1.)
        assert np.max(np.abs(one[inside].astype(int)-new_rgba[inside]))<=1

        driver=frames.driver
        texture_ids=[driver.texture,driver.room_texture,driver.previous_texture]
        program=driver.program
        is_texture=driver.lib.glIsTexture;is_texture.restype=C.c_ubyte;is_texture.argtypes=[C.c_uint]
        is_program=driver.lib.glIsProgram;is_program.restype=C.c_ubyte;is_program.argtypes=[C.c_uint]
        frames.area.make_current()
        assert is_texture(texture_ids[0]) and is_texture(texture_ids[1]) and is_program(program)
        driver.close();driver.close()
        assert not any(is_texture(value) for value in texture_ids),\
            'Closing the renderer must release all cover texture storage'
        assert not is_program(program),'Closing the renderer must release its shader program'
        assert driver.uploaded is None and driver.room_uploaded is None
        frames.close();settle(lambda:frames.released)
        assert frames.driver is None,'Unrealize must not retain the GL renderer'
        print('PASS ripple framebuffer: original artwork, moving local wave, liquid reveal, exact endpoint, rounded alpha, cached uploads and GPU cleanup')
    finally:frames.close()
