"""Complete prose, bounded network/cache work and stale listener isolation."""
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from editorial_translation import (translate_text,chunks,clean,is_russian,identity,
    TranslationError,TranslationCache,EditorialTranslator,CHUNK,MAX_REPLY,TTL)


def reply(source,result='Русский текст'):
    return io.BytesIO(json.dumps([[[result,source]],None,'en']).encode())


class TranslationTests(unittest.TestCase):
    def test_post_has_only_description_and_preserves_all_paragraphs(self):
        value='First story.\n\nSecond paragraph.';calls=[]
        def opener(request,timeout):
            calls.append((request,timeout));return io.BytesIO(json.dumps([
                [['Первая история.\n\n','First story.\n\n'],['Второй абзац.','Second paragraph.']],None,'en']).encode())
        result=translate_text(value,opener)
        self.assertEqual(result,'Первая история.\n\nВторой абзац.')
        request,timeout=calls[0]
        self.assertEqual(request.get_method(),'POST');self.assertNotIn('?',request.full_url)
        self.assertEqual(urllib.parse.parse_qs(request.data.decode())['q'],[value])
        self.assertEqual(timeout,12);self.assertNotIn('Cookie',request.headers);self.assertNotIn('Authorization',request.headers)

    def test_chunks_are_bounded_and_lossless_for_all_boundaries(self):
        for value in ['A story. '*1400,'x'*14000,('x'*2000+'\n\n')*5,('Word '*900)+'End.']:
            parts=list(chunks(value));self.assertEqual(''.join(parts),value)
            self.assertTrue(all(0<len(v)<=CHUNK for v in parts))

    def test_long_translation_is_complete_and_cached_only_as_a_whole(self):
        value=('The story of this record. '*190)+'\n\nAnother story.';parts=[]
        def opener(request,timeout):
            source=urllib.parse.parse_qs(request.data.decode())['q'][0];parts.append(source)
            return reply(source,source.replace('story','история').rstrip())
        result=translate_text(value,opener)
        self.assertEqual(''.join(parts),value)
        self.assertEqual(result,value.replace('story','история'))

    def test_rejects_partial_malformed_empty_and_oversized_replies(self):
        for data in [[],{},[[]],[[['','Story']]],[[['Текст','Missing end']]],[[['Текст',None]]],[[['Текст']]]]:
            with self.subTest(data=data),self.assertRaises(TranslationError):
                translate_text('Story',lambda *_a,**_k:io.BytesIO(json.dumps(data).encode()))
        with self.assertRaises(TranslationError):
            translate_text('Story',lambda *_a,**_k:io.BytesIO(b'x'*(MAX_REPLY+1)))

    def test_cancellation_and_russian_source_do_not_call_network(self):
        fail=lambda *_a,**_k:self.fail('Network must not run')
        self.assertEqual(translate_text('Русское описание музыкального альбома.',fail),'Русское описание музыкального альбома.')
        self.assertTrue(is_russian('История альбома Currents и его звучания.'))
        self.assertFalse(is_russian('Історія альбому та його звучання'))
        with self.assertRaises(TranslationError):translate_text('A story.',fail,alive=lambda:False)
        for value in ['',None,'x'*14001]:
            with self.assertRaises(TranslationError):clean(value)

    def test_offline_cache_validity_budgets_and_atomic_private_files(self):
        with tempfile.TemporaryDirectory() as folder:
            store=TranslationCache(folder);store.write('Source','Перевод')
            self.assertEqual(TranslationCache(folder).read('Source'),'Перевод')
            path=Path(folder)/(identity('Source')+'.json')
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertFalse(list(Path(folder).glob('*.tmp')))
            data=json.loads(path.read_text());data['created']=time.time()-TTL-1;path.write_text(json.dumps(data))
            self.assertIsNone(TranslationCache(folder).read('Source'))
            data['created']=time.time();data['source']='Changed story';path.write_text(json.dumps(data))
            self.assertIsNone(TranslationCache(folder).read('Source'))
            path.write_text('{broken');self.assertIsNone(TranslationCache(folder).read('Source'))
            for i in range(70):store.write(str(i),'Текст')
            self.assertLessEqual(len(list(Path(folder).glob('*.json'))),64)
            self.assertLessEqual(len(store.memory),48)

    def test_deduplicated_async_jobs_detach_destroyed_readers_and_close(self):
        entered=threading.Event();release=threading.Event();dispatch=[];results=[];calls=[]
        with tempfile.TemporaryDirectory() as folder:
            def translate(value,alive):
                calls.append(value);entered.set();release.wait(2);return 'Перевод'
            client=EditorialTranslator(TranslationCache(folder),translate,dispatch.append)
            try:
                detach=client.request('A story.',lambda *r:results.append(('old',r)))
                self.assertTrue(entered.wait(1));detach()
                client.request('A story.',lambda *r:results.append(('new',r)))
                release.set()
                deadline=time.monotonic()+2
                while not dispatch and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(dispatch)
                dispatch.pop(0)()
                self.assertEqual(calls,['A story.']);self.assertEqual(results,[('new',('Перевод',None))])
                client.request('A story.',lambda *r:results.append(('closed',r)))
                client.close()
                for callback in dispatch:callback()
                self.assertEqual(len(results),1)
            finally:release.set();client.close()


if __name__=='__main__':unittest.main()
