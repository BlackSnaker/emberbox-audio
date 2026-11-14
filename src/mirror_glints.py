"""A few drifting rectangular reflections, painted only in damaged footprints."""
import ctypes as C
import math
import weakref
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk


def glints(age,width,height):
    from mirror_facet_model import offset
    result=[]
    for i in range(12):
        phase=(offset(age*.55)+i*.139)%1
        # Fade completely before wrapping, so there is no right-to-left jump.
        envelope=math.sin(math.pi*phase)**2
        x=phase*width;y=(.10+((i*17)%37)/48)*height
        tone=(1.,.85,.62) if i%3 else (.66,.83,1.)
        result.append((x,y,8.+i%3*3,3.+i%2,.32*envelope,tone))
    return result


class Glints:
    def __init__(self,owner):
        from cover_pause_paint import bindings
        self.owner=weakref.ref(owner);self.c,self.g,pointer=bindings();self.closed=False
        self.area=Gtk.DrawingArea();self.area.set_has_window(False);self.area.set_no_show_all(True);self.area.set_can_focus(False)
        self.area.set_halign(Gtk.Align.FILL);self.area.set_valign(Gtk.Align.FILL)
        owner.overlay.add_overlay(self.area);owner.overlay.set_overlay_pass_through(self.area,True)
        owner.overlay.reorder_overlay(self.area,3 if getattr(owner,'facets',None) else 1)
        self.dots=[];self.damage=0
        self.ptr=pointer(self.area.__gpointer__,None)
        self.mask=self.c.cairo_image_surface_create(2,48,48)
        self.c.cairo_surface_flush(self.mask)
        data=[]
        for y in range(48):
            for x in range(48):
                distance=max(abs((x-23.5)/20),abs((y-23.5)/20))
                data.append(round(255*math.exp(-distance**4*3)))
        C.memmove(self.c.cairo_image_surface_get_data(self.mask),bytes(data),len(data));self.c.cairo_surface_mark_dirty(self.mask)
        self.c.cairo_mask_surface.restype=None;self.c.cairo_mask_surface.argtypes=[C.c_void_p,C.c_void_p,C.c_double,C.c_double]
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.g.g_signal_connect_data(self.ptr,b'draw',self.callback,None,None,0)
        self.size_signal=self.area.connect('size-allocate',lambda *_:self.advance(owner.age))

    def advance(self,age):
        if self.closed:return
        owner=self.owner()
        if not owner or not owner.enabled:return
        w,h=self.area.get_allocated_width(),self.area.get_allocated_height();before=self.dots
        self.dots=glints(age,w,h);self.damage=0
        # Old/new footprints stay separate at the horizontal wrap seam.
        for x,y,rx,ry,_,_ in before+self.dots:
            left=max(0,math.floor(x-rx*3-2));top=max(0,math.floor(y-ry*3-2))
            right=min(w,math.ceil(x+rx*3+2));bottom=min(h,math.ceil(y+ry*3+2))
            if right>left and bottom>top:
                self.area.queue_draw_area(left,top,right-left,bottom-top);self.damage+=(right-left)*(bottom-top)

    def draw(self,_area,cr,_data):
        owner=self.owner()
        if self.closed or not owner or not owner.enabled:return False
        c=self.c
        pulse,energy,bass,air,warmth,weave,depth=owner.optics.values
        for index,(x,y,rx,ry,alpha,tone) in enumerate(self.dots):
            alpha*=owner.rhythm.timing.gain*(.86+.16*energy+.24*pulse)
            swell=1+.10*pulse+.06*math.sin(owner.age*.113+index*.7+weave*2)
            rx*=swell;ry*=1+.12*air
            tone=tuple(min(1.,value*(.96+.08*warmth if channel!=2 else 1.04-.08*warmth))
                       for channel,value in enumerate(tone))
            palette=owner.cover_palette.values
            reflected=palette[:3] if index%3 else palette[3:6]
            tone=tuple(a+(b-a)*palette[6] for a,b in zip(tone,reflected))
            if alpha<.003:continue
            for scale,strength in ((2.4,.12),(1.,.9)):
                c.cairo_save(cr);c.cairo_translate(cr,x,y);c.cairo_scale(cr,rx*scale/24,ry*scale/24)
                c.cairo_set_source_rgba(cr,*tone,alpha*strength);c.cairo_mask_surface(cr,self.mask,-24.,-24.);c.cairo_restore(cr)
        return False

    def close(self):
        if self.closed:return
        self.closed=True;self.g.g_signal_handler_disconnect(self.ptr,self.handler)
        self.area.disconnect(self.size_signal);self.area.destroy();self.c.cairo_surface_destroy(self.mask);self.mask=None
