"""Actual mpv pre-listen, beat timing and pitch check on isolated generated audio."""
import json,math,os,select,subprocess,sys,tempfile,threading,time,wave
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gi.repository import GLib
from youtube_audio import YouTubeAudio
from flow_youtube import YouTubeDecks
from flow_beats import EnergyTap,detect


def settle(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.003)

def pactl(*args):return json.loads(subprocess.check_output(['pactl','-f','json',*args],text=True))
class Capture:
    def __init__(self,sink,stream=None):
        args=['pacat','--record','--raw','--format=float32le','--rate=48000','--channels=2','--latency-msec=20',
              '--process-time-msec=10','--device='+sink+'.monitor']
        if stream is not None:args.append('--monitor-stream='+str(stream))
        self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);self.stop=threading.Event();self.tap=EnergyTap();self.raw=[]
        def read():
            data=bytearray()
            while not self.stop.is_set():
                ready,_,_=select.select([self.process.stdout],[],[],.1)
                if not ready:continue
                block=os.read(self.process.stdout.fileno(),32768)
                if not block:break
                data.extend(block);n=len(data)//8*8
                if n:
                    pcm=np.frombuffer(bytes(data[:n]),dtype='<f4').reshape(-1,2);del data[:n]
                    self.raw.append(pcm);self.tap.feed(pcm,time.monotonic()-.025)
        self.thread=threading.Thread(target=read,daemon=True);self.thread.start()
    def close(self):
        self.stop.set();self.thread.join(.3);self.process.terminate();self.process.wait(timeout=1)


def run():
    sink='emberbox_beat_audio_check_'+str(os.getpid());module=None;capture=inc=None
    old=YouTubeAudio(lambda:None,persistent=False);new=YouTubeAudio(lambda:None,persistent=False)
    host=SimpleNamespace(youtube=old,on_youtube_changed=lambda:None,meter=SimpleNamespace(rhythm_key='fixture',beat_grid=None))
    decks=YouTubeDecks(host)
    try:
        module=subprocess.check_output(['pactl','load-module','module-null-sink','sink_name='+sink,'rate=48000','channels=2'],text=True).strip()
        index=next(x['index'] for x in pactl('list','sinks') if x['name']==sink)
        with tempfile.TemporaryDirectory(prefix='emberbeat-waves-') as folder:
            for deck,bpm,phase,carrier in ((old,120,.137,95),(new,124,.32,210)):
                t=np.arange(48000*28)/48000;envelope=np.exp(-((t-phase)%(60/bpm))/.035)
                signal=.55*np.sin(t*carrier*2*np.pi)*envelope+.025*np.sin(t*880*2*np.pi)
                pcm=(signal*32767).astype('<i2');file=Path(folder)/(str(bpm)+'.wav')
                with wave.open(str(file),'wb') as out:
                    out.setparams((2,2,48000,0,'NONE','not compressed'));out.writeframes(np.column_stack((pcm,pcm)).tobytes())
                assert deck._ensure_player(),deck.error
                deck.mpv['audio-client-name']='EmberBeatFixture-'+str(bpm)
                deck.mpv['audio-device']='pulse/'+sink;deck.current={'id':str(bpm),'title':'Generated beat'}
                deck.enabled=deck is old;deck.paused=deck is new
                deck.mpv.command_async('loadfile',str(file),'replace',-1,'pause='+('no' if deck is old else 'yes'))
            until=time.monotonic()+4
            while not(old.loaded and new.loaded) and time.monotonic()<until:settle(.02)
            assert old.loaded and new.loaded
            capture=Capture(sink);settle(6.5);host.meter.beat_grid=capture.tap.result()
            decks.standby=new;until=time.monotonic()+12
            while not decks.ready and time.monotonic()<until:
                settle(.05)
            assert decks.ready,{'message':'Intro was not decoded','error':decks.preview.error,
                'done':decks.preview.future.done(),'position':new.mpv.time_pos,'seeking':new.mpv.seeking}
            host.meter.beat_grid=capture.tap.result();assert host.meter.beat_grid,'Outgoing generated beat was not detected'
            print('prelisten',decks.preview.future.result(),'outgoing',host.meter.beat_grid,flush=True)
            settle(.5)  # The real deck is primed at its matched tempo, paused.
            assert decks.transition(8);assert decks.beat_plan,'Related measured tempos were not matched'
            settle(.8)
            ids={x['index'] for x in pactl('list','sink-inputs') if x['sink']==index and x.get('properties',{}).get('application.name')=='EmberBeatFixture-124'}
            assert len(ids)==1,ids
            inc=Capture(sink,ids.pop());settle(4.1)
            grid=inc.tap.result();assert grid,'Incoming real output did not retain a stable pulse'
            a=host.meter.beat_grid;period=a['period'];reference=time.monotonic()
            oldbeat=a['phase']+round((reference-a['phase'])/period)*period
            newbeat=grid['phase']+round((reference-grid['phase'])/grid['period'])*grid['period']
            error=((newbeat-oldbeat+period/2)%period-period/2)*1000
            pcm=np.concatenate(inc.raw)[:,0];spectrum=np.abs(np.fft.rfft(pcm*np.hanning(len(pcm))));freq=np.fft.rfftfreq(len(pcm),1/48000)
            band=(freq>850)&(freq<910);tone=float(freq[band][np.argmax(spectrum[band])])
            result=dict(beat_audio_smoke=True,bpm=grid['bpm'],phase_error_ms=round(error,2),tone_hz=round(tone,2),rate=decks.beat_plan['rate'])
            # Four seconds of a rising fade can move the estimated attack by
            # a 10 ms hop; verify both the real rate and the measured phase.
            assert abs(float(new.mpv['speed'])-decks.beat_plan['rate'])<.001,result
            assert abs(grid['bpm']-host.meter.beat_grid['bpm'])<=1.5,result
            assert abs(error)<65,result;assert abs(tone-880)<2,result
            settle(5.5);assert decks.outgoing is None;assert abs(float(new.mpv['speed'])-1)<.001
            print(json.dumps(result),flush=True)
    finally:
        decks.cancel();old.close();new.close()
        if capture:capture.close()
        if inc:inc.close()
        if module:subprocess.run(['pactl','unload-module',module],check=True)

if __name__=='__main__':run()
