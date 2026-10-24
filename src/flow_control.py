"""A recessed incandescent EmberFlow switch shared by widget, room and settings."""
from gi.repository import Gtk
from functools import lru_cache
import math
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


@lru_cache(maxsize=201)
def lamp_frame(index):
    """Larger glass capsule; emission and colour follow filament temperature."""
    heat=max(0.,min(1.,index/200))
    light=(max(0.,heat-.2)/.8)**3.5
    emission=(max(0.,heat-.22)/.78)**.55
    def wire_color(value):
        stops=((0.,(93,35,18)),(.25,(117,24,7)),(.45,(187,53,9)),
               (.65,(248,126,24)),(.83,(255,190,87)),(1.,(255,229,168)))
        for (a,low),(b,high) in zip(stops,stops[1:]):
            if value<=b:
                t=max(0.,(value-a)/(b-a))
                return '#%02x%02x%02x'%tuple(round(x+(y-x)*t) for x,y in zip(low,high))
        return '#ffe5a8'
    # Cooler lead-in wires carry heat away from the ends. A continuous gradient
    # lets the centre become incandescent first without a travelling light effect.
    colors=[]
    for position in (0.,.15,.3,.5,.7,.85,1.):
        temperature=heat*(.88+.12*math.sin(math.pi*position)**.55)
        colors.append(f'<stop offset="{position}" stop-color="{wire_color(temperature)}"/>')
    pieces=['M11 12'];x=11.;y=12.
    for n in range(14):
        end=x+26/14;tip=12. if n==13 else 12+(-1 if n%2==0 else 1)*1.9
        pieces.append(f'C{x+.6:.3f} {y:.3f} {end-.6:.3f} {tip:.3f} {end:.3f} {tip:.3f}')
        x,y=end,tip
    coil=''.join(pieces)
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="48" height="24" viewBox="0 0 48 24">
      <defs>
        <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
          <stop stop-color="#10150f"/><stop offset=".5" stop-color="#25271b"/><stop offset="1" stop-color="#13180f"/>
        </linearGradient>
        <radialGradient id="warmth"><stop stop-color="#ff9d29" stop-opacity="{light*.38:.4f}"/>
          <stop offset=".5" stop-color="#ed8118" stop-opacity="{light*.17:.4f}"/>
          <stop offset="1" stop-color="#ce6110" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="wire">{''.join(colors)}</linearGradient>
        <linearGradient id="core"><stop stop-color="#ffecc7" stop-opacity="0"/>
          <stop offset=".5" stop-color="#fff0cf" stop-opacity="{light**2*.42:.4f}"/>
          <stop offset="1" stop-color="#ffecc7" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <rect x=".5" y="1" width="47" height="22" rx="11" fill="#0d120c"/>
      <path d="M3 18Q5 23 12 23H36Q43 23 45 18" fill="none" stroke="#e1d1a6" stroke-opacity=".15" stroke-width=".7"/>
      <rect x="2" y="2.5" width="44" height="19" rx="9.5" fill="url(#glass)" stroke="#79785b" stroke-opacity=".23" stroke-width=".7"/>
      <ellipse cx="24" cy="12" rx="21.5" ry="9" fill="url(#warmth)"/>
      <path d="M7 16L11 12M37 12L41 16" fill="none" stroke="#999071" stroke-opacity=".34" stroke-width=".7"/>
      <path d="{coil}" fill="none" stroke="#8b7e63" stroke-width=".85" stroke-opacity=".3"/>
      <path d="{coil}" fill="none" stroke="#f78b1a" stroke-width="6.4" stroke-opacity="{light*.07:.4f}"/>
      <path d="{coil}" fill="none" stroke="#ffa236" stroke-width="3.4" stroke-opacity="{light*.2:.4f}"/>
      <path d="{coil}" fill="none" stroke="url(#wire)" stroke-width="1.05" stroke-opacity="{emission:.4f}"/>
      <path d="{coil}" fill="none" stroke="url(#core)" stroke-width=".38"/>
      <path d="M7 6Q10 4.4 15 4.4H33" fill="none" stroke="#fff2cf" stroke-opacity=".14" stroke-width=".75" stroke-linecap="round"/>
      <path d="M8 7H14" fill="none" stroke="#fff2cf" stroke-opacity=".045" stroke-width="1.4" stroke-linecap="round"/>
      <path d="M5.5 17.3Q8 20 14 20H34Q40 20 42.5 17.3" fill="none" stroke="#f9b64b" stroke-opacity="{.025+light*.16:.4f}" stroke-width=".8"/>
    </svg>'''
    return pixbuf(svg,48,24)


class FlowControl(Gtk.ToggleButton):
    def __init__(self,flow,beats=False):
        super().__init__();self.flow=flow;self.syncing=False;self.beats=beats
        self.shown=self.target=float(flow.beat_sync if beats else flow.enabled);self.tick=0;self.frame_start=None;self.last_frame=None
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
        self.shown=self.target;self.frame_start=None;self.last_frame=None;self.render()

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
            self.from_position=self.shown;self.target=target;self.frame_start=None;self.last_frame=None
            if self.get_mapped() and self.get_settings().get_property('gtk-enable-animations'):
                if not self.tick:self.tick=self.add_tick_callback(self.animate)
            else:self.settle()
        self.get_accessible().set_description(self.flow.message);self.render()

    def animate(self,_widget,clock):
        now=clock.get_frame_time()/1e6
        if self.frame_start is None:self.frame_start=now
        if self.beats:
            t=min(1.,(now-self.frame_start)/.24);ease=t*t*t*(t*(t*6-15)+10)
            self.shown=self.from_position+(self.target-self.from_position)*ease;finished=t>=1
        else:
            # Bounded thermal approximation: conduction plus radiative loss.
            # Temperature survives a reversal; visible radiance is non-linear.
            elapsed=min(.05,max(0.,now-self.last_frame)) if self.last_frame is not None else 1/60
            steps=max(1,math.ceil(elapsed/.008));dt=elapsed/steps
            for _ in range(steps):
                loss=.32*self.shown+.68*self.shown**4
                self.shown+=dt*(3.2*(1-loss) if self.target else -2.8*loss)
                self.shown=max(0.,min(1.,self.shown))
            finished=(self.shown>=.998 if self.target else self.shown<=.22) or now-self.frame_start>=1.8
            if finished:self.shown=self.target
        self.last_frame=now;self.render()
        if finished:self.tick=0;return False
        return True

    def render(self):
        frame=round(self.shown*(50 if self.beats else 200))
        if frame!=self.frame:
            self.frame=frame;self.indicator.set_from_pixbuf(switch_frame(frame) if self.beats else lamp_frame(frame))
