"""Small deterministic snow showers: absolute-time flight, landing and thaw."""
from dataclasses import dataclass
import math
import random

MAX_FLAKES=48


def smooth(value):
    value=max(0.,min(1.,value));return value*value*value*(value*(value*6.-15.)+10.)


@dataclass
class Flake:
    born:float
    x:float
    speed:float
    drift:float
    sway:float
    phase:float
    size:float
    opacity:float
    landed:float=-1.
    shelf:str=''
    u:float=0.
    hold:float=4.
    thaw:float=7.
    hit_x:float=0.
    hit_y:float=0.


class SnowShower:
    def __init__(self,seed=None):
        self.random=random.Random(seed);self.flakes=[];self.age=0.;self.next_spawn=0.;self.duration=8.
        self.spawned=0;self.landed_count=0;self.previous={}

    def start(self,width,height,frequent=False):
        self.clear();self.width=width;self.height=height
        self.cap=22 if width>600 else 10 if width>360 else 8
        self.frequent=bool(frequent);self.duration=math.inf if self.frequent else 8.
        self.batch=5 if width>600 else 3 if width>360 else 2
        self.wave_start=0.;self.wave_emitted=0
        self.interval=self.duration/self.cap;self.next_spawn=0.

    def clear(self):
        self.flakes=[];self.age=0.;self.next_spawn=0.;self.spawned=0;self.landed_count=0;self.previous={}

    def emit(self,now,shelves):
        r=self.random;targets=[v for v in shelves if v[2]-v[1]>24 and v[3]>45]
        if targets and r.random()<.72:
            target=r.choice(targets);x=r.uniform(target[1]+8,target[2]-8)
        else:x=r.uniform(12,max(13,self.width-12))
        speed=r.uniform(65,100)*max(1.,self.height/1000) if self.width>600 else r.uniform(28,43)
        self.flakes.append(Flake(now,x,speed,r.uniform(-1.6,1.6),r.uniform(2.,6.),r.uniform(0,math.tau),
                                 r.uniform(1.2,2.6),r.uniform(.38,.72),hold=r.uniform(3.5,6.),thaw=r.uniform(6.,9.)))
        self.spawned+=1

    def advance(self,age,shelves):
        next_age=max(self.age,float(age))
        if self.frequent and next_age-self.age>32.:
            # Do not replay hours of missed showers after monitor sleep.
            self.flakes=[];self.previous={};self.next_spawn=next_age
            self.wave_start=next_age;self.wave_emitted=0
        self.age=next_age;lookup={v[0]:v for v in shelves}
        while self.next_spawn<=self.age and self.next_spawn<self.duration and (self.frequent or self.spawned<self.cap):
            # Small recurring waves share the existing live-particle budget.
            # A new wave never clears older deposits or waits for them to thaw.
            if len(self.flakes)<self.cap:self.emit(self.next_spawn,shelves)
            if self.frequent:
                self.wave_emitted+=1
                if self.wave_emitted>=self.batch:
                    self.next_spawn=self.wave_start+self.random.uniform(5.5,8.5)
                    self.wave_start=self.next_spawn;self.wave_emitted=0
                else:self.next_spawn+=.45
            else:self.next_spawn+=self.interval
        dots=[];alive=[]
        for f in self.flakes:
            t=max(0.,self.age-f.born)
            if f.landed<0:
                x=f.x+f.drift*t+f.sway*(math.sin(t*.7+f.phase)-math.sin(f.phase))
                y=-7+f.speed*t
                last=self.previous.get(id(f),(f.x,-7))
                # Land on the first visible top edge crossed this frame.
                hits=[s for s in shelves if last[1]<=s[3]<=y and s[1]+3<=x<=s[2]-3]
                if hits:
                    shelf=min(hits,key=lambda s:s[3]);f.landed=self.age;f.shelf=shelf[0]
                    f.u=(x-shelf[1])/max(1.,shelf[2]-shelf[1]);f.hit_x=x;f.hit_y=shelf[3]
                    self.landed_count+=1;self.previous.pop(id(f),None)
                elif y>self.height+12 or x<-12 or x>self.width+12:
                    self.previous.pop(id(f),None);continue
                else:
                    self.previous[id(f)]=(x,y)
                    dots.append((x,y,f.size,f.opacity*smooth(t/1.2),f.size));alive.append(f);continue
            shelf=lookup.get(f.shelf)
            if not shelf:continue  # Never leave a floating patch after page/layout changes.
            elapsed=self.age-f.landed;melt=smooth((elapsed-f.hold)/f.thaw)
            if melt>=1.:continue
            settle=smooth(elapsed/.7)
            x=shelf[1]+f.u*(shelf[2]-shelf[1]);y=shelf[3]-.6
            # Negative size selects a shallow, softly feathered snow cap.
            width=f.size*(1.+settle*1.65)*(1.-melt*.42)
            height=f.size*(1.-settle*.64)*(1.-melt*.5)
            dots.append((x,y,-width,f.opacity*(1.-melt),max(.35,height)));alive.append(f)
        self.flakes=alive
        return dots

    @property
    def finished(self):return self.age>=self.duration and not self.flakes
