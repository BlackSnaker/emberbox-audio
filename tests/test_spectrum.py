from pathlib import Path
import sys
import unittest
import threading
import time
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import audio_meter


class SpectrumTests(unittest.TestCase):
    def test_slow_recorder_cleanup_never_blocks_a_track_transition(self):
        entered, release, finished = (threading.Event() for _ in range(3))
        class SlowRecorder:
            stdout = None
            def poll(self):return None
            def terminate(self):pass
            def wait(self, timeout):
                entered.set()
                release.wait(2)
                finished.set()
        meter=audio_meter.SpotifyAudioMeter()
        meter.process=SlowRecorder()
        meter.levels=(1.,)*9
        meter.rms_level=1.
        start=time.monotonic()
        try:
            meter.stop()
            self.assertLess(time.monotonic()-start,.15)
            self.assertTrue(entered.wait(.5))
            self.assertIsNone(meter.process)
            self.assertEqual(meter.levels,(0.,)*9)
            self.assertEqual(meter.rms_level,0.)
            self.assertFalse(finished.is_set())
        finally:
            release.set()
            self.assertTrue(finished.wait(.5))

    def test_replacement_recorders_have_distinct_pipewire_nodes(self):
        class Recorder:
            stdout=None
            def poll(self):return 0
            def wait(self,timeout):pass
        meter=audio_meter.SpotifyAudioMeter()
        with patch('audio_meter.subprocess.Popen',side_effect=lambda *a,**kw:Recorder()) as spawn:
            meter.start();meter.start();meter.stop()
        properties=[call.args[0][4] for call in spawn.call_args_list]
        self.assertEqual(len(properties),2)
        self.assertNotEqual(properties[0],properties[1])

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

    def test_vu_follows_stereo_energy_even_with_opposite_phase(self):
        meter=audio_meter.SpotifyAudioMeter()
        wave=np.sin(2*np.pi*440*np.arange(audio_meter.FRAMES)/audio_meter.RATE)
        values=[]
        for amplitude in (0.,.01,.1,.5):
            stereo=np.column_stack((wave*amplitude,-wave*amplitude)).astype('<f4')
            meter._measure(stereo.tobytes())
            values.append(meter.rms_level)
        self.assertEqual(values[0],0.)
        self.assertTrue(all(a<b for a,b in zip(values,values[1:])),values)
        self.assertGreater(values[-1],.8)
