"""Draggable measured waveforms and gain envelopes, with zoom/pan."""
from html import escape
import math
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,Atk
from hardware_controls import pixbuf
from source_picker import text
from flow_youtube import curve
from flow_curves import point as curve_point


def overlap(initial,delta,lane):
    return round(max(1.,min(30.,initial+(delta if lane==0 else -delta))),1)


class TimelineImage(Gtk.Image):
    def do_get_preferred_width(self):return 0,0
    def do_get_preferred_width_for_height(self,_height):return 0,0


class FlowTimeline(Gtk.EventBox):
    def __init__(self,changed):
        super().__init__();self.ember_key_handler=self.key;self.changed=changed;self.set_visible_window(False);self.set_can_focus(True)
        self.image=TimelineImage();self.add(self.image);self.image.set_hexpand(True)
        self.seconds=self.shown=8.;self.morph_tick=0;self.morph_start=None;self.anchor=0.;self.mode='auto';self.shape='shared';self.names=['A','B']
        self.drag=None;self.selected=1;self.tick=0;self.pending=None;self.width=800;self.height=218;self.dense=False;self.span=80.;self.view_center=20.
        self.eq_open=False;self.clip_seconds=32.;self.waves=[None,None];self.wave_states=['empty','empty'];self.point=[.5,.5];self.curve_drag=None
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
        self.dense=dense;self.update_height()

    def set_eq_open(self,opened):
        if self.eq_open==opened:return
        self.eq_open=opened;self.update_height()

    def update_height(self):
        self.height=(150 if self.dense else 170) if self.eq_open else (178 if self.dense else 218)
        self.set_size_request(0,self.height);self.render()

    def set_plan(self,value,names=None):
        if self.drag or self.curve_drag:return
        point=curve_point(value.get('curve_point'))
        if names is None and (self.seconds,self.mode,self.shape,self.point)==(value['seconds'],value['mode'],value['shape'],point):return
        self.seconds=value['seconds'];self.mode=value['mode'];self.shape=value['shape'];self.point=point
        if abs(self.seconds-self.shown)>.01 and self.get_mapped() and self.get_settings().get_property('gtk-enable-animations'):
            self.morph_from=self.shown;self.morph_start=None
            if not self.morph_tick:self.morph_tick=self.add_tick_callback(self.morph)
        else:self.settle_morph()
        if names is not None:self.names=list(names);self.anchor=0
        self.render()

    def positions(self):
        scale=(self.width-40)/self.span;end=20+self.anchor
        start=end-(0 if self.mode=='cut' else self.shown)
        return scale,end,start

    def time_to_x(self,seconds):return 20+(seconds-(self.view_center-self.span/2))*self.positions()[0]

    def zoom(self,factor):
        self.span=max(20.,min(320.,self.span*factor));self.render()

    def pan(self,direction):
        self.view_center+=self.span*.25*direction;self.render()

    def home(self):
        self.view_center=20+self.anchor-self.seconds/2;self.span=max(80.,self.clip_seconds*2.4);self.render()

    def set_waves(self,waves,states,seconds=32):
        if self.waves==waves and self.wave_states==states and self.clip_seconds==seconds:return
        self.waves=list(waves);self.wave_states=list(states);self.clip_seconds=seconds;self.render()

    def handle(self,lane):
        _,end,start=self.positions();row=(self.height-48)/2;clip_height=row-8
        knee=self.point[0] if self.shape=='custom' else .5
        gain=curve(knee,self.shape,*self.point)[lane]
        return self.time_to_x(start+(end-start)*knee),30+row*lane+clip_height-5-gain*(clip_height-27)

    def render(self):
        w,h=self.width,self.height;scale,end,start=self.positions();x=self.time_to_x
        top=30;row=(h-48)/2;clip_height=row-8;pieces=[];definitions=[]
        colors=['#b7c8a1','#f4bc61'];left_view=self.view_center-self.span/2
        overlap_start=x(start);overlap_end=x(end)
        pieces.append(f'<rect x="{overlap_start:.2f}" y="22" width="{max(0,overlap_end-overlap_start):.2f}" height="{h-34}" rx="12" fill="#e8ad4c" opacity=".065"/>')
        step=self.span/8
        for n in range(9):
            t=left_view+n*step;at=x(t)
            pieces.append(f'<path d="M{at:.2f} 22V{h-10}" stroke="#d2d8bf" stroke-opacity=".065"/>')
            pieces.append(f'<text x="{at:.2f}" y="15" text-anchor="middle" fill="#9b9c87" font-size="8">{t-20:+g}s</text>')
        for lane in (0,1):
            data=self.waves[lane];seconds=data['seconds'] if data else self.clip_seconds
            left,right=(end-seconds,end) if lane==0 else (start,start+seconds)
            y=top+row*lane;leftx,rightx=x(left),x(right);active=self.selected==lane;color=colors[lane]
            definitions.append(f'<clipPath id="lane{lane}"><rect x="{leftx:.2f}" y="{y:.2f}" width="{rightx-leftx:.2f}" height="{clip_height:.2f}" rx="24"/></clipPath>')
            pieces.append(f'<rect x="{leftx:.2f}" y="{y:.2f}" width="{rightx-leftx:.2f}" height="{clip_height:.2f}" rx="24" fill="url(#clip{lane})" stroke="{color}" stroke-opacity="{.45 if active else .19}"/>')
            pieces.append(f'<g clip-path="url(#lane{lane})">')
            if data:
                bins=data['bins'];stride=max(1,math.ceil(len(bins)/max(24,min(768,int((rightx-leftx)/2)))))
                peak_path=[];rms_path=[];center=y+22+(clip_height-27)/2;amplitude=(clip_height-29)/2
                for i in range(0,len(bins),stride):
                    group=bins[i:i+stride];at=x(left+min(data['covered'],(i+len(group)/2)*data['step']))
                    if at<0 or at>w:continue
                    low=min(v[0] for v in group);high=max(v[1] for v in group);rms=math.sqrt(sum(v[2]**2 for v in group)/len(group))
                    peak_path.append(f'M{at:.2f} {center-max(-1,min(1,high))*amplitude:.2f}V{center-max(-1,min(1,low))*amplitude:.2f}')
                    rms_path.append(f'M{at:.2f} {center-min(1,rms)*amplitude:.2f}V{center+min(1,rms)*amplitude:.2f}')
                pieces.append(f'<path d="{"".join(peak_path)}" stroke="{color}" stroke-opacity=".58" stroke-width="1.25" stroke-linecap="round"/><path d="{"".join(rms_path)}" stroke="{color}" stroke-opacity=".9" stroke-width="1.25" stroke-linecap="round"/>')
            else:
                caption=text('Reading actual audio peaks…','Читаем настоящие пики…') if self.wave_states[lane]=='loading' else text('Peaks unavailable · retry below','Пики недоступны · можно повторить')
                pieces.append(f'<text x="{(leftx+rightx)/2:.2f}" y="{y+clip_height*.66:.2f}" text-anchor="middle" fill="#b8b69f" font-size="10">{escape(caption)}</text>')
            points=[]
            for i in range(129):
                t=left+(right-left)*i/128;phase=(t-start)/max(.0001,end-start)
                gain=(1 if t<end else 0) if self.mode=='cut' and lane==0 else (0 if t<end else 1) if self.mode=='cut' else curve(phase,self.shape,*self.point)[lane]
                points.append(f'{x(t):.2f},{y+clip_height-5-gain*(clip_height-27):.2f}')
            pieces.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="#fff2cd" stroke-opacity=".36" stroke-width="1" stroke-linecap="round"/>')
            pieces.append('</g>')
            if self.mode!='cut':
                hx,hy=self.handle(lane)
                pieces.append(f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="11" fill="#f4c875" opacity=".08"/><circle cx="{hx:.2f}" cy="{hy:.2f}" r="6" fill="url(#knot)" stroke="#ffedba" stroke-opacity=".7"/><circle cx="{hx-1:.2f}" cy="{hy-1:.2f}" r="1.5" fill="#fff0c8" opacity=".85"/>')
            name=escape(self.names[lane][:max(6,int((rightx-leftx-100)/6.6))])
            pieces.append(f'<text x="{leftx+18:.2f}" y="{y+14:.2f}" fill="{color}" font-size="10">{"A" if lane==0 else "B"} / {name}</text>')
            if data:pieces.append(f'<text x="{rightx-18:.2f}" y="{y+14:.2f}" text-anchor="end" fill="{color}" font-size="8">PCM · {data["covered"]:.1f}s</text>')
        caption=text('NO OVERLAP','БЕЗ СВЕДЕНИЯ') if self.mode=='cut' else ('≤' if self.mode=='auto' else '')+f'{self.seconds:g} '+text('s overlap','с сведения')
        pieces.append(f'<text x="{max(80,min(w-180,(overlap_start+overlap_end)/2)):.2f}" y="{h-3}" text-anchor="middle" fill="#f0c677" font-size="9">{caption}</text>')
        hint=escape(text('Track: move · gold point: shape · Shift: fine','Дорожка: сдвиг · золотая точка: кривая · Shift: точнее'))
        pieces.append(f'<text x="{w-18}" y="{h-3}" text-anchor="end" fill="#a8ab96" font-size="9">{hint}</text>')
        svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
          <defs><linearGradient id="body" x2="0" y2="1"><stop stop-color="#0b1310"/><stop offset="1" stop-color="#17201a"/></linearGradient>
          <linearGradient id="knot" x2=".3" y2="1"><stop stop-color="#fce2a0"/><stop offset=".5" stop-color="#be923e"/><stop offset="1" stop-color="#795a29"/></linearGradient>
          <linearGradient id="clip0" x2=".25" y2="1"><stop stop-color="#344b3c"/><stop offset="1" stop-color="#1c3025"/></linearGradient>
          <linearGradient id="clip1" x2=".25" y2="1"><stop stop-color="#554a30"/><stop offset="1" stop-color="#302c1d"/></linearGradient>{''.join(definitions)}</defs>
          <rect x="1" y="1" width="{w-2}" height="{h-2}" rx="22" fill="url(#body)" stroke="#9da68a" stroke-opacity=".12"/>
          <g font-family="monospace">{''.join(pieces)}</g></svg>'''
        self.image.set_from_pixbuf(pixbuf(svg,w,h))
        self.get_accessible().set_description(text(f'{self.seconds:g} seconds. Drag tracks or use arrow keys. Measured PCM peaks.',
            f'{self.seconds:g} секунды. Двигай дорожки мышью или стрелками. Измеренные пики PCM.'))

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
        if self.mode!='cut':
            for lane in (0,1):
                hx,hy=self.handle(lane)
                if math.hypot(event.x-hx,event.y-hy)<=15:
                    knee=self.point[0] if self.shape=='custom' else .5
                    level=curve(knee,self.shape,*self.point)[1]
                    self.point=[knee,level];self.shape='custom';self.selected=lane;self.grab_focus()
                    self.curve_drag=(event.x_root,event.y_root,knee,level,lane)
                    self.grab_add();self.render();return True
        scale,end,start=self.positions();lane=0 if event.y<30+(self.height-48)/2 else 1
        seconds=self.waves[lane]['seconds'] if self.waves[lane] else self.clip_seconds
        left,right=(end-seconds,end) if lane==0 else (start,start+seconds)
        row=(self.height-48)/2;top=30+row*lane
        if not top<=event.y<=top+row-8:return False
        if not self.time_to_x(left)<=event.x<=self.time_to_x(right):return False
        self.selected=lane;self.grab_focus();self.drag=(event.x_root,self.seconds,self.anchor,lane)
        self.grab_add();self.render();return True

    def motion(self,_widget,event):
        if self.curve_drag:
            self.pending=(event.x_root-self.curve_drag[0],event.y_root-self.curve_drag[1],bool(event.state&Gdk.ModifierType.SHIFT_MASK))
            if not self.tick:self.tick=self.add_tick_callback(self.frame)
            return True
        if not self.drag:return False
        delta=(event.x_root-self.drag[0])/self.positions()[0]
        if event.state&Gdk.ModifierType.SHIFT_MASK:delta*=.2
        self.pending=delta
        if not self.tick:self.tick=self.add_tick_callback(self.frame)
        return True

    def frame(self,*_):
        self.tick=0
        if self.curve_drag and self.pending is not None:
            dx,dy,fine=self.pending;self.pending=None;_,_,knee,level,lane=self.curve_drag
            factor=.2 if fine else 1.;amplitude=(self.height-48)/2-35
            self.point=[round(max(.1,min(.9,knee+factor*dx/(self.positions()[0]*self.seconds))),4),
                        round(max(.05,min(.95,level+factor*dy/amplitude*(1 if lane==0 else -1))),4)]
            self.mode='manual';self.render();self.changed(self.seconds,False,list(self.point))
            return False
        if self.drag and self.pending is not None:
            delta=self.pending;self.pending=None
            initial,anchor,lane=self.drag[1:]
            self.seconds=overlap(initial,delta,lane)
            if lane==0:self.anchor=anchor+self.seconds-initial
            self.mode='manual';self.shown=self.seconds;self.render();self.changed(self.seconds,False)
        return False

    def release(self,_widget,event):
        if event.button!=1 or not (self.drag or self.curve_drag):return False
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.frame();custom=bool(self.curve_drag);self.drag=None;self.curve_drag=None;self.grab_remove()
        if custom:self.changed(self.seconds,True,list(self.point))
        else:self.changed(self.seconds,True)
        return True

    def key(self,_widget,event):
        name=Gdk.keyval_name(event.keyval)
        if event.state&Gdk.ModifierType.CONTROL_MASK and name in ('Up','Down','Left','Right'):
            if self.mode=='cut':return True
            self.settle_morph();knee=self.point[0] if self.shape=='custom' else .5
            level=curve(knee,self.shape,*self.point)[1];step=.005 if event.state&Gdk.ModifierType.SHIFT_MASK else .025
            knee+=step*(1 if name=='Right' else -1) if name in ('Left','Right') else 0
            level+=step*(1 if name=='Up' else -1)*(1 if self.selected else -1) if name in ('Up','Down') else 0
            self.point=[max(.1,min(.9,knee)),max(.05,min(.95,level))];self.shape='custom';self.mode='manual'
            self.render();self.changed(self.seconds,True,list(self.point));return True
        if name in ('Up','Down'):self.selected=0 if name=='Up' else 1;self.render();return True
        if name not in ('Left','Right'):return False
        step=(.1 if event.state&Gdk.ModifierType.SHIFT_MASK else .5)*(1 if name=='Right' else -1)
        self.settle_morph()
        previous=self.seconds;self.seconds=overlap(previous,step,self.selected)
        if self.selected==0:self.anchor+=self.seconds-previous
        self.mode='manual';self.shown=self.seconds;self.render();self.changed(self.seconds,True);return True

    def cancel(self,*_):
        self.settle_morph()
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        if self.drag or self.curve_drag:self.grab_remove();self.drag=None;self.curve_drag=None
        self.pending=None
