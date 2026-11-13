"""Cached moving mirror contours. Two edge strips, no live polygon rasterizing."""
import ctypes as C
import weakref
import math
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
from mirror_facet_model import facets


class FacetLayer:
    def __init__(self,owner):
        from cover_pause_paint import bindings
        self.owner=weakref.ref(owner);self.c,self.g,pointer=bindings();self.closed=False
        self.area=Gtk.DrawingArea();self.area.set_has_window(False);self.area.set_no_show_all(True);self.area.set_can_focus(False)
        self.area.set_halign(Gtk.Align.FILL);self.area.set_valign(Gtk.Align.FILL)
        owner.overlay.add_overlay(self.area);owner.overlay.set_overlay_pass_through(self.area,True);owner.overlay.reorder_overlay(self.area,1)
        self.frames=[];self.blends=[];self.age=0.;self.index=0.;self.damage=0;self.draws=0;self.blend_index=None
        self.ptr=pointer(self.area.__gpointer__,None)
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.g.g_signal_connect_data(self.ptr,b'draw',self.callback,None,None,0)
        self.size_signal=self.area.connect('size-allocate',lambda *_:self.advance(owner.age))

    def set_atlas(self,atlas):
        self.width,self.height,frames=atlas
        for _ in range(2):
            surface=self.c.cairo_image_surface_create(0,self.width,self.height)
            self.blends.append((surface,self.c.cairo_create(surface)))
        for pair in frames:
            surfaces=[]
            for raw in pair:
                surface=self.c.cairo_image_surface_create(0,self.width,self.height)
                self.c.cairo_surface_flush(surface);C.memmove(self.c.cairo_image_surface_get_data(surface),raw,len(raw))
                self.c.cairo_surface_mark_dirty(surface);surfaces.append(surface)
            self.frames.append(tuple(surfaces))
        self.advance(self.owner().age)

    def advance(self,age):
        if self.closed:return
        owner=self.owner()
        if not owner or not owner.enabled:return
        from mirror_facet_atlas import PERIOD
        width,height=self.area.get_allocated_width(),self.area.get_allocated_height()
        self.age=age;self.index=(age%PERIOD)/PERIOD*len(self.frames) if self.frames else 0.
        self.damage=0;band=math.ceil(width*154/640)
        for left in (0,max(0,width-band)):
            self.area.queue_draw_area(left,0,band,height);self.damage+=band*height

    @property
    def cells(self):
        # Geometry inspection is on demand, never on the live frame clock.
        return facets(self.age,self.area.get_allocated_width(),self.area.get_allocated_height()) if self.frames else []

    def draw(self,_area,cr,_data):
        owner=self.owner()
        if self.closed or not owner or not owner.enabled or not self.frames:return False
        c=self.c;first=math.floor(self.index)%len(self.frames);mix=self.index%1
        w,h=self.area.get_allocated_width(),self.area.get_allocated_height();band=w*154/640
        if self.blend_index!=self.index:
            for side,(_surface,context) in enumerate(self.blends):
                c.cairo_set_operator(context,0);c.cairo_paint(context) # CLEAR: no retained trails.
                c.cairo_set_operator(context,1)
                c.cairo_set_source_surface(context,self.frames[first][side],0,0);c.cairo_paint_with_alpha(context,1-mix)
                c.cairo_set_operator(context,12)
                c.cairo_set_source_surface(context,self.frames[(first+1)%len(self.frames)][side],0,0);c.cairo_paint_with_alpha(context,mix)
            self.blend_index=self.index
        for side,left in ((0,0),(1,w-band)):
            c.cairo_save(cr);c.cairo_rectangle(cr,left,0,band,h);c.cairo_clip(cr)
            c.cairo_translate(cr,left,0);c.cairo_scale(cr,band/self.width,h/self.height)
            c.cairo_set_source_surface(cr,self.blends[side][0],0,0)
            c.cairo_paint_with_alpha(cr,min(1.,owner.rhythm.timing.gain));c.cairo_restore(cr)
        self.draws+=1;return False

    def close(self):
        if self.closed:return
        self.closed=True;self.g.g_signal_handler_disconnect(self.ptr,self.handler)
        self.area.disconnect(self.size_signal);self.area.destroy()
        for pair in self.frames:
            for surface in pair:self.c.cairo_surface_destroy(surface)
        self.frames=[]
        for surface,context in self.blends:
            self.c.cairo_destroy(context);self.c.cairo_surface_destroy(surface)
        self.blends=[]
