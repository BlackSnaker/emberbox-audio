"""Licensed stream boundaries, private recipes and original synthetic DSP."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mashup_catalog import Catalog,record,media_url,license_url
from mashup_projects import Projects,recipe
from mashup_dsp import RATE,analyse,decode,plan,render,separate,transform,waveform


def entry(license='https://creativecommons.org/licenses/by/4.0/'):
    return {'upload_id':123,'upload_name':'Original test song','user_name':'fixture','user_real_name':'Ember Sessions',
        'license_url':license,'upload_extra':{'bpm':120},'upload_tags':',acappella,',
        'files':[{'download_url':'https://ccmixter.org/content/fixture/fixture.mp3',
            'file_rawsize':1280,'file_format_info':{'ps':'1:30'}}]}


def project():
    return recipe({'name':'An original sketch','tracks':[{'source':'ccmixter','id':str(i),'role':role,'gain':.75}
        for i,role in [(123,'vocal'),(124,'instrumental')]],'length':5,'auto':False})


class MashupTests(unittest.TestCase):
    def test_only_explicit_by_and_owned_https_audio_is_admitted(self):
        result=record(entry());self.assertEqual(result['duration'],90);self.assertEqual(result['kind'],'vocal')
        for license in ['https://creativecommons.org/licenses/by-nc/4.0/',
            'https://creativecommons.org/licenses/by-nd/4.0/','https://example.org/licenses/by/4.0/','']:
            self.assertIsNone(record(entry(license)))
        for url in ['file:///etc/passwd','https://127.0.0.1/content/a/a.mp3',
            'https://ccmixter.org.evil.test/content/a/a.mp3','https://ccmixter.org/content/a/../x.mp3',
            'https://user:password@ccmixter.org/content/a/a.mp3','https://ccmixter.org/content/a/a.m3u8',
            'https://ccmixter.org:bad/content/a/a.mp3','https://[invalid/content/a/a.mp3']:
            self.assertEqual(media_url(url),'')

    def test_source_is_resolved_afresh_not_from_saved_decoder_urls(self):
        requests=[]
        def opener(request,timeout):
            requests.append(request.full_url);return io.BytesIO(json.dumps([entry()]).encode())
        catalog=Catalog(opener)
        first=catalog.search('voice');second=catalog.search('voice')
        self.assertEqual(len(requests),1);self.assertEqual(first,second)
        item=catalog.resolve({'source':'ccmixter','id':'123','url':'https://evil.test'})
        self.assertIn('ccmixter.org/content/',item['url']);self.assertEqual(len(requests),2)
        for source in ['spotify','apple-music','youtube','yandex-music']:
            with self.assertRaises(ValueError):catalog.resolve({'source':source,'id':'123'})

    def test_private_recipes_do_not_persist_audio_urls_or_tokens(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'projects.json';store=Projects(path);value=project()
            value['tracks'][0].update(url='https://private.test',token='account-secret',pcm='audio-blob')
            saved=store.save(value);text=path.read_text()
            for forbidden in ['private.test','account-secret','audio-blob','"url"']:self.assertNotIn(forbidden,text)
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(Projects(path).items[0]['id'],saved['id'])
            path.write_text('{damaged');broken=Projects(path)
            with self.assertRaises(ValueError):broken.save(value)
            self.assertEqual(path.read_text(),'{damaged')

    def test_full_project_store_preserves_existing_recipes(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Projects(Path(folder)/'recipes.json')
            for _ in range(24):store.save(project())
            before=store.path.read_bytes()
            with self.assertRaisesRegex(ValueError,'project-limit'):store.save(project())
            self.assertEqual(store.path.read_bytes(),before)
            value=store.items[0];value['name']='Updated';store.save(value)
            self.assertEqual(len(store.items),24)

    def test_decoder_uses_anonymous_audio_and_rejects_redirects_size_and_cancel(self):
        item=record(entry());payload=b'fixture'
        class Response(io.BytesIO):
            def __init__(self):
                super().__init__(payload);self.url=item['url'];self.headers={'Content-Length':str(len(payload))}
        commands=[]
        def run(command,stop,**kwargs):
            commands.append(command)
            self.assertIn('-protocol_whitelist',command)
            self.assertEqual(os.read(kwargs['pass_fds'][0],len(payload)),payload)
            os.write(kwargs['stdout'],np.zeros((48,2),np.float32).tobytes())
        with patch('mashup_dsp.shutil.which',return_value='/fixture/ffmpeg'),\
             patch('mashup_dsp.process',side_effect=run),\
             patch('mashup_dsp.urllib.request.build_opener') as build:
            build.return_value.open.side_effect=lambda *_a,**_kw:Response()
            pcm=decode(item,threading.Event(),start=1,duration=5)
            self.assertEqual(pcm.shape,(48,2));self.assertIn('5',commands[0])
            redirect=build.call_args.args[0]()
            with self.assertRaisesRegex(ValueError,'media-redirect-invalid'):
                redirect.redirect_request(None,None,302,'',{},'https://127.0.0.1/private')
            response=Response();response.headers['Content-Length']=str(51*1024*1024)
            build.return_value.open.side_effect=None;build.return_value.open.return_value=response
            with self.assertRaisesRegex(ValueError,'media-too-large'):decode(item,threading.Event())
            build.return_value.open.return_value=Response();stop=threading.Event();stop.set()
            with self.assertRaises(InterruptedError):decode(item,stop)

    def test_recipe_sanitizes_nonfinite_controls_and_bounds(self):
        value=project();value.update(tempo=float('nan'),offset=1e9,shift=-99)
        result=recipe(value)
        self.assertEqual(result['tempo'],0);self.assertEqual(result['offset'],10);self.assertEqual(result['shift'],-6)

    def test_plan_resolves_half_time_and_keeps_uncertain_key_unshifted(self):
        a={'beat':{'bpm':60,'phase':.15,'confidence':.9},'key':{'root':0,'confidence':.9,'margin':.2}}
        b={'beat':{'bpm':120,'phase':.05,'confidence':.9},'key':{'root':2,'confidence':.9,'margin':.2}}
        result=plan(a,b,{'auto':True})
        self.assertEqual(result['rates'],[1,1]);self.assertEqual(result['shift'],-2)
        self.assertAlmostEqual(result['offset'],.1)
        b['key']['margin']=.001;self.assertEqual(plan(a,b,{'auto':True})['shift'],0)
        b['beat']['bpm']=93
        with self.assertRaises(ValueError):plan(a,b,{'auto':True})

    def test_mix_is_stereo_finite_peak_safe_and_has_no_hard_join(self):
        t=np.arange(RATE*6)/RATE
        a=np.column_stack((np.sin(2*np.pi*220*t),np.sin(2*np.pi*330*t))).astype(np.float32)
        b=a*.8;value=project();value['tracks'][0]['gain']=value['tracks'][1]['gain']=1.5
        mixed,attenuation=render(a,b,value,{'offset':.01})
        self.assertEqual(mixed.shape,(RATE*5,2));self.assertLessEqual(np.abs(mixed).max(),.980001)
        self.assertLess(attenuation,1);self.assertTrue(np.isfinite(mixed).all())
        self.assertFalse(np.allclose(mixed[:,0],mixed[:,1]));self.assertAlmostEqual(float(mixed[0,0]),0)
        value['whole']=True;whole,_=render(a,b[:RATE*3],value,{'offset':0})
        self.assertEqual(len(whole),len(a));self.assertLess(abs(float(whole[-1,0])),1e-5)
        self.assertEqual(len(waveform(mixed)),256)

    def test_provided_stems_skip_model_and_overlap_estimates_preserve_signal(self):
        pcm=np.random.default_rng(4).uniform(-.2,.2,(RATE*3,2)).astype(np.float32)
        self.assertIs(separate(pcm,'vocal','vocal',threading.Event()),pcm)
        class Separator:
            def vocals(self,pcm):return pcm*.4
        vocal=separate(pcm,'vocal','song',threading.Event(),separator=Separator())
        instrumental=separate(pcm,'instrumental','song',threading.Event(),separator=Separator())
        np.testing.assert_allclose(vocal,pcm*.4,atol=2e-6)
        np.testing.assert_allclose(vocal+instrumental,pcm,atol=2e-6)
        stop=threading.Event();stop.set()
        with self.assertRaises(InterruptedError):separate(pcm,'vocal','song',stop,separator=Separator())


if __name__=='__main__':unittest.main()
