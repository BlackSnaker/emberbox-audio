"""Measured stereo extrema, exact timing, cancellation and recipe bounds."""
import sys,time,threading,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flow_peaks import PeakBins,validate
from flow_waveforms import WaveformClient
from flow_plans import recipe,duration


class Peaks(unittest.TestCase):
    def test_single_sample_impulses_and_opposite_phase_stereo_survive(self):
        data=np.zeros((48000,2),np.float32);data[113,0]=1.;data[113,1]=-1.
        peaks=PeakBins(48000,1,12);peaks.add(data);value=validate(peaks.result())
        self.assertEqual(value['start'],12);self.assertTrue(any(a==-1 and b==1 for a,b,_ in value['bins']))
        self.assertEqual(value['covered'],1);self.assertLessEqual(len(value['bins']),1024)
    def test_chunks_do_not_shift_peak_bins_or_keep_full_pcm(self):
        data=np.random.default_rng(65).uniform(-.7,.7,(192000,2)).astype(np.float32)
        whole=PeakBins(192000,1);split=PeakBins(192000,1)
        whole.add(data)
        for i in range(0,len(data),997):split.add(data[i:i+997])
        self.assertEqual(whole.result(),split.result())
        self.assertLess(len(split.pending),split.hop);self.assertLess(split.pending.nbytes,4096)
        split.add(np.ones((10000,2),np.float32));self.assertEqual(split.result(),whole.result())
    def test_partial_coverage_is_not_stretched_into_a_complete_song(self):
        peaks=PeakBins(48000,32,100);peaks.add(np.ones((4800,2),np.float32)*.1)
        result=validate(peaks.result());self.assertEqual(result['covered'],.1);self.assertEqual(result['seconds'],32)
        self.assertLess(len(result['bins']),5)
        for value in ({},dict(result,evidence='artwork'),dict(result,covered=99),dict(result,bins=[[float('nan'),1,0]])):
            with self.assertRaises(ValueError):validate(value)
    def test_manual_thirty_second_mix_preserves_choice_and_auto_stays_bounded(self):
        self.assertEqual(duration(recipe(dict(mode='manual',seconds=30)),200,180),30)
        self.assertEqual(duration(recipe(dict(mode='manual',seconds=30)),200,20),18)
        self.assertEqual(duration(recipe({}),200,180),8)
        with self.assertRaises(ValueError):recipe(dict(seconds=30.1))


class Client(unittest.TestCase):
    def test_late_waveform_never_overwrites_the_new_pair(self):
        service=SimpleNamespace(host=SimpleNamespace(source='apple-music'))
        changed=Mock();client=WaveformClient(service,changed)
        try:
            old=client.generation;client.cancel();client.update(old,0,{'old':True},'ready')
            self.assertEqual(client.data,[None,None]);changed.assert_not_called()
        finally:client.close()
    def test_apple_requests_only_derived_peaks_and_releases_its_job(self):
        stop=threading.Event();stop.wait=Mock(return_value=False)
        bins=PeakBins(48000,1);bins.add(np.zeros((48000,2),np.float32));result=bins.result()
        player=Mock();player.state={'emberFlowPeaks':True}
        player.request.side_effect=lambda method,**p: {'phase':'ready','waveform':result} if p['operation']=='waveform-status' else {}
        client=WaveformClient(SimpleNamespace(host=SimpleNamespace(source='apple-music',apple_web=player)),Mock())
        try:
            self.assertEqual(client.apple({'uri':'apple:songs:123'},0,32,stop),result)
            operations=[call.kwargs['operation'] for call in player.request.call_args_list]
            self.assertEqual(operations,['waveform-start','waveform-status','waveform-cancel'])
            self.assertEqual(player.request.call_args_list[0].kwargs['role'],'out')
            self.assertEqual(player.request.call_args_list[0].kwargs['kind'],'songs')
        finally:client.close()


if __name__=='__main__':unittest.main()
