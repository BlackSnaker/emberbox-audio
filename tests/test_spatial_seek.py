import ctypes,json,os,select,shutil,struct,subprocess,sys,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_seek import Seeks,PcmWriter,SeekCancelled
import numpy as np
from spatial_mixer import Mixer,RATE,BLOCK
from spatial_aac import PcmResampler
from spatial_alac import configuration as alac_configuration

class SpatialSeekTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        worker=sys.modules.get('spatial_worker')
        if worker:worker.control.close()

    def test_deep_atmos_seek_keeps_preroll_and_all_audible_samples(self):
        import spatial_worker as worker
        for timescale,full in ((48000,False),(None,False),(48000,True)):
            packets=[(bytes([i]),{'codec':'eac3','duration':1536,'timescale':timescale}) for i in range(100)]
            decoded=[];out=[];events=[]
            class Host:
                def decode_sample(self,packet,crypto,key,deliver):
                    decoded.append(packet[0]);deliver(packet[0],0)
            class Decoder:
                def __init__(self,library,output):self.output=output
                def feed(self,index,size):self.output(np.full((1536,2),index/100,np.float32).tobytes(),1536)
                def finish(self):pass
                def close(self):pass
            class Writer:
                def write(self,data,generation,cancelled):out.append(data)
            prepared={'codec':'eac3','segments':[{'start':0,'duration':3.2,'keyIndex':0}]}
            with patch.object(worker,'request',return_value={'total':1,'data':'AA==','initBytes':0,'originalOffset':0}),patch.object(worker,'samples',return_value=iter(packets)),patch.object(worker,'Joc',Decoder),patch.object(worker,'emit',side_effect=events.append):
                worker.decode_pass({'fullPreroll':full},prepared,{'decoder':'fixture'},48000,Host(),{0:'opaque'},lambda _:None,Writer(),2.,2,threading.Event())
            reference=np.repeat(np.arange(100,dtype=np.float32)/100,1536)[96000:]
            np.testing.assert_array_equal(np.frombuffer(b''.join(out),'<f4').reshape(-1,2)[:,0],reference)
            if timescale and not full:
                self.assertGreater(decoded[0],0);self.assertLessEqual(decoded[0]*1536,96000-24000)
            else:self.assertEqual(decoded[0],0,'Unknown sample timing must retain the complete preroll')
            self.assertEqual(events[-1]['frames'],len(reference))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
    def test_real_hi_res_seek_preserves_exact_24_bit_samples_and_format_evidence(self):
        import spatial_worker as worker
        rate=192000;t=np.arange(rate//2,dtype=np.float64)/rate
        source=np.column_stack((np.round(np.sin(t*2*np.pi*440)*2**20),np.round(np.sin(t*2*np.pi*733)*2**20))).astype('<i4')
        encoded=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','s32le','-ar',str(rate),'-ac','2','-i','pipe:0','-c:a','alac','-sample_fmt','s32p','-movflags','frag_keyframe+empty_moov','-f','mp4','pipe:1'],input=(source*256).tobytes(),capture_output=True,check=True).stdout
        info=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_packets','-show_data','-of','json','pipe:0'],input=encoded,capture_output=True,check=True).stdout)
        def unhex(value):return bytes.fromhex(''.join(line.split(':',1)[1].split('  ',1)[0].strip() for line in value.splitlines() if ':' in line))
        cookie=unhex(info['streams'][0]['extradata'])
        # Older ffprobe omits packet durations for fragmented ALAC. This
        # generated signal has a known sample count and codec frame size.
        frame=alac_configuration(cookie)[0]
        self.assertEqual(len(info['packets']),(len(source)+frame-1)//frame)
        packets=[(unhex(p['data']),{'codec':'alac','cookie':cookie,'duration':min(frame,len(source)-i*frame)}) for i,p in enumerate(info['packets'])]
        class LicensedHost:
            def decode_sample(self,packet,crypto,key,deliver):
                buf=ctypes.create_string_buffer(packet);deliver(ctypes.addressof(buf),len(packet))
        host=LicensedHost();licensed={0:'opaque-fixture'}
        prepared={'drm':'fairplay','codec':'alac','segments':[{'start':0,'duration':.5,'keyIndex':0}]}
        try:
            for generation,origin in ((1,.1),(2,.3)):
                out=[];events=[]
                class Writer:
                    def write(self,data,actual,cancelled):
                        self_test.assertEqual(actual,generation);out.append(data)
                self_test=self
                with patch.object(worker,'request',return_value={'total':1,'data':'AA==','initBytes':0,'originalOffset':0}),patch.object(worker,'samples',return_value=iter(packets)),patch.object(worker,'emit',side_effect=events.append):
                    worker.decode_pass({},prepared,{},rate,host,licensed,lambda _:None,Writer(),origin,generation,threading.Event())
                result=np.frombuffer(b''.join(out),'<f4').reshape(-1,2)
                np.testing.assert_array_equal(result,source[round(origin*rate):].astype(np.float32)/2**23)
                quality=next(e['audioQuality'] for e in events if e['type']=='quality')
                self.assertEqual((quality['codec'],quality['bitDepth'],quality['sampleRate']),('alac',24,192000))
                self.assertEqual(events[-1]['frames'],len(result));self.assertEqual(events[-1]['generation'],generation)
        finally:worker.seeks.processes=[]

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
    def test_cancel_releases_a_real_codec_blocked_by_pcm_backpressure(self):
        seeks=Seeks();seeks.submit(0,1);_,_,cancelled=seeks.next()
        reached=threading.Event();finished=threading.Event()
        def output(data,n):
            reached.set();cancelled.wait(3)
            raise SeekCancelled()
        codec=PcmResampler(48000,48000,output,cancelled);seeks.attach(codec,cancelled)
        def feed():
            try:codec.write(bytes(48000*8*8))
            except (BrokenPipeError,SeekCancelled):pass
            finally:finished.set()
        thread=threading.Thread(target=feed);thread.start()
        try:
            self.assertTrue(reached.wait(2));self.assertFalse(finished.is_set())
            seeks.submit(50,2)
            self.assertTrue(finished.wait(1),'A cancelled codec is still flushing into a full output pipe')
        finally:
            codec.process.kill();cancelled.set();thread.join(2);codec.close();seeks.close()

    def test_latest_seek_cancels_blocked_codec_and_coalesces_intermediate_positions(self):
        seeks=Seeks();seeks.submit(10,1);_,_,cancelled=seeks.next()
        class Process:
            stopped=False
            def kill(self):self.stopped=True
        class Decoder:process=Process()
        seeks.attach(Decoder(),cancelled)
        seeks.submit(30,2);seeks.submit(50,3)
        self.assertTrue(cancelled.is_set());self.assertTrue(Decoder.process.stopped)
        position,generation,active=seeks.next()
        self.assertEqual((position,generation),(50,3));self.assertFalse(active.is_set())
        seeks.close();self.assertTrue(active.is_set());self.assertIsNone(seeks.next())

    def test_cancelled_partial_pcm_frame_finishes_without_corrupting_next_generation(self):
        read,write=os.pipe();stop=threading.Event();cancel=threading.Event();out=[];errors=[]
        try:
            writer=PcmWriter(write,stop);data=bytes(262144)
            def produce():
                try:writer.write(data,1,cancel)
                except SeekCancelled:errors.append('cancelled')
                writer.write(b'12345678',2,threading.Event())
            thread=threading.Thread(target=produce);thread.start()
            self.assertTrue(select.select([read],[],[],2)[0]);cancel.set()
            size=8+len(data)+16
            until=time.monotonic()+3
            while sum(map(len,out))<size and time.monotonic()<until:
                if select.select([read],[],[],.1)[0]:out.append(os.read(read,32768))
            thread.join(1);self.assertFalse(thread.is_alive())
            raw=b''.join(out);self.assertEqual(len(raw),size)
            self.assertEqual(struct.unpack('<II',raw[:8]),(1,len(data)))
            self.assertEqual(struct.unpack('<II',raw[-16:-8]),(2,8));self.assertEqual(raw[-8:],b'12345678')
            self.assertEqual(errors,['cancelled'])
        finally:stop.set();os.close(write);os.close(read)

    def test_seek_discards_queued_audio_and_fade_and_preserves_output_clock(self):
        events=[];m=Mixer(events.append)
        for slot in (0,1):
            m.configure({'slot':slot,'generation':slot+1})
            m.received(slot,slot+1,np.full((RATE,2),-.5,np.float32).tobytes())
        m.control({'type':'transition','duration':.22,'key':'manual','manual':True})
        m.render();clock=m.frames
        m.control({'type':'seek','slot':0,'generation':3,'position':71})
        self.assertIsNone(m.fade);self.assertIsNone(m.slots[1]);self.assertEqual(m.slots[0].frames,0)
        tail=np.frombuffer(m.render(),'<f4');self.assertEqual(m.frames,clock+BLOCK)
        self.assertAlmostEqual(float(tail[-1]),0);self.assertIsNone(m.render())
        m.received(0,1,np.ones((BLOCK,2),np.float32).tobytes());self.assertEqual(m.slots[0].frames,0)
        m.received(0,3,np.full((RATE//5,2),.5,np.float32).tobytes())
        self.assertTrue(m.slots[0].ready)
        attack=np.frombuffer(m.render(),'<f4').reshape(-1,2)
        self.assertAlmostEqual(float(attack[0,0]),0);self.assertAlmostEqual(float(attack[-1,0]),.5)
        self.assertLess(float(abs(np.diff(attack[:,0])).max()),.003)
        self.assertEqual(m.slots[0].origin,71);self.assertEqual(m.slots[0].start,clock+BLOCK)

    def test_paused_seek_and_short_tail_do_not_require_a_second_of_preroll(self):
        events=[];m=Mixer(events.append);m.paused=True
        m.configure({'slot':0,'generation':1});m.frames=RATE*100
        m.control({'type':'seek','slot':0,'generation':2,'position':50})
        m.received(0,2,np.ones((777,2),np.float32).tobytes())
        m.control({'type':'end','slot':0,'generation':2,'frames':777})
        self.assertTrue(m.paused);self.assertTrue(m.slots[0].ready)
        self.assertEqual(m.slots[0].start,RATE*100);self.assertEqual(len(m.render()),777*8)
        self.assertTrue(any(e['type']=='ready' and e['generation']==2 for e in events))

if __name__=='__main__':unittest.main()
