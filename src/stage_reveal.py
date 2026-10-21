"""GPU entrance with fixed GTK geometry and a cheap compositor-fade fallback."""
from gi.repository import GLib, Gtk
from cover_tint import BASE_COLOR
from reveal_gl import RevealGL
from room_snapshot import snapshot, warm_window


def smooth(value):
    t=max(0.,min(1.,value))
    return t*t*t*(t*(t*6-15)+10)


def interpolate(start,end,amount):
    return tuple(a+(b-a)*amount for a,b in zip(start,end))


class StageReveal(Gtk.GLArea):
    DURATION=.9

    def __init__(self,window,background,layout,cover,art_shell):
        super().__init__()
        self.window,self.background,self.layout=window,background,layout
        self.cover,self.art_shell=cover,art_shell
        self.active=False;self.started=None;self.progress=1.;self.handed_off=False
        self.origin=(0,0,1,1);self.cover_origin=None;self.cover_pixels=None
        self.driver=None;self.error='';self.fallback=False
        self.fallback_tick=0
        self.pigment=(.26,.26,.24)
        self.room=None
        self.previous=None;self.cover_end=(0,0,1,1)
        self.reversing=False;self.morphing=False;self.completed=None;self.change=None
        self.set_required_version(3,2);self.set_use_es(False)
        self.set_has_alpha(True);self.set_auto_render(False)
        self.get_style_context().add_class('stage-gl')
        self.set_halign(Gtk.Align.FILL);self.set_valign(Gtk.Align.FILL)
        self.set_no_show_all(True)
        self.connect('render',self.render_scene)
        self.connect('unrealize',self.release)

    def warmup(self,pixels=None,allow_software=False,room=None,monitor=None):
        """Compile and draw offscreen before a fullscreen click, never in it."""
        if self.driver or self.error:return
        try:
            self.window.realize();self.get_parent().realize();self.realize()
            self.make_current()
            if self.get_error():raise RuntimeError('OpenGL context unavailable')
            self.driver=RevealGL(allow_software=allow_software)
            display=self.window.get_display()
            monitor=monitor or display.get_primary_monitor() or display.get_monitor(0)
            if monitor:
                allocation=monitor.get_geometry().copy();allocation.x=allocation.y=0
                self.size_allocate(allocation)
            self.attach_buffers()
            width,height=self.get_allocated_width(),self.get_allocated_height()
            self.driver.call('Viewport',0,0,width*self.get_scale_factor(),height*self.get_scale_factor())
            self.driver.draw(width,height,(0,0,width,height),(0,0,100,100),self.pigment,.5,pixels,room)
            self.driver.call('Finish')
            if monitor:warm_window(self,self.window,allocation)
        except (RuntimeError,OSError,AttributeError) as error:
            self.error=str(error)
            if self.driver:self.driver.close();self.driver=None

    def prepare(self,host,monitor,palette=BASE_COLOR,reverse=False):
        self.finish()
        settings=self.window.get_settings()
        if settings and not settings.get_property('gtk-enable-animations'):return
        geometry=monitor.get_geometry() if monitor else None
        width,height=(geometry.width,geometry.height) if geometry else (1280,800)
        ox,oy=(geometry.x,geometry.y) if geometry else (0,0)
        self.origin=(width*.32,height*.3,width*.36,height*.4)
        if host.window.get_mapped():
            x,y=host.window.get_position();w,h=host.window.get_size()
            self.origin=(max(0,min(width-1,x-ox)),max(0,min(height-1,y-oy)),min(w,width),min(h,height))
        x,y,w,h=self.origin;size=min(96,w,h)
        self.cover_origin=(x+(w-size)/2,y+(h-size)/2,size,size)
        image=getattr(host,'cover',None)
        if image and image.get_mapped() and image.get_pixbuf():
            point=image.translate_coordinates(host.window,0,0)
            if point:
                self.cover_pixels=image.get_pixbuf()
                w,h=self.cover_pixels.get_width(),self.cover_pixels.get_height()
                self.cover_origin=(self.origin[0]+point[0]+(image.get_allocated_width()-w)/2,
                                   self.origin[1]+point[1]+(image.get_allocated_height()-h)/2,w,h)
        self.pigment=tuple(max(26,min(140,67+(value-base)*8))/255 for value,base in zip(palette,BASE_COLOR))
        self.active=True;self.started=None;self.progress=1. if reverse else 0.;self.handed_off=False
        self.reversing=reverse
        self.fallback=self.driver is None
        if self.fallback:
            # Cold clicks and systems without GL use compositor window opacity.
            # Never compile shaders or reconstruct a GTK scene in the click.
            native=self.window.get_window()
            if native:native.set_opacity(self.progress)
            self.fallback_tick=GLib.timeout_add(16,self.fade_step)
        else:
            if self.window.get_screen().is_composited():
                self.window.get_style_context().add_class('stage-opening')
            # GTK 3 still draws opacity-zero widgets into a Cairo group. Hide
            # these trees instead; their allocations were prepared offscreen.
            for widget in (self.background,self.layout):
                widget.set_no_show_all(True);widget.hide()
            self.show();self.queue_render()

    def fade_step(self):
        self.advance(GLib.get_monotonic_time())
        return self.active

    def advance(self,now):
        if not self.active:return
        if self.started is None:self.started=now
        duration=(.32 if self.morphing else .24) if self.fallback else .66 if self.morphing else self.DURATION
        raw=max(0.,min(1.,(now-self.started)/1_000_000/duration))
        self.progress=1.-raw if self.reversing else raw
        if raw>=1.:
            completed=self.completed
            self.finish()
            if completed:completed()
            return
        if self.fallback:
            native=self.window.get_window()
            if self.morphing:
                if raw>=.4 and self.change:
                    change,self.change=self.change,None;change()
                alpha=1.-smooth(raw/.4) if raw<.4 else smooth((raw-.4)/.6)
            else:alpha=smooth(self.progress)
            if native:native.set_opacity(alpha)
        else:
            if self.progress>=.62 and not self.handed_off and self.room is None:
                # A single GTK paint behind an opaque GL frame, no per-frame
                # container opacity, image resizing or layout invalidation.
                for widget in (self.background,self.layout):
                    widget.set_no_show_all(False);widget.show()
                self.handed_off=True
            self.queue_render()

    def render_scene(self,_area,_context):
        if not self.active or self.fallback or not self.driver:return True
        width,height=self.window.get_size()
        t=self.progress
        shell=interpolate(self.origin,(0,0,width,height),smooth(t))
        artwork=(0,0,1,1)
        if self.cover_pixels:
            artwork=interpolate(self.cover_origin,self.cover_end,smooth(t) if self.morphing else smooth(t/.7))
        try:
            self.driver.draw(width,height,shell,artwork,self.pigment,t,self.cover_pixels,self.room,
                             self.previous)
        except (RuntimeError,OSError,AttributeError):
            completed=self.completed
            self.finish()
            if completed:completed()
        return True

    def cover_rect(self):
        # The snapshot is in layout-allocation coordinates. Window-relative
        # translation also includes GTK's margin window and would count it twice.
        point=self.cover.translate_coordinates(self.layout,0,0)
        area=self.layout.get_allocation()
        return (area.x+point[0],area.y+point[1],self.cover.get_allocated_width(),self.cover.get_allocated_height()) if point else (0,0,1,1)

    def scene(self,allocation,without_art=False):
        if without_art:self.art_shell.set_opacity(0.)
        try:return snapshot(self.layout,allocation)
        finally:
            if without_art:self.art_shell.set_opacity(1.)

    def capture(self,allocation,without_art=False):
        if self.active and not self.fallback:
            try:self.room=self.scene(allocation,without_art)
            except (OSError,AttributeError,RuntimeError):self.room=None
            self.layout.hide()
            self.cover_end=self.cover_rect()

    def morph(self,change,completed):
        self.finish()
        if not self.window.get_settings().get_property('gtk-enable-animations'):
            change();completed();return
        self.active=True;self.progress=0.;self.morphing=True;self.completed=completed
        self.fallback=self.driver is None
        if self.fallback:
            self.change=change;self.fallback_tick=GLib.timeout_add(16,self.fade_step)
            return
        allocation=self.window.get_allocation();allocation.x=allocation.y=0
        try:self.previous=self.scene(allocation,without_art=True)
        except (OSError,AttributeError,RuntimeError):
            self.finish();change();completed();return
        self.cover_pixels=self.cover.get_pixbuf()
        self.cover_origin=self.cover_rect()
        for widget in (self.background,self.layout):widget.set_no_show_all(True);widget.hide()
        change();self.capture(allocation,without_art=True)
        if self.room is None:
            self.finish();completed();return
        self.show();self.queue_render()

    def finish(self):
        if self.fallback_tick:GLib.source_remove(self.fallback_tick);self.fallback_tick=0
        self.active=False;self.started=None;self.progress=1.;self.handed_off=False
        self.hide();self.cover_origin=None;self.cover_pixels=None;self.room=None;self.previous=None
        self.reversing=self.morphing=False;self.completed=self.change=None
        for widget in (self.background,self.layout):
            widget.set_no_show_all(False);widget.set_opacity(1.);widget.show()
        self.art_shell.set_opacity(1.)
        native=self.window.get_window()
        if native:native.set_opacity(1.)
        self.window.get_style_context().remove_class('stage-opening')

    def release(self,_area):
        if self.driver:
            self.make_current()
            if not self.get_error():self.driver.close()
            self.driver=None
