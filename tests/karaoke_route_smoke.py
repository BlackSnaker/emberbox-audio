"""Opt-in integration using generated PCM and private, inaudible null sinks.

Run with EMBERBOX_AUDIO_ROUTE_TEST=1 on a PipeWire/PulseAudio session. Never
moves a real application's audio, opens a microphone or changes default output.
"""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time
from collections import deque
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from karaoke_audio import RATE,PREFIX,pactl,recover
from stream_target import Target

if os.environ.get('EMBERBOX_AUDIO_ROUTE_TEST')!='1':
    raise SystemExit('Set EMBERBOX_AUDIO_ROUTE_TEST=1 to run the isolated audio test.')

name=f'emberbox_fixture_{os.getuid()}_{os.getpid()}'
default=pactl('get-default-sink')
module=None;producer=None;monitor=None;helper=None;stopped=threading.Event();recorded=bytearray()
lock=threading.Lock()
captured_bytes=0
NEURAL='--ai' in sys.argv
worker_messages={}


def feed():
    samples=np.arange(4800)/RATE
    centre=.14*np.sin(2*np.pi*1000*samples)
    side=.09*np.sin(2*np.pi*3000*samples)
    bass=.1*np.sin(2*np.pi*70*samples)
    pcm=np.column_stack((centre+bass+side,centre+bass-side)).astype('<f4').tobytes()
    try:
        while not stopped.is_set():producer.stdin.write(pcm);producer.stdin.flush()
    except (OSError,ValueError):pass


def read():
    global captured_bytes
    while not stopped.is_set():
        try:
            ready,_,_=select.select([monitor.stdout],[],[],.2)
            if not ready:continue
            data=os.read(monitor.stdout.fileno(),32768)
            if not data:break
            with lock:
                recorded.extend(data)
                captured_bytes+=len(data)
                if len(recorded)>RATE*8*3:del recorded[:-RATE*8*3]
        except (OSError,ValueError):break


def spectrum():
    with lock:pcm=np.frombuffer(bytes(recorded[-RATE*8:]),dtype='<f4').reshape(-1,2)
    t=np.arange(len(pcm))/RATE
    return {freq:abs(np.sum(pcm[:,0]*np.exp(-2j*np.pi*freq*t)))*2/len(pcm) for freq in (70,1000,3000)}


def start():
    target=Target('youtube',producer.pid,'','original-fixture')
    process=subprocess.Popen([sys.executable,'-B',str(ROOT/'src/karaoke_audio.py'),'--worker',
        json.dumps(target.__dict__),'0.0' if NEURAL else '1.0','ai' if NEURAL else 'stereo'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    ready=threading.Event();messages=worker_messages[process.pid]=deque(maxlen=64)
    def status_reader():
        for row in process.stdout:
            message=json.loads(row);messages.append(message)
            if message.get('active') or message.get('error'):ready.set()
    threading.Thread(target=status_reader,daemon=True).start()
    assert ready.wait(20),'Worker failed to report readiness'
    assert messages[-1].get('active'),list(messages)
    return process


def restored(process):
    process.wait(timeout=5)
    time.sleep(.15)
    streams=pactl('list','sink-inputs',json_output=True)
    source=next(s for s in streams if s.get('properties',{}).get('application.process.id')==str(producer.pid))
    sinks=pactl('list','sinks',json_output=True)
    output=next(s for s in sinks if s['name']==name)
    assert str(source['sink'])==str(output['index']),'Source was not restored'
    assert not any(s['name']==PREFIX+str(process.pid) for s in sinks),'Temporary sink leaked'
    assert pactl('get-default-sink')==default,'Default output must remain unchanged'


try:
    module=pactl('load-module','module-null-sink','sink_name='+name,'rate=48000','channels=2')
    common=['--raw','--format=float32le','--rate=48000','--channels=2','--latency-msec=35']
    producer=subprocess.Popen(['pacat','--playback','--device='+name,'--client-name=Emberbox Test',*common],
        stdin=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
    monitor=subprocess.Popen(['pacat','--record','--device='+name+'.monitor',*common],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
    threading.Thread(target=feed,daemon=True).start();threading.Thread(target=read,daemon=True).start()
    time.sleep(1.4);dry=spectrum()
    assert dry[1000]>.08,dry
    helper=start()
    with lock:boundary=captured_bytes
    deadline=time.monotonic()+6
    # Follow captured sample progress, not a sleep: the server can re-clock a
    # monitor during stream movement. Never analyse an unchanged dry ring.
    while time.monotonic()<deadline:
        with lock:fresh=captured_bytes-boundary
        if fresh>=RATE*8*2:break
        if helper.poll() is not None:raise AssertionError('Filter worker exited during processing')
        time.sleep(.05)
    assert fresh>=RATE*8*2,'Output monitor did not deliver fresh processed PCM'
    wet=spectrum()
    if NEURAL:
        # AI at zero strength still performs inference, then mixes the exact
        # delayed dry block. Verify streaming continuity independently of what
        # a learned separator thinks of synthetic tones.
        for freq in (70,1000,3000):assert .94<wet[freq]/dry[freq]<1.06,(dry,wet)
        delays=[m['delay'] for m in worker_messages[helper.pid] if m.get('active') and 'delay' in m]
        assert delays and all(.3<d<5 for d in delays),delays
        assert max(delays)-min(delays)<.8,delays
        print('AI buffered playback delay:',round(sum(delays)/len(delays),2),'s',flush=True)
    else:assert wet[1000]/dry[1000]<.15,(dry,wet)
    for freq in (70,3000):assert .8<wet[freq]/dry[freq]<1.2,(dry,wet)
    for muted in (True,False):
        helper.stdin.write(json.dumps({'muted':muted})+'\n');helper.stdin.flush()
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            streams=pactl('list','sink-inputs',json_output=True)
            returns=[s for s in streams if s.get('properties',{}).get('emberbox.karaoke')=='true']
            if returns and all(bool(s.get('mute'))==muted for s in returns):break
            time.sleep(.05)
        assert returns and all(bool(s.get('mute'))==muted for s in returns),'Return mute did not follow control'
        assert not next(s for s in streams if s.get('properties',{}).get('application.process.id')==str(producer.pid))['mute']
    helper.stdin.close();restored(helper);helper=None
    # SIGTERM is the GUI's normal nonblocking exit path.
    helper=start();helper.terminate();restored(helper);helper=None
    # A forcibly killed helper is recovered on the next Emberbox startup.
    helper=start();helper.kill();helper.wait(timeout=3);recover();restored(helper);helper=None
    print('PASS real null-sink routing, '+('neural streaming' if NEURAL else 'centre suppression')+', side/bass preservation, EOF, SIGTERM and forced-kill recovery')
    print('Synthetic amplitudes:',json.dumps({'dry':dry,'filtered':wet}))
finally:
    stopped.set()
    if helper and helper.poll() is None:
        helper.terminate()
        try:helper.wait(timeout=5)
        except subprocess.TimeoutExpired:helper.kill();helper.wait(timeout=2);recover()
    for process in (producer,monitor):
        if process:
            process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
    if module:pactl('unload-module',module)
