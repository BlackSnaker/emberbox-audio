"""A small glass heart: finite frame-clock motion, no idle animation loop."""
from functools import lru_cache
import math
import threading
from gi.repository import Gtk,GLib
from hardware_controls import pixbuf
from source_picker import text
from favorites import NAMES

FRAME_STEPS=200
CONFIRMATION_MS=1450
WARNING_MS=1900

CSS=b'''
button.ember-heart, .ember-stage button.ember-heart {
  background: transparent; border: none; box-shadow: none; padding: 0;
  min-width: 0; min-height: 0; border-radius: 50%; outline-style: none;
}
button.ember-heart:focus { outline-width: 0; }
button.ember-heart:disabled { opacity: 1; }
popover.favorite-note { background-image: linear-gradient(to bottom right,#34372c,#252c23);
  background-color: #292e25; color: #ebdbb2; padding: 0;
  border: 1px solid rgba(237,202,126,.15); border-radius: 15px;
  box-shadow: inset 0 1px rgba(255,241,199,.06), inset 0 -1px rgba(0,0,0,.18); }
.favorite-note label.favorite-confirmation { font-size: 11px; font-weight: bold; color: #f3dfad; }
.favorite-note label.favorite-detail { font-size: 9px; color: #aaa58a; }
.favorite-note button { background: transparent; color: #e8bc62; border: none; box-shadow: none;
  font-size: 10px; padding: 2px 0; min-height: 0; min-width: 0; }
'''

_WARMING=set()
_WARM_LOCK=threading.Lock()


def warm_frames(size):
    with _WARM_LOCK:
        if size in _WARMING:return
        _WARMING.add(size)
    def prepare():
        for index in range(FRAME_STEPS+1):heart_frame(index,size)
    threading.Thread(target=prepare,daemon=True,name='ember-heart-frames').start()


def heat_step(heat,velocity,target,seconds):
    """Continuous temperature and velocity, including a reversed switch."""
    rate=6.6 if target else 5.6
    offset=heat-target;momentum=velocity+rate*offset;decay=math.exp(-rate*seconds)
    value=target+(offset+momentum*seconds)*decay
    velocity=(velocity-rate*momentum*seconds)*decay
    return max(0.,min(1.,value)),velocity


def filament_color(heat):
    stops=((0.,(76,37,25)),(.24,(113,35,15)),(.43,(177,58,17)),
           (.65,(237,119,28)),(.84,(255,185,77)),(1.,(255,226,163)))
    for (a,low),(b,high) in zip(stops,stops[1:]):
        if heat<=b:
            t=max(0.,(heat-a)/(b-a))
            return '#%02x%02x%02x'%tuple(round(x+(y-x)*t) for x,y in zip(low,high))
    return '#ffe2a3'


