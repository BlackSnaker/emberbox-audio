"""Nonblocking GTK-side mashup control; one cancellable worker per project."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from gi.repository import GLib
import karaoke_model
from mashup_projects import recipe


class MashupClient:
    def __init__(self,changed):
        self.changed=changed;self.process=None;self.generation=0;self.closed=False
        self.state='idle';self.stage='';self.fraction=None;self.error=''
        self.ready={};self.position=0.;self.paused=True;self.ended=False;self.volume=.8;self.muted=False

    @property
    def playing(self):return self.state=='ready' and not self.paused and not self.ended

    def prepare(self,project):
        self.stop();self.state='preparing';self.error='';self.stage='source-0';self.fraction=None
        self.generation+=1;generation=self.generation
        interpreter=str(karaoke_model.PYTHON) if karaoke_model.ready() else sys.executable
        try:
            env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
            self.process=subprocess.Popen([interpreter,'-B',str(Path(__file__).with_name('mashup_worker.py'))],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,
                bufsize=1,start_new_session=True,env=env)
            self.process.stdin.write(json.dumps(recipe(project),ensure_ascii=False)+'\n');self.process.stdin.flush()
            threading.Thread(target=self.read,args=(self.process,generation),daemon=True,name='mashup-events').start()
        except (OSError,ValueError):self.state='error';self.error='preparation-failed'
        self.changed()

    def read(self,process,generation):
        try:
            for raw in iter(lambda:process.stdout.readline(100001),''):
                if len(raw)>100000:break
                try:value=json.loads(raw)
                except ValueError:break
                GLib.idle_add(self.deliver,generation,value)
        except (OSError,ValueError):pass
        finally:
            process.wait();process.stdout.close()
            GLib.idle_add(self.exited,generation)

    def deliver(self,generation,value):
        if self.closed or generation!=self.generation:return False
        kind=value.get('type')
        if kind=='progress':self.stage=value['stage'];self.fraction=value.get('fraction')
        elif kind=='ready':self.state='ready';self.ready=value;self.paused=True
        elif kind=='position':
            self.position=float(value['position']);self.paused=value['paused'];self.ended=value['ended']
        elif kind=='error':self.state='error';self.error=str(value.get('error','preparation-failed'))
        self.changed();return False

    def exited(self,generation):
        if not self.closed and generation==self.generation and self.state not in ('idle','error'):
            self.state='error';self.error='preparation-failed';self.changed()
        return False

    def send(self,action,**params):
        process=self.process
        if not process or process.poll() is not None:return
        try:process.stdin.write(json.dumps({'action':action,**params})+'\n');process.stdin.flush()
        except (OSError,ValueError):pass

    def play(self):
        if self.state!='ready':return
        if self.ended:self.send('seek',value=0);self.ended=False
        self.paused=False;self.send('pause',paused=False);self.changed()

    def toggle(self):
        if self.state!='ready':return
        if self.paused or self.ended:self.play()
        else:self.paused=True;self.send('pause',paused=True);self.changed()

    def seek(self,value):
        if self.state=='ready':self.send('seek',value=value)

    def set_volume(self,value):
        self.volume=max(0,min(1,float(value)));self.send('volume',value=self.volume);self.changed()

    def toggle_mute(self):
        self.muted=not self.muted;self.send('mute',muted=self.muted);self.changed()

    def stop(self):
        self.generation+=1;process=self.process;self.process=None
        self.state='idle';self.ready={};self.position=0.;self.paused=True;self.ended=False
        self.error='';self.stage='';self.fraction=None
        if process:
            def reap():
                try:
                    if process.stdin:process.stdin.close()
                    process.wait(timeout=.8)
                except (OSError,ValueError,subprocess.TimeoutExpired):
                    try:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=1)
                    except (OSError,subprocess.TimeoutExpired):
                        try:os.killpg(process.pid,signal.SIGKILL)
                        except OSError:pass
            threading.Thread(target=reap,daemon=True,name='mashup-stop').start()

    def close(self):self.closed=True;self.stop()
