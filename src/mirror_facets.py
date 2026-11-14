"""A seamless sideways mirror panorama with GPU and bounded Cairo paths."""
import ctypes as C
import weakref
import math
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk
from mirror_facet_model import offset, facets


_ACCELERATED=None


def accelerated():
    """Avoid enabling GTK's software GL compositor on an unaccelerated X server."""
    global _ACCELERATED
    if _ACCELERATED is None:
        from mirror_pan_gl import hardware_available
        _ACCELERATED=hardware_available() is True
    return _ACCELERATED


class FacetLayer:
    def __init__(self,owner):
        from cover_pause_paint import bindings
        self.owner=weakref.ref(owner);self.c,self.g,pointer=bindings();self.closed=False
        self.c.cairo_mask_surface.restype=None;self.c.cairo_mask_surface.argtypes=[C.c_void_p,C.c_void_p,C.c_double,C.c_double]
        self.c.cairo_pattern_set_extend.restype=None;self.c.cairo_pattern_set_extend.argtypes=[C.c_void_p,C.c_int]
        self.area=Gtk.DrawingArea();self.area.set_has_window(False);self.area.set_no_show_all(True);self.area.set_can_focus(False)
        self.area.set_halign(Gtk.Align.FILL);self.area.set_valign(Gtk.Align.FILL)
        self.fallback=self.area
        owner.overlay.add_overlay(self.area);owner.overlay.set_overlay_pass_through(self.area,True);owner.overlay.reorder_overlay(self.area,1)
        self.gl=Gtk.GLArea();self.gl.set_required_version(3,2);self.gl.set_use_es(False)
        self.gl.set_has_alpha(True);self.gl.set_auto_render(False);self.gl.set_can_focus(False);self.gl.set_no_show_all(True)
        self.gl.set_halign(Gtk.Align.FILL);self.gl.set_valign(Gtk.Align.FILL)
        owner.overlay.add_overlay(self.gl);owner.overlay.set_overlay_pass_through(self.gl,True);owner.overlay.reorder_overlay(self.gl,2)
        self.gl.connect('render',self.render);self.gl.connect('unrealize',self.release)
        self.frames=[];self.age=0.;self.damage=0;self.draws=0;self.mask=None
        self.driver=None;self.failed=False;self.atlas=None
        self.canvas=self.context=None;self.composed_age=None
        self.ptr=pointer(self.fallback.__gpointer__,None)
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.g.g_signal_connect_data(self.ptr,b'draw',self.callback,None,None,0)
        self.size_signal=self.area.connect('size-allocate',lambda *_:self.advance(owner.age))

    def set_atlas(self,atlas):
        from mirror_facet_atlas import vignette
        self.atlas=atlas;self.width,self.height,textures=atlas
        for raw in textures:
            surface=self.c.cairo_image_surface_create(0,self.width,self.height)
            self.c.cairo_surface_flush(surface);C.memmove(self.c.cairo_image_surface_get_data(surface),raw,len(raw))
            self.c.cairo_surface_mark_dirty(surface);self.frames.append(surface)
        self.mask_width,self.mask_height,raw=vignette()
        self.mask=self.c.cairo_image_surface_create(2,self.mask_width,self.mask_height)
        self.c.cairo_surface_flush(self.mask);C.memmove(self.c.cairo_image_surface_get_data(self.mask),raw,len(raw))
        self.c.cairo_surface_mark_dirty(self.mask)
        self.warmup();self.advance(self.owner().age)

    def warmup(self,allow_software=False):
        if self.closed or self.driver or self.failed or self.atlas is None:return
        try:
            from mirror_pan_gl import MirrorPanGL
            if not allow_software and not accelerated():raise RuntimeError('Use Cairo compatibility')
            parents=[];item=self.gl
            while item and not item.get_realized():parents.append(item);item=item.get_parent()
            for item in reversed(parents):item.realize()
            self.gl.make_current()
            if self.gl.get_error():raise RuntimeError('Mirror GL unavailable')
            self.driver=MirrorPanGL(allow_software=allow_software)
            self.gl.show();self.gl.queue_render()
        except (OSError,RuntimeError,AttributeError):
            self.release();self.failed=True;self.gl.hide();self.gl.destroy();self.gl=None
            Gdk.GLContext.clear_current();self.fallback.show()

    def advance(self,age):
        if self.closed:return
        owner=self.owner()
        if not owner or not owner.enabled:return
        self.age=age
        width,height=self.area.get_allocated_width(),self.area.get_allocated_height()
        band=(width+3)//4;self.damage=band*height*2
        if self.driver:self.gl.queue_render()
        else:
            self.fallback.queue_draw_area(0,0,band,height)
            self.fallback.queue_draw_area(max(0,width-band),0,band,height)

    @property
    def cells(self):
        return facets(self.age,self.area.get_allocated_width(),self.area.get_allocated_height()) if self.frames else []

    def render(self,_area,_context):
        owner=self.owner()
        if self.closed or not owner or not owner.enabled:return True
        if not self.driver and not self.failed:self.warmup()
        if not self.driver:return True
        try:
            scale=self.gl.get_scale_factor()
            visual=owner.optics.values
            phases=tuple((self.age*rate)%math.tau for rate in (.19,.113,.071))
            self.driver.draw(self.gl.get_allocated_width()*scale,self.gl.get_allocated_height()*scale,
                             self.atlas,offset(self.age),(visual[:4],visual[4:],phases))
            self.draws+=1
        except (OSError,RuntimeError,AttributeError):
            self.release();self.failed=True;self.gl.hide();self.fallback.show();self.fallback.queue_draw()
        return True

    def draw(self,_area,cr,_data):
        owner=self.owner()
        if self.closed or not owner or not owner.enabled or not self.frames or self.driver:return False
        c=self.c;w,h=self.area.get_allocated_width(),self.area.get_allocated_height()
        # Compatibility compositing stays at 384 x 216. A direct fullscreen
        # source+mask operation falls back to costly per-pixel resampling on
        # some X11 servers; one retained small canvas avoids that slow path.
        if self.canvas is None:
            self.canvas=c.cairo_image_surface_create(0,self.mask_width,self.mask_height)
            self.context=c.cairo_create(self.canvas)
        if self.composed_age!=self.age:
            context=self.context
            c.cairo_set_operator(context,0);c.cairo_paint(context);c.cairo_set_operator(context,2)
            c.cairo_save(context);c.cairo_scale(context,self.mask_width/self.width,self.mask_height/self.height)
            c.cairo_set_source_surface(context,self.frames[0],offset(self.age)*self.width,0)
            source=c.cairo_get_source(context);c.cairo_pattern_set_extend(source,1);c.cairo_pattern_set_filter(source,1)
            c.cairo_scale(context,self.width/self.mask_width,self.height/self.mask_height)
            c.cairo_mask_surface(context,self.mask,0,0);c.cairo_restore(context)
            self.composed_age=self.age
        c.cairo_save(cr)
        c.cairo_rectangle(cr,0,0,w*.25,h);c.cairo_rectangle(cr,w*.75,0,w*.25,h);c.cairo_clip(cr)
        c.cairo_scale(cr,w/self.mask_width,h/self.mask_height)
        c.cairo_set_source_surface(cr,self.canvas,0,0)
        pulse,energy,*_=owner.optics.values
        c.cairo_paint_with_alpha(cr,min(1.,.92+.06*energy+.08*pulse));c.cairo_restore(cr)
        self.draws+=1;return False

    def release(self,*_):
        if self.driver:
            self.gl.make_current()
            if not self.gl.get_error():self.driver.close()
            self.driver=None

    def close(self):
        if self.closed:return
        self.closed=True;self.release();self.g.g_signal_handler_disconnect(self.ptr,self.handler)
        self.area.disconnect(self.size_signal)
        if self.gl:self.gl.destroy();self.gl=None
        self.area.destroy()
        for surface in self.frames:self.c.cairo_surface_destroy(surface)
        self.frames=[];self.atlas=None
        if self.mask:self.c.cairo_surface_destroy(self.mask);self.mask=None
        if self.context:self.c.cairo_destroy(self.context);self.context=None
        if self.canvas:self.c.cairo_surface_destroy(self.canvas);self.canvas=None
