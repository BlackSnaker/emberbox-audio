"""Original synthetic PCM and fake routes; never use desktop audio."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from karaoke_audio import VocalFilter,KaraokeAudio,restore,recover,RATE,SIZE,HOP,PREFIX
from stream_target import Target,matches


def render(pcm,amount):
    processor=VocalFilter(amount)
    return np.concatenate([processor.process(pcm[i:i+HOP]) for i in range(0,len(pcm),HOP)])


class AudioTests(unittest.TestCase):
    def test_bypass_is_delayed_identity_without_volume_gain(self):
        rng=np.random.default_rng(12)
        pcm=rng.uniform(-.35,.35,(HOP*70,2))
        output=render(pcm,0)
        latency=SIZE-HOP
        np.testing.assert_allclose(output[SIZE:],pcm[SIZE-latency:-latency],atol=1e-6)

    def test_centre_voice_reduced_bass_and_side_preserved(self):
        t=np.arange(HOP*140)/RATE
        bass=.12*np.sin(2*np.pi*70*t)
        centre=.15*np.sin(2*np.pi*1000*t)
        side=.1*np.sin(2*np.pi*3000*t)
        original=np.column_stack((bass+centre+side,bass+centre-side))
        output=render(original,1.)[RATE:]
        delayed=original[RATE-(SIZE-HOP):-(SIZE-HOP)]
        def amplitude(pcm,freq):
            times=np.arange(len(pcm))/RATE
            return abs(np.sum(pcm[:,0]*np.exp(-2j*np.pi*freq*times)))*2/len(pcm)
        self.assertLess(amplitude(output,1000)/amplitude(delayed,1000),.1)
        for freq in (70,3000):self.assertAlmostEqual(amplitude(output,freq)/amplitude(delayed,freq),1.,delta=.04)
        self.assertLess(np.max(np.abs(output)),1.)

    def test_live_strength_change_is_smoothed_and_nonfinite_pcm_is_silent(self):
        processor=VocalFilter(0.)
        t=np.arange(HOP*200)/RATE
        signal=.3*np.sin(2*np.pi*1000*t)
        pcm=np.column_stack((signal,signal));chunks=[]
        for i in range(200):
            if i==100:processor.target=1.
            chunks.append(processor.process(pcm[i*HOP:(i+1)*HOP]))
        output=np.concatenate(chunks)
        self.assertLess(np.max(np.abs(np.diff(output[:,0]))),.06)
        self.assertLess(np.std(output[-HOP*10:]),np.std(output[HOP*80:HOP*90])*.12)
        bad=processor.process(np.full((HOP,2),np.nan))
        self.assertTrue(np.isfinite(bad).all())

    def test_return_stream_can_never_match_native_player(self):
        target=Target('youtube',os.getpid(),'','fixture')
        props={'application.process.id':str(os.getpid()),'emberbox.karaoke':'true'}
        self.assertFalse(matches(props,target))
        self.assertTrue(matches({'application.process.id':str(os.getpid())},target))

    def test_quick_reenable_waits_for_old_route_cleanup_and_source_change_cancels(self):
        with patch('karaoke_audio.shutil.which',return_value=None):audio=KaraokeAudio()
        audio.available=True;old=Mock();audio.process=old
        target=Target('youtube',123,'','fixture')
        audio.disable()
        with patch('karaoke_audio.subprocess.Popen') as spawn:
            audio.enable(target)
            spawn.assert_not_called()
            self.assertTrue(audio.starting)
            self.assertEqual(audio.pending,target)
            with patch.object(audio,'enable') as enabled:
                audio._ended(old);enabled.assert_called_once_with(target)
        audio.process=old;audio.disable();audio.enable(target)
        audio.check_target(Target('spotify',0,'','other-fixture'))
        with patch.object(audio,'enable') as enabled:
            audio._ended(old);enabled.assert_not_called()
        audio.close()

    def test_restore_only_temporary_sink_and_own_module(self):
        name=PREFIX+'99999999';calls=[]
        def server(*args,**kwargs):
            calls.append(args)
            if args==('list','sinks'):return [{'index':1,'name':'headphones'},{'index':2,'name':name,'owner_module':456}]
            if args==('get-default-sink',):return 'headphones'
            if args==('list','sink-inputs'):return [{'index':7,'sink':2},{'index':8,'sink':1}]
            if args==('list','modules'):return [
                {'index':123,'name':'module-null-sink','argument':'sink_name=somebody_else'},
                {'name':'module-null-sink','argument':'sink_name='+name}]
            return ''
        with patch('karaoke_audio.pactl',side_effect=server):
            restore({'name':name,'routes':{'7':'headphones','8':'headphones'}})
        self.assertIn(('move-sink-input','7','headphones'),calls)
        self.assertNotIn(('move-sink-input','8','headphones'),calls)
        self.assertIn(('unload-module','456'),calls)
        self.assertNotIn(('unload-module','123'),calls)

    def test_journal_recovery_skips_living_worker_and_foreign_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            dead={'pid':99999999,'name':PREFIX+'99999999','routes':{}}
            living={'pid':os.getpid(),'name':PREFIX+str(os.getpid()),'routes':{}}
            for i,state in enumerate((dead,living,{'pid':99999998,'name':'other-sink'})):
                (root/f'route-{i}.json').write_text(json.dumps(state))
            with patch('karaoke_audio.runtime',return_value=root),patch('karaoke_audio.restore') as restored:
                recover();restored.assert_called_once_with(dead)
            self.assertFalse((root/'route-0.json').exists())
            self.assertTrue((root/'route-1.json').exists())


if __name__=='__main__':unittest.main()
