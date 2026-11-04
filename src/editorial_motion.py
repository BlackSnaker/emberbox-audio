"""Finite reader focus: gently bring an opened article into the shared scroll."""
from gi.repository import GLib,Gtk


class ReaderFocus:
    def __init__(self,scroll,content):
        self.scroll,self.content=scroll,content
        self.wait=0;self.tick=0;self.reader=None;self.started=None
        scroll.connect('unmap',lambda *_:self.stop())
        scroll.connect('destroy',lambda *_:self.stop())
        scroll.connect('scroll-event',self.interrupted)
        # Dragging the scrollbar or touching the page takes precedence.
        scroll.connect('button-press-event',self.interrupted)

    def interrupted(self,*_args):
        self.stop();return False

    def begin(self,reader,delay=32):
        self.stop()
        if reader is None:return
        self.reader=reader
        self.wait=GLib.timeout_add(delay,self.ready)

    def ready(self):
        self.wait=0
        if not self.reader or not self.reader.get_mapped():self.reader=None;return False
        point=self.reader.translate_coordinates(self.content,0,0)
        if point is None:self.reader=None;return False
        adjustment=self.scroll.get_vadjustment()
        self.start=adjustment.get_value()
        self.target=max(0,min(point[1]-8,adjustment.get_upper()-adjustment.get_page_size()))
        if abs(self.target-self.start)<1:self.reader=None;return False
        if not Gtk.Settings.get_default().get_property('gtk-enable-animations'):
            adjustment.set_value(self.target);self.reader=None;return False
        self.started=None;self.tick=self.scroll.add_tick_callback(self.advance)
        return False

    def advance(self,_widget,clock):
        now=clock.get_frame_time()
        if self.started is None:self.started=now
        t=min(1.,max(0.,(now-self.started)/540_000))
        ease=t*t*t*(t*(t*6-15)+10)
        self.scroll.get_vadjustment().set_value(self.start+(self.target-self.start)*ease)
        if t>=1 or not Gtk.Settings.get_default().get_property('gtk-enable-animations'):
            self.scroll.get_vadjustment().set_value(self.target)
            self.tick=0;self.reader=None;return False
        return True

    def stop(self):
        if self.wait:GLib.source_remove(self.wait);self.wait=0
        if self.tick:self.scroll.remove_tick_callback(self.tick);self.tick=0
        self.reader=None;self.started=None
