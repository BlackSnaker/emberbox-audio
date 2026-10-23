"""A cached, layered artist entrance confined to the catalogue viewport."""
from PIL import Image
from gi.repository import GLib,GdkPixbuf,Gtk
from artist_header import portrait_rect
from reveal_gl import RevealGL
from room_snapshot import snapshot


FRAGMENT=b'''#version 150
in vec2 uv;
out vec4 color;
uniform vec2 viewport;
uniform vec4 hero;
uniform vec4 portrait;
uniform float progress;
uniform int hasCover;
uniform sampler2D cover;
uniform sampler2D room;
uniform sampler2D previous;
float ease(float t){t=clamp(t,0.0,1.0);return t*t*t*(t*(t*6.0-15.0)+10.0);}
vec4 over(vec4 a,vec4 b){return a+b*(1.0-a.a);}
float inside(vec2 p,vec4 r){
  return float(all(greaterThanEqual(p,r.xy)) && all(lessThan(p,r.xy+r.zw)));
}
float rounded(vec2 p,vec4 r,float radius){
  vec2 q=abs(p-r.xy-r.zw*.5)-r.zw*.5+radius;
  float d=length(max(q,vec2(0)))+min(max(q.x,q.y),0.0)-radius;
  return 1.0-smoothstep(-.7,.7,d);
}
void main(){
  vec2 p=uv*viewport;
  float atmosphere=ease(progress/.76);
  float photograph=ease((progress-.07)/.83);
  float words=ease((progress-.13)/.77);
  float music=ease((progress-.20)/.80);
  vec2 ambientPoint=p-vec2(0,12.0*(1.0-atmosphere));
  vec4 base=texture(previous,(ambientPoint-hero.xy)/hero.zw);
  base*=rounded(ambientPoint,hero,26.0)*atmosphere;
  if(hasCover==1){
    vec2 centre=portrait.xy+portrait.zw*.5;
    vec2 at=centre+(p-centre-vec2(0,16.0*(1.0-photograph)))/mix(.965,1.0,photograph);
    vec4 tex=texture(cover,(at-hero.xy)/hero.zw);
    tex.rgb*=tex.a;
    vec2 edge=min(at-portrait.xy,portrait.xy+portrait.zw-at);
    float feather=smoothstep(0.0,12.0,min(edge.x,edge.y));
    tex*=inside(at,portrait)*feather*photograph*rounded(p,hero,26.0);
    base=over(tex,base);
  }
  vec2 titlePoint=p-vec2(0,18.0*(1.0-words));
  vec4 title=texture(room,titlePoint/viewport);
  title*=inside(titlePoint,hero)*words;
  base=over(title,base);
  vec2 musicPoint=p-vec2(0,22.0*(1.0-music));
  vec4 songs=texture(room,musicPoint/viewport);
  songs*=float(musicPoint.y>=hero.y+hero.w)*inside(musicPoint,vec4(0,0,viewport))*music;
  color=over(songs,base);
}'''


class ArtistDriver(RevealGL):
    def __init__(self,allow_software=False):
        super().__init__(allow_software,fragment=FRAGMENT,uniforms=('hero','portrait'))

    def draw_artist(self,width,height,frame,ambient,pixels,hero,portrait,progress):
        self.call('Disable',0x0BE2)
        self.call('UseProgram',self.program);self.call('BindVertexArray',self.vao)
        self.call('ActiveTexture',0x84C0);self.upload(pixels)
        self.call('BindTexture',0x0DE1,self.texture)
        for unit,texture,value,attribute in (
                (0x84C1,self.room_texture,frame,'room_uploaded'),
                (0x84C2,self.previous_texture,ambient,'previous_uploaded')):
            self.call('ActiveTexture',unit);self.call('BindTexture',0x0DE1,texture)
            if value is not getattr(self,attribute):
                setattr(self,attribute,value);self.raw_texture(texture,value)
        for name,kind,values in (
                ('viewport','2f',(width,height)),('hero','4f',hero),('portrait','4f',portrait),
                ('progress','1f',(progress,)),('hasCover','1i',(int(pixels is not None),)),
                ('cover','1i',(0,)),('room','1i',(1,)),('previous','1i',(2,))):
            self.call('Uniform'+kind,self.uniforms[name],*values)
        self.call('DrawArrays',0x0004,0,3)
        self.call('BindVertexArray',0);self.call('UseProgram',0)
        self.call('BindTexture',0x0DE1,0);self.call('ActiveTexture',0x84C0)
        self.call('BindTexture',0x0DE1,0)


