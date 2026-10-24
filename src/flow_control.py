"""A recessed incandescent EmberFlow switch shared by widget, room and settings."""
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
button.ember-flow.ember-flow-lamp, .ember-stage button.ember-flow.ember-flow-lamp {
  padding: 4px 8px; border-color: rgba(12,16,12,.52);
  background-image: linear-gradient(to bottom,#1b201a,#252a21);
  box-shadow: inset 0 2px 4px rgba(0,0,0,.44),
              inset 1px 0 2px rgba(0,0,0,.18), 0 1px rgba(235,219,178,.09);
  color: #a89984; outline-style: none;
  transition: color 420ms ease;
}
button.ember-flow.ember-flow-lamp:checked, .ember-stage button.ember-flow.ember-flow-lamp:checked {
  color: #efcf92; border-color: rgba(12,16,12,.52);
  background-image: linear-gradient(to bottom,#201f17,#2c2b20);
}
button.ember-flow.ember-flow-lamp:active, .ember-stage button.ember-flow.ember-flow-lamp:active {
  box-shadow: inset 0 3px 5px rgba(0,0,0,.52), 0 1px rgba(235,219,178,.07);
}
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


@lru_cache(maxsize=101)
def lamp_frame(index):
    """Small filter-free glass/filament sprites; no redraws once heat settles."""
    heat=max(0.,min(1.,index/100));light=heat**3
    def wire_color(value):
        stops=((.0,(88,72,52)),(.35,(170,70,26)),(.68,(247,151,49)),(1.,(255,231,172)))
        for (a,low),(b,high) in zip(stops,stops[1:]):
            if value<=b:
                t=max(0.,(value-a)/(b-a))
                return '#%02x%02x%02x'%tuple(round(x+(y-x)*t) for x,y in zip(low,high))
        return '#ffe7ac'
    center=wire_color(heat);edge=wire_color(max(0.,heat*1.15-.15))
    coil='M10.5 9L11.8 9L12.6 7.7L14 10.3L15.4 7.7L16.8 10.3L18.2 7.7L19.6 10.3L21 7.7L22.4 10.3L23.8 7.7L25.2 10.3L26 9L27.5 9'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="38" height="18" viewBox="0 0 38 18">
      <defs>
        <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
          <stop stop-color="#11160f"/><stop offset=".55" stop-color="#25271a"/><stop offset="1" stop-color="#151a12"/>
        </linearGradient>
        <radialGradient id="warmth"><stop stop-color="#ff9b24" stop-opacity="{light*.38:.4f}"/>
          <stop offset=".5" stop-color="#e88318" stop-opacity="{light*.14:.4f}"/>
          <stop offset="1" stop-color="#d47718" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="wire"><stop stop-color="{edge}"/><stop offset=".5" stop-color="{center}"/><stop offset="1" stop-color="{edge}"/></linearGradient>
      </defs>
      <rect x=".5" y=".8" width="37" height="16.4" rx="8.2" fill="#0f140e"/>
      <path d="M3 13.5Q5 17.2 10 17.2H28Q33 17.2 35 13.5" fill="none" stroke="#e1d1a6" stroke-opacity=".15" stroke-width=".6"/>
      <rect x="1.8" y="2" width="34.4" height="13.7" rx="6.8" fill="url(#glass)" stroke="#79785b" stroke-opacity=".22" stroke-width=".6"/>
      <ellipse cx="19" cy="9" rx="17" ry="6.6" fill="url(#warmth)"/>
      <path d="M7 11.5L10.5 9M27.5 9L31 11.5" fill="none" stroke="#8c8566" stroke-opacity=".38" stroke-width=".65"/>
      <path d="{coil}" fill="none" stroke="#fa8f18" stroke-width="5" stroke-opacity="{light*.07:.4f}" stroke-linejoin="round"/>
      <path d="{coil}" fill="none" stroke="#ffa333" stroke-width="2.8" stroke-opacity="{light*.18:.4f}" stroke-linejoin="round"/>
      <path d="{coil}" fill="none" stroke="url(#wire)" stroke-width=".8" stroke-opacity="{.45+heat*.55:.4f}" stroke-linejoin="round"/>
      <path d="M14 9.2L15.4 7.7L16.8 10.3L18.2 7.7L19.6 10.3L21 7.7L22.4 10.3L23.2 8.9" fill="none" stroke="#fff4d5" stroke-width=".34" stroke-opacity="{light*.6:.4f}"/>
      <path d="M6 4.7Q8 3.4 12 3.4H26" fill="none" stroke="#fff2cf" stroke-opacity=".13" stroke-width=".65" stroke-linecap="round"/>
      <path d="M6.7 5.5H11" fill="none" stroke="#fff2cf" stroke-opacity=".045" stroke-width="1.2" stroke-linecap="round"/>
      <path d="M5 12.6Q7 14.3 11 14.3H27Q31 14.3 33 12.6" fill="none" stroke="#f9b64b" stroke-opacity="{.025+light*.16:.4f}" stroke-width=".65"/>
    </svg>'''
    return pixbuf(svg,38,18)


class FlowControl(Gtk.ToggleButton):
    def __init__(self,flow,beats=False):
        super().__init__();self.flow=flow;self.syncing=False;self.beats=beats
        self.shown=self.target=float(flow.beat_sync if beats else flow.enabled);self.tick=0;self.frame_start=None
        self.get_style_context().add_class('ember-flow');self.set_has_tooltip(False)
        if not beats:self.get_style_context().add_class('ember-flow-lamp')
        self.get_accessible().set_name('Beat sync' if beats else 'EmberFlow')
        box=Gtk.Box(spacing=6);self.add(box)
        box.pack_start(Gtk.Label(label=text('Beats','Биты') if beats else 'EmberFlow'),False,False,0)
        self.indicator=Gtk.Image();self.frame=None;box.pack_end(self.indicator,False,False,0)
        self.connect('toggled',self.toggled)
        self.unsubscribe=flow.music.subscribe(self.sync)
        self.connect('unmap',self.settle)
        self.connect('destroy',self.destroyed);self.sync()

    def settle(self,*_args):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.shown=self.target;self.frame_start=None;self.render()

    def destroyed(self,*_args):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.unsubscribe()

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
            self.duration=.24 if self.beats else (.78 if target else .62)
            if self.get_mapped() and self.get_settings().get_property('gtk-enable-animations'):
                if not self.tick:self.tick=self.add_tick_callback(self.animate)
            else:self.settle()
        self.get_accessible().set_description(self.flow.message);self.render()

    def animate(self,_widget,clock):
        now=clock.get_frame_time()/1e6
        if self.frame_start is None:self.frame_start=now
        t=min(1.,(now-self.frame_start)/self.duration)
        ease=t*t*t*(t*(t*6-15)+10) if self.beats else 1-(1-t)**3 if self.target else t*t*(3-2*t)
        self.shown=self.from_position+(self.target-self.from_position)*ease;self.render()
        if t>=1:self.tick=0;return False
        return True

    def render(self):
        frame=round(self.shown*(50 if self.beats else 100))
        if frame!=self.frame:
            self.frame=frame;self.indicator.set_from_pixbuf(switch_frame(frame) if self.beats else lamp_frame(frame))
