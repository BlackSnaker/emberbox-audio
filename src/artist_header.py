"""A cover-tinted artist masthead, composed off the GTK thread and cached."""
from collections import OrderedDict
import threading
import numpy as np
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


def atmospheric_backdrop(photo,width,height):
    """Light a small photo field, then enlarge it once; no work on the frame clock."""
    backdrop=Image.new('RGBA',photo.size,(35,41,31,255));backdrop.alpha_composite(photo)
    scale=min(1,960/width);small=(max(1,round(width*scale)),max(1,round(height*scale)))
    field=ImageOps.fit(backdrop.convert('RGB'),small,Image.Resampling.LANCZOS,centering=(.5,.4))
    field=ImageEnhance.Color(field).enhance(.72)
    # Two optical depths keep the photograph's light and colour without a
    # distracting second face. Broad highlights illuminate the matte surface.
    near=field.filter(ImageFilter.GaussianBlur(max(12,height*.055)*scale))
    far=field.filter(ImageFilter.GaussianBlur(max(44,height*.19)*scale))
    field=Image.blend(near,far,.34)
    rgb=np.asarray(field,dtype=np.float32)
    yy,xx=np.mgrid[0:small[1],0:small[0]].astype(np.float32)
    xx/=max(1,small[0]-1);yy/=max(1,small[1]-1)
    reading_edge=(width-portrait_slot(width,height))/width
    reveal=np.clip((xx-reading_edge+.19)/.50,0,1);reveal=reveal*reveal*(3-2*reveal)
    exposure=(.14+.46*reveal)*(1-.20*(2*yy-1)**2-.08*(2*xx-1)**2)
    ink=np.array((16,23,21),dtype=np.float32)
    rgb=ink+(rgb-ink)*exposure[:,:,None]
    palette=np.asarray(backdrop.convert('RGB').resize((1,1),Image.Resampling.BOX),dtype=np.float32)[0,0]
    reflected=palette/max(1,float(palette.max()))*155+np.array((45,27,4))
    reflected=reflected*.6+np.array((199,155,91))*.4
    luminance=np.asarray(far.convert('L'),dtype=np.float32)/255
    key=np.exp(-.5*(((xx-.70)/.27)**2+((yy-.12)/.86)**2))
    key*=.16+.09*luminance
    bounce=np.exp(-.5*(((xx-.18)/.38)**2+((yy-1.12)/.62)**2))*.045
    # Screen light into the photo rather than laying a flat brown tint over it.
    rgb+=(255-rgb)*(reflected[None,None,:]/255)*key[:,:,None]
    rgb+=(255-rgb)*(np.array((111,134,107))/255)*bounce[:,:,None]
    base=Image.fromarray(np.clip(rgb,0,255).astype('uint8'),'RGB').resize((width,height),Image.Resampling.BICUBIC)
    # Fixed neutral grain prevents gradient banding; it never touches the
    # clear portrait and cannot shimmer when a cached banner is reapplied.
    rgb=np.asarray(base,dtype=np.float32)
    grain=np.random.default_rng(73).normal(0,.65,(height,width,1)).astype(np.float32)
    base=Image.fromarray(np.clip(rgb+grain,0,255).astype('uint8'),'RGB').convert('RGBA')
    return base


