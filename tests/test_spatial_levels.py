"""Atmos stereo level recovery must not clip, shift time or move the image."""
import ctypes,shutil,sys,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
from scipy.signal import resample_poly
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_aac import PcmResampler
from spatial_codec import Config,Joc


class SpatialMusicConfigTests(unittest.TestCase):
    def test_music_overrides_native_cinema_defaults_before_creating_the_renderer(self):
        configs=[]
        def initialize(pointer):
            config=ctypes.cast(pointer,ctypes.POINTER(Config)).contents
            config.drc=1;config.dialnorm=0;config.lfe=0
            return 0
        def create(pointer,handle):
            config=ctypes.cast(pointer,ctypes.POINTER(Config)).contents
            configs.append((config.render_mode,config.virtual_layout,config.drc,config.dialnorm,config.lfe))
            return 0
        def bind(lib,name,*types):
            if name=='openjoc_get_abi_version':return lambda:0x10007
            if name=='openjoc_decoder_config_init_v1_7':return initialize
            if name=='openjoc_stream_decoder_create':return create
            return Mock(return_value=0)
        with patch('spatial_codec.C.CDLL'),patch('spatial_codec.bind',side_effect=bind):
            decoder=Joc('fixture',lambda data,n:None);decoder.close()
        # 7.1.4 is virtual; BINAURAL emits exactly two channels. ANALOG means
        # unity dialogue gain, not an analog device or a lower-quality codec.
        self.assertEqual(configs,[(2,b'7.1.4',0,2,1)])


@unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
class SpatialPeakTests(unittest.TestCase):
    def render(self,source,rate=48000):
        out=[];decoder=PcmResampler(48000,rate,lambda data,n:out.append(data),threading.Event(),peak_limit=True)
        try:
            # Exercise partial native frames and a tail shorter than lookahead.
            for at in range(0,len(source),1536):decoder.write(source[at:at+1536].astype('<f4').tobytes())
            decoder.finish()
            return np.frombuffer(b''.join(out),'<f4').reshape(-1,2)
        finally:decoder.close()

    def test_unlimited_music_keeps_gain_waveform_timing_and_short_tail(self):
        t=np.arange(12007,dtype=np.float64)/48000
        source=np.column_stack((np.sin(2*np.pi*440*t)*.2,np.sin(2*np.pi*733*t)*.1)).astype('<f4')
        result=self.render(source)
        self.assertEqual(result.shape,source.shape)
        np.testing.assert_allclose(result[128:-128],source[128:-128],atol=2e-6)
        # A drain must also deliver the final, nonzero input samples.
        self.assertGreater(float(abs(result[-64:]).max()),.1)
        short=source[:73];self.assertEqual(self.render(short).shape,short.shape)

    def test_overload_and_intersample_peaks_remain_bounded_at_both_output_rates(self):
        t=np.arange(24013,dtype=np.float64)/48000
        signal=np.sin(2*np.pi*11025*t+np.pi/4)*2.4
        source=np.column_stack((signal,signal*.31)).astype('<f4')
        for rate in (48000,192000):
            with self.subTest(rate=rate):
                result=self.render(source,rate)
                self.assertEqual(len(result),len(source)*(rate//48000))
                self.assertTrue(np.isfinite(result).all())
                self.assertLessEqual(float(abs(result).max()),.94)
                # Check a reconstruction above the device rate, not just its
                # stored samples. Leave resampler edge transients out.
                true_peak=resample_poly(result[128:-128],4,1,axis=0)
                self.assertLess(float(abs(true_peak).max()),1.)
                np.testing.assert_allclose(result[:,1],result[:,0]*.31,atol=3e-6)

    def test_limiter_releases_smoothly_without_raising_quiet_passages(self):
        t=np.arange(48000,dtype=np.float64)/48000
        # The level step is at a zero crossing, so the input has no click.
        mono=np.sin(2*np.pi*1000*t)*np.where(t<.12,2.,.1)
        result=self.render(np.column_stack((mono,mono)))
        reference=mono[-4800:-128]
        np.testing.assert_allclose(result[-4800:-128,0],reference,atol=2e-6)
        self.assertLess(float(abs(np.diff(result[:,0])).max()),.15)


if __name__=='__main__':unittest.main()
