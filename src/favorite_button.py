"""A small glass heart: finite frame-clock motion, no idle animation loop."""
from functools import lru_cache
import math
import threading
from gi.repository import Gtk,GLib
from hardware_controls import pixbuf
from source_picker import text

CSS=b'''
button.ember-heart, .ember-stage button.ember-heart {
  background: transparent; border: none; box-shadow: none; padding: 0;
  min-width: 0; min-height: 0; border-radius: 50%; outline-style: none;
}
button.ember-heart:focus { outline-width: 0; }
popover.favorite-note { background-color: #292d25; color: #ebdbb2;
  border: 1px solid rgba(250,189,47,.16); border-radius: 15px; }
.favorite-note label { font-size: 11px; color: #e3cf9f; }
.favorite-note button { background: transparent; color: #fabd2f; border: none; box-shadow: none; }
'''

_WARMING=set()
_WARM_LOCK=threading.Lock()


def warm_frames(size):
    with _WARM_LOCK:
        if size in _WARMING:return
        _WARMING.add(size)
    def prepare():
        for index in range(101):heart_frame(index,size)
    threading.Thread(target=prepare,daemon=True,name='ember-heart-frames').start()


@lru_cache(maxsize=384)
def heart_frame(index,size):
    t=index/100
    glow=t*t;scale=1+.055*math.sin(math.pi*t)
    heart='M24 32.5C21.5 30.5 14 25.2 14 20.1C14 14.2 21 12.8 24 18.1C27 12.8 34 14.2 34 20.1C34 25.2 26.5 30.5 24 32.5Z'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
    <defs><linearGradient id="rim" x2=".8" y2="1"><stop stop-color="#a69b7c"/><stop offset=".45" stop-color="#3d4437"/><stop offset="1" stop-color="#151d16"/></linearGradient>
    <radialGradient id="well" cx=".62" cy=".72"><stop stop-color="#363c2c"/><stop offset="1" stop-color="#171e18"/></radialGradient>
    <radialGradient id="glow"><stop stop-color="#ffb83f" stop-opacity="{glow*.28:.4f}"/><stop offset="1" stop-color="#e59c2b" stop-opacity="0"/></radialGradient>
    <linearGradient id="gold" x2=".35" y2="1"><stop stop-color="#ffe5a3"/><stop offset=".5" stop-color="#efbd60"/><stop offset="1" stop-color="#b4782d"/></linearGradient></defs>
    <circle cx="25" cy="26" r="20" fill="#101710" opacity=".4"/>
    <circle cx="23.7" cy="23.3" r="20.5" fill="url(#rim)"/>
    <circle cx="24" cy="24" r="18.9" fill="url(#well)" stroke="#151d15" stroke-width="1.2"/>
    <circle cx="24" cy="24" r="18" fill="url(#glow)"/>
    <circle cx="24" cy="24" r="{9+9*t:.3f}" fill="none" stroke="#f2c474" stroke-width=".7" stroke-opacity="{math.sin(math.pi*t)**2*.17:.4f}"/>
    <path d="M10 31A16 16 0 0 0 36 35" fill="none" stroke="#ddd0a0" stroke-opacity=".08"/>
    <g transform="translate(24 24) scale({scale:.5f}) translate(-24 -24)">
    <path d="{heart}" fill="#11190f" stroke="#10180f" stroke-width="3" transform="translate(0 1)"/>
    <path d="{heart}" fill="#373e30" stroke="#a59b7a" stroke-opacity=".62" stroke-width="1.1"/>
    <path d="{heart}" fill="url(#gold)" opacity="{t:.4f}"/>
    <path d="M17 19Q18.5 15.5 21 18" fill="none" stroke="#fff0bc" stroke-opacity="{.12+t*.42:.4f}" stroke-width="1" stroke-linecap="round"/>
    </g></svg>'''
    return pixbuf(svg,size,size)


class FavoriteButton(Gtk.Button):
    def __init__(self,favorites,size=38):
        super().__init__();self.favorites=favorites;self.size=size;self.identity=None
        self.shown=self.target=0.;self.tick=0;self.start=None;self.timeout=0;self.notice_key=None;self.notice_uri=None
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
        self.get_accessible().set_name(text('Remove from favourites','Удалить из избранного') if value else text('Save to favourites','Добавить в избранное'))
        message=self.favorites.messages.get(identity,'')
        self.get_accessible().set_description(message or text('Ember favourites and connected account','Избранное Ember и подключённого аккаунта'))
        if identity!=self.identity:
            self.identity=identity;self.target=value;self.settle()
            if self.note:self.note.popdown()
        elif value!=self.target:
            self.origin=self.shown;self.target=value;self.start=None
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
        if not self.note:
            self.note=Gtk.Popover.new(self);self.note.get_style_context().add_class('favorite-note')
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7);box.set_border_width(12);self.note.add(box)
            self.caption=Gtk.Label();self.caption.set_line_wrap(True);self.caption.set_max_width_chars(34);box.pack_start(self.caption,False,False,0)
            self.retry=Gtk.Button(label=text('Retry account sync','Повторить синхронизацию'))
            self.retry.connect('clicked',lambda _b:self.favorites.set(self.favorites.current(),True));box.pack_start(self.retry,False,False,0)
            box.show_all()
        self.caption.set_text(message)
        saved=self.favorites.items.get(item['uri'])
        self.retry.set_visible(bool(saved and saved.get('sync')!='synced' and item['uri'] not in self.favorites.pending and self.favorites.client(item['source'])))
        # Feedback never grabs keyboard focus or pauses playback.
        self.note.set_modal(False);self.note.popup()
        if self.timeout:GLib.source_remove(self.timeout)
        self.timeout=GLib.timeout_add(4500,self.hide_note)

    def hide_note(self):
        self.timeout=0
        if self.note:self.note.popdown()
        return False

    def animate(self,_widget,clock):
        now=clock.get_frame_time()/1e6
        if self.start is None:self.start=now
        t=min(1.,(now-self.start)/.82);ease=t*t*t*(t*(t*6-15)+10)
        self.shown=self.origin+(self.target-self.origin)*ease;self.render()
        if t>=1:self.tick=0;return False
        return True

    def render(self):
        key=(round(self.shown*100),self.size)
        if key!=self.frame:self.frame=key;self.image.set_from_pixbuf(heart_frame(*key))

    def settle(self,*_):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.shown=self.target;self.start=None;self.render()
        if self.timeout:GLib.source_remove(self.timeout);self.timeout=0
        self.hide_note()

    def destroyed(self,*_):
        self.settle()
        if self.timeout:GLib.source_remove(self.timeout);self.timeout=0
        self.unsubscribe()
        if self.note:self.note.destroy();self.note=None
