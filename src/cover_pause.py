"""A finite optical pause: a wave packet and a critically damped cover socket.

No transport commands, decoding, image resizing or GTK layout work per frame.
The paused image is static after settling; animated artwork supplies one held
frame. Cairo draws one cached print; the settled pose is a plain GTK image.
"""
import math
import weakref
import numpy as np
from PIL import Image,ImageDraw
from gi.repository import GdkPixbuf,GLib,Gtk
from cover_pause_paint import CoverPainter


def spring(value,velocity,target,seconds):
    rate=7.4
    offset=value-target;momentum=velocity+rate*offset;decay=math.exp(-rate*seconds)
    return target+(offset+momentum*seconds)*decay,(velocity-rate*momentum*seconds)*decay


def cover_frames(pixels,size,radius):
    raw,width,height,alpha,stride=pixels
    mode='RGBA' if alpha else 'RGB'
    source=Image.frombytes(mode,(width,height),raw,'raw',mode,stride).convert('RGBA')
    source=source.resize((size,size),Image.Resampling.LANCZOS)
    mask=Image.new('L',(size,size));ImageDraw.Draw(mask).rounded_rectangle((0,0,size-1,size-1),radius,fill=255)
    source.putalpha(Image.fromarray(np.minimum(np.asarray(source.getchannel('A')),np.asarray(mask))))
    pressed=Image.new('RGBA',(size,size),(19,23,19,255))
    inset=max(1,round(size*.021));top=inset+max(1,round(size*.003));span=size-2*inset
    art=source.resize((span,span),Image.Resampling.LANCZOS)
    pressed.alpha_composite(art,(inset,top))
    shadow=np.zeros((size,size,4),dtype=np.uint8)
    shadow[...,3]=(np.exp(-np.arange(size)[:,None]/max(4,size*.025))*55).astype(np.uint8)
    pressed.alpha_composite(Image.fromarray(shadow,'RGBA'));pressed.putalpha(mask)
    rgba=np.asarray(source,dtype=np.uint16)
    bgra=np.empty((size,size,4),dtype=np.uint8)
    bgra[...,:3]=((rgba[...,[2,1,0]]*rgba[...,3:4]+127)//255).astype(np.uint8)
    bgra[...,3]=rgba[...,3]
    return source.tobytes(),pressed.tobytes(),bgra.tobytes()


class CoverPause(Gtk.Overlay):
    WAVE_SECONDS=1.7

    def __init__(self,pool):
        super().__init__()
        self.pool=pool;self.frame_job=None;self.frame_key=None;self.frame_serial=0
        self.still=Gtk.Image();self.add(self.still)
        self.rest_image=Gtk.Image();self.add_overlay(self.rest_image)
        self.set_overlay_pass_through(self.rest_image,True)
        self.canvas=Gtk.DrawingArea();self.canvas.set_no_show_all(True)
        self.add_overlay(self.canvas);self.set_overlay_pass_through(self.canvas,True)
        self.painter=CoverPainter(self.canvas,self)
        self.connect('unmap',lambda *_:self.reset())
        self.connect('destroy',self.close)
        self.set_no_show_all(True);self.set_halign(Gtk.Align.FILL);self.set_valign(Gtk.Align.FILL)
        self.size=112;self.radius=13;self.closed=False
        self.pixels=None;self.key=self.playing=None
        self.depth=self.velocity=0.;self.target=0.;self.wave=self.WAVE_SECONDS
        self.last_now=None;self.wall_start=None;self.tick=0;self.age=0.

    def resize(self,size,radius=22):
        if (size,radius)==(self.size,self.radius):return
        self.size,self.radius=size,radius
        self.set_size_request(size,size);self.still.set_size_request(size,size);self.canvas.set_size_request(size,size)
        if self.get_visible():
            self.still.clear();self.rest_image.clear();self.painter.clear()
            self.prepare_frames()

    def sync(self,playing,pixels,key,*,blocked=False):
        if self.closed:return
        parent=self.get_parent()
        if blocked or pixels is None or not parent or not parent.get_mapped():self.reset();return
        if not self.get_settings().get_property('gtk-enable-animations'):self.reset();return
        playing=bool(playing)
        initial=self.key is None or key!=self.key
        changed=not initial and self.playing!=playing
        if initial:
            self.reset();self.key=key;self.playing=playing
            if playing:return
            self.depth=self.target=1.;self.set_pixels(pixels);self.present_frame();return
        self.playing=playing
        if not changed:
            if not playing and pixels is not self.pixels:
                self.set_pixels(pixels);self.queue_frame()
            return
        self.target=0. if playing else 1.
        self.set_pixels(pixels)
        # Reversing direction preserves depth and velocity. A rapid second
        # pause does not stack another loop or restart from an endpoint.
        self.wave=0.;self.age=0.;self.wall_start=None;self.present_frame()
        if not self.tick:self.last_now=None;self.tick=self.add_tick_callback(self.advance)

    def set_pixels(self,pixels):
        if pixels is self.pixels:return
        self.pixels=pixels
        self.prepare_frames()

    def prepare_frames(self):
        if self.pixels is None:return
        key=(id(self.pixels),self.size,self.radius)
        if key==self.frame_key:return
        self.frame_key=key
        self.frame_serial+=1;serial=self.frame_serial
        if self.frame_job:self.frame_job.cancel()
        p=self.pixels
        data=(bytes(p.get_pixels()),p.get_width(),p.get_height(),p.get_has_alpha(),p.get_rowstride())
        try:future=self.pool.submit(cover_frames,data,self.size,self.radius)
        except RuntimeError:return
        self.frame_job=future;owner=weakref.ref(self)
        def done(result):
            try:frames=result.result()
            except Exception:return
            def apply():
                target=owner()
                if target is None or target.closed or target.frame_key!=key or target.frame_serial!=serial:return False
                target.frame_job=None
                for image,raw in zip((target.still,target.rest_image),frames):
                    image.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(raw),
                        GdkPixbuf.Colorspace.RGB,True,8,key[1],key[1],key[1]*4))
                try:target.painter.set_frame(frames[2],key[1])
                except (RuntimeError,ValueError):target.reset();return False
                target.queue_frame();return False
            GLib.idle_add(apply)
        future.add_done_callback(done)

    def present_frame(self):
        self.still.show();self.rest_image.hide();self.canvas.show();self.show();self.queue_frame()

    def queue_frame(self):
        if self.depth==1 and self.target==1 and self.wave>=self.WAVE_SECONDS and not self.tick and self.rest_image.get_pixbuf():
            self.canvas.hide();self.rest_image.set_opacity(1);self.rest_image.show()
        else:self.rest_image.hide();self.canvas.show();self.canvas.queue_draw()

    def advance(self,_widget,clock):
        if self.closed or not self.get_mapped() or not self.get_settings().get_property('gtk-enable-animations'):
            self.tick=0;self.reset();return False
        now=clock.get_frame_time() if clock else GLib.get_monotonic_time()
        wall=GLib.get_monotonic_time()
        if self.wall_start is None:self.wall_start=wall
        dt=max(0,min(.08,(now-self.last_now)/1e6)) if self.last_now is not None else 0.
        self.last_now=max(now,self.last_now or now);self.age+=dt;self.wave+=dt
        self.depth,self.velocity=spring(self.depth,self.velocity,self.target,dt)
        settled=abs(self.depth-self.target)<.0004 and abs(self.velocity)<.003
        # A slow software compositor must not stretch a decorative packet
        # into an endless loop. Normal display pacing uses only the frame clock.
        if (self.wave>=self.WAVE_SECONDS and settled) or wall-self.wall_start>=2_600_000:
            self.depth=self.target;self.velocity=0.;self.wave=self.WAVE_SECONDS
            self.tick=0;self.last_now=self.wall_start=None
            if not self.target:self.reset()
            else:self.queue_frame()
            return False
        self.queue_frame();return True

    def reset(self):
        if self.key is None and self.pixels is None and not self.tick and not self.get_visible():return
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.pixels=None;self.key=self.playing=None
        if self.frame_job:self.frame_job.cancel();self.frame_job=None
        self.frame_key=None;self.still.clear();self.rest_image.clear()
        self.frame_serial+=1
        self.depth=self.velocity=self.target=0.;self.wave=self.WAVE_SECONDS;self.age=0.;self.last_now=self.wall_start=None
        self.hide()
        self.painter.clear()

    def close(self,*_):
        if self.closed:return
        self.reset();self.closed=True;self.painter.close()
