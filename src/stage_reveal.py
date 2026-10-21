"""A frame-clock fullscreen entrance using only GTK and owned widget images.

The window is fullscreen once. Animate lightweight overlay pieces instead of
asking the window manager to resize a window on every frame.
"""
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk


def smooth(value):
    t=max(0.,min(1.,value))
    return t*t*t*(t*(t*6-15)+10)


def interpolate(start,end,amount):
    return tuple(a+(b-a)*amount for a,b in zip(start,end))


class StageReveal(Gtk.Fixed):
    DURATION=.72

    def __init__(self,window,background,layout,cover,art_shell):
        super().__init__()
        self.window,self.background,self.layout=window,background,layout
        self.cover,self.art_shell=cover,art_shell
        self.active=False;self.started=None;self.progress=1.
        self.origin=(0,0,1,1);self.cover_origin=None;self.cover_pixels=None
        self.panel=Gtk.Box()
        self.panel.get_style_context().add_class('stage-opening-card')
        self.ghost=Gtk.Image();self.flying_cover=Gtk.Image()
        self.put(self.panel,0,0);self.put(self.ghost,0,0);self.put(self.flying_cover,0,0)
        self.set_halign(Gtk.Align.FILL);self.set_valign(Gtk.Align.FILL)
        self.set_no_show_all(True)

    def prepare(self,host,monitor):
        self.finish()
        settings=self.window.get_settings()
        if settings and not settings.get_property('gtk-enable-animations'):return
        geometry=monitor.get_geometry() if monitor else None
        width,height=(geometry.width,geometry.height) if geometry else (1280,800)
        ox,oy=(geometry.x,geometry.y) if geometry else (0,0)
        self.origin=(width*.32,height*.3,width*.36,height*.4)
        native=host.window.get_window()
        if native and host.window.get_mapped():
            x,y=host.window.get_position();w,h=host.window.get_size()
            self.origin=(max(0,min(width-1,x-ox)),max(0,min(height-1,y-oy)),
                         min(w,width),min(h,height))
            try:
                # Read only our own application window, never the desktop.
                pixels=Gdk.pixbuf_get_from_window(native,0,0,w,h)
                if pixels:self.ghost.set_from_pixbuf(pixels)
            except GLib.Error:
                pass
        image=getattr(host,'cover',None)
        if image and image.get_mapped() and image.get_pixbuf():
            point=image.translate_coordinates(host.window,0,0)
            if point:
                self.cover_pixels=image.get_pixbuf()
                w,h=self.cover_pixels.get_width(),self.cover_pixels.get_height()
                self.cover_origin=(self.origin[0]+point[0]+(image.get_allocated_width()-w)/2,
                                   self.origin[1]+point[1]+(image.get_allocated_height()-h)/2,w,h)
        self.active=True;self.started=None;self.progress=0.
        # Non-composited desktops need an opaque base; transparent X11 pixels
        # otherwise expose uninitialised backing storage during the first fade.
        if self.window.get_screen().is_composited():
            self.window.get_style_context().add_class('stage-opening')
        self.background.set_opacity(0.);self.layout.set_opacity(0.)
        self.art_shell.set_opacity(0. if self.cover_pixels else 1.)
        self.panel.set_opacity(1.);self.ghost.set_opacity(1.)
        x,y,w,h=self.origin
        self.panel.set_size_request(round(w),round(h));self.move(self.panel,round(x),round(y))
        self.move(self.ghost,round(x),round(y))
        self.panel.show();self.ghost.show();self.show()

    def advance(self,now):
        if not self.active:return
        if self.started is None:self.started=now
        t=max(0.,(now-self.started)/1_000_000/self.DURATION)
        self.progress=min(1.,t)
        if t>=1.:
            self.finish();return
        width,height=self.window.get_size()
        x,y,w,h=interpolate(self.origin,(0,0,width,height),smooth(t))
        self.panel.set_size_request(max(1,round(w)),max(1,round(h)))
        self.move(self.panel,round(x),round(y))
        self.panel.set_opacity(1.-smooth((t-.35)/.65))
        self.ghost.set_opacity(1.-smooth(t/.28))
        self.background.set_opacity(smooth((t-.08)/.78))
        self.layout.set_opacity(smooth((t-.17)/.83))
        if self.cover_pixels:
            point=self.cover.translate_coordinates(self.window,0,0)
            if point:
                destination=(*point,self.cover.get_allocated_width(),self.cover.get_allocated_height())
                x,y,w,h=interpolate(self.cover_origin,destination,smooth(t/.9))
                size=max(1,round(min(w,h)))
                # The high-quality image may arrive during the entrance.
                pixels=self.cover.get_pixbuf() or self.cover_pixels
                self.flying_cover.set_from_pixbuf(pixels.scale_simple(size,size,GdkPixbuf.InterpType.BILINEAR))
                self.move(self.flying_cover,round(x),round(y));self.flying_cover.show()
                blend=smooth((t-.72)/.28)
                self.flying_cover.set_opacity(1.-blend);self.art_shell.set_opacity(blend)
        self.queue_draw()

    def finish(self):
        self.active=False;self.started=None;self.progress=1.
        self.hide();self.flying_cover.hide()
        self.ghost.clear();self.flying_cover.clear()
        self.cover_origin=None;self.cover_pixels=None
        self.background.set_opacity(1.);self.layout.set_opacity(1.);self.art_shell.set_opacity(1.)
        self.window.get_style_context().remove_class('stage-opening')
