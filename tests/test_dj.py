"""Personal DJ boundaries: intent, private taste, real tracks and safe setup."""
import io,json,os,stat,sys,tarfile,tempfile,time,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dj_intent import Intent,local_intent,model_intent
from dj_memory import ListeningMemory
from dj_catalog import rank,DJCatalog
from dj_setup import safe_unpack
from dj_brain import LocalBrain
from listening_queue import QueueBook
from music_library import MusicService


def song(i=1,**kw):
    return dict({'uri':'spotify:track:'+str(i),'title':'Song '+str(i),'artist':'Artist '+str(i),'duration_ms':180000},**kw)


class IntentTests(unittest.TestCase):
    def test_moods_and_languages(self):
        for prompt,mood in [('Хочу расслабляющую музыку','relax'),('Music to focus','focus'),('Бодрую музыку','energy'),('New music','discover')]:
            with self.subTest(prompt=prompt):self.assertEqual(local_intent(prompt).mood,mood)
    def test_exclusion_is_not_positive_genre(self):
        i=local_intent('Хочу джаз, без металла и рэпа')
        self.assertEqual(i.genres,('jazz',));self.assertIn('metal',i.avoid);self.assertIn('hip hop',i.avoid)
    def test_followup(self):
        i=local_intent('without vocals',Intent(mood='relax',genres=('indie',)))
        self.assertTrue(i.instrumental);self.assertEqual(i.genres,('indie',));self.assertEqual(i.mood,'relax')
    def test_command_is_deliberate(self):
        self.assertEqual(local_intent('дальше').action,'next')
        self.assertEqual(local_intent('группа Next').action,'mix')
    def test_bad_model_output_and_constraints(self):
        fallback=local_intent('Без вокала, без металла')
        i=model_intent({'mood':'injected','genres':'not-array','instrumental':False,'familiarity':[]},fallback)
        self.assertTrue(i.instrumental);self.assertIn('metal',i.avoid);self.assertEqual(i.mood,'any')
        self.assertEqual(model_intent([],fallback),fallback)
    def test_small_model_cannot_invent_artist_or_style(self):
        fallback=local_intent('Хочу расслабляющую музыку без вокала')
        i=model_intent({'mood':'relax','genres':['electronic'],'artists':['Armin van Buuren'],
            'avoid':['vocals'],'query':'invented jazz'},fallback,'Хочу расслабляющую музыку без вокала')
        self.assertEqual(i.artists,());self.assertEqual(i.genres,());self.assertEqual(i.avoid,());self.assertEqual(i.query,'')
    def test_model_never_selects_ids(self):
        i=model_intent({'songs':['invented'],'action':'play','artists':['Real Artist']},Intent())
        self.assertEqual(i.action,'mix');self.assertFalse(hasattr(i,'songs'))


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'taste.json';self.m=ListeningMemory(self.path,lambda:1000.)
    def tearDown(self):self.tmp.cleanup()
    def test_only_actual_heard_time_counts(self):
        s=dict(song(),valid=True,playing=True,duration=180,position=0)
        self.m.observe('spotify',s,0);s['position']=179
        self.m.observe('spotify',s,100)
        self.assertEqual(self.m.profile('spotify'),{})
        for t in range(101,161):self.m.observe('spotify',s,t)
        self.assertEqual(self.m.profile('spotify')[s['uri']]['listen'],1)
        for t in range(161,200):self.m.observe('spotify',s,t)
        self.assertEqual(self.m.profile('spotify')[s['uri']]['listen'],1)
    def test_pause_does_not_credit_time(self):
        s=dict(song(),valid=True,playing=False,duration=180)
        for t in range(100):self.m.observe('spotify',s,t)
        self.assertFalse(self.m.profile('spotify'))
    def test_votes_source_isolation_and_clear(self):
        s=song();self.m.record('spotify',s,'like');self.m.record('spotify',s,'like')
        self.assertEqual(self.m.profile('spotify')[s['uri']]['vote'],1)
        self.assertFalse(self.m.profile('apple-music'));self.assertGreater(self.m.artist_affinity('spotify')[s['artist'].lower()],0)
        self.m.record('spotify',s,'dislike');self.assertLess(self.m.artist_affinity('spotify')[s['artist'].lower()],0)
        self.m.clear();self.assertFalse(self.m.profile('spotify'))
    def test_import_is_idempotent(self):
        self.m.import_recent('spotify',[song()]);self.m.import_recent('spotify',[song()])
        self.assertEqual(self.m.profile('spotify')[song()['uri']]['listen'],1)
    def test_bounded_private_persistence(self):
        for i in range(410):self.m.record('spotify',song(i),'listen')
        self.m.settings['enabled']=True;self.m.save()
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)
        loaded=ListeningMemory(self.path);self.assertEqual(len(loaded.profile('spotify')),400);self.assertTrue(loaded.settings['enabled'])
        self.assertFalse(any(k in self.path.read_text() for k in ('password','cookie','audio_pcm')))
    def test_corrupt_nested_values(self):
        self.path.write_text(json.dumps({'sources':{'spotify':{'x':{'artist':'A','listen':{},'vote':'bad','last':'NaN'}}},'settings':{'voice':[]}}))
        m=ListeningMemory(self.path);self.assertEqual(m.artist_affinity('spotify'),{'a':0.});self.assertTrue(m.settings['voice'])


