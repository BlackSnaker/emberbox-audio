import json,shutil,subprocess,sys,unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flow_beats import detect,match,EnergyTap


def pulse(bpm=120,phase=.137,seconds=8):
    t=np.arange(0,seconds,.01);e=np.exp(-((t-phase)%(60/bpm))/.035)
    return np.column_stack((t,e*2,e))

def syncopated():
    t=np.arange(0,12,.01);env=np.zeros(len(t));rng=np.random.default_rng(13)
    for i,at in enumerate(np.arange(.137,12,60/112/2)):
        volume=(1.3 if i%2==0 else .8)*(.25 if i%11==0 else 1)
        env+=volume*np.where(t>=at,np.exp(-np.maximum(0,t-at)/.04),0)
    for at in rng.uniform(0,12,36):
        env+=.6*np.where(t>=at,np.exp(-np.maximum(0,t-at)/.025),0)
    return np.column_stack((t,env,env*.6))

class BeatTests(unittest.TestCase):
    def test_grids_from_real_observations_cover_slow_and_fast_pulses(self):
        for bpm in (84,96,118.75,120,124,150,176):
            grid=detect(pulse(bpm));self.assertIsNotNone(grid);self.assertLess(abs(grid['bpm']-bpm),.3)
            self.assertGreater(grid['confidence'],.9);self.assertLess(abs(grid['phase']-.137),.015)
    def test_weak_short_silent_and_irregular_signals_do_not_force_a_match(self):
        self.assertIsNone(detect(pulse(seconds=2)))
        value=pulse();value[:,1:]=0;self.assertIsNone(detect(value))
        rng=np.random.default_rng(431);value[:,1:]=rng.random((len(value),2));self.assertIsNone(detect(value))
        self.assertIsNone(detect([[0,float('nan'),0]]*500));self.assertIsNone(detect(pulse().tolist()*10))
    def test_equal_eighth_notes_do_not_cancel_the_underlying_pulse(self):
        grid=detect(pulse(240));self.assertIsNotNone(grid);self.assertAlmostEqual(grid['bpm'],120,delta=.5)
    def test_syncopated_drums_with_fills_keep_the_recurrent_grid(self):
        grid=detect(syncopated());self.assertIsNotNone(grid)
        self.assertAlmostEqual(grid['bpm'],112,delta=.5);self.assertAlmostEqual(grid['phase'],.137,delta=.02)
        for seed in range(16):
            value=syncopated();value[:,1:]=np.random.default_rng(seed).random((len(value),2))*3
            self.assertIsNone(detect(value))
    def test_nearby_tempo_and_half_time_match_but_different_tempos_do_not(self):
        plan=match(detect(pulse(120)),detect(pulse(124)));self.assertAlmostEqual(plan['rate'],120/124)
        self.assertIsNone(match(detect(pulse(100)),detect(pulse(140))))
        self.assertAlmostEqual(match(detect(pulse(86)),detect(pulse(172)))['rate'],1)
    @unittest.skipUnless(shutil.which('node'),'Node needed to compare engines')
    def test_native_engine_and_python_agree_on_measured_beat_grids(self):
        script="const {detectBeat}=require('./src/apple_web_host/rhythm.cjs');let s='';process.stdin.on('data',b=>s+=b);process.stdin.on('end',()=>console.log(JSON.stringify(detectBeat(JSON.parse(s)))));"
        for points in (pulse(124),syncopated()):
            a=detect(points)
            b=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(points.tolist()),text=True,cwd=Path(__file__).resolve().parents[1]))
            self.assertEqual(a['bpm'],b['bpm']);self.assertLess(abs(a['phase']-b['phase']),.003)
            self.assertAlmostEqual(a['confidence'],b['confidence'],places=5)
    def test_stereo_capture_measures_audible_opposite_phase_drums(self):
        rate=48000;t=np.arange(rate*7)/rate;env=np.exp(-((t-.14)%.5)/.035)
        wave=.5*np.sin(t*2*np.pi*85)*env;pcm=np.column_stack((wave,-wave)).astype('f4')
        tap=EnergyTap()
        for start in range(0,len(pcm),2048):
            chunk=pcm[start:start+2048];tap.feed(chunk,(start+len(chunk))/rate)
        grid=tap.result();self.assertIsNotNone(grid);self.assertLess(abs(grid['bpm']-120),.5)
        self.assertLessEqual(len(tap.points),1600)
    def test_lamp_worker_can_track_beats_and_release_analysis_when_disabled(self):
        from audio_meter import SpotifyAudioMeter,FRAMES
        meter=SpotifyAudioMeter();meter.set_rhythm('generated-track')
        rate=48000;t=np.arange(rate*8)/rate;signal=.5*np.sin(t*2*np.pi*85)*np.exp(-((t-.14)%.5)/.035)
        pcm=np.column_stack((signal,-signal)).astype('<f4');now=0.
        with patch('audio_meter.time.monotonic',side_effect=lambda:now):
            for end in range(FRAMES,len(pcm)+1,FRAMES//2):
                now=end/rate;meter._measure(pcm[end-FRAMES:end].tobytes(),now)
        self.assertIsNotNone(meter.beat_grid);self.assertLess(abs(meter.beat_grid['bpm']-120),.5)
        meter.set_rhythm(None);self.assertIsNone(meter.rhythm);self.assertIsNone(meter.beat_grid)
