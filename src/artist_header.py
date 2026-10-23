"""A cover-tinted artist masthead, composed off the GTK thread and cached."""
from collections import OrderedDict
import threading
from PIL import Image,ImageOps,ImageFilter,ImageEnhance,ImageDraw
from gi.repository import Gtk,GdkPixbuf,GLib


def compose(pixels,width,height):
    raw,size,alpha,stride=pixels
    photo=Image.frombytes('RGBA' if alpha else 'RGB',size,raw,'raw','RGBA' if alpha else 'RGB',stride).convert('RGB')
    base=ImageOps.fit(photo,(width,height),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(24))
    base=ImageEnhance.Color(base).enhance(.4).convert('RGBA')
    # A clearer portrait on the right fades into the quieter reading area.
    part=min(width,int(height*3.2));portrait=ImageOps.fit(photo,(part,height),Image.Resampling.LANCZOS,centering=(.5,.18))
    fade=Image.linear_gradient('L').rotate(90).resize((part,height))
    fade=fade.point(lambda value:min(255,int(value*1.7)))
    base.paste(portrait,(width-part,0),fade)
    shade=ImageOps.mirror(Image.linear_gradient('L').rotate(90)).resize((width,height)).point(lambda v:55+int(v*.71))
    base=Image.composite(Image.new('RGBA',(width,height),(26,30,22,255)),base,shade)
    warmth=Image.new('RGBA',(width,height),(178,118,34,14));base=Image.alpha_composite(base,warmth)
    mask=Image.new('L',(width,height));ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),26,fill=255)
    base.putalpha(mask)
    return base.tobytes()


class BannerCache:
    def __init__(self,pool):self.pool=pool;self.frames=OrderedDict();self.lock=threading.Lock()
    def get(self,key):
        with self.lock:return self.frames.get(key)
    def put(self,key,value):
        with self.lock:
            self.frames[key]=value;self.frames.move_to_end(key)
            while len(self.frames)>4:self.frames.popitem(last=False)
    def clear(self):
        with self.lock:self.frames.clear()


class ArtistBanner(Gtk.Overlay):
    def __init__(self,content,uri,cache,height):
        super().__init__();self.uri=uri;self.cache=cache;self.pixels=None;self.key=None;self.closed=False
        self.get_style_context().add_class('stage-artist-banner')
        base=Gtk.Box();base.set_size_request(-1,height);self.add(base)
        self.background=Gtk.Image();self.background.set_halign(Gtk.Align.FILL);self.background.set_valign(Gtk.Align.FILL)
        self.add_overlay(self.background);self.set_overlay_pass_through(self.background,True)
        content.get_style_context().add_class('stage-artist-banner-content')
        content.set_valign(Gtk.Align.CENTER);self.add_overlay(content)
        self.source_image=Gtk.Image()
        self.connect('size-allocate',lambda *_:self.render())
        self.connect('destroy',self.close)

    def set_photo(self,pixels):
        if self.closed or not pixels:return
        self.pixels=(bytes(pixels.get_pixels()),(pixels.get_width(),pixels.get_height()),pixels.get_has_alpha(),pixels.get_rowstride())
        self.render()

    def render(self):
        width,height=self.get_allocated_width(),self.get_allocated_height()
        if self.closed or not self.pixels or width<10 or height<10:return
        width=min(3840,width);height=min(600,height)
        key=(self.uri,width,height)
        if key==self.key:return
        self.key=key;cached=self.cache.get(key)
        if cached:self.apply(key,cached);return
        pixels=self.pixels
        future=self.cache.pool.submit(compose,pixels,width,height)
        def done(result):
            try:data=result.result()
            except Exception:return
            self.cache.put(key,data);GLib.idle_add(self.apply,key,data)
        future.add_done_callback(done)

    def apply(self,key,data):
        if not self.closed and self.key==key:
            self.background.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(data),GdkPixbuf.Colorspace.RGB,True,8,key[1],key[2],key[1]*4))
        return False

    def close(self,*_args):
        self.closed=True;self.pixels=None;self.source_image.destroy()