class RankingTests(unittest.TestCase):
    def test_only_real_playable_source_items(self):
        values=[song(),song(2,playable=False),song(3,uri='apple:songs:3'),{'title':'Invented'}]
        self.assertEqual([v['uri'] for v in rank(values,'spotify',Intent(),{}, {})],['spotify:track:1'])
    def test_no_vocals_is_not_silently_ignored(self):
        values=[song(),song(2,title='Instrumental Piano')]
        self.assertEqual([v['uri'] for v in rank(values,'spotify',Intent(instrumental=True),{},{})],['spotify:track:2'])
        self.assertEqual(rank([song()],'spotify',Intent(instrumental=True),{},{}),[])
    def test_exclusions_dislike_and_repeat(self):
        values=[song(1,genres=['metal']),song(2),song(3),song(4)]
        profile={'spotify:track:2':{'vote':-1}}
        self.assertEqual([v['uri'] for v in rank(values,'spotify',Intent(avoid=('metal',)),profile,{},exclude=['spotify:track:3'])],['spotify:track:4'])
    def test_personal_taste_changes_ranking(self):
        values=[song(1),song(2)]
        result=rank(values,'spotify',Intent(),{}, {'artist 2':5})
        self.assertEqual(result[0]['uri'],'spotify:track:2');self.assertEqual(result[0]['_reason'],'artist')
    def test_diversity_and_duplicate_editions(self):
        values=[song(i,artist='One Artist') for i in range(10)]
        self.assertEqual(len(rank(values,'spotify',Intent(),{},{})),2)
    def test_cached_apple_feed_still_loads_collections(self):
        calls=[]
        def request(method,**kw):
            calls.append(method)
            return {'personal':True,'items':[{'id':'p.1','kind':'playlists','title':'Relax'}]} if method=='browse' else {'tracks':[dict(song(),uri='apple:songs:1')]}
        host=SimpleNamespace(apple_mode='native',apple_web=SimpleNamespace(request=request))
        catalog=DJCatalog(SimpleNamespace(host=host,repository=SimpleNamespace(load=lambda *_a,**_kw:{})))
        for _ in range(2):self.assertTrue(catalog.collect('apple-music',Intent(),{})[0])
        self.assertEqual(calls,['browse','tracks']);catalog.close()