def glass_mount(base,rect):
    """A shallow, photo-lit glass mount; every highlight stays outside the photo.

    Its refracted field and edge normals are baked once in the worker, not
    evaluated on GTK's frame clock. The same mount is retained by the entrance.
    """
    x,y,pw,ph=rect;outset=8;radius=16
    bounds=(x-outset,y-outset,x+pw+outset-1,y+ph+outset-1)
    fw,fh=pw+2*outset,ph+2*outset
    # Contact shadow and a dark seating seam give the glass a place in the
    # housing without a broad floating drop shadow or decorative metal corners.
    shadow=Image.new('RGBA',base.size)
    ImageDraw.Draw(shadow).rounded_rectangle(tuple(v+(2 if i%2==0 else 3) for i,v in enumerate(bounds)),
                                           radius,fill=(3,8,10,118))
    base=Image.alpha_composite(base,shadow.filter(ImageFilter.GaussianBlur(6)))
    yy,xx=np.mgrid[0:fh,0:fw].astype(np.float32);xx+=.5;yy+=.5
    qx=np.abs(xx-fw/2)-(fw/2-radius);qy=np.abs(yy-fh/2)-(fh/2-radius)
    ox=np.maximum(qx,0);oy=np.maximum(qy,0);length=np.maximum(np.hypot(ox,oy),.0001)
    distance=np.hypot(ox,oy)+np.minimum(np.maximum(qx,qy),0)-radius
    nx=np.where((ox+oy)>0,ox/length,np.where(qx>qy,1.,0.))*np.sign(xx-fw/2)
    ny=np.where((ox+oy)>0,oy/length,np.where(qy>=qx,1.,0.))*np.sign(yy-fh/2)
    key=np.clip(-.56*nx-.74*ny,0,1);bounce=np.clip(.70*nx+.55*ny,0,1)
    depth=-distance
    # A tiny spatial displacement in the atmospheric field reads as clear
    # thickness. Low neutral smoke leaves the source light visible beneath it.
    reflected=base.crop((bounds[0]-2,bounds[1]-1,bounds[2]-1,bounds[3])).convert('RGB')
    rgb=np.asarray(reflected,dtype=np.float32)*.73+np.array((12.,15.,17.))
    crown=np.exp(-.5*((depth-1.05)/.78)**2)
    shoulder=np.exp(-.5*((depth-2.8)/1.35)**2)
    groove=np.exp(-.5*((depth-6.4)/.85)**2)
    rgb+=np.array((255.,231.,190.))*((.09+.30*key)*crown)[:,:,None]
    rgb+=np.array((166.,215.,234.))*(.17*bounce*crown)[:,:,None]
    rgb+=np.array((230.,230.,213.))*(.045*key*shoulder)[:,:,None]
    rgb*=1-(.23*groove)[:,:,None]
    alpha=np.clip(.5-distance,0,1)
    pixels=np.empty((fh,fw,4),dtype=np.uint8)
    pixels[:,:,:3]=np.clip(rgb,0,255).astype('uint8');pixels[:,:,3]=(alpha*255+.5).astype('uint8')
    base.alpha_composite(Image.fromarray(pixels,'RGBA'),bounds[:2])
    seam=Image.new('RGBA',base.size);edge=ImageDraw.Draw(seam)
    # These two hairlines are behind the photograph's actual boundary.
    edge.rectangle((x-2,y-2,x+pw+1,y+ph+1),outline=(184,197,190,34),width=1)
    edge.rectangle((x-1,y-1,x+pw,y+ph),outline=(5,10,12,210),width=1)
    return Image.alpha_composite(base,seam)


def glass_edge(base):
    """A restrained meniscus around the masthead, shared with its cached layer."""
    width,height=base.size
    edge=Image.new('RGBA',base.size);draw=ImageDraw.Draw(edge)
    draw.rounded_rectangle((0,0,width-1,height-1),26,outline=(211,225,226,30),width=1)
    draw.rounded_rectangle((1,1,width-2,height-2),25,outline=(4,10,13,62),width=1)
    # Short soft edge reflections suggest a continuous polished surface rather
    # than a white rectangular border. The central body remains transparent.
    draw.line((27,1,max(28,round(width*.57)),1),fill=(247,229,191,38),width=1)
    draw.line((1,27,1,max(28,round(height*.53))),fill=(181,220,232,27),width=1)
    draw.line((round(width*.64),height-2,width-28,height-2),fill=(170,188,220,19),width=1)
    return Image.alpha_composite(base,edge)


def compose(pixels,width,height,with_atmosphere=False):
    raw,size,alpha,stride=pixels
    photo=Image.frombytes('RGBA' if alpha else 'RGB',size,raw,'raw','RGBA' if alpha else 'RGB',stride).convert('RGBA')
    rect=portrait_rect(photo.size,width,height)
    base=glass_edge(glass_mount(atmospheric_backdrop(photo,width,height),rect))
    # Retain the complete housing under the photographic layer during the
    # artist entrance, so its glass mount cannot pop in after the animation.
    mask=Image.new('L',(width,height));ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),26,fill=255)
    base.putalpha(mask)
    atmosphere=(width,height,base.tobytes('raw','BGRA')) if with_atmosphere else None
    # All four edges and every source pixel of the contained photograph stay
    # clear: the mount and lighting never cross into this rectangle.
    x,y,pw,ph=rect
    base.alpha_composite(photo.resize((pw,ph),Image.Resampling.LANCZOS),(x,y))
    base.putalpha(mask)
    data=base.tobytes()
    return (data,atmosphere) if with_atmosphere else data


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
        self.atmosphere=None
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
        future=self.cache.pool.submit(compose,pixels,width,height,True)
        def done(result):
            try:data=result.result()
            except Exception:return
            self.cache.put(key,data);GLib.idle_add(self.apply,key,data,priority=GLib.PRIORITY_DEFAULT)
        future.add_done_callback(done)

    def apply(self,key,data):
        if not self.closed and self.key==key:
            data,self.atmosphere=data
            self.background.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(data),GdkPixbuf.Colorspace.RGB,True,8,key[1],key[2],key[1]*4))
        return False

    def close(self,*_args):
        self.closed=True;self.pixels=None;self.atmosphere=None;self.source_image.destroy()
        if self.height_idle:GLib.source_remove(self.height_idle);self.height_idle=0
