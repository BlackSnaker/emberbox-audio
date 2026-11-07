"""Cancellable, sequential waveform preparation. Only derived peaks are cached."""
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import json,os,select,shutil,subprocess,threading,time,uuid
import numpy as np
from gi.repository import GLib
from flow_peaks import PeakBins,validate
from youtube_search import yt_dlp_executable,js_runtime_args


class WaveformClient:
    def __init__(self,service,changed):
        self.service=service;self.changed=changed;self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='flow-peaks')
        self.generation=0;self.closed=False;self.stop=threading.Event();self.cache=OrderedDict()
        self.data=[None,None];self.states=['empty','empty'];self.errors=['',''];self.seconds=32;self.key=None

    def cancel(self):self.generation+=1;self.stop.set()

    def load(self,items,seconds=32,force=False):
        key=(self.service.host.source,tuple(v['uri'] for v in items),seconds)
        if not force and key==self.key and any(s in ('loading','ready') for s in self.states):return
        self.key=key
        self.cancel();self.seconds=seconds;self.stop=stop=threading.Event();generation=self.generation;source=self.service.host.source
        self.data=[None,None];self.errors=['',''];self.states=['loading','loading']
        self.changed()
        self.pool.submit(self.run,tuple(items),source,seconds,generation,stop)

    def update(self,generation,lane,data,state,error=''):
        if self.closed or generation!=self.generation:return False
        self.data[lane]=data;self.states[lane]=state;self.errors[lane]=error;self.changed();return False

    def run(self,items,source,seconds,generation,stop):
        for lane,item in enumerate(items[:2]):
            if stop.is_set() or self.closed:return
            key=(source,item['uri'],lane,seconds)
            data=self.cache.get(key)
            if data is None:
                try:
                    if source=='apple-music':data=self.apple(item,lane,seconds,stop)
                    elif source=='youtube':data=self.youtube(item,lane,seconds,stop)
                    else:raise ValueError('unsupported')
                    data=validate(data)
                    if stop.is_set():return
                    self.cache[key]=data;self.cache.move_to_end(key)
                    while len(self.cache)>8:self.cache.popitem(last=False)
                except Exception as error:
                    if stop.is_set():return
                    code=str(error)
                    if code not in ('unsupported','cancelled','timeout','SPATIAL_BUSY','SPATIAL_SETUP_REQUIRED'):code='unavailable'
                    GLib.idle_add(self.update,generation,lane,None,'error',code);continue
            GLib.idle_add(self.update,generation,lane,data,'partial' if data['covered']<data['seconds']-.2 else 'ready')

    def apple(self,item,lane,seconds,stop):
        player=self.service.host.apple_web
        if getattr(player,'state',{}).get('emberFlowPeaks') is not True:raise ValueError('unsupported')
        key=uuid.uuid4().hex
        try:
            parts=item['uri'].split(':',2)
            player.request('flow',operation='waveform-start',key=key,kind=parts[1],id=parts[2],role='out' if lane==0 else 'in',seconds=seconds)
            until=time.monotonic()+65
            while not stop.wait(.45) and time.monotonic()<until:
                result=player.request('flow',operation='waveform-status',key=key)
                if result.get('phase')=='ready':return result['waveform']
                if result.get('phase')=='error':raise ValueError(result.get('error') or 'unavailable')
                if result.get('phase')=='cancelled':raise ValueError('cancelled')
            raise ValueError('timeout')
        finally:
            try:player.request('flow',operation='waveform-cancel',key=key)
            except Exception:pass

    def youtube(self,item,lane,seconds,stop):
        duration=float(item.get('duration_ms') or 0)/1000
        if duration<=0:raise ValueError('unsupported')
        start=max(0,duration-seconds) if lane==0 else 0;seconds=min(seconds,duration)
        process=None;decoder=None
        try:
            import re
            if not re.fullmatch('[A-Za-z0-9_-]{11}',item['id']):raise ValueError('unsupported')
            url='https://www.youtube.com/watch?v='+item['id']
            command=[yt_dlp_executable(),*js_runtime_args(),'--no-playlist','--no-warnings','--socket-timeout','8','--retries','0','-f','bestaudio','--get-url',url]
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            try:os.setpriority(os.PRIO_PROCESS,process.pid,15)
            except OSError:pass
            until=time.monotonic()+24;raw=None
            while not stop.is_set() and time.monotonic()<until:
                try:raw=process.communicate(timeout=.15)[0];break
                except subprocess.TimeoutExpired:continue
            if raw is None or process.returncode or len(raw)>65536:raise ValueError('timeout')
            stream=raw.decode().strip().splitlines()[0]
            from urllib.parse import urlsplit
            parsed=urlsplit(stream)
            if parsed.scheme!='https' or parsed.username or parsed.password:raise ValueError('unavailable')
            ffmpeg=shutil.which('ffmpeg')
            if not ffmpeg:raise ValueError('unsupported')
            decoder=subprocess.Popen([ffmpeg,'-nostdin','-v','error','-threads','1','-filter_threads','1','-rw_timeout','6000000',
                '-ss',str(start),'-i',stream,'-t',str(seconds),'-vn','-ac','2','-ar','48000','-f','f32le','pipe:1'],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
            try:os.setpriority(os.PRIO_PROCESS,decoder.pid,15)
            except OSError:pass
            peaks=PeakBins(48000,seconds,start);pending=bytearray();until=time.monotonic()+35
            while not stop.is_set() and time.monotonic()<until and not peaks.done:
                if not select.select([decoder.stdout],[],[],.15)[0]:continue
                block=os.read(decoder.stdout.fileno(),32768)
                if not block:break
                pending.extend(block);n=len(pending)//8*8
                if n:peaks.add(np.frombuffer(bytes(pending[:n]),dtype='<f4').reshape(-1,2));del pending[:n]
            if not peaks.frames:raise ValueError('unavailable')
            return peaks.result()
        finally:
            for child in (decoder,process):
                if child:
                    if child.poll() is None:child.kill()
                    try:child.wait(timeout=1)
                    except subprocess.TimeoutExpired:pass
                    if child.stdout:child.stdout.close()

    def close(self):
        self.closed=True;self.cancel();self.cache.clear();self.pool.shutdown(wait=False,cancel_futures=True)