class SetupTests(unittest.TestCase):
    def test_zip_traversal_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape','bad')
            with self.assertRaises(ValueError):safe_unpack(archive,Path(directory)/'out')
            with zipfile.ZipFile(archive,'w') as z:z.writestr('fine/model','12345')
            with self.assertRaises(ValueError):safe_unpack(archive,Path(directory)/'out',4)
    def test_tar_links_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'bad.tar'
            with tarfile.open(archive,'w') as tar:
                info=tarfile.TarInfo('link');info.type=tarfile.SYMTYPE;info.linkname='../../escape';tar.addfile(info)
            with self.assertRaises(ValueError):safe_unpack(archive,Path(directory)/'out')
    def test_valid_runtime_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'fine.tar'
            with tarfile.open(archive,'w') as tar:
                info=tarfile.TarInfo('runtime/bin');info.mode=0o755;info.size=3;tar.addfile(info,io.BytesIO(b'bin'))
            target=Path(directory)/'out';safe_unpack(archive,target)
            self.assertTrue(os.access(target/'runtime/bin',os.X_OK))


class BrainTests(unittest.TestCase):
    def test_only_wish_and_intent_reach_model(self):
        b=LocalBrain();requests=[]
        def request(url,data=None,**kw):
            requests.append(data)
            return {'message':{'content':json.dumps({'mood':'relax','genres':[],'artists':[],'avoid':[],'instrumental':None,'familiarity':.65,'query':''})}}
        with patch.object(b,'models',return_value=['qwen2.5:1.5b']),patch('dj_brain.request_json',side_effect=request):
            intent,engine=b.interpret('Consider the atmosphere of an observatory under the stars far away from everything tonight')
        self.assertEqual(engine,'ai');self.assertEqual(intent.mood,'relax')
        user=json.loads(requests[0]['messages'][1]['content']);self.assertEqual(set(user),{'previous','wish'})
    def test_common_wishes_never_start_a_model(self):
        b=LocalBrain()
        with patch.object(b,'models',side_effect=AssertionError('A model was consulted')):
            for prompt in ('Хочу спокойную музыку','without vocals','Найди Let It Happen','как Tame Impala'):
                self.assertEqual(b.interpret(prompt)[1],'local')
    def test_no_model_keeps_keyboard_usable(self):
        b=LocalBrain()
        with patch.object(b,'models',return_value=[]),patch.object(b,'native',side_effect=RuntimeError('missing')):
            intent,engine=b.interpret('Спокойную музыку')
        self.assertEqual(engine,'local');self.assertEqual(intent.mood,'relax')
    def test_cancellation_does_not_produce_new_plan(self):
        b=LocalBrain()
        with patch.object(b,'models',return_value=[]):
            with self.assertRaises(InterruptedError):b.interpret('Music',alive=lambda:False)


class QueueTests(unittest.TestCase):
    def test_dj_preserves_user_tail_and_clears_only_future_dj(self):
        with tempfile.TemporaryDirectory() as directory:
            book=QueueBook(Path(directory)/'queue.json');book.add('spotify',[song(1),song(2,origin='context')]);book.select('spotify',0)
            starts=[]
            service=SimpleNamespace(host=SimpleNamespace(source='spotify'),book=book,play_generation=0,loading=False,
                watch=SimpleNamespace(reset=lambda:None),start=lambda i:starts.append(i),changed=lambda:None)
            self.assertTrue(MusicService.play_dj(service,[song(3),song(4)]))
            self.assertEqual([v['uri'] for v in book.queues['spotify']],['spotify:track:1','spotify:track:3','spotify:track:4','spotify:track:2'])
            book.select('spotify',1);MusicService.clear_dj(service,'spotify')
            self.assertEqual([v['uri'] for v in book.queues['spotify']],['spotify:track:1','spotify:track:3','spotify:track:2'])
    def test_full_queue_does_not_destroy_user_music(self):
        with tempfile.TemporaryDirectory() as directory:
            book=QueueBook(Path(directory)/'q.json');book.add('spotify',[song(i) for i in range(200)])
            service=SimpleNamespace(host=SimpleNamespace(source='spotify'),book=book)
            self.assertFalse(MusicService.play_dj(service,[song(500)]));self.assertEqual(len(book.queues['spotify']),200)

if __name__=='__main__':unittest.main()
