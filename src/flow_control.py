"""An amber, tactile EmberFlow switch shared by widget, room and settings."""
from gi.repository import Gtk
from functools import lru_cache
from hardware_controls import pixbuf
from source_picker import text

CSS=b'''
button.ember-flow, .ember-stage button.ember-flow {
  padding: 4px 7px; min-height: 18px; min-width: 0; border-radius: 14px;
  border: 1px solid rgba(235,219,178,.06); color: #a89984;
  background-image: linear-gradient(to bottom,#34362d,#282c25);
  box-shadow: 2px 3px 5px rgba(0,0,0,.17), inset 0 1px rgba(235,219,178,.05);
  font-size: 9px; font-weight: bold; outline-width: 0;
}
button.ember-flow:checked, .ember-stage button.ember-flow:checked {
  color: #f1cf83; border-color: rgba(215,153,33,.22);
  background-image: linear-gradient(to bottom,#3a392a,#2c3025);
}
button.ember-flow:disabled { opacity: .55; }
'''


@lru_cache(maxsize=51)
def switch_frame(index):
    t=index/50;x=8+13*t
    high=tuple(round(a+(b-a)*t) for a,b in zip((140,148,122),(242,207,128)))
    low=tuple(round(a+(b-a)*t) for a,b in zip((71,84,69),(161,102,33)))
    color=lambda c:'#%02x%02x%02x'%c
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="29" height="14" viewBox="0 0 29 14">
      <defs><linearGradient id="face" x1="0" y1="0" x2="0" y2="1">
      <stop stop-color="{color(high)}"/><stop offset="1" stop-color="{color(low)}"/></linearGradient>
      <radialGradient id="light"><stop stop-color="#f2b64d" stop-opacity="{t*.4:.3f}"/>
      <stop offset="1" stop-color="#f2b64d" stop-opacity="0"/></radialGradient></defs>
      <rect x="1" y="1" width="27" height="12" rx="6" fill="#141a14" stroke="#8b8261" stroke-opacity=".25"/>
      <circle cx="{x:.2f}" cy="7" r="8" fill="url(#light)"/>
      <circle cx="{x:.2f}" cy="7" r="4.8" fill="url(#face)"/>
      <path d="M{x-3:.2f} 5a3.5 3.5 0 0 1 5-1" fill="none" stroke="#fff3c5" stroke-opacity=".4" stroke-width=".8"/>
    </svg>'''
    return pixbuf(svg,29,14)


class FlowControl(Gtk.ToggleButton):
    def __init__(self,flow,beats=False):
        super().__init__();self.flow=flow;self.syncing=False;self.beats=beats
        self.shown=self.target=float(flow.beat_sync if beats else flow.enabled);self.tick=0;self.frame_start=None
        self.get_style_context().add_class('ember-flow');self.set_has_tooltip(False)
        self.get_accessible().set_name('Beat sync' if beats else 'EmberFlow')
        box=Gtk.Box(spacing=6);self.add(box)
        box.pack_start(Gtk.Label(label=text('Beats','Биты') if beats else 'EmberFlow'),False,False,0)
        self.indicator=Gtk.Image();self.frame=None;box.pack_end(self.indicator,False,False,0)
        self.connect('toggled',self.toggled)
        self.unsubscribe=flow.music.subscribe(self.sync)
        self.connect('destroy',lambda *_:self.unsubscribe());self.sync()

    def toggled(self,_button):
        if not self.syncing:
            (self.flow.set_beat_sync if self.beats else self.flow.set_enabled)(self.get_active())

    def sync(self):
        self.syncing=True
        value=self.flow.beat_sync if self.beats else self.flow.enabled
        try:self.set_active(value);self.set_sensitive(self.flow.supported or self.flow.enabled)
        finally:self.syncing=False
        target=float(value)
        if target!=self.target:
            self.from_position=self.shown;self.target=target;self.frame_start=None
            if self.get_mapped() and self.get_settings().get_property('gtk-enable-animations'):
                if not self.tick:self.tick=self.add_tick_callback(self.animate)
            else:self.shown=target
        self.get_accessible().set_description(self.flow.message);self.render()

    def animate(self,_widget,clock):
        now=clock.get_frame_time()/1e6
        if self.frame_start is None:self.frame_start=now
        t=min(1.,(now-self.frame_start)/.24);ease=t*t*t*(t*(t*6-15)+10)
        self.shown=self.from_position+(self.target-self.from_position)*ease;self.render()
        if t>=1:self.tick=0;return False
        return True

    def render(self):
        frame=round(self.shown*50)
        if frame!=self.frame:self.frame=frame;self.indicator.set_from_pixbuf(switch_frame(frame))
