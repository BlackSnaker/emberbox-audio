from pathlib import Path
import sys,unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from audio_quality import describe,current,has_track


class QualityTests(unittest.TestCase):
    def test_selected_paused_song_does_not_need_a_duration_for_quality(self):
        host=SimpleNamespace(source='apple-music',apple_mode='native',length=0,playing=False,
            apple_web=SimpleNamespace(state={'id':'123','title':'Paused song','duration':0}))
        self.assertTrue(has_track(host))
        self.assertFalse(current(host)['known'])
        host.apple_web.state={'id':'-1'};self.assertFalse(has_track(host))
        host.apple_web.state={'title':'Restoring song'};self.assertTrue(has_track(host))
        host.apple_web.state={};self.assertFalse(has_track(host))
        host.source='spotify';host.session=None;self.assertFalse(has_track(host))
        host.session=SimpleNamespace(metadata={'xesam:title':'Live song'})
        self.assertTrue(has_track(host))

    def test_catalogue_never_becomes_playback_evidence(self):
        value=describe({'availableFormats':['dolby-atmos','hi-res-lossless','lossless'],
                        'audioQuality':{'codec':'flac','sampleRate':192000}})
        self.assertFalse(value['known']);self.assertEqual(value['name'],'')
        self.assertIn('Dolby Atmos',value['available'])
    def test_verified_aac_and_lossless_have_different_badges(self):
        value=describe({'audioQuality':{'codec':'aac','sampleRate':44100,'channels':2,'evidence':'decoder'},
                        'availableFormats':['dolby-atmos','lossless']})
        self.assertEqual(value['name'],'AAC');self.assertIn('44',value['badge'])
        self.assertNotIn('Lossless',value['badge']);self.assertNotIn('Atmos',value['badge'])
        for rate,name in ((44100,'Lossless'),(48000,'Lossless'),(96000,'Hi‑Res Lossless')):
            q=describe({'audioQuality':{'codec':'alac','sampleRate':rate,'evidence':'decoder'}})
            self.assertEqual(q['name'],name)
    def test_eac3_and_multichannel_do_not_imply_atmos(self):
        q=describe({'audioQuality':{'codec':'eac3','channels':6,'sampleRate':48000,'evidence':'decoder'}})
        self.assertEqual(q['name'],'Dolby Digital Plus')
        for codec in ('aac','pcm','flac'):
            q=describe({'audioQuality':{'codec':codec,'variant':'dolby-atmos','evidence':'decoder'}})
            self.assertNotEqual(q['name'],'Dolby Atmos')
        q=describe({'audioQuality':{'codec':'eac3','variant':'dolby-atmos','evidence':'catalogue'}})
        self.assertFalse(q['known'])
        q=describe({'audioQuality':{'codec':'eac3','variant':'dolby-atmos','evidence':'decoder'}})
        self.assertEqual(q['name'],'Dolby Atmos')
    def test_native_binaural_details_and_preparation_are_explicit(self):
        q=describe({'audioQuality':{'codec':'eac3','variant':'dolby-atmos','evidence':'decoder','renderer':'openjoc-binaural','channels':2,'sampleRate':48000}})
        self.assertEqual(q['name'],'Dolby Atmos')
        self.assertNotIn('Stereo',q['details']);self.assertNotIn('Стерео',q['details'])
        self.assertIn('PCM',q['details']);self.assertIn('2',q['details'])
        waiting=describe({'spatial':{'enabled':True,'phase':'preparing'},'audioQuality':{'codec':'aac','evidence':'decoder'}})
        self.assertFalse(waiting['known']);self.assertEqual(waiting['name'],'')
        self.assertNotIn(' · ',waiting['details'])
    def test_maximum_preference_cannot_invent_quality(self):
        q=describe({'qualityPreference':{'mode':'maximum','applied':True}})
        self.assertFalse(q['known']);self.assertNotEqual(q['policy'],'')
        self.assertNotIn('Lossless',q['badge'])
    def test_malformed_fields_are_ignored(self):
        q=describe({'audioQuality':{'codec':'aac','sampleRate':'nan','channels':{},'bitrate':float('inf'),'evidence':'mpv'},'availableFormats':{}})
        self.assertEqual(q['details'],'AAC');self.assertEqual(q['available'],[])
        self.assertFalse(describe({'audioQuality':[]})['known'])
    def test_source_switch_cannot_leak_native_quality_to_mpris(self):
        host=SimpleNamespace(source='apple-music',apple_mode='native',
            apple_web=SimpleNamespace(state={'audioQuality':{'codec':'aac','evidence':'decoder'}}))
        self.assertEqual(current(host)['name'],'AAC')
        host.source='spotify';self.assertFalse(current(host)['known'])
        host.source='apple-music';host.apple_mode='browser';self.assertFalse(current(host)['known'])
        host.source='youtube';host.youtube_mode='native';host.youtube=SimpleNamespace(loaded=False,quality={'codec':'opus','evidence':'mpv'})
        self.assertFalse(current(host)['known']);host.youtube.loaded=True
        self.assertEqual(current(host)['name'],'Opus')


if __name__=='__main__':unittest.main()
