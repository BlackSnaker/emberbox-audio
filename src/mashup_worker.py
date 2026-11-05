#!/usr/bin/env python3
"""Isolated preparation/player. Audio exists only in process memory/memfds."""
import ctypes
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','2')
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
libc=ctypes.CDLL(None)
libc.prctl(4,0,0,0,0);libc.prctl(1,15,0,0,0)
try:os.nice(10)
except OSError:pass
import numpy as np
from mashup_catalog import Catalog
from mashup_projects import recipe
from mashup_dsp import RATE,decode,analyse,plan,separate,transform,render,waveform


class IPC:
    def __init__(self,path):
        self.socket=socket.socket(socket.AF_UNIX);self.socket.settimeout(.5);self.socket.connect(str(path))
        self.buffer=b'';self.serial=0;self.lock=threading.Lock()
    def call(self,*command):
        with self.lock:
            self.serial+=1;ident=self.serial
            self.socket.sendall((json.dumps({'command':list(command),'request_id':ident})+'\n').encode())
            until=time.monotonic()+1
            while time.monotonic()<until:
                while b'\n' in self.buffer:
                    line,self.buffer=self.buffer.split(b'\n',1);value=json.loads(line)
                    if value.get('request_id')==ident:return value.get('data')
                self.buffer+=self.socket.recv(65536)
                if len(self.buffer)>262144:raise ValueError('player-invalid-reply')
            raise TimeoutError('player-timeout')
    def close(self):self.socket.close()


