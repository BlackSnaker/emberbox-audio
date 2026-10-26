#!/usr/bin/env python3
"""Two bounded PCM inputs, one output clock and sample-smooth spatial EmberFlow."""
import collections,json,os,resource,struct,sys,threading,time
import numpy as np
from spatial_mix import RATE,BLOCK,BUFFER,blend,curve
# A session uses one rate for both decks; ordinary Atmos stays at 48 kHz.
RATE=int(os.environ.get('EMBERBOX_SPATIAL_RATE',RATE))
if RATE not in (48000,192000):raise RuntimeError('SPATIAL_PCM_FORMAT')
BLOCK=RATE//50;BUFFER=RATE*4
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
# PR_SET_DUMPABLE also prevents system crash handlers from retaining audio.
import ctypes
if ctypes.CDLL(None).prctl(4,0,0,0,0)!=0:raise RuntimeError('SPATIAL_DUMP_PROTECTION')
if ctypes.CDLL(None).prctl(1,15,0,0,0)!=0:raise RuntimeError('SPATIAL_PARENT_PROTECTION')
if os.getppid()==1:os._exit(1)

class Slot:
    def __init__(self,generation,origin,preroll=2):
        self.generation=generation;self.origin=float(origin);self.parts=collections.deque()
        self.frames=0;self.received=0;self.consumed=0;self.total=None;self.start=0;self.ready=False;self.padding=0
        self.preroll=max(.4,min(2.,float(preroll)))
        self.seeking=False;self.attack=0
    def take(self,n):
        parts=[]
        while n and self.parts:
            value=self.parts[0];count=min(n,len(value));parts.append(value[:count])
            if count==len(value):self.parts.popleft()
            else:self.parts[0]=value[count:]
            n-=count;self.frames-=count;self.consumed+=count
        return parts[0].copy() if len(parts)==1 else np.concatenate(parts) if parts else np.empty((0,2),np.float32)
    def ended(self):return self.total is not None and self.consumed>=self.total

