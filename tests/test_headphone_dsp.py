"""Real streaming filters, their limits, switches and exact unprocessed path."""
import hashlib,json,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scipy.signal import sosfreqz,resample_poly
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from headphone_profiles import catalogue,settings
from headphone_dsp import Chain,HeadphoneProcessor,biquad
from hrtf_store import sofa_bytes
from spatial_mixer import Mixer


class HeadphoneTests(unittest.TestCase):
    def stream(self,p,x,block=960):
        return np.concatenate([p.process(x[i:i+block]) for i in range(0,len(x),block)])

    def test_catalogue_distinguishes_measured_profiles_from_unmeasured_buds4(self):
        rows=catalogue();self.assertEqual(len({p['id'] for p in rows}),len(rows))
        self.assertEqual(sum(p.get('measured',False) for p in rows),10)
        buds=next(p for p in rows if p['id']=='buds4-pro');self.assertFalse(buds['measured']);self.assertEqual(buds['filters'],[])
        for p in rows:
            if p.get('measured'):
                self.assertRegex(p['source'],r'github.com/jaakkopasanen/AutoEq/blob/[a-f0-9]{40}/')
                self.assertRegex(p['sha256'],r'^[a-f0-9]{64}$')

    def test_default_and_buds4_original_preserve_every_float_and_stereo_image(self):
        x=np.random.default_rng(12).uniform(-.9,.9,(24000,2)).astype('<f4')
        for rate in (48000,192000):
            p=HeadphoneProcessor(rate);p.configure({'mode':'headphones','headphones':{'profile':'buds4-pro'}})
            output=self.stream(p,np.concatenate((x,np.zeros((p.lookahead,2)))))
            np.testing.assert_array_equal(output[p.lookahead:],x)

    def test_speaker_mode_cannot_apply_a_saved_headphone_correction(self):
        c=Chain({'mode':'speakers','headphones':{'profile':'buds3-pro','bass':4}},48000)
        x=np.ones((50,2))*.1;self.assertFalse(c.active);np.testing.assert_array_equal(c.process(x),x)

    def test_rbj_peak_and_shelf_response_matches_requested_db_at_both_rates(self):
        for rate in (48000,192000):
            for kind,frequency,measure in [('PK',1000,1000),('LSC',140,1),('HSC',4500,rate/2-1)]:
                for gain in (-4,4):
                    _,h=sosfreqz([biquad(kind,frequency,gain,.7071,rate)],worN=[measure],fs=rate)
                    self.assertAlmostEqual(float(20*np.log10(abs(h[0]))),gain,places=3)

    def test_every_measured_preset_is_stable_and_retains_digital_headroom(self):
        for rate in (48000,192000):
            for p in catalogue():
                c=Chain({'mode':'headphones','headphones':{'profile':p['id'],'bass':4,'treble':4}},rate)
                for row in c.sos:self.assertLess(max(abs(np.roots(row[3:]))),1)
                _,h=sosfreqz(c.sos,worN=131072,fs=rate)
                self.assertLess(float(max(abs(h))*c.gain),.85)

    def test_dry_comparison_has_same_headroom_and_never_changes_the_head_model(self):
        value={'profile':'airpods-pro-2','bass':2,'bypass':True}
        c=Chain({'mode':'headphones','hrtf':1,'headphones':value},48000)
        original=Chain({'mode':'headphones','hrtf':0,'headphones':{**value,'bypass':False}},48000)
        self.assertEqual(c.gain,original.gain)
        x=np.random.default_rng(2).uniform(-.1,.1,(777,2))
        np.testing.assert_array_equal(c.process(x),x*c.gain)

    def test_filter_state_and_delay_cross_arbitrary_buffer_boundaries(self):
        x=np.random.default_rng(1).normal(0,.01,(24000,2))
        def make():
            p=HeadphoneProcessor(48000);p.configure({'mode':'headphones','headphones':{'profile':'buds2-pro'}});return p
        a=self.stream(make(),x,960);b=self.stream(make(),x,777)
        np.testing.assert_allclose(a,b,atol=1e-7)

    def test_limiter_preserves_ear_ratio_and_catches_true_peaks_without_hard_clipping(self):
        for rate in (48000,192000):
            t=np.arange(rate)/rate
            mono=np.sin(2*np.pi*11025*t+np.pi/4)*np.where(t<.5,.05,3.)
            x=np.column_stack((mono,mono*.31))
            p=HeadphoneProcessor(rate);p.configure({'mode':'headphones','headphones':{'bass':1}})
            out=self.stream(p,x,rate//50)
            self.assertTrue(np.isfinite(out).all());self.assertLess(float(abs(out).max()),.90)
            np.testing.assert_allclose(out[:,1],out[:,0]*.31,atol=2e-7)
            self.assertLess(float(abs(resample_poly(out[rate//2+100:-100],4,1,axis=0)).max()),1.)

    def test_fades_accept_latest_change_without_filter_restarts_or_clicks(self):
        rate=48000;p=HeadphoneProcessor(rate);values=[]
        for n in range(100):
            if n in (10,12,14,16):p.configure({'mode':'headphones','headphones':{'bass':4 if n==16 else -4,'treble':1}})
            t=(np.arange(960)+n*960)/rate;x=np.column_stack((np.sin(2*np.pi*100*t),)*2)*.15
            values.append(p.process(x))
        out=np.concatenate(values)
        self.assertLess(float(abs(np.diff(out[:,0])).max()),.004)
        self.assertEqual(p.chain.value['bass'],4);self.assertIsNone(p.old);self.assertIsNone(p.pending)

    def test_validation_rejects_wrong_models_nonfinite_and_out_of_range_settings(self):
        for bad in ({'profile':'buds4-pro-fake-eq'},{'bass':8},{'strength':float('nan')},{'treble':True},{'bypass':'yes'}):
            with self.assertRaises(ValueError):settings(bad)
        with self.assertRaises(ValueError):HeadphoneProcessor(48000).process(np.array([[np.inf,0]]))

    def test_cold_filter_design_does_not_block_or_discard_the_first_song_samples(self):
        m=Mixer(lambda _:None);started=threading.Event();release=threading.Event()
        def design(scene):started.set();release.wait(2);return {'active':True}
        with patch.object(m.headphones,'configure',side_effect=design):
            m.control({'type':'headphones','scene':{'mode':'headphones'}})
            self.assertTrue(started.wait(1))
            m.control({'type':'slot','slot':0,'generation':1})
            m.received(0,1,np.ones((960,2),np.float32).tobytes())
            self.assertEqual(m.slots[0].received,960)
            release.set();m.control({'type':'stop'});m.headphone_thread.join(2)
            self.assertFalse(m.headphone_thread.is_alive())

    def test_imported_sofa_must_match_its_digest_and_cannot_escape_private_folder(self):
        with tempfile.TemporaryDirectory() as tmp,patch('hrtf_store.ROOT',Path(tmp)):
            data=b'fixture';ident=hashlib.sha256(data).hexdigest();file=Path(tmp)/(ident+'.sofa');file.write_bytes(data)
            self.assertEqual(sofa_bytes(ident),data);file.write_bytes(b'changed')
            with self.assertRaises(ValueError):sofa_bytes(ident)
            for bad in ('../profile','x'*64):
                with self.assertRaises(ValueError):sofa_bytes(bad)


if __name__=='__main__':unittest.main()
