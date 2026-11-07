"""Audible custom envelopes: engine parity, headroom, continuity and isolation."""
import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from flow_curves import custom,point
from flow_youtube import curve as youtube
from spatial_mix import curve,blend
from flow_plans import FlowPlans,playlist_key,recipe
from spatial_mixer import Mixer
from spatial_mix import RATE


class Curves(unittest.TestCase):
    def test_extreme_knots_are_monotone_complementary_and_match_native(self):
        times=np.linspace(0,1,4097)
        for knee in (.1,.35,.5,.9):
            for level in (.05,.3,.5,.95):
                values=np.array([custom(t,knee,level) for t in times])
                self.assertEqual(values[0],0);self.assertEqual(values[-1],1)
                self.assertTrue(np.all(np.diff(values)>=-1e-12))
                self.assertAlmostEqual(custom(knee,knee,level),level)
                np.testing.assert_allclose(curve(times,flow=True,shape='custom',point=[knee,level]),values,atol=1e-12)
                for t in times[::64]:
                    a,b=youtube(t,'custom',knee,level)
                    self.assertAlmostEqual(a+b,1);self.assertAlmostEqual(b,custom(t,knee,level))
                e=1e-7
                self.assertAlmostEqual((level-custom(knee-e,knee,level))/e,(custom(knee+e,knee,level)-level)/e,delta=.0001)
                self.assertLess(custom(e,knee,level)/e,.0001)
                self.assertLess((1-custom(1-e,knee,level))/e,.0001)
    def test_actual_pcm_keeps_correlated_peak_headroom(self):
        data=np.ones((5001,2),np.float32)
        for p in ([.1,.95],[.9,.05],[.35,.7]):
            np.testing.assert_array_equal(blend(data,data,0,len(data),flow=True,shape='custom',point=p),data)
            out=blend(data,-data,0,len(data),flow=True,shape='custom',point=p)
            self.assertLessEqual(abs(out).max(),1)
    @unittest.skipUnless(shutil.which('node'),'Node unavailable')
    def test_musickit_matches_sample_mixer_at_asymmetric_points(self):
        script="const {mixCurve}=require('./src/apple_web_host/flow.cjs');console.log(JSON.stringify([[.1,.95],[.9,.05],[.35,.7]].map(p=>Array.from({length:101},(_,i)=>mixCurve(i/100,'custom',p)))));"
        values=json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT,text=True))
        for p,result in zip(([.1,.95],[.9,.05],[.35,.7]),values):
            np.testing.assert_allclose(result,curve(np.linspace(0,1,101),flow=True,shape='custom',point=p),atol=1e-12)
    def test_native_cancellation_starts_at_current_custom_gain(self):
        mixer=Mixer(lambda _:None)
        for slot,level in ((0,.2),(1,-.2)):
            mixer.configure({'slot':slot,'generation':slot+1})
            mixer.received(slot,slot+1,np.full((RATE*3,2),level,np.float32).tobytes())
        mixer.control({'type':'transition','duration':2,'key':'curve','shape':'custom','point':[.2,.8]})
        for _ in range(30):last=np.frombuffer(mixer.render(),'<f4')
        mixer.control({'type':'cancel','keep':0})
        next=np.frombuffer(mixer.render(),'<f4')
        self.assertLess(abs(next[:2]-last[-2:]).max(),.001)
    def test_validation_and_private_recipe_round_trip(self):
        for value in ([0,.5],[.5,1],[.2,float('nan')],[.5],{},['bad',.5]):
            with self.assertRaises((ValueError,TypeError)):point(value)
        with tempfile.TemporaryDirectory() as tmp:
            store=FlowPlans(Path(tmp)/'flow.json');key=playlist_key('apple-music',{'id':'curves'})
            a,b,c=[{'uri':f'apple:songs:{i}'} for i in range(3)]
            store.put(key,[(a,b,dict(shape='custom',curve_point=[.3,.8]))])
            value=FlowPlans(store.path).get(key,a,b);self.assertEqual(value['curve_point'],[.3,.8])
            value['curve_point'][0]=.9
            self.assertEqual(store.get(key,a,b)['curve_point'],[.3,.8]);self.assertIsNone(store.get(key,b,c))
            self.assertEqual(recipe({})['curve_point'],[.5,.5])


if __name__=='__main__':unittest.main()
