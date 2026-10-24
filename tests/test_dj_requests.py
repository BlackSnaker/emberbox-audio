"""The reported Beatles failure: exact artist scope, enough songs, honest replies."""
import sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dj_intent import Intent,local_intent,same_artist
from dj_catalog import DJCatalog,rank
from dj_reply import reply,summary
from listening_queue import QueueBook
from music_library import MusicService
from dj_brain import LocalBrain
from unittest.mock import patch


def song(i,artist='The Beatles',**extra):
    return dict({'uri':'apple:songs:'+str(i),'id':str(i),'artist':artist,'title':'Recording '+str(i),'kind':'songs'},**extra)


class RequestTests(unittest.TestCase):
    def test_conversational_moods_do_not_become_track_titles(self):
        previous=Intent(artists=('The Beatles',),query='Beatles',mode='artist')
        cases={'давай что-нибудь повеселее':'happy','чего-то более позитивного':'happy',
            'А теперь поживее':'energy','побыстрее':'energy','поспокойнее':'relax',
            'хочется перед сном':'relax','музыку для работы':'focus','для свидания':'romance',
            'давай потанцуем':'party','не грустное, а повеселее':'happy',
            'подними настроение':'happy','что-нибудь другое':'discover','удиви меня':'discover',
            'давай что-нибудь повеселее, чтобы настроение поднять':'happy',
            'make it happier':'happy','more upbeat':'happy','something calmer':'relax',
            'something for a workout':'energy','something else':'discover'}
        brain=LocalBrain()
        with patch.object(brain,'models',side_effect=AssertionError('Common wishes started a heavy model')):
            for prompt,mood in cases.items():
                with self.subTest(prompt=prompt):
                    intent,engine=brain.interpret(prompt,previous)
                    self.assertEqual(intent.mood,mood);self.assertEqual(intent.mode,'mix')
                    self.assertEqual(intent.query,'');self.assertEqual(intent.artists,());self.assertEqual(engine,'local')
    def test_named_mood_qualifier_and_explicit_anaphor_keep_the_artist(self):
        previous=Intent(artists=('The Beatles',),query='Beatles',mode='artist')
        for prompt in ('Beatles, но повеселее','поставь Beatles повеселее','Хочу повеселее от Beatles'):
            intent=local_intent(prompt,previous)
            self.assertEqual(intent.query,'Beatles');self.assertEqual(intent.mode,'lookup');self.assertEqual(intent.mood,'happy')
        intent=local_intent('их же, но повеселее',previous)
        self.assertEqual(intent.mode,'artist');self.assertEqual(intent.artists,previous.artists);self.assertEqual(intent.mood,'happy')
    def test_mood_followup_retains_genre_but_new_name_clears_constraints(self):
        previous=local_intent('Хочу джаз без металла')
        intent=local_intent('давай повеселее',previous)
        self.assertEqual(intent.genres,('jazz',));self.assertIn('metal',intent.avoid)
        self.assertEqual(local_intent('давай Queen',intent),Intent(query='Queen',mode='lookup'))
        self.assertEqual(local_intent('что-нибудь другое',intent).genres,())
    def test_unfamiliar_occasion_uses_theme_search_not_exact_song_filter(self):
        for prompt in ('музыку для вечерней прогулки','что-нибудь атмосферное','music for a road trip'):
            with self.subTest(prompt=prompt):
                intent=local_intent(prompt)
                self.assertEqual(intent.mode,'theme');self.assertTrue(intent.query)
    def test_mood_playlist_tracks_win_over_unrelated_favourites(self):
        calls=[]
        def request(method,**kw):
            calls.append((method,kw))
            if method=='search':
                self.assertEqual(kw['types'],'playlists');self.assertEqual(kw['term'],'feel good')
                return {'items':[{'id':'pl.happy','kind':'playlists','title':'Feel Good Hits'}]}
            return {'tracks':[song(i,'Band '+str(i),title='Real recording '+str(i)) for i in range(1,21)]}
        host=SimpleNamespace(apple_mode='native',apple_web=SimpleNamespace(request=request))
        c=DJCatalog(SimpleNamespace(host=host,repository=SimpleNamespace()))
        c.personal=lambda *_:{'tracks':[song(100,'Favourite',_personal=True)]}
        try:
            intent=local_intent('давай что-нибудь повеселее',Intent(artists=('The Beatles',),mode='artist'))
            values,_,_=c.collect('apple-music',intent,{'favourite':100})
            selected=rank(values,'apple-music',intent,{},{'favourite':100})
            self.assertEqual(len(selected),14);self.assertTrue(all(v.get('_dj_mood')=='happy' for v in selected))
            self.assertEqual(calls[1],('tracks',{'kind':'playlists','id':'pl.happy'}))
        finally:c.close()
    def test_personal_duplicate_does_not_hide_matching_collection_metadata(self):
        values=[song(1,_personal=True),song(1,_context='Feel Good',_dj_mood='happy')]
        self.assertEqual(len(rank(values,'apple-music',Intent(mood='happy'),{},{})),1)
    def test_named_requests_keep_the_target(self):
        for value in ('Beatles','The Beatles','Битлз','Хочу послушать Beatles','Включи мне музыку Beatles','Beatles, пожалуйста','Только Beatles'):
            with self.subTest(value=value):
                intent=local_intent(value)
                self.assertEqual(intent.mode,'lookup');self.assertTrue(same_artist(intent.query,'The Beatles'))
    def test_similar_is_explicit_and_name_has_no_trailing_constraint(self):
        intent=local_intent('Хочу как Beatles, но без вокала')
        self.assertEqual(intent.mode,'similar');self.assertEqual(intent.artists,('Beatles',));self.assertTrue(intent.instrumental)
    def test_new_request_does_not_inherit_unrelated_context(self):
        first=Intent(mood='focus',genres=('ambient',),instrumental=True)
        intent=local_intent('Beatles',first)
        self.assertEqual(intent.mood,'any');self.assertEqual(intent.genres,());self.assertIsNone(intent.instrumental)
    def test_artist_followup_keeps_artist_scope(self):
        previous=Intent(artists=('The Beatles',),query='Beatles',mode='artist')
        intent=local_intent('ещё',previous)
        self.assertEqual(intent.mode,'artist');self.assertEqual(intent.query,'Beatles');self.assertEqual(intent.artists,('The Beatles',))
    def test_exact_artist_resolution_loads_the_catalogue_not_song_title_hits(self):
        calls=[]
        def load(source,category,**kw):
            calls.append((category,kw))
            if category=='artist':return {'choices':[{'id':'136975','name':'The Beatles'},{'id':'9','name':'Beatles Tribute'}]}
            if category=='artist-section':return {'items':[song(i) for i in range(1,25)]+[song(100,'Rae Sremmurd',title='Black Beatles')]}
            raise AssertionError('A personal or generic song search replaced the artist')
        music=SimpleNamespace(host=SimpleNamespace(),repository=SimpleNamespace(load=load));catalog=DJCatalog(music)
        try:
            intent=local_intent('Beatles');values,_,_=catalog.collect('apple-music',intent,{})
            selected=rank(values,'apple-music',intent,{}, {'michael jackson':20})
            self.assertEqual(len(selected),14,'Explicit artist mode must bypass the two-tracks-per-artist cap')
            self.assertTrue(all(v['artist']=='The Beatles' for v in selected))
            self.assertEqual(calls[1][1]['collection'],{'id':'136975','section':'top-songs'})
            catalog.collect('apple-music',intent,{})
            self.assertEqual(len(calls),2,'The resolved artist catalogue should be reused')
        finally:catalog.close()
    def test_named_artist_rejects_title_hits_and_personal_tracks(self):
        intent=Intent(artists=('The Beatles',),query='Beatles',mode='artist')
        values=[song(i) for i in range(1,21)]+[song(99,'Rae Sremmurd',title='Black Beatles'),song(100,'Michael Jackson',_personal=True)]
        selected=rank(values,'apple-music',intent,{}, {'michael jackson':100})
        self.assertEqual(len(selected),14);self.assertEqual({v['artist'] for v in selected},{'The Beatles'})
    def test_failed_artist_catalogue_does_not_fall_back_to_recommendations(self):
        def load(source,category,**kw):
            if category=='artist':return {'choices':[{'id':'1','name':'The Beatles'}]}
            raise RuntimeError('source timeout')
        c=DJCatalog(SimpleNamespace(host=SimpleNamespace(),repository=SimpleNamespace(load=load)))
        try:self.assertEqual(c.collect('apple-music',local_intent('Beatles'),{})[0],[])
        finally:c.close()
    def test_track_search_rejects_unrelated_personal_results(self):
        intent=local_intent('Найди Let It Happen')
        values=[song(1,'Tame Impala',title='Let It Happen'),song(2,'Michael Jackson',title='Beat It',_personal=True)]
        selected=rank(values,'apple-music',intent,{}, {})
        self.assertEqual([v['id'] for v in selected],['1'])
    def test_replies_describe_artist_and_recording_instead_of_fixed_copy(self):
        a=reply(Intent(artists=('The Beatles',),mode='artist'),[song(1)],'Apple Music')
        b=reply(Intent(artists=('Queen',),mode='artist'),[song(2,'Queen',title='Somebody to Love')],'Spotify')
        self.assertIn('The Beatles',a);self.assertIn('Recording 1',a);self.assertIn('Somebody to Love',b);self.assertNotEqual(a,b)
        self.assertIn('The Beatles',summary(Intent(artists=('The Beatles',),mode='artist')))
    def test_artist_refill_goes_before_unrelated_saved_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            book=QueueBook(Path(folder)/'queue.json')
            book.add('apple-music',[song(1,origin='dj'),song(2,'Michael Jackson',origin='manual')]);book.select('apple-music',0)
            service=SimpleNamespace(host=SimpleNamespace(source='apple-music'),book=book,changed=lambda:None)
            MusicService.extend_dj(service,[song(3),song(4)],before_pending=True)
            self.assertEqual([v['id'] for _,v in book.upcoming('apple-music')],['3','4','2'])
            self.assertEqual(book.queues['apple-music'][-1]['origin'],'manual')

if __name__=='__main__':unittest.main()
