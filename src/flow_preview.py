"""Read a short intro from the already selected public audio stream, in memory.

The real mpv deck remains paused and connected to its destination. One low
priority decoder worker reads at most 6.5 seconds; it never changes routing,
records a microphone, reads cookies, re-encodes playback or saves decoded PCM.
"""
from concurrent.futures import ThreadPoolExecutor
import os,select,shutil,subprocess,threading,time
import numpy as np
from flow_beats import EnergyTap


class Preview:
    def __init__(self,deck):
        self.deck=deck;self.stop=threading.Event();self.error=''
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='flow-intro');self.future=self.pool.submit(self.run)
    def cancel(self):self.stop.set();self.pool.shutdown(wait=False,cancel_futures=True)
    def run(self):
        process=None;tap=EnergyTap();data=bytearray();frames=0
        try:
            decoder=shutil.which('ffmpeg')
            if not decoder:return None
            source=str(self.deck.mpv.stream_open_filename or '')
            if not source.startswith(('https://','http://','/')):return None
            process=subprocess.Popen([decoder,'-nostdin','-v','error','-threads','1','-filter_threads','1',
                '-rw_timeout','5000000','-i',source,'-t','6.5','-vn','-ac','2','-ar','48000','-f','f32le','pipe:1'],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
            try:os.setpriority(os.PRIO_PROCESS,process.pid,10)
            except OSError:pass
            until=time.monotonic()+9
            while not self.stop.is_set() and time.monotonic()<until and frames<312000:
                ready,_,_=select.select([process.stdout],[],[],.1)
                if not ready:continue
                block=os.read(process.stdout.fileno(),32768)
                if not block:break
                data.extend(block);n=len(data)//8*8
                if n:
                    pcm=np.frombuffer(bytes(data[:n]),dtype='<f4').reshape(-1,2);del data[:n]
                    pcm=pcm[:312000-frames];frames+=len(pcm);tap.feed(pcm,frames/48000)
            return tap.result() if not self.stop.is_set() else None
        except (OSError,ValueError,RuntimeError,AttributeError):return None
        finally:
            if process:
                if process.poll() is None:process.terminate()
                try:process.wait(timeout=.5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=.5)
                process.stdout.close()
