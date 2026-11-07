"""Small cached hardware sprites. Motion runs only while a control settles."""
import math
from functools import lru_cache
from gi.repository import GObject,Gdk
from hardware_controls import VolumeKnob,MuteToggle,pixbuf
from source_picker import text


@lru_cache(maxsize=201)
def time_dial(index):
    value=index/200;angle=math.radians(135+270*value);ticks=[];ridges=[]
    for n in range(29):
        a=math.radians(135+270*n/28);inner=34 if n%4==0 else 36
        ticks.append(f'<path d="M{44+inner*math.cos(a):.2f} {42+inner*math.sin(a):.2f}L{44+39*math.cos(a):.2f} {42+39*math.sin(a):.2f}" stroke="{"#e7bb66" if n/28<=value else "#686c61"}" stroke-width="{1.2 if n%4==0 else .7}"/>')
    for n in range(64):
        a=math.tau*n/64
        ridges.append(f'<path d="M{44+29*math.cos(a):.2f} {42+29*math.sin(a):.2f}L{44+32*math.cos(a):.2f} {42+32*math.sin(a):.2f}" stroke="#c6c8b9" stroke-opacity=".27" stroke-width=".8"/>')
    return pixbuf(f'''<svg xmlns="http://www.w3.org/2000/svg" width="88" height="88" viewBox="0 0 88 88">
      <defs><linearGradient id="metal" x2=".8" y2="1"><stop stop-color="#b0b3a6"/><stop offset=".2" stop-color="#686f63"/><stop offset=".55" stop-color="#303b34"/><stop offset="1" stop-color="#111b17"/></linearGradient>
      <radialGradient id="face" cx=".3" cy=".18" r=".9"><stop stop-color="#626c5b"/><stop offset=".65" stop-color="#343f34"/><stop offset="1" stop-color="#1a241e"/></radialGradient></defs>
      <circle cx="45" cy="45" r="33" fill="#050907" opacity=".6"/>
      <circle cx="44" cy="42" r="33.5" fill="#0b100e" stroke="#c7b58d" stroke-opacity=".1"/>
      {''.join(ticks)}<circle cx="44" cy="42" r="31.8" fill="url(#metal)"/>{''.join(ridges)}
      <circle cx="44" cy="42" r="27.7" fill="url(#face)" stroke="#131e17" stroke-width="1.3"/>
      <circle cx="44" cy="42" r="26.6" fill="none" stroke="#d5d5bc" stroke-opacity=".12" stroke-width=".6"/>
      <circle cx="44" cy="42" r="23.8" fill="none" stroke="#d5d5bc" stroke-opacity=".035" stroke-width=".6"/>
      <path d="M{44+16*math.cos(angle):.2f} {42+16*math.sin(angle):.2f}L{44+24*math.cos(angle):.2f} {42+24*math.sin(angle):.2f}" stroke="#111810" stroke-width="4.5" stroke-linecap="round"/>
      <path d="M{44+16*math.cos(angle):.2f} {42+16*math.sin(angle):.2f}L{44+24*math.cos(angle):.2f} {42+24*math.sin(angle):.2f}" stroke="#edc379" stroke-width="2.2" stroke-linecap="round"/>
    </svg>''',88,88)


class TimeDial(VolumeKnob):
    def __init__(self,changed):
        super().__init__(changed,large=True)
        self.ember_key_handler=self._key
        self.get_accessible().set_name(text('Overlap duration','Длительность смешивания'))
        self.connect('unmap',self.settle);self.connect('destroy',self.settle)

    def _render(self):
        index=round(max(0,min(1,self.shown))*200)
        if self.frame!=index:self.image.set_from_pixbuf(time_dial(index));self.frame=index

    def set_seconds(self,seconds,available):
        self.set_state((seconds-1)/29,False,available)
        self.get_accessible().set_description(text(f'{seconds:g} seconds. Drag, scroll or use arrow keys.',
            f'{seconds:g} секунды. Перетаскивание, колесо или клавиши со стрелками.'))

    def _key(self,_widget,event):
        name=Gdk.keyval_name(event.keyval)
        steps={'Up':.5/29,'Right':.5/29,'Down':-.5/29,'Left':-.5/29,'Page_Up':2/29,'Page_Down':-2/29}
        if name in steps:self._change(self.value+steps[name]);return True
        return super()._key(_widget,event)

    def _scroll(self,_widget,event):
        if event.direction==Gdk.ScrollDirection.SMOOTH:
            ok,_dx,dy=event.get_scroll_deltas()
            if not ok or abs(dy)<.01:return True
            sign=-1 if dy>0 else 1
        else:sign=1 if event.direction in (Gdk.ScrollDirection.UP,Gdk.ScrollDirection.RIGHT) else -1
        self._change(self.value+sign*.5/29);return True

    def settle(self,*_):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.shown=self.value;self._render()


