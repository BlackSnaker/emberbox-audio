"""Actual PCM, smooth automation, headroom and private EQ recipe isolation."""
import sys,tempfile,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flow_eq import BandEQ,ease
from flow_plans import recipe,configuration,FlowPlans,playlist_key
from flow_timeline import overlap
from spatial_mixer import Mixer
from spatial_mix import RATE


class TransitionEQ(unittest.TestCase):
    def test_band_cut_changes_actual_spectrum_and_keeps_stereo(self):
        for rate in (48000,192000):
            t=np.arange(rate)/rate
            data=np.column_stack((.15*np.sin(t*2*np.pi*60)+.15*np.sin(t*2*np.pi*10000),
                                  .13*np.sin(t*2*np.pi*1000)))
            eq=BandEQ(rate,[-12,0,0]);result=eq.process(data,1)
            tail=result[rate//2:,0];times=t[rate//2:]
            amplitude=lambda hz:2*abs(np.dot(tail,np.exp(-2j*np.pi*hz*times)))/len(tail)
            self.assertLess(amplitude(60)/amplitude(10000),.45)
            self.assertGreater(float(np.max(abs(result[:,1]))),.03)
            self.assertTrue(np.isfinite(result).all())
    def test_split_blocks_are_identical_and_endpoints_release_the_original(self):
        rng=np.random.default_rng(147);data=rng.uniform(-.8,.8,(48000,2)).astype(np.float32)
        w=1-ease(np.linspace(0,1,len(data)))
        a=BandEQ(48000,[-9,-3,-2]);b=BandEQ(48000,[-9,-3,-2])
        whole=a.process(data,w)
        split=np.concatenate([b.process(data[i:i+997],w[i:i+997]) for i in range(0,len(data),997)])
        np.testing.assert_array_equal(whole,split);np.testing.assert_array_equal(whole[-1],data[-1])
        neutral=BandEQ(48000,[0,0,0]).process(data,w)
        np.testing.assert_array_equal(neutral,data)
    def test_peak_budget_holds_for_adversarial_pcm_and_all_cut_patterns(self):
        rng=np.random.default_rng(51);data=rng.choice([-1.,1.],(16000,2)).astype(np.float32)
        for values in ((-12,0,-12),(0,-12,0),(-12,-12,0),(0,0,-12),(-9,-6,-3)):
            eq=BandEQ(48000,values);out=eq.process(data,np.linspace(0,1,len(data)))
            self.assertLessEqual(float(abs(out).max()),1.0000001)
            self.assertGreaterEqual(eq.reserve,1)
    def test_native_mixer_uses_eq_and_cancellation_releases_without_a_step(self):
        m=Mixer(lambda _:None)
        for slot,hz in enumerate((65,1200)):
            t=np.arange(RATE*3)/RATE
            data=np.column_stack([.2*np.sin(t*2*np.pi*hz)]*2).astype(np.float32)
            m.configure({'slot':slot,'generation':slot+1});m.received(slot,slot+1,data.tobytes())
        m.control({'type':'transition','duration':2,'key':'eq','eq':{'out':[-9,0,0],'in':[-6,0,0]}})
        chunks=[np.frombuffer(m.render(),'<f4') for _ in range(40)]
        before=chunks[-1][-2:];m.control({'type':'cancel','keep':0})
        self.assertIn('eq_cancel',m.fade)
        out=np.frombuffer(m.render(),'<f4');self.assertLess(float(abs(out[:2]-before).max()),.035)
        for _ in range(8):m.render()
        self.assertTrue(all(eq.amount==0 for eq in m.fade['eq'].values()))
        self.assertTrue(np.isfinite(out).all());self.assertLessEqual(float(abs(out).max()),.2)
    def test_recipes_validate_and_do_not_share_mutable_band_arrays(self):
        for value in ({'eq_mode':'unknown'},{'eq_out':[-13,0,0]},{'eq_in':[0,0,float('nan')]},{'eq_out':[0,0]}):
            with self.assertRaises(ValueError):recipe(value)
        self.assertIsNone(configuration(recipe({})))
        self.assertEqual(configuration(recipe({'eq_mode':'auto'})),{'out':[-9.,0.,0.],'in':[-6.,0.,0.]})
        with tempfile.TemporaryDirectory() as tmp:
            store=FlowPlans(Path(tmp)/'plans.json');key=playlist_key('apple-music',{'id':'test'})
            a,b={'uri':'apple:songs:1'},{'uri':'apple:songs:2'}
            store.put(key,[(a,b,dict(eq_mode='manual',eq_out=[-6,0,0]))])
            value=store.get(key,a,b);value['eq_out'][0]=0
            self.assertEqual(store.get(key,a,b)['eq_out'][0],-6)
            self.assertEqual(FlowPlans(store.path).get(key,a,b)['eq_mode'],'manual')
    def test_both_lane_directions_and_drag_bounds(self):
        self.assertEqual(overlap(4,2,0),6);self.assertEqual(overlap(4,2,1),2)
        self.assertEqual(overlap(4,100,0),30);self.assertEqual(overlap(4,100,1),1)


if __name__=='__main__':unittest.main()
