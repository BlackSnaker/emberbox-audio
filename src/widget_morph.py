"""Small-card resizing using two owned bitmap frames, not live GTK relayout."""
import numpy as np
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
from room_snapshot import snapshot


def pixels(frame):
    width,height,data=frame
    rgba=np.frombuffer(data,dtype=np.uint8).reshape(height,width,4)[...,[2,1,0,3]].copy()
    alpha=np.maximum(rgba[...,3:4].astype(np.float32),1.)
    rgba[...,:3]=np.clip(rgba[...,:3].astype(np.float32)*255/alpha,0,255).astype(np.uint8)
    return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgba.tobytes()),GdkPixbuf.Colorspace.RGB,True,8,width,height,width*4)


class WidgetMorph(Gtk.Overlay):
    DURATION=.38

    def __init__(self,window,root,finished):
        super().__init__()
        self.window,self.root,self.finished=window,root,finished
        self.add(root)
        self.images=[Gtk.Image(),Gtk.Image()]
        for image in self.images:
            image.set_halign(Gtk.Align.START);image.set_valign(Gtk.Align.START)
            image.set_no_show_all(True);self.add_overlay(image);self.set_overlay_pass_through(image,True)
        self.active=False;self.tick=0;self.started=None
        self.frames=[];self.source_size=self.target_size=(1,1);self.target_request=(1,1)

    def play(self,change):
        if self.active:self.finish()
        if not self.window.get_mapped() or not self.window.get_settings().get_property('gtk-enable-animations'):
            change();return
        width,height=self.window.get_size()
        rect=Gdk.Rectangle();rect.width=width;rect.height=height
        try:before=pixels(snapshot(self.root,rect))
        except (OSError,AttributeError,RuntimeError):change();return
        self.active=True
        change()
        self.target_request=tuple(self.window.get_size_request())
        preferred=self.root.get_preferred_size()[1]
        target_width=max(1,self.target_request[0],preferred.width)
        target_height=max(1,self.target_request[1],preferred.height)
        rect.width,rect.height=target_width,target_height
        try:after=pixels(snapshot(self.root,rect))
        except (OSError,AttributeError,RuntimeError):
            self.active=False;self.finished();return
        self.source_size=(width,height);self.target_size=(target_width,target_height)
        self.frames=[before,after];self.started=None
        self.root.set_no_show_all(True);self.root.hide()
        self.window.set_size_request(width,height);self.window.resize(width,height)
        for image in self.images:image.show()
        self.images[0].set_from_pixbuf(before);self.images[1].set_opacity(0.)
        self.tick=self.window.add_tick_callback(self.advance)

    def advance(self,_window,clock):
        now=clock.get_frame_time()
        if self.started is None:self.started=now
        t=max(0.,min(1.,(now-self.started)/1e6/self.DURATION))
        eased=t*t*t*(t*(t*6-15)+10)
        width,height=(max(1,round(a+(b-a)*eased)) for a,b in zip(self.source_size,self.target_size))
        for image,frame in zip(self.images,self.frames):
            image.set_from_pixbuf(frame.scale_simple(width,height,GdkPixbuf.InterpType.BILINEAR))
        self.images[0].set_opacity(1.-eased);self.images[1].set_opacity(eased)
        self.window.set_size_request(width,height);self.window.resize(width,height)
        if t>=1.:
            self.tick=0;self.finish();return False
        return True

    def finish(self,notify=True):
        if self.tick:self.window.remove_tick_callback(self.tick);self.tick=0
        if not self.active:return
        self.active=False
        for image in self.images:image.hide();image.clear();image.set_opacity(1.)
        self.frames=[];self.started=None
        self.root.set_no_show_all(False);self.root.show()
        if self.window.get_window():
            self.window.set_size_request(*self.target_request);self.window.resize(*self.target_size)
        if notify:self.finished()
