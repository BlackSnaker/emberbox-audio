"""Voice upgrades, private runtime selection and short spoken radio links."""
import io,json,subprocess,sys,tempfile,unittest,importlib.util,signal,wave,array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import dj_setup
from dj_intent import Intent,MOODS
from dj_reply import spoken_reply
from dj_voice import DJVoice


class SpeechTests(unittest.TestCase):
    def test_russian_upgrade_needs_kseniya_not_the_old_voice_or_piper(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(dj_setup,'ROOT',Path(folder)):
            root=Path(folder);python=root/'runtime/bin/python';python.parent.mkdir(parents=True);python.touch()
            asr=root/'asr-ru/am/final.mdl';asr.parent.mkdir(parents=True);asr.touch()
            with (root/dj_setup.ASSETS['tts-ru'][3]).open('wb') as f:f.truncate(dj_setup.ASSETS['tts-ru'][2])
            marker=root/'voice-ru.json'
            marker.write_text(json.dumps({'version':1,'python':str(python),'voice':'ru_RU-irina-medium'}))
            self.assertFalse(dj_setup.ready('voice','ru'))
            marker.write_text(json.dumps({'version':1,'python':str(python),'voice':dj_setup.VOICES['ru']}))
            self.assertTrue(dj_setup.ready('voice','ru'))
            self.assertFalse((root/'piper').exists(),'Russian speech must not require the English synthesizer')
    def test_speech_uses_the_prepared_private_python(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'voice-ru.json').write_text(json.dumps({'python':'/private/voice/python'}))
            host=SimpleNamespace(source='spotify',sound=SimpleNamespace(muted=False,set_ducking=lambda _:None))
            voice=DJVoice(host,lambda *_:None,lambda *_:None)
            child=Mock(stdin=io.StringIO(),stdout=iter(()))
            with patch('dj_voice.ROOT',root),patch('dj_voice.ready',return_value=True),patch('dj_voice.subprocess.Popen',return_value=child) as popen,patch('dj_voice.threading.Thread'),patch('dj_voice.GLib.timeout_add',return_value=1):
                self.assertTrue(voice.launch('speak','ru','Теперь повеселее.'))
                self.assertEqual(popen.call_args.args[0][0],'/private/voice/python')
                self.assertEqual(json.loads(child.stdin.getvalue())['text'],'Теперь повеселее.')
    def test_tampered_torch_package_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'silero-v5_5_ru.pt').write_bytes(b'not a publisher model')
            worker=Path(__file__).resolve().parents[1]/'src/dj_voice_worker.py'
            result=subprocess.run([sys.executable,'-I',str(worker),'speak','--root',folder,'--language','ru','--output',str(root/'out.wav')],
                input=json.dumps({'text':'Привет.'}),text=True,capture_output=True,timeout=3)
            self.assertNotEqual(result.returncode,0);self.assertIn('voice-model-invalid',result.stdout)
    def test_spoken_links_are_short_localized_and_not_catalogue_diagnostics(self):
        for mood in MOODS:
            for language in ('ru','en'):
                value=spoken_reply(Intent(mood=mood),[{'uri':'apple:songs:1'}],language)
                self.assertLessEqual(len(value),200);self.assertNotIn('Apple',value);self.assertNotIn('14',value)
                if language=='ru':self.assertTrue(any('а'<=c.lower()<='я' for c in value))
        value=spoken_reply(Intent(artists=('The Beatles',),mode='artist'),[],'ru')
        self.assertIn('Битлз',value);self.assertNotIn('The Beatles',value)
    def test_mood_links_vary_with_the_set(self):
        variants={spoken_reply(Intent(mood='happy'),[{'uri':str(i)}],'ru') for i in range(20)}
        self.assertGreater(len(variants),1)
    @unittest.skipUnless(importlib.util.find_spec('torch'),'Optional CPU speech runtime not installed')
    def test_inference_tensor_audio_has_soft_edges_and_no_overload(self):
        import torch
        previous=signal.getsignal(signal.SIGTERM)
        try:
            from dj_voice_worker import write_pcm
        finally:signal.signal(signal.SIGTERM,previous)
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'voice.wav'
            with torch.inference_mode():audio=torch.linspace(-2,2,2400)
            write_pcm(audio,out)
            with wave.open(str(out)) as f:
                self.assertEqual(f.getframerate(),48000);self.assertEqual(f.getnframes(),2400)
                samples=array.array('h',f.readframes(f.getnframes()))
            self.assertEqual((samples[0],samples[-1]),(0,0));self.assertLessEqual(max(abs(v) for v in samples),30802)
            with self.assertRaisesRegex(ValueError,'voice-audio-invalid'):write_pcm(torch.tensor([float('nan')]*10),out)


if __name__=='__main__':unittest.main()