class Mixer:
    def __init__(self,emit):
        self.emit=emit;self.condition=threading.Condition();self.slots=[None,None]
        self.current=0;self.fade=None;self.frames=0;self.paused=False;self.stopped=False
        self.player=None;self.finished=False;self.seek_tail=None
    def configure(self,p):
        slot=int(p['slot']);generation=int(p['generation'])
        if slot not in (0,1) or not 0<generation<2**32:raise ValueError('Invalid spatial slot')
        with self.condition:
            if self.fade:raise ValueError('Spatial mix in progress')
            self.slots[slot]=Slot(generation,p.get('position',0),p.get('preroll',2));self.condition.notify_all()
    def received(self,slot,generation,raw):
        value=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
        if not np.isfinite(value).all():raise ValueError('Nonfinite spatial samples')
        with self.condition:
            while not self.stopped:
                target=self.slots[slot]
                if target is None or target.generation!=generation:return
                if target.frames<BUFFER:break
                self.condition.wait(.1)
            if self.stopped:return
            target.parts.append(value.copy());target.frames+=len(value);target.received+=len(value)
            if not target.ready and target.received>=RATE*target.preroll:
                target.ready=True;self.emit({'type':'ready','slot':slot,'generation':generation})
            self.condition.notify_all()
    def control(self,p):
        action=p['type']
        if action=='slot':self.configure(p)
        elif action=='seek':
            slot=int(p['slot']);generation=int(p['generation']);position=float(p['position'])
            if slot not in (0,1) or not 0<generation<2**32 or not 0<=position<86400:raise ValueError('Invalid spatial slot')
            with self.condition:
                # Discard old buffered PCM immediately, including a half-finished
                # Flow mix. Keep the device and its absolute output clock alive.
                old=self.slots[self.current]
                tail=old.take(BLOCK) if old and not self.paused else np.empty((0,2),np.float32)
                self.seek_tail=tail*(1.-curve(np.linspace(0,1,len(tail))))[:,None] if len(tail) else None
                self.fade=None;self.current=slot;self.slots[1-slot]=None
                target=self.slots[slot]=Slot(generation,position,.4)
                target.start=self.frames+(len(tail) if len(tail) else 0);target.preroll=.12;target.seeking=True
                self.finished=False;self.condition.notify_all()
        elif action=='end':
            with self.condition:
                target=self.slots[int(p['slot'])]
                if target and target.generation==p['generation']:
                    target.total=int(p['frames'])
                    if not target.ready and target.received>=target.total:
                        target.ready=True;self.emit({'type':'ready','slot':int(p['slot']),'generation':target.generation})
                self.condition.notify_all()
        elif action=='transition':
            with self.condition:
                other=1-self.current;target=self.slots[other]
                minimum=RATE*(.4 if p.get('manual') is True else 1.)
                if self.fade or not target or target.frames<minimum:raise ValueError('Spatial next not ready')
                duration=max(.15,min(8.,float(p['duration'])))
                outgoing=self.slots[self.current]
                if outgoing.total is not None:duration=min(duration,max(.01,(outgoing.total-outgoing.consumed)/RATE))
                target.start=self.frames;self.fade={'old':self.current,'next':other,'start':self.frames,
                    'length':round(duration*RATE),'initial':0.,'announced':False,'key':p['key']}
                self.finished=False;self.condition.notify_all()
        elif action=='cancel':
            with self.condition:
                if self.fade:
                    fade=self.fade;x=(self.frames-fade['start'])/max(1,fade['length']-1)
                    gain=fade['initial']+(1.-fade['initial'])*float(curve(x))
                    if int(p.get('keep',self.current))==fade['old']:
                        fade['old'],fade['next']=fade['next'],fade['old'];gain=1.-gain
                    fade.update(initial=gain,start=self.frames,length=round(.18*RATE),rendered=False,announced=True)
                else:self.slots[1-self.current]=None
                self.condition.notify_all()
        elif action=='pause':
            self.paused=p.get('paused') is True
            if self.player:self.player.pause=self.paused
        elif action=='stop':
            with self.condition:self.stopped=True;self.condition.notify_all()
    def render(self):
        with self.condition:
            if self.seek_tail is not None:
                tail=self.seek_tail;self.seek_tail=None;self.frames+=len(tail)
                return tail.astype('<f4',copy=False).tobytes()
            fade=self.fade if self.fade and not self.fade.get('rendered') else None
            old=self.slots[fade['old'] if fade else self.current]
            new=self.slots[fade['next']] if fade else None
            if not old:return None
            if old.seeking and not old.ready:return None
            if old.ended() and not fade and old.padding<RATE*.15:
                old.padding+=BLOCK;self.frames+=BLOCK;return bytes(BLOCK*8)
            count=min(BLOCK,old.frames)
            if fade:
                if old.ended():count=BLOCK
                count=min(count,new.frames if new else 0,fade['length']-(self.frames-fade['start']))
            if count<BLOCK and not old.ended() and old.total!=old.consumed+old.frames and not fade:return None
            if not count:return None
            out=old.take(count)
            if old.seeking:
                # A short sample envelope avoids an abrupt first waveform edge.
                length=round(.020*RATE);n=min(len(out),max(0,length-old.attack))
                if n:out[:n]*=curve((np.arange(n)+old.attack)/max(1,length-1))[:,None]
                old.attack+=len(out)
            if fade and len(out)<count:out=np.pad(out,((0,count-len(out)),(0,0)))
            if fade:out=blend(out,new.take(count),self.frames-fade['start'],fade['length'],fade['initial'])
            self.frames+=count
            if fade and self.frames>=fade['start']+fade['length']:
                fade['rendered']=True;self.current=fade['next']
            self.condition.notify_all();return out.astype('<f4',copy=False).tobytes()
    def watch(self):
        while not self.stopped:
            time.sleep(.15)
            if not self.player:continue
            try:played=max(0.,float(self.player.time_pos or 0))*RATE
            except Exception:continue
            with self.condition:
                fade=self.fade
                if fade and not fade['announced'] and played>=self.slots[fade['next']].start:
                    fade['announced']=True
                    self.emit({'type':'flow-started','key':fade['key'],'slot':fade['next'],'duration':fade['length']/RATE})
                if fade and fade.get('rendered') and fade['announced']:
                    old=fade['old'];generation=self.slots[old].generation;self.slots[old]=None;self.fade=None
                    self.emit({'type':'released','slot':old,'generation':generation});self.condition.notify_all()
                current=self.slots[fade['next'] if fade and fade['announced'] else self.current]
                if not current:continue
                elapsed=max(0.,(played-current.start)/RATE)
                position=current.origin+min(elapsed,current.total/RATE) if current.total is not None else current.origin+elapsed
                ended=current.ended() and played>=current.start+current.total-1
                ready=current.ready if current.seeking else current.received>=min(RATE,current.total or RATE)
                self.emit({'type':'state','slot':fade['next'] if fade and fade['announced'] else self.current,
                    'generation':current.generation,
                    'position':position,'phase':'ended' if ended else 'playing' if ready else 'preparing',
                    'playing':ready and not self.paused and not ended,'seeking':current.seeking and (not ready or not self.paused and played<current.start),
                    'buffers':[[s.frames,s.received,s.consumed,s.total if s.total is not None else -1] if s else [] for s in self.slots],
                    'playedFrame':round(played),'paused':self.paused,
                    'mixFrame':self.frames,'fade':([self.fade['start'],self.fade['length']] if self.fade else [])})


