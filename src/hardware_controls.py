"""Grunesphism: smooth metal, warm ticks and soft, restrained relief.

Vector sprites keep the physical controls antialiased at both widget sizes.
"""

import math
from functools import lru_cache

from gi.repository import Atk, Gdk, GdkPixbuf, Gtk


def pixbuf(svg, width, height):
    loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
    loader.set_size(width, height)
    loader.write(svg.encode())
    loader.close()
    return loader.get_pixbuf()


@lru_cache(maxsize=512)
def knob_frame(index, compact, large=False):
    value = index / 200
    angle = math.radians(135 + 270 * value)
    ticks = []
    for n in range(19):
        a = math.radians(135 + n * 15)
        color = '#d79921' if n / 18 <= value else '#686254'
        ticks.append(f'<path d="M{32 + math.cos(a)*26:.2f} {29 + math.sin(a)*26:.2f}L{32 + math.cos(a)*28:.2f} {29 + math.sin(a)*28:.2f}" stroke="{color}" stroke-width="1" stroke-linecap="round"/>')
    ridges = []
    for n in range(48):
        a = n * math.tau / 48
        ridges.append(f'<path d="M{32 + math.cos(a)*20:.2f} {29 + math.sin(a)*20:.2f}L{32 + math.cos(a)*22:.2f} {29 + math.sin(a)*22:.2f}" stroke="#e0dcc7" stroke-opacity=".15" stroke-width=".7"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="68" viewBox="0 0 64 68">
      <defs>
        <linearGradient id="bevel" x1="0" y1="0" x2=".8" y2="1">
          <stop stop-color="#bcbba6"/><stop offset=".28" stop-color="#747b6a"/>
          <stop offset=".72" stop-color="#3e463b"/><stop offset="1" stop-color="#1b211b"/>
        </linearGradient>
        <radialGradient id="face" cx=".32" cy=".22" r=".85">
          <stop stop-color="#707764"/><stop offset=".52" stop-color="#454d3f"/>
          <stop offset="1" stop-color="#292f27"/>
        </radialGradient>
      </defs>
      {''.join(ticks)}
      <circle cx="33" cy="32" r="23" fill="#121510" opacity=".22"/>
      <circle cx="32" cy="29" r="23" fill="#161b16"/>
      <circle cx="32" cy="29" r="21.8" fill="url(#bevel)" stroke="#a49e85" stroke-opacity=".4" stroke-width=".6"/>
      {''.join(ridges)}
      <circle cx="32" cy="29" r="18.4" fill="url(#face)" stroke="#20271e" stroke-width=".8"/>
      <circle cx="32" cy="29" r="17.3" fill="none" stroke="#d4d0b9" stroke-opacity=".06" stroke-width=".7"/>
      <circle cx="32" cy="29" r="15.2" fill="none" stroke="#d4d0b9" stroke-opacity=".025" stroke-width=".5"/>
      <path d="M{32+math.cos(angle)*11:.2f} {29+math.sin(angle)*11:.2f}L{32+math.cos(angle)*17:.2f} {29+math.sin(angle)*17:.2f}"
        stroke="#11180f" stroke-width="3.4" stroke-linecap="round"/>
      <path d="M{32+math.cos(angle)*11:.2f} {29+math.sin(angle)*11:.2f}L{32+math.cos(angle)*17:.2f} {29+math.sin(angle)*17:.2f}"
        stroke="#f5bd51" stroke-width="1.8" stroke-linecap="round"/>
      <text x="32" y="64" text-anchor="middle" font-family="monospace" font-size="10" fill="#bdae93">{round(value*100)}%</text>
    </svg>'''
    return pixbuf(svg, 88 if large else 38 if compact else 48,
                  94 if large else 42 if compact else 52)


@lru_cache(maxsize=256)
def switch_frame(index, compact):
    position = index / 100
    tip = 18 + position * 24
    muted = position > .5
    light = '#{:02x}{:02x}{:02x}'.format(*(round(on+(off-on)*position)
                                        for on,off in zip((215,153,33),(102,93,69))))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="40" height="64" viewBox="0 0 40 64">
      <defs>
        <radialGradient id="washer" cx=".3" cy=".18" r=".9">
          <stop stop-color="#eee7d2"/><stop offset=".3" stop-color="#bdc1af"/>
          <stop offset=".62" stop-color="#697a6b"/><stop offset=".85" stop-color="#3d4b3e"/>
          <stop offset="1" stop-color="#b2b59f"/>
        </radialGradient>
        <linearGradient id="steel" gradientUnits="userSpaceOnUse" x1="15.7" x2="24.3">
          <stop stop-color="#5e695f"/><stop offset=".28" stop-color="#f4eddb"/>
          <stop offset=".46" stop-color="#c7ccbc"/><stop offset=".8" stop-color="#7d8b7b"/>
          <stop offset="1" stop-color="#323b31"/>
        </linearGradient>
      </defs>
      <circle cx="20" cy="6" r="2.2" fill="{light}"/>
      <circle cx="21" cy="33" r="13.8" fill="#141812" opacity=".28"/>
      <circle cx="20" cy="30" r="13" fill="url(#washer)" stroke="#252b22" stroke-width="1"/>
      <circle cx="20" cy="30" r="11.7" fill="none" stroke="#e7e3ce" stroke-opacity=".20" stroke-width=".65"/>
      <path d="M10.2 25.5a10.8 10.8 0 0 1 12-5.8" fill="none" stroke="#fff4da" stroke-opacity=".25" stroke-width=".7" stroke-linecap="round"/>
      <ellipse cx="20" cy="30" rx="7" ry="8.3" fill="#171e16" stroke="#5c6656" stroke-width="1"/>
      <path d="M20 30L20 {tip:.2f}" stroke="#11180e" stroke-width="8" stroke-linecap="round"/>
      <path d="M20 30L20 {tip:.2f}" stroke="url(#steel)" stroke-width="6.4" stroke-linecap="round"/>
      <rect x="15.7" y="{tip-4.7:.2f}" width="8.6" height="9.4" rx="4.3" fill="url(#steel)" stroke="#c2c4b1" stroke-opacity=".22" stroke-width=".5"/>
      <path d="M17.8 {tip-2.3:.2f}v4.6" stroke="#f6efda" stroke-opacity=".45" stroke-width=".6"/>
      <text x="20" y="60" text-anchor="middle" font-family="monospace" font-size="9" fill="{'#928374' if muted else '#bdae93'}">{'OFF' if muted else 'ON'}</text>
    </svg>'''
    return pixbuf(svg, 30 if compact else 36, 48 if compact else 58)


class VolumeKnob(Gtk.EventBox):
    def __init__(self, changed, *, large=False):
        super().__init__()
        self.changed = changed
        self.set_visible_window(False)
        self.set_can_focus(True)
        self.image = Gtk.Image()
        self.add(self.image)
        self.set_valign(Gtk.Align.CENTER)
        self.value = self.shown = 1.0
        self.muted = self.compact = False
        self.large = large
        self.drag = None
        self.tick = 0
        self.last_frame = None
        self.frame = None
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.SCROLL_MASK |
                        Gdk.EventMask.SMOOTH_SCROLL_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.connect('button-press-event', self._press)
        self.connect('button-release-event', self._release)
        self.connect('motion-notify-event', self._motion)
        self.connect('scroll-event', self._scroll)
        self.connect('key-press-event', self._key)
        self.get_accessible().set_role(Atk.Role.DIAL)
        self.get_accessible().set_name('Громкость')
        self._render()

    def set_compact(self, compact):
        self.compact = compact
        self.frame = None
        self._render()

    def set_state(self, value, muted, available):
        self.value, self.muted = value, muted
        self.set_sensitive(available)
        self.image.set_opacity(.4 if not available else .72 if muted else 1.0)
        suffix = ' · звук выключен тумблером' if muted else ''
        self.get_accessible().set_description(f'{round(value*100)} процентов{suffix}')
        if abs(self.shown - value) > .001 and not self.tick:
            self.last_frame = None
            self.tick = self.add_tick_callback(self._animate)

    def _render(self):
        index = round(max(0,min(1,self.shown))*200)
        key = (index,self.compact,self.large)
        if key != self.frame:
            self.image.set_from_pixbuf(knob_frame(*key));self.frame = key

    def _animate(self, _widget, clock):
        now = clock.get_frame_time()
        elapsed = min(.05,(now-self.last_frame)/1_000_000) if self.last_frame else 1/60
        self.last_frame = now
        self.shown += (self.value-self.shown)*(1-math.exp(-elapsed/.045))
        if abs(self.shown-self.value)<.001:
            self.shown=self.value;self._render();self.tick=0;return False
        self._render();return True

    def _change(self, value):
        self.changed(max(0,min(1,value)))

    def _press(self, _widget, event):
        if event.button != 1:return False
        self.grab_focus();self.drag=(event.x_root,event.y_root,self.value)
        self.grab_add();return True

    def _release(self, _widget, event):
        if event.button != 1 or self.drag is None:return False
        self.drag=None;self.grab_remove();return True

    def _motion(self, _widget, event):
        if self.drag is None:return False
        x,y,value=self.drag
        fine=.25 if event.state & Gdk.ModifierType.SHIFT_MASK else 1
        self._change(value+((y-event.y_root)/160+(event.x_root-x)/240)*fine)
        return True

    def _scroll(self, _widget, event):
        step=.005 if event.state & Gdk.ModifierType.SHIFT_MASK else .02
        if event.direction==Gdk.ScrollDirection.SMOOTH:
            success,_dx,dy=event.get_scroll_deltas()
            if success:self._change(self.value-dy*step)
        else:
            self._change(self.value+step*(1 if event.direction in (Gdk.ScrollDirection.UP,Gdk.ScrollDirection.RIGHT) else -1))
        return True

    def _key(self, _widget, event):
        name=Gdk.keyval_name(event.keyval)
        steps={'Up':.02,'Right':.02,'Down':-.02,'Left':-.02,'Page_Up':.1,'Page_Down':-.1}
        if name in steps:self._change(self.value+steps[name]);return True
        if name in ('Home','End'):self._change(0 if name=='Home' else 1);return True
        return False


class MuteToggle(Gtk.Button):
    def __init__(self, changed):
        super().__init__()
        self.get_style_context().add_class('hardware-toggle')
        self.image = Gtk.Image();self.add(self.image)
        self.set_valign(Gtk.Align.CENTER)
        self.compact=False;self.position=self.target=0.0;self.tick=0;self.last_frame=None
        self.start_position=0.0;self.elapsed=0.0
        self.connect('clicked',lambda _button:changed())
        self.get_accessible().set_name('Звук Spotify')
        self.get_accessible().set_role(Atk.Role.TOGGLE_BUTTON)
        self._render()

    def set_compact(self,compact):
        self.compact=compact;self._render()

    def set_state(self,_volume,muted,available):
        self.set_sensitive(available)
        self.image.set_opacity(1 if available else .4)
        target=1.0 if muted else 0.0
        if target != self.target:
            self.target=target;self.start_position=self.position;self.elapsed=0.0
        self.get_accessible().set_description('Включить звук Spotify' if muted else 'Полностью отключить звук Spotify')
        self.get_accessible().notify_state_change(Atk.StateType.CHECKED,not muted)
        if abs(self.position-self.target)>.001 and not self.tick:
            self.last_frame=None;self.tick=self.add_tick_callback(self._animate)

    def _render(self):
        self.image.set_from_pixbuf(switch_frame(round(self.position*100),self.compact))

    def _animate(self,_widget,clock):
        now=clock.get_frame_time()
        elapsed=min(.05,(now-self.last_frame)/1_000_000) if self.last_frame else 1/60
        self.last_frame=now
        self.elapsed += elapsed
        progress=min(1.0,self.elapsed/.25)
        eased=progress**3*(progress*(progress*6-15)+10)
        self.position=self.start_position+(self.target-self.start_position)*eased
        if progress>=1:
            self.position=self.target;self._render();self.tick=0;return False
        self._render();return True
