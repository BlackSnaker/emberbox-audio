import ctypes,json,re,shutil,struct,subprocess,sys,threading,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_alac import Alac,configuration


def unhex(value):
    return bytes.fromhex(''.join(line.split(':',1)[1].split('  ',1)[0].strip() for line in value.splitlines() if ':' in line))


class AlacTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
    def test_real_24bit_alac_packets_preserve_samples_at_source_rate(self):
        for rate in (44100,96000,192000):
            with self.subTest(rate=rate):
                t=np.arange(rate//5,dtype=np.float64)/rate
                # Exact 24-bit values, including the low bits lost by 16-bit conversion.
                source=np.column_stack((np.round(np.sin(t*2*np.pi*440)*2**20),np.round(np.sin(t*2*np.pi*733)*2**20))).astype('<i4')
                encoded=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','s32le','-ar',str(rate),'-ac','2','-i','pipe:0','-c:a','alac','-sample_fmt','s32p','-movflags','frag_keyframe+empty_moov','-f','mp4','pipe:1'],input=(source*256).tobytes(),capture_output=True,check=True).stdout
                data=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_packets','-show_data','-of','json','pipe:0'],input=encoded,capture_output=True,check=True).stdout)
                cookie=unhex(data['streams'][0]['extradata'])
                self.assertEqual(configuration(cookie)[1:],(24,rate))
                out=[];decoder=Alac(cookie,lambda value,n:out.append(value),threading.Event(),output_rate=rate)
                try:
                    for packet in data['packets']:
                        raw=unhex(packet['data']);buf=ctypes.create_string_buffer(raw);decoder.feed(ctypes.addressof(buf),len(raw))
                    decoder.finish();result=np.frombuffer(b''.join(out),'<f4').reshape(-1,2)
                    self.assertEqual(len(result),len(source));self.assertTrue(np.isfinite(result).all())
                    np.testing.assert_array_equal(result,source.astype(np.float32)/2**23)
                finally:decoder.close()
    def test_rejects_invalid_cookie(self):
        for cookie in (b'',bytes(36),struct.pack('>I4sI',36,b'alac',0)+bytes(24)):
            with self.assertRaises(ValueError):configuration(cookie)

if __name__=='__main__':unittest.main()
