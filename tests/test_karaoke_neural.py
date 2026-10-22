"""Neural framing/mixing without downloaded weights, accounts or device audio."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    import scipy
    from karaoke_neural import (stft,istft,NeuralSeparator,NeuralBlocks,WINDOW_SAMPLES,
                                MODEL_SAMPLES,LOOKAHEAD,FREQUENCIES,FRAMES)
except ImportError:scipy=None


@unittest.skipIf(scipy is None,'Optional neural runtime needs SciPy')
class NeuralTests(unittest.TestCase):
    def test_stft_preserves_stereo_phase_and_sample_alignment(self):
        rng=np.random.default_rng(15)
        pcm=rng.normal(0,.1,(2,MODEL_SAMPLES)).astype(np.float32)
        result=istft(stft(pcm)[0])
        self.assertEqual(result.shape,pcm.shape)
        np.testing.assert_allclose(result,pcm,atol=2e-7)

    def test_vocal_model_contract_and_compensation(self):
        class Session:
            def get_inputs(self):return [type('Input',(),{'name':'fixture'})()]
            def run(self,_,inputs):
                value=inputs['fixture']
                assert value.shape==(1,4,FREQUENCIES,FRAMES)
                assert value.dtype==np.float32
                return [value*.5]
        separator=NeuralSeparator(session=Session())
        t=np.arange(WINDOW_SAMPLES)/48000
        pcm=np.column_stack((np.sin(2*np.pi*1000*t),np.cos(2*np.pi*1000*t))).astype(np.float32)*.2
        result=separator.vocals(pcm)
        # Ignore only the resampler's padded boundary; the stereo phase and
        # level must match UVR's 1.035 vocal compensation across the interior.
        np.testing.assert_allclose(result[4096:-4096],pcm[4096:-4096]*.5175,atol=.001)

    def test_streaming_zero_strength_retains_exact_samples_across_windows(self):
        class Voice:
            def vocals(self,pcm):return pcm*.25
        block=32768;engine=NeuralBlocks(Voice(),block,0.)
        pcm=np.random.default_rng(12).normal(0,.1,(block*4+LOOKAHEAD,2)).astype(np.float32)
        result=[];offset=0
        for _ in range(4):
            needed=engine.required;result.append(engine.process(pcm[offset:offset+needed]));offset+=needed
        np.testing.assert_array_equal(np.concatenate(result),pcm[:block*4])

    def test_stems_mix_without_mid_side_cancellation_or_boundary_jumps(self):
        class Voice:
            def vocals(self,pcm):
                # Independent left and right voice estimates, not a centre gate.
                return pcm*.25
        block=32768;engine=NeuralBlocks(Voice(),block,1.)
        t=np.arange(block*3+LOOKAHEAD)/48000
        pcm=np.column_stack((np.sin(2*np.pi*440*t),np.cos(2*np.pi*660*t))).astype(np.float32)*.1
        result=[];offset=0
        for _ in range(3):
            needed=engine.required;result.append(engine.process(pcm[offset:offset+needed]));offset+=needed
        np.testing.assert_allclose(np.concatenate(result),pcm[:block*3]*.75,atol=2e-8)

    def test_slow_inference_is_rejected_before_routing(self):
        separator=object.__new__(NeuralSeparator)
        with patch.object(separator,'vocals'),patch('karaoke_neural.time.monotonic',side_effect=(0,1.,2.,3.)):
            with self.assertRaisesRegex(RuntimeError,'ai-too-slow'):separator.benchmark()

    def test_denoise_cancels_polarity_independent_model_noise(self):
        class Session:
            def __init__(self):self.inputs=[]
            def get_inputs(self):return [type('Input',(),{'name':'fixture'})()]
            def run(self,_,inputs):
                value=inputs['fixture'];self.inputs.append(value.copy())
                # A signal-independent texture in both polarity predictions
                # must cancel without changing the genuine vocal component.
                return [value*.5+np.random.default_rng(8).normal(0,.1,value.shape).astype(np.float32)]
        session=Session();separator=NeuralSeparator(session=session)
        t=np.arange(WINDOW_SAMPLES)/48000
        pcm=np.column_stack((np.sin(2*np.pi*1000*t),np.cos(2*np.pi*1000*t))).astype(np.float32)*.2
        result=separator.vocals(pcm)
        self.assertEqual(len(session.inputs),2)
        np.testing.assert_array_equal(session.inputs[1],-session.inputs[0])
        np.testing.assert_allclose(result[4096:-4096],pcm[4096:-4096]*.5175,atol=.001)

    def test_full_strength_overload_is_limited_without_flat_clipped_peaks(self):
        class Voice:
            def vocals(self,pcm):return -pcm  # A phase error can enlarge a residual.
        block=32768;engine=NeuralBlocks(Voice(),block,1.)
        t=np.arange(block+LOOKAHEAD)/48000
        wave=(.7*np.sin(2*np.pi*1000*t)).astype(np.float32)
        result=engine.process(np.column_stack((wave,wave*.5)))
        self.assertLessEqual(float(np.max(np.abs(result))),.98)
        self.assertEqual(int(np.sum(np.abs(result)>=.999999)),0)
        np.testing.assert_array_equal(result[:,1],result[:,0]*.5)


if __name__=='__main__':unittest.main()
