"""Decode CDM-licensed ALAC packets through an in-memory fragmented MP4 pipe."""
import ctypes
import struct
from spatial_aac import Aac


def box(kind,body):return struct.pack('>I4s',len(body)+8,kind)+body

def full(kind,flags,body):return box(kind,struct.pack('>I',flags)+body)

def configuration(cookie):
    if len(cookie)!=36 or cookie[:12]!=struct.pack('>I4sI',36,b'alac',0):raise ValueError('Invalid ALAC configuration')
    frame,version,depth,pb,mb,kb,channels,run,maximum,bitrate,rate=struct.unpack('>IBBBBBBHIII',cookie[12:])
    if version or depth not in (16,20,24) or channels!=2 or not 1<=frame<=65536 or rate not in (44100,48000,88200,96000,176400,192000):
        raise ValueError('Unsupported ALAC configuration')
    return frame,depth,rate


def initialization(cookie):
    _,depth,rate=configuration(cookie)
    matrix=struct.pack('>9I',65536,0,0,0,65536,0,0,0,1<<30)
    mvhd=full(b'mvhd',0,struct.pack('>4IIH',0,0,1000,0,65536,256)+bytes(10)+matrix+bytes(24)+struct.pack('>I',2))
    tkhd=full(b'tkhd',3,struct.pack('>5I',0,0,1,0,0)+bytes(8)+struct.pack('>4H',0,0,256,0)+matrix+bytes(8))
    mdhd=full(b'mdhd',0,struct.pack('>4I2H',0,0,rate,0,0x55c4,0))
    hdlr=full(b'hdlr',0,bytes(4)+b'soun'+bytes(12)+b'Ember\0')
    entry=box(b'alac',bytes(6)+struct.pack('>H',1)+bytes(8)+struct.pack('>4HI',2,depth,0,0,min(rate,65535)<<16)+cookie)
    stbl=box(b'stbl',full(b'stsd',0,struct.pack('>I',1)+entry)+full(b'stts',0,bytes(4))+full(b'stsc',0,bytes(4))+full(b'stsz',0,bytes(8))+full(b'stco',0,bytes(4)))
    dinf=box(b'dinf',full(b'dref',0,struct.pack('>I',1)+full(b'url ',1,b'')))
    minf=box(b'minf',full(b'smhd',0,bytes(4))+dinf+stbl)
    trak=box(b'trak',tkhd+box(b'mdia',mdhd+hdlr+minf))
    mvex=box(b'mvex',full(b'trex',0,struct.pack('>5I',1,1,0,0,0)))
    return box(b'ftyp',b'isom'+bytes(4)+b'isomiso6')+box(b'moov',mvhd+trak+mvex)


def fragment(packet,number,time,duration):
    if not 0<len(packet)<=1048576 or not 0<duration<=65536:raise ValueError('Invalid ALAC packet')
    def moof(offset):return box(b'moof',full(b'mfhd',0,struct.pack('>I',number))+box(b'traf',full(b'tfhd',0x20000,struct.pack('>I',1))+full(b'tfdt',0x1000000,struct.pack('>Q',time))+full(b'trun',0x301,struct.pack('>4I',1,offset,duration,len(packet)))))
    header=moof(0);return moof(len(header)+8)+box(b'mdat',packet)


class Alac(Aac):
    def __init__(self,cookie,output,stopping,output_rate=48000):
        import subprocess,threading
        self.frame,self.depth,self.rate=configuration(cookie);self.output=output;self.stopping=stopping;self.error=None;self.number=0;self.time=0
        self.process=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-threads','1','-probesize','32','-analyzeduration','0','-f','mp4','-i','pipe:0','-threads','1',
            '-af',f'aresample={output_rate}:filter_size=64:phase_shift=10','-ac','2','-ar',str(output_rate),'-f','f32le','pipe:1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
        self.process.stdin.write(initialization(cookie));self.process.stdin.flush()
    def feed(self,pointer,size):
        if self.error:raise self.error
        self.number+=1
        duration=getattr(self,'packet_duration',self.frame)
        if not 0<duration<=self.frame:raise ValueError('Invalid ALAC duration')
        self.process.stdin.write(fragment(ctypes.string_at(pointer,size),self.number,self.time,duration));self.process.stdin.flush();self.time+=duration
