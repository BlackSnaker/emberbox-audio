"""A cover-tinted artist masthead, composed off the GTK thread and cached."""
from collections import OrderedDict
import threading
from PIL import Image,ImageOps,ImageFilter,ImageEnhance,ImageDraw
from gi.repository import Gtk,GdkPixbuf,GLib


def portrait_slot(width,height):
    """Leave a stable reading area; the photograph fits entirely to its right."""
    return max(48,round(width*(.46 if width>=1200 else .40)))


def portrait_rect(source_size,width,height):
    """Contain the whole photograph in a generous gallery area, not an avatar."""
    slot=portrait_slot(width,height);inset=20
    scale=min(max(1,slot-2*inset)/source_size[0],max(1,height-2*inset)/source_size[1])
    pw,ph=max(1,round(source_size[0]*scale)),max(1,round(source_size[1]*scale))
    return width-slot+(slot-pw)//2,(height-ph)//2,pw,ph


def compose(pixels,width,height):
    raw,size,alpha,stride=pixels
    photo=Image.frombytes('RGBA' if alpha else 'RGB',size,raw,'raw','RGBA' if alpha else 'RGB',stride).convert('RGBA')
    backdrop=Image.new('RGBA',photo.size,(35,41,31,255));backdrop.alpha_composite(photo)
    backdrop=backdrop.convert('RGB')
    base=ImageOps.fit(backdrop,(width,height),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(max(18,min(48,height*.085))))
    base=ImageEnhance.Color(base).enhance(.4).convert('RGBA')
    shade=ImageOps.mirror(Image.linear_gradient('L').rotate(90)).resize((width,height)).point(lambda v:120+int(v*.45))
    base=Image.composite(Image.new('RGBA',(width,height),(26,30,22,255)),base,shade)
    warmth=Image.new('RGBA',(width,height),(178,118,34,10));base=Image.alpha_composite(base,warmth)
    # The background is atmospheric; the actual photo is contained in full,
    # with no face crop, stretching, edge fade or text painted over it.
    x,y,pw,ph=portrait_rect(photo.size,width,height)
    portrait=photo.resize((pw,ph),Image.Resampling.LANCZOS)
    bounds=(x-6,y-6,x+pw+5,y+ph+5)
    shadow=Image.new('RGBA',(width,height));ImageDraw.Draw(shadow).rounded_rectangle(
        tuple(value+(3 if index%2==0 else 4) for index,value in enumerate(bounds)),14,fill=(5,10,6,100))
    base=Image.alpha_composite(base,shadow.filter(ImageFilter.GaussianBlur(10)))
    # A narrow gallery mount and one light edge keep the photograph dominant.
    fw,fh=bounds[2]-bounds[0]+1,bounds[3]-bounds[1]+1
    ramp=Image.blend(Image.linear_gradient('L').resize((fw,fh)),
        ImageOps.mirror(Image.linear_gradient('L').rotate(90)).resize((fw,fh)),.25)
    metal=ImageOps.colorize(ramp,(53,57,46),(27,32,26)).convert('RGBA')
    bezel=Image.new('L',(fw,fh));ImageDraw.Draw(bezel).rounded_rectangle((0,0,fw-1,fh-1),14,fill=255);metal.putalpha(bezel)
    frame=Image.new('RGBA',(width,height));frame.alpha_composite(metal,bounds[:2]);edge=ImageDraw.Draw(frame)
    edge.rounded_rectangle(bounds,14,outline=(226,215,183,42),width=1)
    edge.line((bounds[0]+14,bounds[1]+1,bounds[2]-14,bounds[1]+1),fill=(247,231,193,35))
    base=Image.alpha_composite(base,frame);base.alpha_composite(portrait,(x,y))
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
        super().__init__();self.uri=uri;self.cache=cache;self.pixels=None;self.key=None;self.closed=False;self.content=content
        self.get_style_context().add_class('stage-artist-banner')
        self.minimum_height=height;self.photo_area_width=0;self.height_idle=0;self.requested_height=height
        self.base=Gtk.Box();self.base.set_size_request(-1,height);self.add(self.base)
        self.background=Gtk.Image();self.background.set_halign(Gtk.Align.FILL);self.background.set_valign(Gtk.Align.FILL)
        self.add_overlay(self.background);self.set_overlay_pass_through(self.background,True)
        content.get_style_context().add_class('stage-artist-banner-content')
        content.set_valign(Gtk.Align.FILL);self.add_overlay(content)
        self.source_image=Gtk.Image()
        self.connect('get-child-position',self.position_content)
        self.connect('size-allocate',lambda *_:self.render())
        self.connect('destroy',self.close)

    def position_content(self,_overlay,widget,area):
        if widget is not self.content:return False
        width,height=self.get_allocated_width(),self.get_allocated_height()
        self.photo_area_width=portrait_slot(width,height) if self.uri else 0
        area.x=0;area.width=max(1,width-self.photo_area_width)
        needed=self.content.get_preferred_height_for_width(area.width)[1]
        # Overlay children otherwise take their natural width even when that
        # would put the controls across the photo. Reserve its space before
        # allocating text, and allow a wrapped heading to grow the masthead.
        desired=max(self.minimum_height,needed)
        self.requested_height=desired
        if self.base.get_size_request()[1]!=desired and not self.height_idle:
            # GTK can drop a resize queued from inside size allocation. Apply
            # the new request outside it, before the following frame's layout.
            self.height_idle=GLib.idle_add(self.resize_content,priority=GLib.PRIORITY_DEFAULT)
        area.y=max(0,(height-needed)//2);area.height=needed
        return True

    def resize_content(self):
        self.height_idle=0
        if not self.closed:
            self.base.set_size_request(-1,self.requested_height);self.queue_resize()
        return False

    def set_photo(self,pixels):
        if self.closed or not pixels:return
        self.pixels=(bytes(pixels.get_pixels()),(pixels.get_width(),pixels.get_height()),pixels.get_has_alpha(),pixels.get_rowstride())
        self.key=None
        self.render()

    def render(self):
        width,height=self.get_allocated_width(),self.get_allocated_height()
        if self.closed or width<10 or height<10:return
        width=min(3840,width);height=min(600,height)
        if not self.pixels:return
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
        if self.height_idle:GLib.source_remove(self.height_idle);self.height_idle=0
