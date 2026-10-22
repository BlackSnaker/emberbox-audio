"""Opt-in local neural karaoke, isolated from GTK and the system mix.

The helper owns a temporary PulseAudio sink and restores routed application
streams on EOF, signal, device loss or DSP failure. No microphone is opened,
and no PCM is written to disk. The optional UVR model estimates vocals; the
explicit fast mode uses stereo centre suppression and also affects instruments.
"""
import json
import math
import os
from pathlib import Path
import select
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time

import numpy as np
from stream_target import Target, matches
import karaoke_model

RATE=48000
SIZE=2048
HOP=512
PREFIX=f'emberbox_karaoke_{os.getuid()}_'


class VocalFilter:
    """Overlap-add spectral mid/side reduction with bass protection.

    32 ms of algorithmic delay, independent of server buffering. Real
    complex spectra retain phase; bounded smoothed gain avoids hard bin gates.
    No makeup gain or automatic volume jump is applied.
    """
    def __init__(self,amount=.7):
        self.window=np.sqrt(np.hanning(SIZE+1)[:-1])
        self.input=np.zeros((SIZE,2));self.output=np.zeros((SIZE,2))
        self.amount=0.;self.target=float(np.clip(amount,0,1))
        freq=np.fft.rfftfreq(SIZE,1/RATE)
        self.band=np.minimum(np.clip((freq-120)/180,0,1),np.clip((10000-freq)/2500,0,1))
        self.gain=np.ones(len(freq))

    def process(self,pcm):
        if pcm.shape!=(HOP,2):raise ValueError('Expected a stereo hop')
        self.input[:-HOP]=self.input[HOP:];self.input[-HOP:]=np.nan_to_num(pcm,nan=0,posinf=0,neginf=0)
        spectrum=np.fft.rfft(self.input*self.window[:,None],axis=0)
        left,right=spectrum[:,0],spectrum[:,1]
        mid=(left+right)*.5;side=(left-right)*.5
        self.amount+=(self.target-self.amount)*(1-math.exp(-HOP/RATE/.085))
        # A coherence gate can leave a centred voice nearly untouched whenever
        # wide accompaniment occupies the same bins. Reduce the vocal-band mid
        # directly: the dial must have an audible, predictable effect in a mix.
        # Side and low bass remain intact; other centred instruments can change.
        desired=1-self.amount*.97*self.band
        self.gain+=.32*(desired-self.gain)
        mid*=self.gain
        filtered=np.column_stack((mid+side,mid-side))
        frame=np.fft.irfft(filtered,n=SIZE,axis=0)*self.window[:,None]/2
        self.output+=frame
        result=self.output[:HOP].copy()
        self.output[:-HOP]=self.output[HOP:];self.output[-HOP:]=0
        return np.clip(result,-1,1).astype('<f4')


def pactl(*args,json_output=False):
    command=['pactl']+(['-f','json'] if json_output else [])+list(args)
    result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=2)
    return json.loads(result.stdout) if json_output else result.stdout.strip()


def runtime():
    # UID-specific private recovery journals contain route IDs only.
    root=Path(os.environ.get('XDG_RUNTIME_DIR',f'/tmp/emberbox-{os.getuid()}'))/'emberbox-karaoke'
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    return root


def recover():
    for path in runtime().glob('route-*.json'):
        try:
            state=json.loads(path.read_text())
            pid=int(state['pid']);name=state['name']
            if not name.startswith(PREFIX) or name!=PREFIX+str(pid):continue
            if Path(f'/proc/{pid}').exists():continue
            restore(state);path.unlink(missing_ok=True)
        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):pass


