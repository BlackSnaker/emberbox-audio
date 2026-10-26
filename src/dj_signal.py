"""A physical microphone dial, prepared as vector sprites away from GTK."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import math,time
from gi.repository import Gtk,GdkPixbuf,GLib


@lru_cache(maxsize=256)
def frame(size,level=0,recording=False,phase=-1):
    energy=level/40;busy=phase>=0;ticks=[]
    for i in range(48):
        angle=i*math.tau/48-math.pi/2;long=i%4==0;r=72 if long else 74
        amount=(math.sin(angle*3+phase*math.tau/32)*.5+.5) if busy else energy
        ticks.append(f'<path d="M {84+math.cos(angle)*r:.2f} {84+math.sin(angle)*r:.2f} L {84+math.cos(angle)*78:.2f} {84+math.sin(angle)*78:.2f}" stroke="#f5bd52" stroke-opacity="{(.42 if long else .16)+amount*.23:.3f}" stroke-width="{1.1 if long else .75}"/>')
    angle=-math.pi/2+(phase*math.tau/32 if busy else -.65);length=1.35 if busy else 1.25+energy*2
    x,y=84+math.cos(angle)*60,84+math.sin(angle)*60
    ex,ey=84+math.cos(angle+length)*60,84+math.sin(angle+length)*60
    icon='#ffca63' if recording else '#e8d9a6'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 168 168">
<defs><radialGradient id="halo"><stop offset=".57" stop-color="#ff9e26" stop-opacity="{.10+energy*.17:.3f}"/><stop offset="1" stop-color="#ff9e26" stop-opacity="0"/></radialGradient>
<linearGradient id="metal" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#756e52"/><stop offset=".16" stop-color="#4a4a3b"/><stop offset=".55" stop-color="#242e24"/><stop offset="1" stop-color="#192119"/></linearGradient>
<radialGradient id="inner" cx="33%" cy="26%" r="80%"><stop stop-color="#525942"/><stop offset="1" stop-color="#293629"/></radialGradient></defs>
<circle cx="84" cy="84" r="84" fill="url(#halo)"/><circle cx="87" cy="90" r="66" fill="#000" opacity=".28"/>
<circle cx="84" cy="84" r="66" fill="url(#metal)"/><circle cx="84" cy="84" r="65.5" fill="none" stroke="#edd192" stroke-opacity=".26"/>
<circle cx="84" cy="84" r="57" fill="none" stroke="#050a08" stroke-opacity=".8"/>{''.join(ticks)}
<circle cx="84" cy="84" r="52" fill="url(#inner)" stroke="#e8d9a3" stroke-opacity=".1"/>
<path d="M{x:.2f} {y:.2f} A60 60 0 {int(length>math.pi)} 1 {ex:.2f} {ey:.2f}" fill="none" stroke="#ffba47" stroke-opacity="{.2+energy*.65:.3f}" stroke-width="2.2" stroke-linecap="round"/>
<g transform="translate(84 84)" fill="none" stroke="{icon}" stroke-width="2.5" stroke-linecap="round">
<path d="M-7 -13 V-1 C-7 9 7 9 7 -1 V-13 C7 -23 -7 -23 -7 -13 Z M-13 -3 C-13 17 13 17 13 -3 M0 12 V21 M-7 21 H7"/></g>
<circle cx="84" cy="121" r="2.1" fill="#ffba3d" opacity="{.9 if recording else .32}"/></svg>'''
    loader=GdkPixbuf.PixbufLoader.new_with_type('svg');loader.write(svg.encode());loader.close();return loader.get_pixbuf()


class DJSignal(Gtk.Image):
    def __init__(self,service):
        super().__init__();self.service=service;self.level=0.;self.tick=0;self.last=None;self.size=168
        self.key=None;self.closed=False;self.active=False;self.prepared=set();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-dj-dial')
        self.frames={};self.show_frame((168,0,False,-1),frame(168))
        self.connect('map',self.mapped);self.connect('unmap',self.unmapped);self.connect('destroy',self.close)
    def show_frame(self,key,pixbuf):
        if self.closed:return False
        self.key=key;self.set_from_pixbuf(pixbuf);return False
    def warm(self,size):
        if size in self.prepared:return
        self.prepared.add(size)
        def prepare():
            for recording in (False,True):
                for level in range(41):
                    if self.closed:return
                    key=(size,level,recording,-1);self.frames[key]=frame(*key)
            for phase in range(32):
                if self.closed:return
                key=(size,0,False,phase);self.frames[key]=frame(*key)
        self.pool.submit(prepare)
    def mapped(self,*_args):
        if self.closed or not self.active:return
        self.last=None;self.warm(self.size)
        if not self.tick:self.tick=self.add_tick_callback(self.animate)
    def set_active(self,active):
        self.active=bool(active)
        if self.active and self.get_mapped():self.mapped()
        else:self.unmapped()
    def unmapped(self,*_args):
        if self.tick:self.remove_tick_callback(self.tick);self.tick=0
        self.last=None
    def resize(self,small):
        self.size=94 if small else 168;self.set_size_request(self.size,self.size)
        if self.active and self.get_mapped():self.warm(self.size)
        self.show_frame((self.size,0,False,-1),frame(self.size))
    def animate(self,_widget,clock):
        if self.closed or not self.active:self.tick=0;self.last=None;return False
        now=clock.get_frame_time()/1e6;dt=min(.06,max(.001,now-self.last)) if self.last else 1/60;self.last=now
        voice=self.service.voice;recording=voice.phase=='listening'
        busy=self.service.busy or voice.phase in ('preparing-voice','preparing-reply')
        if recording:target=voice.level
        elif self.service.host.playing:
            levels=getattr(self.service.host,'visual_levels',[]);target=sum(levels)/max(1,len(levels))*.65
        else:target=0.
        self.level+=(target-self.level)*(1-math.exp(-dt/(.1 if target>self.level else .3)))
        key=(self.size,0 if busy else round(max(0,min(1,self.level))*40),False if busy else recording,int(now*24)%32 if busy else -1)
        if key!=self.key:
            sprite=self.frames.get(key)
            if sprite:self.show_frame(key,sprite)
        return True
    def close(self,*_args):
        self.closed=True;self.unmapped();self.pool.shutdown(wait=False,cancel_futures=True);self.frames.clear()
