"""Fixed-geometry transitions with GPU or retained in-window composition."""
from gi.repository import GLib, Gtk
from cover_tint import BASE_COLOR
from reveal_gl import RevealGL
from room_snapshot import snapshot, warm_window


def smooth(value):
    t=max(0.,min(1.,value))
    return t*t*t*(t*(t*6-15)+10)


def interpolate(start,end,amount):
    return tuple(a+(b-a)*amount for a,b in zip(start,end))


class StageReveal(Gtk.Overlay):
    DURATION=.9

    def __init__(self,window,background,layout,cover,art_shell,current_art=None):
        super().__init__()
        self.window,self.background,self.layout=window,background,layout
        self.cover,self.art_shell=cover,art_shell
        self.current_art=current_art or cover.get_pixbuf
        self.active=False;self.started=None;self.last_now=None;self.progress=1.;self.handed_off=False
        self.origin=(0,0,1,1);self.cover_origin=None;self.cover_pixels=None
        self.driver=None;self.error='';self.fallback=False
        self.fallback_tick=0
        self.pigment=(.26,.26,.24)
        self.room=self.backdrop=None
        self.previous=None;self.cover_end=(0,0,1,1)
        self.reversing=False;self.morphing=False;self.completed=None
        from stage_reveal_paint import RevealPaint
        self.paint=RevealPaint(self);self.add(self.paint.area)
        self.area=Gtk.GLArea();self.area.set_required_version(3,2);self.area.set_use_es(False)
        self.area.set_has_alpha(True);self.area.set_auto_render(False)
        self.area.set_no_show_all(True);self.area.set_can_focus(False)
        self.add_overlay(self.area);self.set_overlay_pass_through(self.area,True)
        self.get_style_context().add_class('stage-gl')
        self.set_halign(Gtk.Align.FILL);self.set_valign(Gtk.Align.FILL)
        self.set_no_show_all(True)
        self.area.connect('render',self.render_scene)
        self.area.connect('unrealize',self.release)
        self.connect('destroy',lambda *_:self.paint.close())

    def queue_render(self):
        if self.fallback:self.paint.area.queue_draw()
        else:self.area.queue_render()

    def warmup(self,pixels=None,allow_software=False,room=None,monitor=None):
        """Compile and draw offscreen before a fullscreen click, never in it."""
        if self.driver or self.error:return
        try:
            self.window.realize();self.get_parent().realize();self.realize();self.area.realize()
            self.area.make_current()
            if self.area.get_error():raise RuntimeError('OpenGL context unavailable')
            self.driver=RevealGL(allow_software=allow_software)
            display=self.window.get_display()
            monitor=monitor or display.get_primary_monitor() or display.get_monitor(0)
            if monitor:
                allocation=monitor.get_geometry().copy();allocation.x=allocation.y=0
                self.size_allocate(allocation);self.area.size_allocate(allocation)
            self.area.attach_buffers()
            width,height=self.get_allocated_width(),self.get_allocated_height()
            self.driver.call('Viewport',0,0,width*self.get_scale_factor(),height*self.get_scale_factor())
            self.driver.draw(width,height,(0,0,width,height),(0,0,100,100),self.pigment,.5,pixels,room)
            self.driver.call('Finish')
            if monitor:warm_window(self.area,self.window,allocation)
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
        if getattr(getattr(host,'appearance',None),'dark',False):self.pigment=(.065,.069,.067)
        self.active=True;self.started=None;self.progress=1. if reverse else 0.;self.handed_off=False
        self.reversing=reverse
        self.backdrop=self.background.get_pixbuf()
        self.fallback=self.driver is None or self.area.get_error() is not None
        if self.fallback:
            # Never fade the native window out: that looks like closing the
            # player, especially while a newly selected theme is warming up.
            self.fallback_tick=GLib.timeout_add(16,self.fade_step)
        else:
            if self.window.get_screen().is_composited():
                self.window.get_style_context().add_class('stage-opening')
            # GTK 3 still draws opacity-zero widgets into a Cairo group. Hide
            # these trees instead; their allocations were prepared offscreen.
            for widget in (self.background,self.layout):
                widget.set_no_show_all(True);widget.hide()
            self.area.show();self.show();self.queue_render()

    def fade_step(self):
        self.advance(GLib.get_monotonic_time())
        return self.active

    def advance(self,now):
        if not self.active:return
        if self.last_now is not None:
            now=max(now,self.last_now)
            # A slow first GTK paint must not consume the entire entrance.
            # Keep normal frame timing, but spend at most 50 ms of animation
            # on a frame delivered after a rendering or scheduling stall.
            gap=now-self.last_now
            if gap>50_000:self.started+=gap-50_000
        if self.started is None:self.started=now
        self.last_now=now
        duration=.66 if self.morphing else self.DURATION
        raw=max(0.,min(1.,(now-self.started)/1_000_000/duration))
        self.progress=1.-raw if self.reversing else raw
        if raw>=1.:
            completed=self.completed
            self.finish()
            if completed:completed()
            return
        if self.fallback:
            self.queue_render()
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
                             self.previous,self.backdrop)
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
        if self.active:
            self.backdrop=self.background.get_pixbuf()
            try:self.room=self.scene(allocation,without_art or self.fallback)
            except (OSError,AttributeError,RuntimeError):self.room=None
            self.cover_end=self.cover_rect()
            if self.fallback:
                if self.room is None:self.finish();return
                try:self.paint.prepare(self.room,self.previous,self.background.get_pixbuf(),self.current_art() or self.cover_pixels)
                except (OSError,AttributeError,RuntimeError):self.finish();return
                for widget in (self.background,self.layout):widget.set_no_show_all(True);widget.hide()
                self.area.hide();self.paint.area.show();self.show();self.queue_render()
            else:self.layout.hide()

    def morph(self,change,completed):
        self.finish()
        if not self.window.get_settings().get_property('gtk-enable-animations'):
            change();completed();return
        self.active=True;self.progress=0.;self.morphing=True;self.completed=completed
        self.fallback=self.driver is None or self.area.get_error() is not None
        allocation=self.window.get_allocation();allocation.x=allocation.y=0
        try:self.previous=self.scene(allocation,without_art=True)
        except (OSError,AttributeError,RuntimeError):
            self.finish();change();completed();return
        self.cover_pixels=self.current_art()
        self.cover_origin=self.cover_rect()
        for widget in (self.background,self.layout):widget.set_no_show_all(True);widget.hide()
        change();self.capture(allocation,without_art=True)
        if self.room is None:
            self.finish();completed();return
        if self.fallback:self.fallback_tick=GLib.timeout_add(16,self.fade_step)
        else:self.area.show()
        self.show();self.queue_render()

    def finish(self):
        if self.fallback_tick:GLib.source_remove(self.fallback_tick);self.fallback_tick=0
        self.active=False;self.started=None;self.last_now=None;self.progress=1.;self.handed_off=False
        self.hide();self.area.hide();self.paint.area.hide();self.paint.clear()
        self.cover_origin=None;self.cover_pixels=None;self.room=None;self.previous=None;self.backdrop=None
        self.reversing=self.morphing=False;self.completed=None
        for widget in (self.background,self.layout):
            widget.set_no_show_all(False);widget.set_opacity(1.);widget.show()
        self.art_shell.set_opacity(1.)
        native=self.window.get_window()
        if native:native.set_opacity(1.)
        self.window.get_style_context().remove_class('stage-opening')

    def release(self,_area):
        if self.driver:
            self.area.make_current()
            if not self.area.get_error():self.driver.close()
            self.driver=None