def restore(state):
    sinks=pactl('list','sinks',json_output=True)
    names={str(s['index']):s['name'] for s in sinks}
    owned=next((s for s in sinks if s['name']==state['name']),None)
    if owned is None:return
    index=str(owned['index'])
    default=pactl('get-default-sink')
    fallback=default if default in names.values() and default!=state['name'] else next(
        (name for name in names.values() if not name.startswith(PREFIX)),None)
    failed=False
    for stream in pactl('list','sink-inputs',json_output=True):
        if str(stream['sink'])!=index:continue  # Respect manual routing elsewhere.
        old=state.get('routes',{}).get(str(stream['index']),fallback)
        destination=old if old in names.values() and old!=state['name'] else fallback
        if destination:
            try:pactl('move-sink-input',str(stream['index']),destination)
            except (OSError,subprocess.SubprocessError):failed=True
        else:failed=True
    # Unloading a null sink also lets the server rescue streams if their old
    # output disappeared. Never unload a module by a recycled numeric ID.
    for module in pactl('list','modules',json_output=True):
        if module.get('name')=='module-null-sink' and 'sink_name='+state['name'] in module.get('argument','').split():
            # PipeWire's pactl JSON can omit module indices; the verified
            # sink's owner_module is the corresponding server ID.
            identifier=module.get('index',owned.get('owner_module'))
            if identifier is None:raise RuntimeError('Missing module identifier')
            pactl('unload-module',str(identifier))
            return
    if failed:raise RuntimeError('Could not restore karaoke route')


