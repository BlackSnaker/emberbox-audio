"""Push-to-talk, cancellable neural replies and temporary music attenuation."""
import json,os,signal,subprocess,sys,threading,time
from pathlib import Path
from gi.repository import GLib
from dj_setup import ROOT,ready


class DJVoice:
    def __init__(self,host,event,transcript):
        self.host,self.event,self.transcript=host,event,transcript
        self.process=None;self.generation=0;self.mode='';self.phase='';self.source=''
        self.closed=False;self.level=0.;self.monitor=0

    def emit(self,event,**data):
        self.phase=event;self.event(event,data)

    def duck(self,value):
        method=getattr(self.host.sound,'set_ducking',None)
        if method:method(value)

    def launch(self,mode,language,text=''):
        self.cancel()
        if self.closed or not ready('voice',language):return False
        if mode=='speak' and self.host.sound.muted:return False
        self.generation+=1;generation=self.generation;self.mode=mode;self.source=self.host.source;self.started=time.monotonic()
        python=json.loads((ROOT/('voice-'+language+'.json')).read_text())['python']
        self.emit('preparing-voice' if mode=='listen' else 'preparing-reply')
        command=[python,'-I',str(Path(__file__).with_name('dj_voice_worker.py')),mode,'--root',str(ROOT),'--language',language]
        try:
            self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                text=True,bufsize=1,start_new_session=True)
        except OSError:self.mode='';self.emit('voice-error',message='voice-start-failed');return False
        process=self.process
        if mode=='speak':process.stdin.write(json.dumps({'text':text},ensure_ascii=False)+'\n');process.stdin.flush()
        self.monitor=GLib.timeout_add(100,self.check_source)
        threading.Thread(target=self.read,args=(process,generation),daemon=True,name='ember-dj-voice').start()
        return True

    def read(self,process,generation):
        try:
            for line in process.stdout:
                if len(line)>8000:continue
                try:data=json.loads(line)
                except ValueError:continue
                GLib.idle_add(self.receive,generation,data,priority=GLib.PRIORITY_DEFAULT)
        finally:
            process.wait()
            GLib.idle_add(self.ended,generation,process.returncode,priority=GLib.PRIORITY_DEFAULT)

    def receive(self,generation,data):
        if self.closed or generation!=self.generation or self.source!=self.host.source:return False
        event=data.get('event')
        if event in ('listening','speaking'):
            if event=='speaking' and self.host.sound.muted:self.cancel();return False
            self.duck(.12 if event=='listening' else .28)
        if event=='level':self.level=max(0,min(1,float(data.get('value') or 0)));self.event('level',{'value':self.level});return False
        if event=='partial':self.event(event,{'text':str(data.get('text',''))[:500]});return False
        if event=='result':
            value=str(data.get('text','')).strip()[:500];self.duck(1.)
            if value:self.transcript(value)
            else:self.emit('voice-error',message='no-speech')
        elif event=='error':self.emit('voice-error',message=str(data.get('message',''))[:150])
        else:self.emit(event)
        return False

    def ended(self,generation,code):
        if generation!=self.generation:return False
        self.process=None;self.mode='';self.level=0.;self.duck(1.)
        if self.monitor:GLib.source_remove(self.monitor);self.monitor=0
        if not self.closed:self.event('voice-idle',{})
        return False

    def stop_listening(self):
        if self.mode=='listen' and self.process:
            try:self.process.stdin.write('stop\n');self.process.stdin.flush()
            except (OSError,ValueError):self.cancel()

    def check_source(self):
        if self.closed or not self.process:self.monitor=0;return False
        if time.monotonic()-self.started>60:
            self.monitor=0;self.cancel();self.emit('voice-error',message='voice-timeout');return False
        if self.source!=self.host.source or self.mode=='speak' and self.host.sound.muted:
            self.monitor=0;self.cancel();return False
        if self.phase in ('listening','speaking'):self.duck(.12 if self.phase=='listening' else .28)
        return True

    def cancel(self):
        self.generation+=1;process,self.process=self.process,None
        self.mode=self.phase='';self.level=0.;self.duck(1.)
        if self.monitor:GLib.source_remove(self.monitor);self.monitor=0
        if process and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            def reap():
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait(timeout=1)
            threading.Thread(target=reap,daemon=True,name='ember-dj-voice-cleanup').start()

    def close(self):self.closed=True;self.cancel()
