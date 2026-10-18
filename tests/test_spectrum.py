from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import audio_meter


class SpectrumTests(unittest.TestCase):
    def test_silence_and_frequency_separation(self):
        meter=audio_meter.SpotifyAudioMeter()
        samples=np.zeros((audio_meter.FRAMES,2),dtype='<f4')
        meter._measure(samples.tobytes())
        self.assertEqual(meter.levels,(0.,)*9)
        t=np.arange(audio_meter.FRAMES)/audio_meter.RATE
        wave=.1*np.sin(2*np.pi*440*t)
        meter._measure(np.column_stack((wave,wave)).astype('<f4').tobytes())
        self.assertEqual(int(np.argmax(meter.levels)),3)
        self.assertGreater(meter.levels[3],.3)
        self.assertGreater(meter.last_sample,0)