def pixbuf(frame):
    w,h,data=frame
    # Cairo snapshots are premultiplied BGRA; GTK's image requires straight RGBA.
    raw=Image.frombytes('RGBA',(w,h),data,'raw','BGRa').tobytes()
    return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(raw),GdkPixbuf.Colorspace.RGB,True,8,w,h,w*4)


class ArtistReveal(Gtk.Overlay):
    DURATION=1.05

    def __init__(self,live,completed):
        super().__init__();self.live=live;self.completed=completed
        self.driver=None;self.failed=False;self.closed=False
        self.preparing=False;self.active=False;self.wait=0;self.tick=0
        self.frame=self.ambient=self.pixels=None;self.hero=self.portrait=(0,0,1,1)
        self.started=None;self.progress=0.;self.banner=None
        self.add(live)
        self.hold=Gtk.Image();self.hold.set_no_show_all(True)
        self.hold.set_halign(Gtk.Align.FILL);self.hold.set_valign(Gtk.Align.FILL)
        self.add_overlay(self.hold);self.set_overlay_pass_through(self.hold,True)
        self.area=Gtk.GLArea();self.area.set_required_version(3,2);self.area.set_use_es(False)
        self.area.set_has_alpha(True);self.area.set_auto_render(False);self.area.set_no_show_all(True)
        self.add_overlay(self.area);self.set_overlay_pass_through(self.area,True)
        self.area.connect('render',self.render_scene);self.area.connect('unrealize',self.release)
        self.connect('destroy',self.close)

    def warmup(self,allow_software=False):
        if self.closed or self.driver or self.failed:return False
        if not self.get_settings().get_property('gtk-enable-animations'):return False
        try:
            parents=[];widget=self.area
            while widget and not widget.get_realized():parents.append(widget);widget=widget.get_parent()
            for widget in reversed(parents):widget.realize()
            self.area.make_current()
            if self.area.get_error():raise RuntimeError('Artist GL unavailable')
            self.driver=ArtistDriver(allow_software)
            self.area.attach_buffers()
            blank=(1,1,bytes(4))
            self.driver.draw_artist(1,1,blank,blank,None,(0,0,1,1),(0,0,1,1),0.)
            self.driver.call('Finish')
        except (OSError,RuntimeError,AttributeError):
            self.release(self.area);self.failed=True
            if self.area.get_realized():self.area.unrealize()
        return False

    @property
    def busy(self):return self.preparing or self.active

    def allocation(self):
        area=self.get_allocation().copy();area.x=area.y=0
        return area

    def hold_loading(self):
        self.finish()
        if self.closed or not self.get_mapped() or not self.get_settings().get_property('gtk-enable-animations'):return False
        try:self.hold.set_from_pixbuf(pixbuf(snapshot(self.live,self.allocation())))
        except (OSError,RuntimeError,AttributeError):return False
        self.preparing=True;self.hold.set_opacity(1.);self.hold.show()
        self.live.set_no_show_all(True);self.live.hide()
        return True

    def begin(self,banner):
        self.banner=banner;self.wait_started=GLib.get_monotonic_time()
        # Measure once while hidden. This also starts the off-thread photo job.
        self.live.show();self.live.get_preferred_size();self.live.size_allocate(self.allocation());self.live.hide()
        self.wait=GLib.timeout_add(16,self.ready)

    def ready(self):
        if self.closed or not self.preparing:return False
        elapsed=(GLib.get_monotonic_time()-self.wait_started)/1e6
        if elapsed<.048:return True
        if self.banner.uri and not self.banner.atmosphere and elapsed<.65:return True
        if not self.get_settings().get_property('gtk-enable-animations'):
            self.finish(notify=True);return False
        self.live.show();allocation=self.allocation()
        try:
            self.live.get_preferred_size();self.live.size_allocate(allocation)
            banner=self.banner;position=banner.translate_coordinates(self.live,0,0)
            if position is None:raise RuntimeError('Artist no longer visible')
            self.hero=(*position,banner.get_allocated_width(),banner.get_allocated_height())
            self.pixels=banner.background.get_pixbuf()
            # The hidden loading page can have a narrower first allocation.
            # Wait for its replacement job rather than stretching that older
            # portrait texture to the new viewport on the very first entrance.
            current=not self.pixels or (self.pixels.get_width(),self.pixels.get_height())==self.hero[2:]
            if (not current or banner.height_idle) and elapsed<.85:
                self.live.hide();return True
            if not current:self.pixels=None
            self.ambient=banner.atmosphere or (1,1,bytes((27,34,27,255)))
            if self.ambient[:2]!=self.hero[2:]:self.ambient=(1,1,bytes((27,34,27,255)))
            if banner.pixels:
                x,y,w,h=portrait_rect(banner.pixels[1],self.hero[2],self.hero[3])
                self.portrait=(position[0]+x-20,position[1]+y-20,w+40,h+40)
            if self.driver:
                banner.get_style_context().add_class('stage-artist-capture')
                banner.background.set_opacity(0.)
                try:self.frame=snapshot(self.live,allocation)
                finally:
                    banner.background.set_opacity(1.)
                    banner.get_style_context().remove_class('stage-artist-capture')
                self.area.show()
            else:
                self.hold.set_from_pixbuf(pixbuf(snapshot(self.live,allocation)))
                self.hold.set_opacity(0.)
        except (OSError,RuntimeError,AttributeError):
            self.finish(notify=True);return False
        self.wait=0
        self.live.hide();self.preparing=False;self.active=True;self.started=None;self.progress=0.
        self.tick=self.add_tick_callback(self.advance)
        if self.driver:self.area.queue_render()
        return False

    def advance(self,_widget,clock):
        now=clock.get_frame_time()
        if self.started is None:self.started=now
        self.progress=min(1.,max(0.,(now-self.started)/1e6/(self.DURATION if self.driver else .32)))
        if not self.get_settings().get_property('gtk-enable-animations') or self.progress>=1.:
            self.tick=0;self.finish(notify=True);return False
        if self.driver:
            if self.hold.get_visible():
                t=min(1.,self.progress/.16)
                if t>=1.:self.hold.hide()
                else:self.hold.set_opacity(1-t*t*(3-2*t))
            self.area.queue_render()
        else:
            t=self.progress;self.hold.set_opacity(t*t*t*(t*(t*6-15)+10))
        return True

    def render_scene(self,_area,_context):
        if not self.active or not self.driver:return True
        try:self.driver.draw_artist(self.get_allocated_width(),self.get_allocated_height(),self.frame,
            self.ambient,self.pixels,self.hero,self.portrait,self.progress)
        except (OSError,RuntimeError,AttributeError):
            self.failed=True;self.release(self.area);self.finish(notify=True)
        return True

    def finish(self,notify=False):
        if self.wait:GLib.source_remove(self.wait);self.wait=0
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.preparing=self.active=False;self.started=None;self.banner=None
        self.area.hide();self.hold.hide();self.hold.clear();self.hold.set_opacity(1.)
        self.live.set_no_show_all(False);self.live.show()
        self.frame=self.ambient=self.pixels=None
        if self.driver:self.driver.uploaded=self.driver.room_uploaded=self.driver.previous_uploaded=None
        if notify and not self.closed:self.completed()

    def release(self,_area):
        if self.driver:
            self.area.make_current()
            if not self.area.get_error():self.driver.close()
            self.driver=None

    def close(self,*_args):
        self.closed=True;self.finish()
