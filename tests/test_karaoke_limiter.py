"""Peak limiting: original synthetic PCM, no model, devices or account data."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from karaoke_limiter import StereoPeakLimiter,FUTURE
except ImportError:
    StereoPeakLimiter=None


@unittest.skipIf(StereoPeakLimiter is None,'Optional neural runtime needs SciPy')
class LimiterTests(unittest.TestCase):
    def test_quiet_audio_is_exact_unity_including_silent_future(self):
        pcm=np.random.default_rng(12).uniform(-.7,.7,(32768+FUTURE,2)).astype(np.float32)
        result=StereoPeakLimiter().process(pcm,32768)
        np.testing.assert_array_equal(result,pcm[:32768])

    def test_overloaded_sine_is_bounded_without_hard_flat_tops(self):
        count=48000;t=np.arange(count+FUTURE)/48000
        pcm=np.column_stack((1.6*np.sin(2*np.pi*440*t),.7*np.sin(2*np.pi*440*t))).astype(np.float32)
        result=StereoPeakLimiter().process(pcm,count)
        self.assertLessEqual(float(np.max(np.abs(result))),.98)
        self.assertTrue(np.isfinite(result).all())
        # Clipping this input flattens many consecutive samples every cycle.
        # Limited output keeps a curved waveform even at the loudest peaks.
        flat=np.abs(np.diff(result[2400:,0]))<1e-7
        self.assertLess(float(np.mean(flat)),.001)
        np.testing.assert_allclose(result[:,1],result[:,0]*(.7/1.6),atol=1e-7)

    def test_gain_anticipates_peak_and_recovers_smoothly(self):
        count=96000;pcm=np.full((count+FUTURE,2),.2,np.float32)
        peak=4800;pcm[peak]=(2.,1.)
        result=StereoPeakLimiter().process(pcm,count)
        gain=result[:,0]/pcm[:count,0]
        self.assertEqual(float(gain[peak-FUTURE-1]),1.)
        self.assertLess(float(gain[peak-96]),.99)
        self.assertLessEqual(float(np.max(np.abs(np.diff(gain[peak-FUTURE:peak])))),.006)
        self.assertLess(float(gain[peak+1]),.6)
        self.assertGreater(float(gain[peak+4800]),.80)
        self.assertGreater(float(gain[peak+4800]),float(gain[peak+100]))
        np.testing.assert_array_equal(result[-100:],pcm[count-100:count])

    def test_block_boundaries_match_single_pass_and_keep_sample_timing(self):
        count=32768*4;block=32768
        t=np.arange(count+FUTURE)/48000
        pcm=np.column_stack((.25*np.sin(2*np.pi*440*t),.16*np.cos(2*np.pi*660*t))).astype(np.float32)
        # Peaks before, directly at and immediately after different block joins.
        for index in (block-300,2*block,3*block+300):pcm[index]=(1.7,-1.3)
        expected=StereoPeakLimiter().process(pcm,count)
        limiter=StereoPeakLimiter()
        chunks=[limiter.process(pcm[i:i+block+FUTURE],block) for i in range(0,count,block)]
        result=np.concatenate(chunks)
        np.testing.assert_array_equal(result,expected)
        self.assertEqual(int(np.argmax(np.abs(result[:,0]))),int(np.argmax(np.abs(expected[:,0]))))

    def test_bad_values_are_finite_and_do_not_change_channel_image(self):
        pcm=np.full((4096+FUTURE,2),.2,np.float32)
        pcm[100]=(np.nan,np.inf);pcm[200]=(-np.inf,np.nan);pcm[300]=(1e30,-5e29)
        result=StereoPeakLimiter().process(pcm,4096)
        self.assertTrue(np.isfinite(result).all())
        self.assertLessEqual(float(np.max(np.abs(result))),.98)
        self.assertEqual(result.shape,(4096,2))
        self.assertEqual(result.dtype,np.dtype('<f4'))

    def test_requires_bounded_future_without_consuming_it(self):
        limiter=StereoPeakLimiter();pcm=np.zeros((4096+FUTURE,2),np.float32)
        self.assertLessEqual(limiter.required_future,8192)
        self.assertEqual(limiter.process(pcm,4096).shape,(4096,2))
        with self.assertRaises(ValueError):limiter.process(pcm[:-1],4096)


if __name__=='__main__':unittest.main()
