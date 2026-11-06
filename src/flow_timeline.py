"""Two draggable gain-envelope clips. No invented PCM waveform or recorder."""
from html import escape
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,Atk
from hardware_controls import pixbuf
from source_picker import text
from flow_youtube import curve


def overlap(initial,delta,lane):
    return round(max(1.,min(8.,initial+(delta if lane==0 else -delta))),1)


class TimelineImage(Gtk.Image):
    def do_get_preferred_width(self):return 0,0
    def do_get_preferred_width_for_height(self,_height):return 0,0


class FlowTimeline(Gtk.EventBox):
    def __init__(self,changed):
        super().__init__();self.changed=changed;self.set_visible_window(False);self.set_can_focus(True)
        self.image=TimelineImage();self.add(self.image);self.image.set_hexpand(True)
        self.seconds=self.shown=8.;self.morph_tick=0;self.morph_start=None;self.anchor=0.;self.mode='auto';self.shape='shared';self.names=['A','B']
        self.drag=None;self.selected=1;self.tick=0;self.pending=None;self.width=800;self.height=178;self.dense=False
        self.set_size_request(0,self.height);self.get_style_context().add_class('flow-timeline')
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK|Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.KEY_PRESS_MASK)
        self.connect('button-press-event',self.press);self.connect('button-release-event',self.release)
        self.connect('motion-notify-event',self.motion);self.connect('key-press-event',self.key)
        self.connect('size-allocate',self.allocated);self.connect('unmap',self.cancel);self.connect('destroy',self.cancel)
        self.get_accessible().set_role(Atk.Role.SLIDER)
        self.get_accessible().set_name(text('Transition timeline: drag either track','Лента перехода: перетащи любую дорожку'))
        self.render()

    def allocated(self,_widget,allocation):
        width=max(200,allocation.width)
        if width!=self.width:self.width=width;self.render()

    def set_dense(self,dense):
        if self.dense==dense:return
        self.dense=dense;self.height=140 if dense else 178;self.set_size_request(0,self.height);self.render()

    def set_plan(self,value,names=None):
        if self.drag:return
        if names is None and (self.seconds,self.mode,self.shape)==(value['seconds'],value['mode'],value['shape']):return
        self.seconds=value['seconds'];self.mode=value['mode'];self.shape=value['shape']
        if abs(self.seconds-self.shown)>.01 and self.get_mapped() and self.get_settings().get_property('gtk-enable-animations'):
            self.morph_from=self.shown;self.morph_start=None
            if not self.morph_tick:self.morph_tick=self.add_tick_callback(self.morph)
        else:self.settle_morph()
        if names is not None:self.names=list(names);self.anchor=0
        self.render()

    def positions(self):
        scale=(self.width-40)/40;end=20+self.anchor
        start=end-(0 if self.mode=='cut' else self.shown)
        return scale,end,start

    def render(self):
        w,h=self.width,self.height;scale,end,start=self.positions();x=lambda seconds:20+seconds*scale
        top=30;row=(h-48)/2;clip_height=row-8;pieces=[]
        color=['#b7c8a1','#f4bc61'];overlap_start=x(start);overlap_end=x(end)
        pieces.append(f'<rect x="{overlap_start:.2f}" y="22" width="{max(0,overlap_end-overlap_start):.2f}" height="{h-34}" rx="8" fill="#e8ad4c" opacity=".065"/>')
        for n in range(0,41,5):
            at=x(n);pieces.append(f'<path d="M{at:.2f} 22V{h-10}" stroke="#d2d8bf" stroke-opacity=".065"/>')
            pieces.append(f'<text x="{at:.2f}" y="15" text-anchor="middle" fill="#9b9c87" font-size="8">{n-20:+d}s</text>')
        for lane,(left,right) in enumerate(((end-16,end),(start,start+16))):
            y=top+row*lane;leftx,rightx=x(left),x(right)
            active=self.selected==lane
            pieces.append(f'<rect x="{leftx:.2f}" y="{y:.2f}" width="{rightx-leftx:.2f}" height="{clip_height:.2f}" rx="24" fill="url(#clip{lane})" stroke="{color[lane]}" stroke-opacity="{.45 if active else .19}"/>')
            pieces.append(f'<path d="M{leftx+22:.2f} {y+3:.2f}H{rightx-22:.2f}" stroke="#fff1cc" stroke-opacity=".12"/>')
            points=[]
            for i in range(129):
                t=left+(right-left)*i/128
                phase=(t-start)/max(.0001,end-start)
                gain=(1 if t<end else 0) if self.mode=='cut' and lane==0 else (0 if t<end else 1) if self.mode=='cut' else curve(phase,self.shape)[lane]
                points.append(f'{x(t):.2f},{y+clip_height-6-gain*(clip_height-27):.2f}')
            points=' '.join(points)
            pieces.append(f'<polyline points="{points}" fill="none" stroke="{color[lane]}" stroke-opacity=".12" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="{points}" fill="none" stroke="{color[lane]}" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round"/>')
            name=escape(self.names[lane][:max(6,int((rightx-leftx-35)/6.6))])
            pieces.append(f'<text x="{leftx+18:.2f}" y="{y+14:.2f}" fill="{color[lane]}" font-size="10">{"A" if lane==0 else "B"} / {name}</text>')
            pieces.append(''.join(f'<circle cx="{rightx-12:.2f}" cy="{y+clip_height/2+d:.2f}" r="1.25" fill="#f6e9c8" fill-opacity=".28"/>' for d in (-4,0,4)))

        caption=text('NO OVERLAP','БЕЗ СВЕДЕНИЯ') if self.mode=='cut' else ('≤' if self.mode=='auto' else '')+f'{self.seconds:g} '+text('s overlap','с сведения')
        pieces.append(f'<text x="{(overlap_start+overlap_end)/2:.2f}" y="{h-3}" text-anchor="middle" fill="#f0c677" font-size="9">{caption}</text>')
        hint=escape(text('Drag A or B · Shift for precision','Тяни A или B · Shift — точнее'))
        pieces.append(f'<text x="{w-18}" y="{h-3}" text-anchor="end" fill="#a8ab96" font-size="9">{hint}</text>')
        svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
          <defs><linearGradient id="body" x2="0" y2="1"><stop stop-color="#0b1310"/><stop offset="1" stop-color="#17201a"/></linearGradient>
          <linearGradient id="clip0" x2=".25" y2="1"><stop stop-color="#344b3c"/><stop offset="1" stop-color="#1c3025"/></linearGradient>
          <linearGradient id="clip1" x2=".25" y2="1"><stop stop-color="#554a30"/><stop offset="1" stop-color="#302c1d"/></linearGradient></defs>
          <rect x="1" y="1" width="{w-2}" height="{h-2}" rx="22" fill="url(#body)" stroke="#9da68a" stroke-opacity=".12"/>
          <g font-family="monospace">{''.join(pieces)}</g></svg>'''
        self.image.set_from_pixbuf(pixbuf(svg,w,h))
        self.get_accessible().set_description(text(f'{self.seconds:g} seconds. Left/right moves the selected track; Shift for fine adjustment.',
            f'{self.seconds:g} секунды. Влево/вправо двигает выбранную дорожку; Shift — точная настройка.'))

    def morph(self,_widget,clock):
        now=clock.get_frame_time()/1e6
        if self.morph_start is None:self.morph_start=now
        t=min(1.,(now-self.morph_start)/.32);s=t*t*t*(t*(t*6-15)+10)
        self.shown=self.morph_from+(self.seconds-self.morph_from)*s;self.render()
        if t>=1:self.morph_tick=0;return False
        return True

    def settle_morph(self):
        if self.morph_tick:self.remove_tick_callback(self.morph_tick);self.morph_tick=0
        self.shown=self.seconds

    def press(self,_widget,event):
        if event.button!=1:return False
        self.settle_morph()
        scale,end,start=self.positions();lane=0 if event.y<30+(self.height-48)/2 else 1
        left,right=(end-16,end) if lane==0 else (start,start+16)
        row=(self.height-48)/2;top=30+row*lane
        if not top<=event.y<=top+row-8:return False
        if not 20+left*scale<=event.x<=20+right*scale:return False
        self.selected=lane;self.grab_focus();self.drag=(event.x_root,self.seconds,self.anchor,lane)
        self.grab_add();self.render();return True

    def motion(self,_widget,event):
        if not self.drag:return False
        delta=(event.x_root-self.drag[0])/self.positions()[0]
        if event.state&Gdk.ModifierType.SHIFT_MASK:delta*=.2
        self.pending=delta
        if not self.tick:self.tick=self.add_tick_callback(self.frame)
        return True

    def frame(self,*_):
        self.tick=0
        if self.drag and self.pending is not None:
            delta=self.pending;self.pending=None
            initial,anchor,lane=self.drag[1:]
            self.seconds=overlap(initial,delta,lane)
            if lane==0:self.anchor=max(-4,min(4,anchor+self.seconds-initial))
            self.mode='manual';self.shown=self.seconds;self.render();self.changed(self.seconds,False)
        return False

    def release(self,_widget,event):
        if event.button!=1 or not self.drag:return False
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.frame();self.drag=None;self.grab_remove();self.changed(self.seconds,True);return True

    def key(self,_widget,event):
        name=Gdk.keyval_name(event.keyval)
        if name in ('Up','Down'):self.selected=0 if name=='Up' else 1;self.render();return True
        if name not in ('Left','Right'):return False
        step=(.1 if event.state&Gdk.ModifierType.SHIFT_MASK else .5)*(1 if name=='Right' else -1)
        self.settle_morph()
        previous=self.seconds;self.seconds=overlap(previous,step,self.selected)
        if self.selected==0:self.anchor=max(-4,min(4,self.anchor+self.seconds-previous))
        self.mode='manual';self.shown=self.seconds;self.render();self.changed(self.seconds,True);return True

    def cancel(self,*_):
        self.settle_morph()
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        if self.drag:self.grab_remove();self.drag=None
        self.pending=None
