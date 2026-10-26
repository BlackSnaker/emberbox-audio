"""Decode licensed AAC access units for mixed Atmos/stereo queue transitions."""
import ctypes,subprocess,threading

RATES=(96000,88200,64000,48000,44100,32000,24000,22050,16000,12000,11025,8000,7350)

def configuration(asc):
    if len(asc)<2:raise ValueError('Missing AAC configuration')
    value=int.from_bytes(asc[:2],'big');profile=value>>11;rate=(value>>7)&15;channels=(value>>3)&15
    if profile!=2 or rate>=len(RATES) or channels!=2:raise ValueError('Unsupported AAC configuration')
    return rate,RATES[rate]

class Aac:
    def __init__(self,asc,output,stopping,output_rate=48000):
        self.rate_index,self.rate=configuration(asc);self.output=output;self.stopping=stopping;self.error=None
        self.process=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-threads','1',
            '-probesize','32','-analyzeduration','0','-f','aac','-i','pipe:0','-threads','1',
            '-af',f'aresample={output_rate}:filter_size=64:phase_shift=10','-ac','2','-ar',str(output_rate),'-f','f32le','pipe:1'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
    def read(self):
        try:
            while not self.stopping.is_set():
                data=self.process.stdout.read(8192)
                if not data:break
                if len(data)%8:raise RuntimeError('SPATIAL_PCM_FORMAT')
                self.output(data,len(data)//8)
        except Exception as error:self.error=error
    def feed(self,pointer,size):
        if self.error:raise self.error
        length=size+7
        if not 7<length<8192:raise ValueError('AAC access unit limit')
        f=self.rate_index;c=2
        header=bytes((255,241,(1<<6)|(f<<2)|(c>>2),((c&3)<<6)|(length>>11),(length>>3)&255,((length&7)<<5)|31,252))
        self.process.stdin.write(header+ctypes.string_at(pointer,size));self.process.stdin.flush()
    def finish(self):
        self.process.stdin.close()
        while self.thread.is_alive() and not self.stopping.wait(.1):self.thread.join(.1)
        if self.error:raise self.error
        if not self.stopping.is_set() and self.process.wait(timeout=3)!=0:raise RuntimeError('SPATIAL_AAC_DECODE_FAILED')
    def close(self):
        if self.process.poll() is None:self.process.terminate()
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        # A warm seek starts a new PCM generation in this same process.
        # Join the old reader before any callback can reach the next pass.
        if self.thread is not threading.current_thread():self.thread.join(timeout=2)
        for stream in (self.process.stdin,self.process.stdout):
            try:stream.close()
            except OSError:pass


class PcmResampler(Aac):
    """A bounded streaming pipe when native decks need one common clock."""
    def __init__(self,rate,output_rate,output,stopping):
        self.output=output;self.stopping=stopping;self.error=None
        self.process=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-threads','1',
            '-probesize','32','-analyzeduration','0','-f','f32le','-ac','2','-ar',str(rate),'-i','pipe:0','-threads','1',
            '-af',f'aresample={output_rate}:filter_size=64:phase_shift=10','-ac','2','-ar',str(output_rate),
            '-f','f32le','pipe:1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()

    def write(self,data,samples=None):
        if self.error:raise self.error
        self.process.stdin.write(data);self.process.stdin.flush()
