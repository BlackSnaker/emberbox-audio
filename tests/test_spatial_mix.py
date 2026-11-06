import sys,unittest,time,threading
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spatial_mix import blend,curve,RATE,BLOCK
from spatial_mixer import Mixer

class SpatialMixTests(unittest.TestCase):
    def test_manual_selection_releases_an_already_buffered_auto_preroll(self):
        events=[];m=Mixer(events.append)
        m.configure({'slot':0,'generation':1});m.configure({'slot':1,'generation':2})
        m.received(0,1,np.zeros((RATE,2),np.float32).tobytes());m.received(1,2,np.ones((RATE//5,2),np.float32).tobytes())
        before=m.slots[1].frames;self.assertFalse(m.slots[1].ready)
        m.control({'type':'preroll','slot':1,'generation':2,'seconds':.16})
        self.assertTrue(m.slots[1].ready);self.assertEqual(m.slots[1].frames,before)
        m.control({'type':'transition','manual':True,'duration':.22,'key':'manual'})
        self.assertIsNotNone(m.render())

    def test_manual_handover_uses_short_preroll_and_a_click_free_envelope(self):
        events=[];m=Mixer(events.append)
        m.configure({'slot':0,'generation':1});m.configure({'slot':1,'generation':2,'preroll':.4})
        m.received(0,1,np.full((RATE,2),-.5,np.float32).tobytes())
        m.received(1,2,np.full((RATE//2,2),.5,np.float32).tobytes())
        self.assertTrue(m.slots[1].ready);self.assertFalse(m.slots[0].ready)
        with self.assertRaises(ValueError):m.control({'type':'transition','duration':8,'key':'automatic'})
        m.control({'type':'transition','duration':.22,'key':'manual','manual':True})
        audio=np.frombuffer(b''.join(m.render() for _ in range(11)),'<f4').reshape(-1,2)
        self.assertAlmostEqual(float(audio[0,0]),-.5);self.assertAlmostEqual(float(audio[-1,0]),.5)
        self.assertLess(float(abs(np.diff(audio[:,0])).max()),.001)
        self.assertLessEqual(float(abs(audio).max()),.5)
    def test_chunk_boundaries_preserve_the_exact_envelope_and_peak_headroom(self):
        n=RATE*2;t=np.arange(n,dtype=np.float32)/RATE
        a=np.column_stack((np.sin(2*np.pi*220*t),np.sin(2*np.pi*441*t))).astype(np.float32)
        b=np.column_stack((np.sin(2*np.pi*330*t),np.sin(2*np.pi*550*t))).astype(np.float32)
        whole=blend(a,b,0,n)
        split=np.concatenate([blend(a[p:p+997],b[p:p+997],p,n) for p in range(0,n,997)])
        np.testing.assert_array_equal(whole,split)
        self.assertTrue(np.isfinite(whole).all());self.assertLessEqual(float(abs(whole).max()),1.)
        np.testing.assert_allclose(blend(a,a,0,n),a,atol=1.2e-7)
        np.testing.assert_allclose(whole[0],a[0]);np.testing.assert_allclose(whole[-1],b[-1])
    def test_three_phases_have_smooth_boundaries(self):
        for at in (0.,.38,.62,1.):
            delta=1e-5
            self.assertLess(abs(float(curve(at+delta)-curve(at-delta))),1e-9)
        self.assertAlmostEqual(float(curve(.5)),.5)

    def test_automatic_flow_retains_both_actual_signals_through_the_shared_phrase(self):
        n=RATE*4;t=np.arange(n)/RATE
        a=np.column_stack([.2*np.sin(t*2*np.pi*220)]*2).astype(np.float32)
        b=np.column_stack([.2*np.sin(t*2*np.pi*440)]*2).astype(np.float32)
        events=[];m=Mixer(events.append)
        for slot,pcm in enumerate((a,b)):
            m.configure({'slot':slot,'generation':slot+1});m.received(slot,slot+1,pcm.tobytes())
        m.control({'type':'transition','duration':4,'key':'shared'})
        output=np.frombuffer(b''.join(m.render() for _ in range(200)),'<f4').reshape(-1,2)
        self.assertTrue(np.isfinite(output).all());self.assertLessEqual(abs(output).max(),.2)
        # Measure the real rendered tones in three separate middle windows.
        for at in (1.5,1.9,2.3):
            block=output[round(at*RATE):round((at+.15)*RATE),0];axis=(at+np.arange(len(block))/RATE)
            levels=[2*abs(np.dot(block,np.exp(-2j*np.pi*hz*axis)))/len(block) for hz in (220,440)]
            self.assertGreater(min(levels),.2*.38,(at,levels))
        np.testing.assert_allclose(output[-1],b[-1],atol=2e-7)

    def test_shared_phrase_has_smooth_boundaries_and_cancellation_keeps_its_level(self):
        for at in (0.,.36,.64,1.):
            self.assertLess(abs(float(curve(at+1e-5,flow=True)-curve(at-1e-5,flow=True))),1e-9)
        m=Mixer(lambda _:None)
        for slot,gain in enumerate((.2,.7)):
            m.configure({'slot':slot,'generation':slot+1})
            m.received(slot,slot+1,np.full((RATE*3,2),gain,np.float32).tobytes())
        m.control({'type':'transition','duration':2,'key':'cancel'})
        for _ in range(40):m.render()
        gain=float(curve(m.frames/(m.fade['length']-1),flow=True))
        expected=.2*(1-gain)+.7*gain
        m.control({'type':'cancel','keep':0})
        self.assertFalse(m.fade['flow']);self.assertAlmostEqual(float(np.frombuffer(m.render(),'<f4')[0]),expected,places=6)
    def test_custom_smooth_recipe_renders_pcm_and_cancels_at_the_actual_gain(self):
        m=Mixer(lambda _:None)
        for slot,gain in enumerate((.2,.7)):
            m.configure({'slot':slot,'generation':slot+1})
            m.received(slot,slot+1,np.full((RATE*3,2),gain,np.float32).tobytes())
        m.control({'type':'transition','duration':2,'key':'custom','shape':'smooth'})
        for _ in range(35):m.render()
        x=m.frames/(m.fade['length']-1);gain=float(curve(x,flow=True,shape='smooth'))
        expected=.2*(1-gain)+.7*gain
        m.control({'type':'cancel','keep':0})
        block=np.frombuffer(m.render(),'<f4')
        self.assertAlmostEqual(float(block[0]),expected,places=6)
        self.assertTrue(np.isfinite(block).all());self.assertLessEqual(float(abs(block).max()),.7)

    def test_old_pcm_generation_cannot_leak_into_a_reused_slot(self):
        m=Mixer(lambda _:None);m.configure({'slot':1,'generation':2})
        m.received(1,1,np.ones((BLOCK,2),np.float32).tobytes())
        self.assertEqual(m.slots[1].received,0)
    def test_real_mixer_promotes_and_releases_the_outgoing_slot(self):
        events=[];m=Mixer(events.append)
        for slot in (0,1):
            m.configure({'slot':slot,'generation':slot+1})
            m.received(slot,slot+1,np.full((RATE*2,2),.5 if slot else -.5,np.float32).tobytes())
        m.control({'type':'transition','duration':.2,'key':'test'})
        chunks=[m.render() for _ in range(10)]
        audio=np.frombuffer(b''.join(chunks),'<f4').reshape(-1,2)
        self.assertAlmostEqual(float(audio[0,0]),-.5);self.assertAlmostEqual(float(audio[-1,0]),.5)
        self.assertLess(float(abs(np.diff(audio[:,0])).max()),.001)
        class Player:time_pos=.25
        m.player=Player();thread=threading.Thread(target=m.watch);thread.start();time.sleep(.18);m.stopped=True;thread.join()
        self.assertTrue(any(e['type']=='flow-started' for e in events));self.assertTrue(any(e['type']=='released' for e in events))
        self.assertEqual(m.current,1);self.assertIsNone(m.slots[0]);self.assertIsNotNone(m.render())
    def test_shorter_outgoing_tail_cannot_stall_a_transition(self):
        m=Mixer(lambda _:None)
        for slot in (0,1):
            m.configure({'slot':slot,'generation':slot+1})
            m.received(slot,slot+1,np.full((RATE,2),.1,np.float32).tobytes())
        m.control({'type':'transition','duration':.5,'key':'tail'})
        # EOF can become known after the transition was scheduled.
        m.slots[0].parts.clear();m.slots[0].frames=0;m.slots[0].total=0
        for _ in range(25):self.assertIsNotNone(m.render())
        self.assertTrue(m.fade['rendered']);self.assertEqual(m.current,1)
    def test_finish_is_flushed_without_cutting_the_last_pcm_packet(self):
        m=Mixer(lambda _:None);m.configure({'slot':0,'generation':1})
        m.received(0,1,np.ones((777,2),np.float32).tobytes())
        m.control({'type':'end','slot':0,'generation':1,'frames':777})
        self.assertEqual(len(m.render()),777*8)
        self.assertEqual(m.render(),bytes(BLOCK*8))
        self.assertEqual(m.slots[0].consumed,777)

if __name__=='__main__':unittest.main()