class Route:
    def __init__(self,target,amount,engine='stereo',notify=lambda **_:None,muted=False):
        self.target=target;self.filter=VocalFilter(amount) if engine=='stereo' else None
        self.engine=engine;self.notify=notify;self.amount=amount;self.neural=None
        self.workers=[];self.samples_in=self.samples_out=self.samples_consumed=0
        self.delay=0.;self.output_started=False
        self.muted=muted
        self.name=PREFIX+str(os.getpid());self.path=runtime()/f'route-{os.getpid()}.json'
        self.state={'pid':os.getpid(),'name':self.name,'routes':{}}
        self.capture=None;self.playback=None;self.thread=None
        self.stop=threading.Event();self.error=None;self.heartbeat=time.monotonic()
        self.destination=None;self.sink_index=None;self.routed=False

    def save(self):
        temporary=self.path.with_suffix('.next')
        with temporary.open('w') as stream:
            os.chmod(temporary,0o600);json.dump(self.state,stream)
        temporary.replace(self.path)

    def start(self):
        streams=[s for s in pactl('list','sink-inputs',json_output=True) if matches(s.get('properties',{}),self.target)]
        sinks=pactl('list','sinks',json_output=True)
        names={str(s['index']):s['name'] for s in sinks}
        destinations={names.get(str(s['sink'])) for s in streams}
        destinations.discard(None)
        if len(destinations)>1:raise RuntimeError('multiple-outputs')
        if not streams:raise RuntimeError('no-stream')
        if any(s.get('channel_map')!='front-left,front-right' for s in streams):raise RuntimeError('stereo-required')
        self.destination=next(iter(destinations),pactl('get-default-sink'))
        if self.destination.startswith(PREFIX):raise RuntimeError('invalid-output')
        if self.engine=='ai':
            self.notify(phase='model')
            from karaoke_neural import NeuralSeparator,NeuralBlocks,LOOKAHEAD
            separator=NeuralSeparator()
            block,duration=separator.benchmark()
            self.neural=NeuralBlocks(separator,block,self.amount)
            self.delay=block/RATE+LOOKAHEAD/RATE+duration*1.4+.15
        if self.stop.is_set():raise RuntimeError('cancelled')
        # Save before creating anything, so a crash during setup is recoverable.
        self.save()
        pactl('load-module','module-null-sink','sink_name='+self.name,'rate=48000','channels=2',
              'sink_properties=device.description=Emberbox_Karaoke')
        self.sink_index=str(next(s['index'] for s in pactl('list','sinks',json_output=True) if s['name']==self.name))
        common=['--raw','--format=float32le','--rate=48000','--channels=2','--channel-map=front-left,front-right',
                '--latency-msec=35','--process-time-msec=10','--client-name=Emberbox Karaoke',
                '--property=emberbox.karaoke=true']
        self.playback=subprocess.Popen(['pacat','--playback','--volume=65536','--device='+self.destination,*common],
                                       stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,bufsize=0)
        self.capture=subprocess.Popen(['pacat','--record','--device='+self.name+'.monitor',*common],
                                      stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        # Let the return client enter the server graph before moving the source.
        # A policy rescan during late client registration can otherwise restore
        # an application's explicit original target over our first move.
        deadline=time.monotonic()+2
        return_target=Target('karaoke',os.getpid(),'','karaoke',True)
        while not self.stop.is_set():
            streams=pactl('list','sink-inputs',json_output=True)
            if any(matches(s.get('properties',{}),return_target) for s in streams):break
            if time.monotonic()>deadline:raise RuntimeError('audio-failed')
            self.stop.wait(.03)
        self.heartbeat=time.monotonic()
        if self.engine=='ai':self.notify(phase='buffering',delay=self.delay)
        self.thread=threading.Thread(target=self.audio,daemon=True);self.thread.start()
        self.refresh()

    def refresh(self):
        # The real output must still exist; stop rather than leave a silent sink.
        sinks=pactl('list','sinks',json_output=True)
        if self.destination not in {s['name'] for s in sinks}:raise RuntimeError('output-lost')
        names={str(s['index']):s['name'] for s in sinks}
        streams=pactl('list','sink-inputs',json_output=True)
        self.sync_return_mute(streams)
        for stream in streams:
            if not matches(stream.get('properties',{}),self.target):continue
            if stream.get('channel_map')!='front-left,front-right':raise RuntimeError('stereo-required')
            index=str(stream['index']);sink=str(stream['sink'])
            if sink==self.sink_index:continue
            if index in self.state['routes']:raise RuntimeError('route-changed')
            old=names.get(sink)
            if not old or old.startswith(PREFIX) or old!=self.destination:raise RuntimeError('multiple-outputs')
            self.state['routes'][index]=old;self.save()
            pactl('move-sink-input',index,self.name);self.routed=True
        if self.error:raise RuntimeError('ai-too-slow' if str(self.error)=='ai-too-slow' else 'audio-failed')
        if time.monotonic()-self.heartbeat>2:raise RuntimeError('audio-stalled')

    def audio(self):
        if self.engine=='ai':return self.audio_ai()
        try:
            buffer=bytearray();hop_bytes=HOP*8
            while not self.stop.is_set():
                if self.playback.poll() is not None or self.capture.poll() is not None:raise RuntimeError('Audio client exited')
                ready,_,_=select.select([self.capture.stdout],[],[],.2)
                if not ready:continue
                chunk=os.read(self.capture.stdout.fileno(),32768)
                if not chunk:break
                buffer.extend(chunk)
                while len(buffer)>=hop_bytes and not self.stop.is_set():
                    pcm=np.frombuffer(bytes(buffer[:hop_bytes]),dtype='<f4').reshape(HOP,2)
                    del buffer[:hop_bytes]
                    data=memoryview(self.filter.process(pcm).tobytes())
                    while data and not self.stop.is_set():
                        _,writable,_=select.select([],[self.playback.stdin],[],.2)
                        if writable:data=data[os.write(self.playback.stdin.fileno(),data):]
                    self.heartbeat=time.monotonic()
            if not self.stop.is_set():raise RuntimeError('Audio capture ended')
        except Exception as error:self.error=error

    def set_amount(self,amount):
        self.amount=amount
        if self.filter:self.filter.target=amount
        if self.neural:self.neural.target=amount

    def sync_return_mute(self,streams=None):
        target=Target('karaoke',os.getpid(),'','karaoke',True)
        for stream in streams if streams is not None else pactl('list','sink-inputs',json_output=True):
            if matches(stream.get('properties',{}),target) and bool(stream.get('mute'))!=self.muted:
                pactl('set-sink-input-mute',str(stream['index']),'1' if self.muted else '0')

    def audio_ai(self):
        """Capture, infer and play on separate bounded queues.

        Inference must not stop capture or be paced by pacat's playback pipe.
        Overflow restores the original route instead of accumulating latency.
        """
        input_queue=queue.Queue(maxsize=128);output_queue=queue.Queue(maxsize=4)
        started=time.monotonic();delay=self.delay
        def fail(error):
            if self.error is None:self.error=error
            self.stop.set()
        def infer():
            pending=np.zeros((0,2),np.float32)
            try:
                while not self.stop.is_set():
                    needed=self.neural.required
                    while len(pending)<needed and not self.stop.is_set():
                        try:chunk=input_queue.get(timeout=.15)
                        except queue.Empty:continue
                        pending=np.concatenate((pending,chunk));self.samples_consumed+=len(chunk)
                    if self.stop.is_set():break
                    chunk,pending=pending[:needed],pending[needed:]
                    result=self.neural.process(chunk)
                    try:output_queue.put(result,timeout=.2)
                    except queue.Full:raise RuntimeError('ai-too-slow')
            except Exception as error:fail(error)
        def play():
            try:
                while not self.stop.is_set():
                    try:pcm=output_queue.get(timeout=.15)
                    except queue.Empty:continue
                    if self.stop.wait(max(0,started+delay-time.monotonic())):break
                    data=memoryview(pcm.tobytes())
                    while data and not self.stop.is_set():
                        _,writable,_=select.select([],[self.playback.stdin],[],.15)
                        if writable:
                            count=os.write(self.playback.stdin.fileno(),data);data=data[count:]
                            self.samples_out+=count//8
                            if not self.output_started:
                                self.output_started=True
                                self.notify(active=True,engine='ai',delay=max(0,(self.samples_in-self.samples_out)/RATE)+.07)
            except Exception as error:fail(error)
        for name,work in (('neural-inference',infer),('neural-playback',play)):
            thread=threading.Thread(target=work,name=name,daemon=True);self.workers.append(thread);thread.start()
        buffer=bytearray()
        try:
            while not self.stop.is_set():
                if self.capture.poll() is not None or self.playback.poll() is not None:raise RuntimeError('Audio client exited')
                if not select.select([self.capture.stdout],[],[],.2)[0]:continue
                chunk=os.read(self.capture.stdout.fileno(),32768)
                if not chunk:raise RuntimeError('Audio capture ended')
                buffer.extend(chunk);size=len(buffer)//8*8
                if not size:continue
                pcm=np.frombuffer(bytes(buffer[:size]),dtype='<f4').reshape(-1,2)
                pcm=np.nan_to_num(pcm,nan=0,posinf=0,neginf=0);del buffer[:size]
                try:input_queue.put_nowait(pcm)
                except queue.Full:raise RuntimeError('ai-too-slow')
                self.samples_in+=len(pcm);self.heartbeat=time.monotonic()
                if self.samples_in-self.samples_consumed>RATE*3:raise RuntimeError('ai-too-slow')
        except Exception as error:fail(error)

    def close(self):
        self.stop.set()
        # Restore first, while the processed output is still alive.
        restored=False
        try:restore(self.state);restored=True
        except (OSError,ValueError,KeyError,TypeError,RuntimeError,subprocess.SubprocessError):pass
        for process in (self.capture,self.playback):
            if process:
                try:
                    process.terminate();process.wait(timeout=.5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=.5)
                except OSError:pass
        if self.thread:self.thread.join(timeout=.5)
        for thread in self.workers:thread.join(timeout=.5)
        if restored:self.path.unlink(missing_ok=True)


class KaraokeAudio:
    """GTK-side IPC only; no routing, subprocess waits or DSP on the UI thread."""
    def __init__(self,changed=lambda:None):
        self.changed=changed;self.process=None;self.active=False;self.starting=False
        self.error='';self.amount=.7;self.target=None;self.closed=False
        self.retiring=set();self.pending=None
        self.engine='ai';self.delay=0.;self.phase='';self.setup_process=None;self.setup_stage='';self.setup_fraction=0.
        self.muted=False
        self.pulse_available=bool(shutil.which('pacat') and shutil.which('pactl'))
        self.model_ready=karaoke_model.ready()
        self.available=self.pulse_available and self.model_ready
        # Cleanup after a previous helper was forcibly killed.
        if self.pulse_available:threading.Thread(target=self._recover,daemon=True).start()

    def set_engine(self,engine):
        if engine not in ('ai','stereo') or engine==self.engine:return
        self.disable();self.engine=engine
        self.available=self.pulse_available and (engine=='stereo' or self.model_ready)
        self.changed()

    def prepare(self):
        if self.closed or self.setup_process:return
        self.error='';self.setup_stage='download';self.setup_fraction=0.
        try:
            self.setup_process=subprocess.Popen([sys.executable,'-B',str(Path(karaoke_model.__file__).resolve()),
                '--prepare','--watch-parent'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,text=True,bufsize=1)
        except OSError:
            self.error='ai-setup-failed';self.setup_stage='';self.changed();return
        process=self.setup_process
        threading.Thread(target=self._read_setup,args=(process,),daemon=True).start();self.changed()

    def _read_setup(self,process):
        from gi.repository import GLib
        for row in process.stdout:
            try:message=json.loads(row)
            except ValueError:continue
            GLib.idle_add(self._setup_status,process,message,priority=GLib.PRIORITY_DEFAULT)
        process.wait();process.stdout.close();process.stdin.close()
        GLib.idle_add(self._setup_done,process,priority=GLib.PRIORITY_DEFAULT)

    def _setup_status(self,process,message):
        if self.setup_process is process and not self.closed:
            self.setup_stage=str(message.get('stage') or '')
            self.setup_fraction=max(0,min(1,float(message.get('fraction') or 0)))
            self.changed()
        return False

    def _setup_done(self,process):
        if self.setup_process is process:
            self.setup_process=None;self.model_ready=process.returncode==0 and karaoke_model.ready();self.setup_stage=''
            self.available=self.pulse_available and (self.engine=='stereo' or self.model_ready)
            if not self.model_ready:self.error='ai-setup-failed'
            if not self.closed:self.changed()
        return False

    @staticmethod
    def _recover():
        try:recover()
        except Exception:pass

    def enable(self,target):
        if self.closed or self.process or not self.available:return
        if not target or not target.player:self.error='no-stream';self.changed();return
        if self.retiring:
            self.pending=target;self.target=target;self.starting=True;self.changed();return
        self.target=target;self.error='';self.starting=True
        try:
            python=str(karaoke_model.PYTHON) if self.engine=='ai' else sys.executable
            self.process=subprocess.Popen([python,'-B',str(Path(__file__).resolve()),
                '--worker',json.dumps(target.__dict__),str(self.amount),self.engine,str(int(self.muted))],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1)
        except OSError:
            self.error='audio-failed';self.starting=False;self.changed();return
        process=self.process
        threading.Thread(target=self._read,args=(process,),daemon=True).start()
        self.changed()

    def _read(self,process):
        from gi.repository import GLib
        message={}
        for row in process.stdout:
            try:message=json.loads(row)
            except ValueError:continue
            GLib.idle_add(self._status,process,message,priority=GLib.PRIORITY_DEFAULT)
        process.wait()
        process.stdout.close();process.stdin.close()
        GLib.idle_add(self._ended,process,priority=GLib.PRIORITY_DEFAULT)

    def _status(self,process,message):
        if self.process is process and not self.closed:
            self.active=bool(message.get('active'));self.starting=False
            self.phase=str(message.get('phase') or '')
            if self.phase:self.starting=True
            value=message.get('delay',self.delay)
            if isinstance(value,(int,float)) and math.isfinite(value):self.delay=max(0,min(8,float(value)))
            self.error=str(message.get('error') or '');self.changed()
        return False

    def _ended(self,process):
        self.retiring.discard(process)
        if self.process is process:
            self.process=None;self.active=self.starting=False
            if not self.error:self.error='ai-runtime-invalid' if self.engine=='ai' else 'audio-failed'
            if not self.closed:self.changed()
        if not self.retiring and self.pending and not self.closed:
            target=self.pending;self.pending=None;self.starting=False
            self.enable(target)
        return False

    def set_amount(self,amount):
        self.amount=max(0,min(1,float(amount)))
        if self.process:
            try:self.process.stdin.write(json.dumps({'amount':self.amount})+'\n');self.process.stdin.flush()
            except (OSError,ValueError):self.disable()

    def set_muted(self,muted):
        if self.muted==bool(muted):return
        self.muted=bool(muted)
        if self.process:
            try:self.process.stdin.write(json.dumps({'muted':self.muted})+'\n');self.process.stdin.flush()
            except (OSError,ValueError):self.disable()

    def disable(self):
        process=self.process;self.process=None;self.active=self.starting=False;self.error='';self.target=None;self.delay=0.;self.phase=''
        self.pending=None
        if process:
            self.retiring.add(process)
            # SIGTERM reaches the helper's finally even if its input pipe is busy.
            try:process.terminate()
            except OSError:pass
        if not self.closed:self.changed()

    def check_target(self,target):
        if (self.process or self.pending) and target!=self.target:self.disable()

    def close(self):
        self.closed=True;self.disable()
        if self.setup_process:
            try:self.setup_process.terminate()
            except OSError:pass


def worker(target,amount,engine='stereo',muted=False):
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
    def emit(**value):
        try:print(json.dumps(value),flush=True)
        except BrokenPipeError:stop.set()
    route=Route(target,amount,engine,emit,muted)
    def cancelled():
        stop.wait();route.stop.set()
    threading.Thread(target=cancelled,daemon=True).start()
    try:
        route.start()
        if engine=='stereo':emit(active=True,engine='stereo',delay=.1)
        pending=b'';last=0.
        while not stop.is_set():
            ready,_,_=select.select([sys.stdin],[],[],.15)
            if ready:
                chunk=os.read(sys.stdin.fileno(),4096)
                if not chunk:break
                pending+=chunk
                if len(pending)>8192:raise RuntimeError('invalid-control')
                while b'\n' in pending:
                    row,pending=pending.split(b'\n',1)
                    command=json.loads(row)
                    if 'amount' in command:
                        amount=float(command['amount'])
                        if not math.isfinite(amount):raise ValueError('Invalid amount')
                        route.set_amount(max(0,min(1,amount)))
                    if type(command.get('muted')) is bool:
                        route.muted=command['muted'];route.sync_return_mute()
            if time.monotonic()-last>.6:
                route.refresh();last=time.monotonic()
                if engine=='ai' and route.output_started:
                    emit(active=True,engine='ai',delay=max(0,(route.samples_in-route.samples_out)/RATE)+.07)
    except Exception as error:
        code=str(error)
        emit(active=False,error=code if code in ('no-stream','multiple-outputs','output-lost','route-changed','stereo-required',
            'ai-too-slow','ai-model-invalid','ai-invalid-output') else 'audio-failed')
    finally:route.close()


if __name__=='__main__' and len(sys.argv) in (4,5,6) and sys.argv[1]=='--worker':
    worker(Target(**json.loads(sys.argv[2])),float(sys.argv[3]),sys.argv[4] if len(sys.argv)>=5 else 'stereo',
           len(sys.argv)==6 and sys.argv[5]=='1')
