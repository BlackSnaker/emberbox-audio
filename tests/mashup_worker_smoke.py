"""Real mpv, anonymous PCM and controls; original tones and null audio only."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
script='''
import sys,socket
sys.path.insert(0,sys.argv[1])
import mashup_worker as worker
from mashup_dsp import RATE
import numpy as np
t=np.arange(RATE*6)/RATE
pcm=np.column_stack((.15*np.sin(2*np.pi*220*t),.15*np.sin(2*np.pi*330*t))).astype('float32')
def resolve(self,item):
 return {**item,'kind':item['role'],'bpm':120,'duration':6,'license':'https://creativecommons.org/licenses/by/4.0/'}
if sys.argv[2]!='live':
 worker.Catalog.resolve=resolve
 worker.decode=lambda *_a,**_kw:pcm
real=worker.subprocess.Popen
def silent(command,*args,**kwargs):
 if '--audio-client-name=Ember Mashups' in command:command.insert(-1,'--ao=null')
 return real(command,*args,**kwargs)
worker.subprocess.Popen=silent
worker.main()
'''
project={'name':'Original null-output tones','tracks':[{'source':'ccmixter','id':str(i),'role':role}
    for i,role in [(1,'vocal'),(2,'instrumental')]],'length':5,'auto':False}
live='--live-catalogue' in sys.argv
if live:
 sys.path.insert(0,str(ROOT/'src'))
 from mashup_catalog import Catalog
 catalogue=Catalog();voices=catalogue.search('', 'vocal');bases=catalogue.search('', 'instrumental')
 pairs=[(abs(a['bpm']/b['bpm']-1),a,b) for a in voices for b in bases if a['bpm'] and b['bpm'] and .8<=a['bpm']/b['bpm']<=1.25]
 assert pairs,'No compatible CC BY pair in the current small catalogue page'
 _,voice,base=min(pairs,key=lambda v:v[0])
 project['tracks']=[{**item,'role':role} for item,role in [(voice,'vocal'),(base,'instrumental')]]
 project['auto']=True
 print('Live licensed stream IDs:',voice['id'],base['id'],flush=True)
child=subprocess.Popen([sys.executable,'-u','-c',script,str(ROOT/'src'),'live' if live else 'fixture'],stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=False,start_new_session=True,
    env={**os.environ,'EMBERBOX_MASHUP_DEBUG':'1'})
pending=bytearray();events=[]
def send(value):child.stdin.write((json.dumps(value)+'\n').encode());child.stdin.flush()
def wait(predicate,limit=8):
    end=time.monotonic()+limit
    while time.monotonic()<end:
        if select.select([child.stdout],[],[],.1)[0]:
            part=os.read(child.stdout.fileno(),65536)
            if not part:break
            pending.extend(part)
            while b'\n' in pending:
                line,_,tail=pending.partition(b'\n');pending[:]=tail
                value=json.loads(line);events.append(value)
                if value.get('type')=='error':
                    child.wait(timeout=3);raise AssertionError((value,child.stderr.read().decode()))
                if predicate(value):return value
        if child.poll() is not None:break
    raise AssertionError(('Worker event missing',events[-5:],child.stderr.read().decode() if child.poll() is not None else 'running'))
try:
    send(project);ready=wait(lambda value:value['type']=='ready',90 if live else 8)
    assert ready['duration']==5 and len(ready['waves'])==2
    send({'action':'pause','paused':False})
    wait(lambda value:value.get('position',0)>.3)
    send({'action':'pause','paused':True});paused=wait(lambda value:value.get('paused') is True)
    send({'action':'seek','value':2.5})
    seek=wait(lambda value:value.get('position',0)>2)
    assert abs(seek['position']-2.5)<.2
    send({'action':'pause','paused':False});wait(lambda value:value.get('position',0)>3)
    send({'action':'stop'});child.wait(timeout=3);assert child.returncode==0
    print('PASS real null-output mashup worker, anonymous audio, pause, seek and cleanup')
finally:
    if child.poll() is None:
        import signal
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=2)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    child.stdin.close();child.stdout.close();child.stderr.close()
