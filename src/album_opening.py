"""A finite, frame-clock album entrance. No image work or layout per frame."""
from gi.repository import Gtk


def ease(value):
    t=max(0.,min(1.,value));return t*t*t*(t*(t*6-15)+10)


class AlbumOpening:
    def __init__(self,owner):
        self.owner=owner;self.widgets=();self.tick=0;self.started=None
        owner.connect('unmap',lambda *_:self.finish())
        owner.connect('destroy',lambda *_:self.finish())

    @property
    def busy(self):return bool(self.tick)

    def begin(self,hero,records):
        self.finish()
        if not self.owner.get_mapped() or not Gtk.Settings.get_default().get_property('gtk-enable-animations'):return
        self.widgets=tuple(w for w in (hero,records) if w is not None)
        for w in self.widgets:w.set_opacity(.08)
        self.started=None;self.tick=self.owner.add_tick_callback(self.advance)

    def advance(self,_widget,clock):
        now=clock.get_frame_time()
        if self.started is None:self.started=now
        t=(now-self.started)/1e6
        if not Gtk.Settings.get_default().get_property('gtk-enable-animations') or t>=.66:
            self.tick=0;self.finish();return False
        for index,w in enumerate(self.widgets):w.set_opacity(.08+.92*ease((t-index*.075)/.54))
        return True

    def finish(self):
        if self.tick:self.owner.remove_tick_callback(self.tick);self.tick=0
        for widget in self.widgets:widget.set_opacity(1.)
        self.widgets=();self.started=None
