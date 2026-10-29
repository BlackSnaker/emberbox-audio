"""Cover-local water transition, with a compositor fade on systems without GL."""
from gi.repository import GLib,Gtk
from cover_ripple_gl import CoverRippleGL


def smooth(value):
    t=max(0.,min(1.,value))
    return t*t*t*(t*(t*6-15)+10)


class CoverRipple(Gtk.Overlay):
    REVEAL=1.35
    MAX_WAIT=27.

    def __init__(self):
        super().__init__()
        self.driver=None;self.failed=False;self.closed=False
        self.active=False;self.tick=0;self.age=0.;self.progress=0.;self.last_now=None
        self.old=self.new=None;self.ready=False;self.reveal_start=None;self.wait_start=None
        self.size=380;self.radius=22
        self.old_image=Gtk.Image();self.add(self.old_image)
        self.new_image=Gtk.Image();self.add_overlay(self.new_image)
        self.set_overlay_pass_through(self.new_image,True)
        self.area=Gtk.GLArea();self.area.set_required_version(3,2);self.area.set_use_es(False)
        self.area.set_has_alpha(True);self.area.set_auto_render(False)
        self.add_overlay(self.area);self.set_overlay_pass_through(self.area,True)
        self.area.connect('render',self.render);self.area.connect('unrealize',self.release)
        self.connect('unmap',lambda *_:self.cancel())
        self.connect('destroy',self.close)
        self.set_halign(Gtk.Align.FILL);self.set_valign(Gtk.Align.FILL)
        for item in (self,self.area,self.new_image):item.set_no_show_all(True)

    def resize(self,size,radius=22):
        self.size,self.radius=size,radius
        self.set_size_request(size,size)
        self.old_image.set_size_request(size,size);self.new_image.set_size_request(size,size)
        if self.active and not self.driver:self.paint_fallback()

    def warmup(self,allow_software=False):
        if self.closed or self.driver or self.failed:return
        if not self.get_settings().get_property('gtk-enable-animations'):return
        try:
            parents=[];item=self.area
            while item and not item.get_realized():parents.append(item);item=item.get_parent()
            for item in reversed(parents):item.realize()
            self.area.make_current()
            if self.area.get_error():raise RuntimeError('Cover GL unavailable')
            self.driver=CoverRippleGL(allow_software=allow_software)
            self.area.attach_buffers()
            self.driver.draw(1,1,None,None,0.,0.)
            self.driver.call('Finish')
        except (OSError,RuntimeError,AttributeError):
            self.release(self.area);self.failed=True

    def begin(self,pixels):
        self.cancel()
        if self.closed or pixels is None:return False
        if not self.get_settings().get_property('gtk-enable-animations'):return False
        self.old=pixels;self.active=True;self.wait_start=GLib.get_monotonic_time()
        self.show()
        if self.driver:
            self.old_image.hide();self.new_image.hide();self.area.show();self.area.queue_render()
        else:
            self.area.hide();self.paint_fallback()
        self.tick=self.add_tick_callback(self.advance)
        return True

    def supply(self,pixels):
        if not self.active or pixels is None:return
        if pixels is self.new:return
        self.new=pixels
        if not self.driver:self.paint_fallback()

    def resolve(self):
        self.ready=True

    def get_pixbuf(self):
        return self.new if self.new is not None and self.progress>=.5 else self.old

    def advance(self,_widget,clock):
        if not self.active or not self.get_mapped():self.cancel();return False
        if not self.get_settings().get_property('gtk-enable-animations'):self.cancel();return False
        wall_now=GLib.get_monotonic_time()
        if self.wait_start and wall_now-self.wait_start>self.MAX_WAIT*1e6:self.cancel();return False
        # Sample the presentation clock, so varying GTK callback arrival times
        # cannot jitter the optical front between otherwise regular frames.
        now=clock.get_frame_time() if clock is not None else wall_now
        delta=max(0.,min(.05,(now-self.last_now)/1e6)) if self.last_now is not None else 0.
        self.last_now=max(now,self.last_now or now);self.age+=delta
        if self.ready and self.new is not None:
            if self.reveal_start is None:self.reveal_start=self.age
            self.progress=smooth((self.age-self.reveal_start)/self.REVEAL)
        if self.progress>=1.:
            self.cancel();return False
        if self.driver:self.area.queue_render()
        else:self.new_image.set_opacity(self.progress)
        return True

    def paint_fallback(self):
        from gi.repository import GdkPixbuf
        for image,pixels in ((self.old_image,self.old),(self.new_image,self.new)):
            if pixels is None:image.clear();continue
            if pixels.get_width()!=self.size or pixels.get_height()!=self.size:
                pixels=pixels.scale_simple(self.size,self.size,GdkPixbuf.InterpType.BILINEAR)
            image.set_from_pixbuf(pixels)
        self.old_image.show();self.new_image.set_opacity(self.progress);self.new_image.show()

    def render(self,_area,_context):
        if not self.driver or not self.active or self.old is None:return True
        try:
            scale=self.area.get_scale_factor()
            self.driver.call('Viewport',0,0,self.area.get_allocated_width()*scale,self.area.get_allocated_height()*scale)
            self.driver.draw(self.area.get_allocated_width()*scale,self.area.get_allocated_height()*scale,
                             self.old,self.new,self.age,self.progress,self.radius*scale)
        except (OSError,RuntimeError,AttributeError):
            self.release(self.area);self.failed=True;self.area.hide();self.paint_fallback()
        return True

    def cancel(self):
        self.active=False
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.old=self.new=None;self.old_image.clear();self.new_image.clear()
        self.age=self.progress=0.;self.last_now=None;self.reveal_start=None;self.wait_start=None;self.ready=False
        self.hide()
        if self.driver:self.driver.forget()

    def release(self,_area):
        if self.driver:
            self.area.make_current()
            if not self.area.get_error():self.driver.close()
            self.driver=None

    def close(self,*_):
        if self.closed:return
        self.cancel();self.closed=True
