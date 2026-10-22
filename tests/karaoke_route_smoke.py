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
        json.dumps(target.__dict__),'1.0'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    ready,_,_=select.select([process.stdout],[],[],6)
    assert ready,'Worker failed to report readiness'
    status=json.loads(process.stdout.readline())
    assert status.get('active'),status
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
    assert wet[1000]/dry[1000]<.15,(dry,wet)
    for freq in (70,3000):assert .8<wet[freq]/dry[freq]<1.2,(dry,wet)
    helper.stdin.close();restored(helper);helper=None
    # SIGTERM is the GUI's normal nonblocking exit path.
    helper=start();helper.terminate();restored(helper);helper=None
    # A forcibly killed helper is recovered on the next Emberbox startup.
    helper=start();helper.kill();helper.wait(timeout=3);recover();restored(helper);helper=None
    print('PASS real null-sink routing, centre suppression, side/bass preservation, EOF, SIGTERM and forced-kill recovery')
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