def main():
    stopping=threading.Event();player=None;ipc=None;audio=None
    signal.signal(signal.SIGTERM,lambda *_:stopping.set());signal.signal(signal.SIGINT,lambda *_:stopping.set())
    lock=threading.Lock();last=[0.]
    def emit(value):
        with lock:print(json.dumps(value,ensure_ascii=False),flush=True)
    def progress(stage,fraction=None,force=False):
        now=time.monotonic()
        if force or now-last[0]>.15:
            last[0]=now;emit({'type':'progress','stage':stage,'fraction':fraction})
    try:
        raw=sys.stdin.buffer.readline(65537)
        if not raw or len(raw)>65536:raise ValueError('project-invalid')
        project=recipe(json.loads(raw))
        if len(project['tracks'])!=2:raise ValueError('two-tracks-required')
        catalog=Catalog();tracks=[];data=[];observations=[]
        for index,item in enumerate(project['tracks']):
            if stopping.is_set():raise InterruptedError('cancelled')
            progress(f'source-{index}',force=True)
            source=catalog.resolve(item);tracks.append(source)
            progress(f'load-{index}',0.,True)
            if item['start']>=source['duration']:raise ValueError('fragment-outside-track')
            pcm=decode(source,stopping,lambda value:progress(f'load-{index}',value),
                start=item['start'],duration=None if project['whole'] else project['length'])
            if len(pcm)<RATE:raise ValueError('fragment-too-short')
            progress(f'analyse-{index}',force=True);observations.append(analyse(pcm,source['bpm']))
            if item['role']!='song' and item['role']!=source['kind']:
                import karaoke_model
                if not karaoke_model.ready():raise ValueError('ai-missing')
                progress(f'separate-{index}',0.,True)
                pcm=separate(pcm,item['role'],source['kind'],stopping,lambda value:progress(f'separate-{index}',value))
            data.append(pcm)
            del pcm
        proposal=plan(*observations,project)
        for index in (0,1):
            progress(f'align-{index}',force=True)
            data[index]=transform(data[index],proposal['rates'][index],proposal['shift'] if index else 0,stopping)
        progress('mix',force=True);mixed,attenuation=render(*data,project,proposal)
        duration=len(mixed)/RATE
        audio=os.memfd_create('ember-mashup-output',os.MFD_CLOEXEC)
        view=memoryview(mixed).cast('B')
        while view:
            if stopping.is_set():raise InterruptedError('cancelled')
            written=os.write(audio,view[:262144]);view=view[written:]
        view.release();del view
        waves=[waveform(v) for v in data]
        del mixed,data
        os.lseek(audio,0,0)
        executable=shutil.which('mpv')
        if not executable:raise ValueError('mpv-missing')
        runtime=os.environ.get('XDG_RUNTIME_DIR')
        with tempfile.TemporaryDirectory(prefix='ember-mashup-',dir=runtime if runtime and Path(runtime).is_dir() else None) as folder:
            path=Path(folder)/'player.sock'
            # The small exec wrapper makes the kernel terminate mpv even if
            # its worker dies before ordinary cleanup can run.
            wrapper="import ctypes,os,sys;ctypes.CDLL(None).prctl(1,15,0,0,0);os.getppid()==1 and sys.exit(1);os.execv(sys.argv[1],sys.argv[1:])"
            player=subprocess.Popen([sys.executable,'-c',wrapper,executable,'--no-config','--terminal=no',
                '--no-video','--idle=yes','--keep-open=yes','--pause=yes','--audio-client-name=Ember Mashups',
                '--volume=100','--volume-max=100','--demuxer=rawaudio','--demuxer-rawaudio-format=floatle',
                '--demuxer-rawaudio-rate=48000','--demuxer-rawaudio-channels=stereo',
                '--input-ipc-server='+str(path),'fd://'+str(audio)],
                pass_fds=(audio,),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            until=time.monotonic()+5
            while not path.exists():
                if stopping.wait(.03) or player.poll() is not None or time.monotonic()>until:raise ValueError('player-start-failed')
            ipc=IPC(path)
            until=time.monotonic()+5
            while ipc.call('get_property','duration') is None:
                if stopping.wait(.03) or time.monotonic()>until:raise ValueError('player-start-failed')
            emit({'type':'ready','duration':duration,'plan':proposal,'waves':waves,'attenuation':attenuation,
                'tracks':[{k:v for k,v in item.items() if k!='url'} for item in tracks]})
            def controls():
                try:
                    while not stopping.is_set():
                        raw=sys.stdin.buffer.readline(4097)
                        if not raw or len(raw)>4096:break
                        value=json.loads(raw);action=value.get('action')
                        if action=='stop':break
                        elif action=='pause':ipc.call('set_property','pause',value.get('paused') is True)
                        elif action in ('seek','volume'):
                            number=float(value['value'])
                            if not np.isfinite(number):continue
                            if action=='seek':ipc.call('seek',max(0,min(duration-.01,number)),'absolute+exact')
                            else:ipc.call('set_property','volume',max(0,min(1,number))**(1/3)*100)
                        elif action=='mute':ipc.call('set_property','mute',value.get('muted') is True)
                except (OSError,ValueError,TypeError,KeyError):pass
                finally:stopping.set()
            threading.Thread(target=controls,daemon=True,name='mashup-controls').start()
            while not stopping.wait(.15) and player.poll() is None:
                if os.getppid()==1:break
                position=ipc.call('get_property','time-pos') or 0
                paused=ipc.call('get_property','pause') is True
                eof=ipc.call('get_property','eof-reached') is True
                emit({'type':'position','position':position,'paused':paused,'ended':eof})
    except InterruptedError:pass
    except Exception as exc:
        if os.environ.get('EMBERBOX_MASHUP_DEBUG')=='1':
            import traceback
            traceback.print_exc(file=sys.stderr)
        # Only stable codes cross the boundary. Network URLs, audio data and
        # private runtime paths are never dumped into GUI errors or journals.
        code=str(exc)
        allowed={'source-not-editable','track-unavailable','two-tracks-required','ai-missing','tempo-too-far',
            'rubberband-missing','ffmpeg-missing','mpv-missing','fragment-outside-track','fragment-too-short',
            'audio-duration-limit','media-too-large','media-incomplete','audio-decoder-failed','player-start-failed'}
        emit({'type':'error','error':code if code in allowed else 'preparation-failed','kind':type(exc).__name__})
    finally:
        stopping.set()
        if ipc:ipc.close()
        if player and player.poll() is None:
            player.terminate()
            try:player.wait(timeout=1)
            except subprocess.TimeoutExpired:player.kill();player.wait()
        if audio is not None:os.close(audio)


if __name__=='__main__':main()
