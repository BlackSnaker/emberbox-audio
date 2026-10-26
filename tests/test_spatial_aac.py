import ctypes,shutil,subprocess,sys,threading,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_aac import Aac,PcmResampler,configuration

class AacTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
    def test_short_spatial_tail_is_flushed_at_the_common_hires_clock(self):
        t=np.arange(48000//2,dtype=np.float32)/48000
        source=np.column_stack((np.sin(2*np.pi*440*t),np.sin(2*np.pi*660*t))).astype('<f4')*.2
        out=[];decoder=PcmResampler(48000,192000,lambda data,n:out.append(data),threading.Event())
        try:
            # A final partial segment must survive asynchronous resampling.
            for at in range(0,len(source),1536):decoder.write(source[at:at+1536].tobytes())
            decoder.finish();result=np.frombuffer(b''.join(out),'<f4').reshape(-1,2)
            self.assertEqual(len(result),len(source)*4);self.assertTrue(np.isfinite(result).all())
            self.assertLess(float(abs(result).max()),.21)
        finally:decoder.close()
    def test_unsupported_profiles_do_not_turn_into_stereo_claims(self):
        self.assertEqual(configuration(b'\x12\x10'),(4,44100))
        for value in (b'',b'\0\0',b'\x2b\x92',b'\x12\x08'):
            with self.assertRaises(ValueError):configuration(value)
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
    def test_real_aac_access_units_decode_into_finite_48khz_pcm(self):
        t=np.arange(13230,dtype=np.float32)/44100
        source=np.column_stack((np.sin(t*2*np.pi*440)*.2,np.sin(t*2*np.pi*660)*.2)).astype('<f4')
        encoded=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','f32le','-ar','44100','-ac','2','-i','pipe:0','-c:a','aac','-b:a','256k','-f','adts','pipe:1'],input=source.tobytes(),capture_output=True,check=True).stdout
        out=[];decoder=Aac(b'\x12\x10',lambda data,n:out.append(data),threading.Event())
        try:
            at=0
            while at<len(encoded):
                length=((encoded[at+3]&3)<<11)|(encoded[at+4]<<3)|(encoded[at+5]>>5)
                packet=encoded[at+7:at+length];buf=ctypes.create_string_buffer(packet);decoder.feed(ctypes.addressof(buf),len(packet));at+=length
            decoder.finish()
            result=np.frombuffer(b''.join(out),'<f4').reshape(-1,2)
            self.assertTrue(np.isfinite(result).all());self.assertGreater(len(result),14400);self.assertLess(len(result),17000)
            self.assertLess(float(abs(result).max()),.4)
        finally:decoder.close()

if __name__=='__main__':unittest.main()
