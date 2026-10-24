"""Free-form routing, context, grounded targets and cancellable local inference."""
import json,sys,tempfile,threading,time,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dj_intent import Intent,local_intent,quick_wish
from dj_semantics import decode,follows,caption_for
from dj_brain import LocalBrain
from dj_model_client import request
from dj_reply import summary


class SemanticTests(unittest.TestCase):
    def test_short_or_keyword_containing_descriptions_still_need_semantics(self):
        for value in ('Дождливый вечер','Тёплое виниловое радио','Хочу спокойную музыку как в зимнем лесу',
                      'Как в старом джазовом баре','Нужно что-то, от чего хочется прыгать по комнате'):
            with self.subTest(value=value):self.assertFalse(quick_wish(value))
        for value in ('Beatles','Найди Let It Happen','Хочу джаз','Спокойную музыку','как Tame Impala','без вокала'):
            with self.subTest(value=value):self.assertTrue(quick_wish(value))
    def test_semantics_compiles_a_playlist_search_not_a_literal_title(self):
        prompt='Хочу будто оказаться в старом джазовом баре'
        i=decode({'kind':'mix','query':'jazz lounge, swing, vintage piano'},prompt,None,local_intent(prompt))
        self.assertEqual(i.search,'jazz lounge');self.assertEqual(i.query,'');self.assertEqual(i.mode,'mix')
        self.assertTrue(i.caption);self.assertLessEqual(len(i.caption),64)
        localized=decode({'kind':'mix','query':'vintage jazz'},'Старый джазовый бар',None,local_intent('Старый джазовый бар'))
        self.assertNotIn('jazz',summary(localized).split(' · '))
    def test_context_and_explicit_voice_constraints(self):
        base=Intent(search='rainy night jazz',caption='Rainy night',genres=('jazz',))
        prompt='А теперь в этом же духе, но чтобы никто не пел'
        i=decode({'kind':'mix','query':'instrumental jazz'},prompt,base,local_intent(prompt,base))
        self.assertTrue(i.instrumental);self.assertEqual(i.search,base.search);self.assertEqual(i.genres,('jazz',))
        prompt='same feeling, but bring the singing back'
        j=decode({'kind':'mix','query':'jazz with vocals'},prompt,i,local_intent(prompt,i))
        self.assertFalse(j.instrumental);self.assertEqual(j.search,base.search)
        prompt='А теперь верни вокал'
        j=decode({'kind':'mix','query':'jazz with vocals'},prompt,i,local_intent(prompt,i))
        self.assertFalse(j.instrumental);self.assertEqual(j.search,base.search)
    def test_new_requests_release_previous_atmosphere_and_constraints(self):
        previous=Intent(search='winter ambient',caption='Winter',genres=('ambient',),instrumental=True)
        prompt='Нужно что-то, от чего хочется прыгать по комнате'
        self.assertFalse(follows(prompt))
        i=decode({'kind':'mix','query':'energetic dance'},prompt,previous,local_intent(prompt,previous))
        self.assertEqual(i.search,'energetic dance');self.assertEqual(i.genres,());self.assertIsNone(i.instrumental)
    def test_fully_covered_voice_changes_do_not_wait_for_a_model(self):
        b=LocalBrain();base=Intent(search='vintage jazz',caption='Vintage',genres=('jazz',))
        try:
            with patch.object(b,'native',side_effect=AssertionError('A known constraint started inference')):
                for prompt in ('В том же духе, но чтобы никто не пел','А теперь без пения','same feeling, but without singing'):
                    i,e=b.interpret(prompt,base)
                    self.assertEqual(e,'local');self.assertTrue(i.instrumental);self.assertEqual(i.search,base.search)
                i,e=b.interpret('А теперь верни вокал',i)
                self.assertEqual(e,'local');self.assertFalse(i.instrumental);self.assertEqual(i.search,base.search)
        finally:b.close()
    def test_names_cannot_be_invented_and_moods_cannot_become_titles(self):
        for data,prompt in (({'kind':'artist','query':'Norah Jones'},'Уютный вечер'),
                            ({'kind':'track','query':'Дождливый вечер'},'Дождливый вечер'),
                            ({'kind':'artist','query':'ai'},'rain')):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):decode(data,prompt,None,local_intent(prompt))
        i=decode({'kind':'artist','query':'The Beatles'},'Песни Битлз',None,local_intent('Песни Битлз'))
        self.assertEqual(i.mode,'artist');self.assertEqual(i.artists,('The Beatles',))
    def test_a_new_scene_does_not_inherit_genres_from_a_conversational_opening(self):
        b=LocalBrain();base=Intent(search='old jazz bar',genres=('jazz',),instrumental=True)
        try:
            with patch('dj_brain.ready',return_value=False),patch.object(b,'models',return_value=['fixture']),patch.object(b,'generate',return_value={'message':{'content':json.dumps({'kind':'mix','query':'energetic dance'})}}):
                i,e=b.interpret('Давай что-нибудь, от чего хочется прыгать по комнате',base)
                self.assertEqual(e,'ai');self.assertEqual(i.genres,());self.assertIsNone(i.instrumental)
        finally:b.close()
    def test_model_instructions_ids_and_account_questions_are_not_forwarded(self):
        for query in ('spotify:track:123','https://example.com','English playlist keywords'):
            with self.assertRaises(ValueError):decode({'kind':'mix','query':query},'Музыку',None,Intent())
        i=decode({'kind':'clarify','query':'What is your password?'},'???',None,Intent())
        self.assertNotIn('password',i.question);self.assertEqual(i.action,'clarify')
    def test_missing_model_or_disabled_ai_does_not_search_the_sentence(self):
        b=LocalBrain()
        try:
            with patch('dj_brain.ready',return_value=False),patch.object(b,'models',return_value=[]):
                i,e=b.interpret('Тёплый свет старого винилового радио')
                self.assertEqual(e,'needs-model');self.assertEqual(i.action,'clarify');self.assertEqual(i.query,'')
            i,e=b.interpret('Дождливый вечер',enabled=False)
            self.assertEqual(i.action,'clarify');self.assertEqual(e,'disabled')
        finally:b.close()
    def test_same_request_cache_is_bounded_and_context_is_part_of_key(self):
        b=LocalBrain();payloads=[]
        def generate(_url,data,*_args,**_kwargs):
            payloads.append(json.loads(data['messages'][-1]['content']))
            return {'message':{'content':json.dumps({'kind':'mix','query':'night jazz'})}}
        try:
            with patch('dj_brain.ready',return_value=False),patch.object(b,'models',return_value=['fixture']),patch.object(b,'generate',side_effect=generate):
                previous=Intent(search='rainy jazz')
                a,_=b.interpret('В том же духе, но пожёстче',previous)
                c,_=b.interpret('В том же духе, но пожёстче',previous)
                self.assertEqual(a,c);self.assertEqual(len(payloads),1)
                b.interpret('В том же духе, но пожёстче',Intent(search='winter ambient'))
                self.assertEqual(len(payloads),2)
                b.interpret('Тёплое радио после долгого дня',previous)
                self.assertEqual(payloads[-1]['previous'],{})
                self.assertEqual(set(payloads[-1]),{'previous','wish','language'})
                for n in range(70):b.interpret('Музыка для путешествия номер '+str(n))
                self.assertLessEqual(len(b.cache),64)
        finally:b.close()
    def test_local_client_rejects_external_urls_before_sending(self):
        with self.assertRaises(ValueError):request({'url':'https://example.com/api/chat','data':{}})
    def test_native_path_uses_the_same_validated_contract(self):
        b=LocalBrain()
        try:
            with patch('dj_brain.ready',return_value=True),patch.object(b,'native',return_value=('http://127.0.0.1:1','fixture')),patch.object(b,'generate',return_value={'choices':[{'message':{'content':json.dumps({'kind':'mix','query':'vintage jazz'})}}]}):
                i,e=b.interpret('Старый джазовый бар')
                self.assertEqual(e,'ai');self.assertEqual(i.search,'vintage jazz')
        finally:b.close()
    def test_an_existing_but_loading_process_is_not_treated_as_ready(self):
        b=LocalBrain();entered=threading.Event();release=threading.Event();results=[]
        child=Mock();child.poll.return_value=None
        def health(*_a,**_kw):entered.set();release.wait(1);return {'status':'ok'}
        try:
            with patch('dj_brain.ready',return_value=True),patch('dj_brain.subprocess.Popen',return_value=child),patch('dj_brain.request_json',side_effect=health):
                first=threading.Thread(target=lambda:results.append(b.native(lambda:True)));first.start();self.assertTrue(entered.wait(1))
                second=threading.Thread(target=lambda:results.append(b.native(lambda:True)));second.start()
                time.sleep(.03);self.assertFalse(results,'A request skipped health readiness while warm-up was loading')
                release.set();first.join(1);second.join(1);self.assertEqual(len(results),2);self.assertTrue(b.available.is_set())
        finally:release.set();b.close()
    def test_canceling_inference_closes_the_http_helper_promptly(self):
        entered=threading.Event();release=threading.Event();alive=threading.Event();alive.set()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length',0)));entered.set();release.wait(2)
                try:self.send_response(200);self.end_headers();self.wfile.write(b'{}')
                except (BrokenPipeError,ConnectionResetError):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();b=LocalBrain()
        def cancel():entered.wait(1);alive.clear()
        threading.Thread(target=cancel,daemon=True).start()
        try:
            start=time.monotonic()
            with self.assertRaises(InterruptedError):b.generate('http://127.0.0.1:'+str(server.server_port)+'/api/chat',{},alive.is_set)
            self.assertLess(time.monotonic()-start,.7)
        finally:release.set();server.shutdown();server.server_close();b.close()


if __name__=='__main__':unittest.main()