def exact(stream,n):
    data=bytearray()
    while len(data)<n:
        part=stream.read(n-len(data))
        if not part:return None
        data.extend(part)
    return bytes(data)


def main():
    output_lock=threading.Lock()
    def emit(value):
        with output_lock:print(json.dumps(value,separators=(',',':')),flush=True)
    mixer=Mixer(emit)
    def control():
        try:
            for raw in sys.stdin.buffer:
                if len(raw)>65536:break
                mixer.control(json.loads(raw))
                if mixer.stopped:return
        finally:mixer.control({'type':'stop'})
    def receive(slot):
        try:
            with os.fdopen(3+slot,'rb',buffering=0) as stream:
                while not mixer.stopped:
                    header=exact(stream,8)
                    if header is None:return
                    generation,length=struct.unpack('<II',header)
                    if not 0<length<=1048576 or length%8:raise ValueError('Invalid PCM frame')
                    data=exact(stream,length)
                    if data is None:return
                    mixer.received(slot,generation,data)
        except Exception:emit({'type':'error','code':'SPATIAL_MIX_INPUT'});mixer.control({'type':'stop'})
    threading.Thread(target=control,daemon=True).start()
    for slot in (0,1):threading.Thread(target=receive,args=(slot,),daemon=True).start()
    import mpv
    player=mixer.player=mpv.MPV(config=False,idle=True,keep_open=True,vid='no',vo='null',audio_display='no',
        force_window=False,input_default_bindings=False,input_vo_keyboard=False,osc=False,
        terminal=False,osd_level=0,ao='pulse',volume=100,volume_max=100,mute=False,
        audio_client_name='Emberbox Audio · Apple Music',demuxer='rawaudio',
        demuxer_rawaudio_format='floatle',demuxer_rawaudio_rate=RATE,demuxer_rawaudio_channels='stereo',
        cache=False,demuxer_readahead_secs=.2,demuxer_max_bytes=131072,demuxer_max_back_bytes=0,audio_buffer=.1)
    read_fd,write_fd=os.pipe();player.pause=mixer.paused;player.play('fd://'+str(read_fd))
    threading.Thread(target=mixer.watch,daemon=True).start()
    try:
        while not mixer.stopped:
            data=mixer.render()
            if data is None:
                with mixer.condition:mixer.condition.wait(.015)
                continue
            view=memoryview(data)
            while view and not mixer.stopped:view=view[os.write(write_fd,view):]
    finally:
        player.terminate();os.close(read_fd);os.close(write_fd)

if __name__=='__main__':
    try:main()
    except Exception as error:
        hints={'Spatial mix in progress','Spatial next not ready','Invalid spatial slot','Nonfinite spatial samples','Invalid PCM frame'}
        hint=str(error) if str(error) in hints else type(error).__name__
        print(json.dumps({'type':'error','code':'SPATIAL_MIX_FAILED','hint':hint}),flush=True);raise SystemExit(1)