class CutDial(TimeDial):
    def __init__(self,changed,name):
        super().__init__(lambda v:changed(round(-12+12*v)))
        self.get_accessible().set_name(name)
        self.small=False

    def set_db(self,db,available):
        self.set_state((db+12)/12,False,available)
        self.get_accessible().set_description(text(f'{db:g} dB. Cuts only; applies during the transition.',
            f'{db:g} дБ. Ослабление только во время перехода.'))

    def _render(self):
        index=round(max(0,min(1,self.shown))*200);small=getattr(self,'small',False)
        key=index,small
        if self.frame!=key:
            pixels=time_dial(index)
            if small:
                from gi.repository import GdkPixbuf
                pixels=pixels.scale_simple(54,54,GdkPixbuf.InterpType.BILINEAR)
            self.image.set_from_pixbuf(pixels);self.frame=key

    def _key(self,_widget,event):
        name=Gdk.keyval_name(event.keyval)
        steps={'Up':1/12,'Right':1/12,'Down':-1/12,'Left':-1/12,'Page_Up':3/12,'Page_Down':-3/12}
        if name in steps:self._change(self.value+steps[name]);return True
        return VolumeKnob._key(self,_widget,event)

    def _scroll(self,_widget,event):
        if event.direction==Gdk.ScrollDirection.SMOOTH:
            ok,_dx,dy=event.get_scroll_deltas()
            if not ok or abs(dy)<.01:return True
            sign=-1 if dy>0 else 1
        else:sign=1 if event.direction in (Gdk.ScrollDirection.UP,Gdk.ScrollDirection.RIGHT) else -1
        self._change(self.value+sign/12);return True


class BeatSwitch(MuteToggle):
    __gsignals__={'toggled':(GObject.SignalFlags.RUN_LAST,None,())}
    def __init__(self):
        self.active=True
        super().__init__(lambda:self.set_active(not self.active))
        self.get_accessible().set_name(text('Beat alignment','Совмещение битов'))
        self.set_has_tooltip(False)
        self.connect('unmap',self.settle);self.connect('destroy',self.settle)

    def get_active(self):return self.active

    def set_active(self,active):
        previous=self.active;self.active=bool(active)
        self.set_state(1,not self.active,self.get_sensitive())
        self.get_accessible().set_description(text('Align confident beats when the engine supports it',
            'Совмещать уверенно распознанные биты, когда движок это поддерживает'))
        if previous!=self.active:self.emit('toggled')

    def settle(self,*_):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.position=self.target;self._render()


@lru_cache(maxsize=1)
def screw():
    return pixbuf('''<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14">
      <defs><linearGradient id="s" x2=".8" y2="1"><stop stop-color="#77796c"/><stop offset="1" stop-color="#20271f"/></linearGradient></defs>
      <circle cx="7" cy="7.5" r="5" fill="#0b100d"/><circle cx="7" cy="7" r="4.3" fill="url(#s)" stroke="#b9b599" stroke-opacity=".12"/>
      <path d="M4.5 8.5L9.5 5.5" stroke="#101710" stroke-width="1.3" stroke-linecap="round"/>
      <path d="M4.5 9L9.5 6" stroke="#aeaf95" stroke-opacity=".25" stroke-width=".5"/>
    </svg>''',14,14)