@lru_cache(maxsize=896)
def heart_frame(index,size):
    heat=index/FRAME_STEPS
    glow=(max(0.,heat-.12)/.88)**2.2
    emission=(max(0.,heat-.12)/.88)**.7
    heart='M24 32.5C21.5 30.5 14 25.2 14 20.1C14 14.2 21 12.8 24 18.1C27 12.8 34 14.2 34 20.1C34 25.2 26.5 30.5 24 32.5Z'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
    <defs><linearGradient id="rim" x2=".8" y2="1"><stop stop-color="#a69b7c"/><stop offset=".45" stop-color="#3d4437"/><stop offset="1" stop-color="#151d16"/></linearGradient>
    <radialGradient id="well" cx=".62" cy=".72"><stop stop-color="#363c2c"/><stop offset="1" stop-color="#171e18"/></radialGradient>
    <radialGradient id="glow"><stop stop-color="#ffae34" stop-opacity="{glow*.38:.4f}"/><stop offset=".6" stop-color="#ec8b22" stop-opacity="{glow*.12:.4f}"/><stop offset="1" stop-color="#e59c2b" stop-opacity="0"/></radialGradient>
    <linearGradient id="wire" x2=".25" y2="1"><stop stop-color="{filament_color(heat*.9)}"/><stop offset=".5" stop-color="{filament_color(heat)}"/><stop offset="1" stop-color="{filament_color(heat*.85)}"/></linearGradient>
    <radialGradient id="heart-light"><stop stop-color="{filament_color(heat)}" stop-opacity="{glow*.46:.4f}"/><stop offset="1" stop-color="#cc6a1b" stop-opacity="{glow*.18:.4f}"/></radialGradient></defs>
    <circle cx="25" cy="26" r="20" fill="#101710" opacity=".4"/>
    <circle cx="23.7" cy="23.3" r="20.5" fill="url(#rim)"/>
    <circle cx="24" cy="24" r="18.9" fill="url(#well)" stroke="#151d15" stroke-width="1.2"/>
    <circle cx="24" cy="24" r="18" fill="url(#glow)"/>
    <path d="M10 34A17 17 0 0 0 38 31" fill="none" stroke="#f3b85f" stroke-opacity="{glow*.18:.4f}" stroke-width=".8"/>
    <path d="M10 31A16 16 0 0 0 36 35" fill="none" stroke="#ddd0a0" stroke-opacity=".08"/>
    <path d="{heart}" fill="#11190f" stroke="#10180f" stroke-width="3" transform="translate(0 1)"/>
    <path d="{heart}" fill="#242c21" stroke="#96896a" stroke-opacity=".4" stroke-width="1"/>
    <path d="{heart}" fill="url(#heart-light)"/>
    <path d="{heart}" fill="none" stroke="#f08a20" stroke-width="6" stroke-opacity="{glow*.06:.4f}"/>
    <path d="{heart}" fill="none" stroke="#ffab38" stroke-width="3.2" stroke-opacity="{glow*.2:.4f}"/>
    <path d="{heart}" fill="none" stroke="url(#wire)" stroke-width="1.25" stroke-opacity="{emission:.4f}"/>
    <path d="{heart}" fill="none" stroke="#fff0ce" stroke-width=".4" stroke-opacity="{glow*glow*.6:.4f}"/>
    <path d="M17 19Q18.5 15.5 21 18" fill="none" stroke="#fff0bc" stroke-opacity="{.1+glow*.28:.4f}" stroke-width=".8" stroke-linecap="round"/>
    <path d="M10 12Q14 8 21 7" fill="none" stroke="#fff3d0" stroke-opacity=".1" stroke-width=".7" stroke-linecap="round"/>
    </svg>'''
    return pixbuf(svg,size,size)


class FavoriteButton(Gtk.Button):
    def __init__(self,favorites,size=38):
        super().__init__();self.favorites=favorites;self.size=size;self.identity=None
        self.shown=self.target=self.velocity=0.;self.tick=0;self.start=self.last_frame=None;self.timeout=0;self.notice_key=None;self.notice_uri=None
        self.note_tick=0;self.note_start=None;self.note_phase='';self.note_origin=0.
        self.get_style_context().add_class('ember-heart');self.set_has_tooltip(False)
        self.image=Gtk.Image();self.add(self.image);self.frame=None;self.note=None
        warm_frames(size)
        self.connect('clicked',self.on_clicked)
        self.connect('unmap',self.settle);self.connect('destroy',self.destroyed)
        self.unsubscribe=favorites.subscribe(self.sync);self.sync()

    def set_size(self,size):
        if size!=self.size:self.size=size;self.frame=None;warm_frames(size);self.render()

    def sync(self):
        item=self.favorites.current();identity=item and item['uri'];value=float(self.favorites.saved(item))
        self.set_sensitive(bool(item) and identity not in self.favorites.pending)
        self.image.set_opacity(1 if item else .4)
        self.get_accessible().set_name(text('Remove from favourites','Удалить из избранного') if value else text('Save to favourites','Добавить в избранное'))
        message=self.favorites.messages.get(identity,'')
        self.get_accessible().set_description(message or text('Ember favourites and connected account','Избранное Ember и подключённого аккаунта'))
        if identity!=self.identity:
            self.identity=identity;self.target=value;self.settle()
            if self.note:self.note.popdown()
        elif value!=self.target:
            self.target=value;self.start=self.last_frame=None
            if self.get_mapped() and self.get_settings().get_property('gtk-enable-animations'):
                if not self.tick:self.tick=self.add_tick_callback(self.animate)
            else:self.settle()
        if identity and identity==self.notice_uri and message and message!=self.notice_key:
            self.notice_key=message;self.feedback(message,item)
        self.render()

    def on_clicked(self,_button):
        item=self.favorites.current()
        if item:
            self.notice_uri=item['uri'];self.notice_key=None;self.favorites.toggle(item)

    def feedback(self,message,item):
        if not self.get_mapped():return
        event=self.favorites.feedback.get(item['uri'],{})
        phase=event.get('phase');saved=event.get('saved',self.favorites.saved(item))
        if phase=='saving':return
        if not self.note:
            self.note=Gtk.Popover.new(self);self.note.get_style_context().add_class('favorite-note')
            appearance=getattr(self.get_toplevel(),'ember_appearance',None)
            if appearance:appearance.decorate_popup(self.note)
            self.note.set_position(Gtk.PositionType.TOP);self.note.set_modal(False)
            if hasattr(self.note,'set_transitions_enabled'):self.note.set_transitions_enabled(False)
            box=Gtk.Box(spacing=9);box.set_border_width(10);self.note.add(box)
            light=Gtk.Image.new_from_pixbuf(heart_frame(FRAME_STEPS,22));light.set_valign(Gtk.Align.CENTER)
            box.pack_start(light,False,False,0)
            names=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3);box.pack_start(names,True,True,0)
            self.caption=Gtk.Label();self.caption.set_xalign(0);self.caption.get_style_context().add_class('favorite-confirmation')
            names.pack_start(self.caption,False,False,0)
            self.detail=Gtk.Label();self.detail.set_xalign(0);self.detail.get_style_context().add_class('favorite-detail')
            self.detail.set_line_wrap(True);self.detail.set_max_width_chars(32);names.pack_start(self.detail,False,False,0)
            self.retry=Gtk.Button(label=text('Retry','Повторить'))
            self.retry.get_accessible().set_name(text('Retry account sync','Повторить синхронизацию аккаунта'))
            self.retry.set_halign(Gtk.Align.START)
            self.retry.connect('clicked',lambda _b:self.favorites.retry(self.retry_item));names.pack_start(self.retry,False,False,0)
            box.show_all()
        warning=phase in ('error','unconfirmed')
        self.caption.set_text(text('Could not save','Не удалось сохранить') if phase=='error' else
                              text('In your favourites','В избранном') if saved else text('Removed','Удалено'))
        detail=('Ember + '+NAMES[item['source']] if phase=='synced' else
                text('Ember · syncing','Ember · синхронизация') if phase=='local' else
                text('Ember · will sync automatically','Ember · отправлю автоматически') if phase=='unconfirmed' else
                text('Please try again','Попробуй ещё раз') if phase=='error' else 'Ember')
        self.detail.set_text(detail);self.note.get_accessible().set_name(message)
        self.retry_item=dict(item)
        stored=self.favorites.operations.get(item['uri'])
        self.retry.set_visible(bool(stored and warning and item['uri'] not in self.favorites.pending and self.favorites.client(item['source'])))
        # Feedback never grabs keyboard focus or pauses playback.
        if not self.note.get_visible() or warning:
            if self.timeout:GLib.source_remove(self.timeout)
            if not self.note.get_visible():self.note.set_opacity(0.)
            self.note.popup();self.fade_note('in')
            duration=WARNING_MS if warning else CONFIRMATION_MS
            self.timeout=GLib.timeout_add(duration-200,self.expire_note)
        # Local-save and account-result updates share one short display period.

    def fade_note(self,phase):
        self.note_phase=phase;self.note_start=None;self.note_origin=self.note.get_opacity()
        if not self.get_settings().get_property('gtk-enable-animations'):
            self.note.set_opacity(1.)
            if phase=='out':self.hide_note()
            return
        if not self.note_tick:self.note_tick=self.note.add_tick_callback(self.animate_note)

    def expire_note(self):
        self.timeout=0
        if self.note:self.fade_note('out')
        return False

    def animate_note(self,_widget,clock):
        if not self.get_settings().get_property('gtk-enable-animations'):
            self.note_tick=0;self.note.set_opacity(1.)
            if self.note_phase=='out':self.note.popdown()
            return False
        now=clock.get_frame_time()/1e6
        if self.note_start is None:self.note_start=now
        t=min(1.,(now-self.note_start)/(.16 if self.note_phase=='in' else .2));ease=t*t*(3-2*t)
        target=1. if self.note_phase=='in' else 0.
        self.note.set_opacity(self.note_origin+(target-self.note_origin)*ease)
        if t>=1:
            self.note_tick=0
            if self.note_phase=='out':self.note.popdown();self.note.set_opacity(1.)
            return False
        return True

    def hide_note(self):
        if self.timeout:GLib.source_remove(self.timeout);self.timeout=0
        if self.note:
            if self.note_tick:self.note.remove_tick_callback(self.note_tick);self.note_tick=0
            self.note.popdown();self.note.set_opacity(1.)
        return False

    def animate(self,_widget,clock):
        if not self.get_settings().get_property('gtk-enable-animations'):
            self.tick=0;self.shown=self.target;self.velocity=0.;self.render();return False
        now=clock.get_frame_time()/1e6
        if self.start is None:self.start=now
        dt=min(.08,max(0.,now-self.last_frame)) if self.last_frame is not None else 0.
        self.last_frame=now
        self.shown,self.velocity=heat_step(self.shown,self.velocity,self.target,dt);self.render()
        if (abs(self.shown-self.target)<.001 and abs(self.velocity)<.006) or now-self.start>=1.8:
            self.shown=self.target;self.velocity=0.;self.render();self.tick=0;return False
        return True

    def render(self):
        key=(round(self.shown*FRAME_STEPS),self.size)
        if key!=self.frame:self.frame=key;self.image.set_from_pixbuf(heart_frame(*key))

    def settle(self,*_):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.shown=self.target;self.velocity=0.;self.start=self.last_frame=None;self.render()
        self.hide_note()

    def destroyed(self,*_):
        self.settle()
        if self.timeout:GLib.source_remove(self.timeout);self.timeout=0
        self.unsubscribe()
        if self.note:self.note.destroy();self.note=None
