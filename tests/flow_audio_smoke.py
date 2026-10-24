"""Optional real mpv/PulseAudio check on a private, silent test sink.

Only locally generated tones are used. No user stream is moved or recorded;
captured synthetic samples stay in memory. Run with system Python in a session.
"""
import json,os,resource,select,subprocess,sys,tempfile,threading,time,wave
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gi.repository import GLib
from youtube_audio import YouTubeAudio
from flow_youtube import YouTubeDecks


def settle(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.003)


def run():
    sink='emberbox_flow_check_'+str(os.getpid());module=None;capture=None;stop=threading.Event();raw=[]
    old=YouTubeAudio(lambda:None,persistent=False);new=YouTubeAudio(lambda:None,persistent=False)
    host=SimpleNamespace(youtube=old,on_youtube_changed=lambda:None);decks=YouTubeDecks(host)
    try:
        module=subprocess.check_output(['pactl','load-module','module-null-sink','sink_name='+sink,'rate=48000','channels=2'],text=True).strip()
        with tempfile.TemporaryDirectory(prefix='emberflow-tones-') as directory:
            for deck,hz in ((old,220),(new,440)):
                pcm=(.18*np.sin(np.arange(48000*9)*hz*2*np.pi/48000)*32767).astype('<i2')
                file=Path(directory)/(str(hz)+'.wav')
                with wave.open(str(file),'wb') as stream:
                    stream.setparams((2,2,48000,0,'NONE','not compressed'));stream.writeframes(np.column_stack((pcm,pcm)).tobytes())
                assert deck._ensure_player(),deck.error
                deck.mpv['audio-device']='pulse/'+sink;deck.current={'id':str(hz),'title':'Synthetic tone'}
                deck.enabled=deck is old;deck.paused=deck is new
                deck.mpv.command_async('loadfile',str(file),'replace',-1,'pause='+('no' if deck is old else 'yes'))
            until=time.monotonic()+4
            while not(old.loaded and new.loaded) and time.monotonic()<until:settle(.02)
            assert old.loaded and new.loaded,'Local decoders did not load'
            capture=subprocess.Popen(['pacat','--record','--raw','--format=float32le','--rate=48000','--channels=2',
                '--latency-msec=30','--device='+sink+'.monitor'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            def read():
                while not stop.is_set():
                    ready,_,_=select.select([capture.stdout],[],[],.1)
                    if ready:
                        block=os.read(capture.stdout.fileno(),32768)
                        if not block:break
                        raw.append(block)
            reader=threading.Thread(target=read,daemon=True);reader.start()
            usage=resource.getrusage(resource.RUSAGE_SELF);cpu=usage.ru_utime+usage.ru_stime;start=time.monotonic()
            settle(1);decks.standby=new;assert decks.transition(3)
            settle(4.5);stop.set();reader.join(.3)
            samples=np.frombuffer(b''.join(raw)[:len(b''.join(raw))//8*8],dtype='<f4').reshape(-1,2)[:,0]
            def bands(at):
                value=samples[int(at*48000):int((at+.3)*48000)];assert len(value)>100
                spectrum=np.abs(np.fft.rfft(value*np.hanning(len(value))))/len(value)*4
                freq=np.fft.rfftfreq(len(value),1/48000)
                return [round(float(spectrum[(freq>hz-8)&(freq<hz+8)].max()),4) for hz in (220,440)]
            before,middle,after=bands(.4),bands(2.4),bands(4.7)
            # The server can restore the application's own output volume.
            # Compare against that baseline, without changing the user's mixer.
            baseline=before[0];assert baseline>.005
            assert before[1]<baseline*.05,(before,middle,after)
            assert min(middle)>baseline*.25,(before,middle,after)
            assert after[0]<baseline*.05 and after[1]>baseline*.9,(before,middle,after)
            assert np.max(np.abs(samples))<.185,'Overlap exceeded the input peak'
            usage=resource.getrusage(resource.RUSAGE_SELF)
            print(json.dumps({'pass':True,'before_220_440':before,'overlap_220_440':middle,'after_220_440':after,
                'peak':round(float(np.max(np.abs(samples))),4),'cpu_seconds':round(usage.ru_utime+usage.ru_stime-cpu,3),
                'wall_seconds':round(time.monotonic()-start,2),'peak_process_mib':round(usage.ru_maxrss/1024,1)}))
    finally:
        stop.set();decks.cancel();old.close();new.close()
        if capture:
            capture.terminate()
            try:capture.wait(timeout=1)
            except subprocess.TimeoutExpired:capture.kill();capture.wait(timeout=1)
        if module:subprocess.run(['pactl','unload-module',module],check=True)


if __name__=='__main__':run()
