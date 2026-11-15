"""Retained in-window transitions when hardware GL is unavailable.

Two endpoint scenes and the artwork are captured once. Only their composition
changes per frame; the native window stays mapped and fully opaque throughout.
"""
import ctypes as C
from ctypes.util import find_library
import weakref
from gi.repository import Gtk
from cover_pause_paint import bindings,rounded,ease


class RevealPaint:
    def __init__(self,owner):
        self.owner=weakref.ref(owner)
        self.c,self.g,self.pointer=bindings()
        self.area=Gtk.DrawingArea();self.area.set_has_window(False)
        self.area.set_can_focus(False);self.area.set_no_show_all(True)
        self.area.set_halign(Gtk.Align.FILL);self.area.set_valign(Gtk.Align.FILL)
        self.frames=[];self.art=self.base=None;self.closed=False
        self.ptr=self.pointer(self.area.__gpointer__,None)
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.g.g_signal_connect_data(self.ptr,b'draw',self.callback,None,None,0)

    def image(self,pixels):
        if pixels is None:return None
        c=self.c;w,h=pixels.get_width(),pixels.get_height()
        surface=c.cairo_image_surface_create(0,w,h);cr=c.cairo_create(surface)
        gdk=C.CDLL(find_library('gdk-3'))
        gdk.gdk_cairo_set_source_pixbuf.restype=None
        gdk.gdk_cairo_set_source_pixbuf.argtypes=[C.c_void_p,C.c_void_p,C.c_double,C.c_double]
        try:
            gdk.gdk_cairo_set_source_pixbuf(cr,self.pointer(pixels.__gpointer__,None),0.,0.)
            c.cairo_paint(cr)
        finally:c.cairo_destroy(cr)
        return surface,w,h

    def prepare(self,room,previous,background,pixels):
        self.clear();c=self.c
        self.base=self.image(background)
        for frame in (previous,room):
            if frame is None:self.frames.append(None);continue
            w,h,data=frame
            content=c.cairo_image_surface_create(0,w,h)
            c.cairo_surface_flush(content)
            C.memmove(c.cairo_image_surface_get_data(content),data,len(data))
            c.cairo_surface_mark_dirty(content)
            surface=c.cairo_image_surface_create(0,w,h);cr=c.cairo_create(surface)
            try:
                # Opaque endpoint scenes prevent the old text/artwork from
                # showing through the transparent parts of its replacement.
                c.cairo_set_source_rgba(cr,.065,.069,.067,1.);c.cairo_paint(cr)
                if self.base:self.paint(cr,self.base,(0,0,w,h))
                c.cairo_set_source_surface(cr,content,0,0);c.cairo_paint(cr)
            finally:c.cairo_destroy(cr);c.cairo_surface_destroy(content)
            self.frames.append((surface,w,h))
        self.art=self.image(pixels)

    def paint(self,cr,image,rect,alpha=1.,radius=0.):
        c=self.c;surface,w,h=image;x,y,width,height=rect
        if width<=0 or height<=0 or alpha<=0:return
        c.cairo_save(cr)
        try:
            if radius:rounded(c,cr,x,y,width,height,radius);c.cairo_clip(cr)
            c.cairo_translate(cr,x,y);c.cairo_scale(cr,width/w,height/h)
            c.cairo_set_source_surface(cr,surface,0,0)
            c.cairo_pattern_set_filter(c.cairo_get_source(cr),1)
            c.cairo_paint_with_alpha(cr,alpha)
        finally:c.cairo_restore(cr)

    def draw(self,_area,cr,_data):
        owner=self.owner()
        if self.closed or not owner or not owner.active or not owner.fallback or not self.frames:return False
        width,height=self.area.get_allocated_width(),self.area.get_allocated_height()
        rect=(0,0,width,height);old,new=self.frames;t=ease(owner.progress)
        if old:
            self.paint(cr,old,rect)
            if new:self.paint(cr,new,rect,t)
        elif new:
            # Reveal the controls over a stable themed room, never the desktop.
            if self.base:self.paint(cr,self.base,rect)
            else:
                self.c.cairo_set_source_rgba(cr,*owner.pigment,1.);self.c.cairo_paint(cr)
            self.paint(cr,new,rect,ease((owner.progress-.18)/.82))
        if self.art:
            start,end=owner.cover_origin,owner.cover_end
            if start and end:
                art=tuple(a+(b-a)*t for a,b in zip(start,end))
                self.paint(cr,self.art,art,radius=max(6.,min(22.,art[2]*.04)))
        return True

    def clear(self):
        for image in self.frames+[self.art,self.base]:
            if image:self.c.cairo_surface_destroy(image[0])
        self.frames=[];self.art=self.base=None

    def close(self):
        if self.closed:return
        self.closed=True;self.clear()
        self.g.g_signal_handler_disconnect(self.ptr,self.handler)
