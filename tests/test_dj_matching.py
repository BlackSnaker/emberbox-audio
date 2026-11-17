"""Behavioural examples for entity boundaries, abstract wishes and taste scope."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dj_intent import Intent,local_intent,quick_wish
from dj_brain import LocalBrain
from dj_semantics import decode
from dj_catalog import DJCatalog,rank


def song(i,**kw):
    return dict({'uri':'apple:songs:'+str(i),'id':str(i),'kind':'songs',
        'title':'Recording '+str(i),'artist':'Artist '+str(i)},**kw)


class UnderstandingTests(unittest.TestCase):
    def test_genres_and_subgenres_are_not_artist_names(self):
        cases={'Джаз':'jazz','джазовую музыку':'jazz','драм-н-бейс':'drum and bass',
            'R&B':'r&b','пост-рок':'post rock','постпанк':'post punk','deep house':'deep house',
            'dream pop':'dream pop','synthwave':'synthwave','хочу рэп':'hip hop'}
        for prompt,genre in cases.items():
            with self.subTest(prompt=prompt):
                i=local_intent(prompt)
                self.assertEqual(i.mode,'mix');self.assertEqual(i.query,'')
                self.assertEqual(i.genres,(genre,));self.assertTrue(quick_wish(prompt))
        for prompt in ('в стиле джаза','в жанре джаз'):
            i=local_intent(prompt)
            self.assertEqual(i.mode,'mix');self.assertEqual(i.genres,('jazz',));self.assertEqual(i.artists,())

    def test_artist_names_do_not_get_split_into_style_words(self):
        for name in ('Metallica','металлика','Рокет','Jazztronik','Pop Smoke','Happy Mondays','Daft Punk','Household'):
            with self.subTest(name=name):
                i=local_intent(name)
                self.assertEqual(i.mode,'lookup');self.assertEqual(i.query,name)
                self.assertEqual(i.genres,());self.assertEqual(i.mood,'any');self.assertTrue(quick_wish(name))

    def test_explicit_entity_type_overrides_an_ambiguous_name(self):
        for prompt,name in (('Включи группу Кино','Кино'),('Хочу исполнителя Джаз','Джаз'),
                            ('Поставь artist Jazz','Jazz')):
            i=local_intent(prompt)
            self.assertEqual(i.mode,'artist');self.assertEqual(i.artists,(name,))
            self.assertEqual(i.target_kind,'artist');self.assertEqual(i.genres,())
        for prompt,name in (('песню Happy','Happy'),('трек Relax','Relax'),('song Jazz','Jazz')):
            i=local_intent(prompt)
            self.assertEqual(i.target_kind,'track');self.assertEqual(i.query,name)
            self.assertEqual(i.genres,());self.assertEqual(i.mood,'any')

    def test_reported_similar_daftpunk_keeps_the_complete_name_without_punk_genre(self):
        for prompt in ('что-то похожее на daft punk','как Daft Punk','similar to daft punk'):
            i=local_intent(prompt)
            self.assertEqual(i.mode,'similar');self.assertEqual(i.genres,())
            self.assertEqual(i.artists[0].casefold(),'daft punk');self.assertTrue(quick_wish(prompt))
        i=local_intent('похожее на Daft Punk, но без вокала')
        self.assertTrue(i.instrumental);self.assertEqual(i.genres,())

    def test_familiar_abstract_wishes_never_load_a_language_model(self):
        cases={
            'что-нибудь потеплее для вечера':('warm',),
            'Хочу джаз для уютного вечера':('jazz','warm'),
            'Хочу будто парю в космосе':('ethereal','ambient'),
            'что-нибудь до мурашек':('emotional','cinematic'),
            'электронику для ночной поездки':('electronic','night','drive'),
            'Музыку как будто я главный герой нуарного фильма':('noir','jazz'),
            'Хочу будто сидеть в старом джазовом баре':('jazz','vintage','lounge'),
            'русский рок девяностых':('russian','rock','90s'),
            'энергично, но без агрессии':('energetic','mellow')}
        brain=LocalBrain()
        try:
            with patch.object(brain,'models',side_effect=AssertionError('Unneeded model')):
                for prompt,keywords in cases.items():
                    with self.subTest(prompt=prompt):
                        i,engine=brain.interpret(prompt,enabled=False)
                        self.assertEqual(engine,'local');self.assertEqual(i.mode,'mix');self.assertEqual(i.query,'')
                        for word in keywords:self.assertIn(word,i.search.split())
        finally:brain.close()

    def test_wish_for_a_song_is_not_always_a_named_song(self):
        for prompt in ('Хочу песню для сна','Поставь трек повеселее','song for a workout'):
            i=local_intent(prompt)
            self.assertEqual(i.mode,'mix');self.assertEqual(i.query,'');self.assertEqual(i.target_kind,'auto')

    def test_genre_and_context_refinements_keep_compatible_constraints(self):
        base=local_intent('Хочу джаз для уютного вечера')
        for prompt in ('чуть теплее','a little warmer'):
            warmer=local_intent(prompt,base)
            self.assertEqual(warmer.genres,('jazz',));self.assertIn('jazz',warmer.search)
        without=local_intent('без джаза',base)
        self.assertNotIn('jazz',without.genres);self.assertNotIn('jazz',without.search)
        self.assertNotIn('Jazz',without.caption)
        rock=local_intent('а теперь рок',base)
        self.assertEqual(rock.genres,('rock',));self.assertNotIn('jazz',rock.search)
        fresh=local_intent('Metallica',base)
        self.assertEqual(fresh.genres,());self.assertEqual(fresh.mood,'any')

    def test_model_cannot_reclassify_a_genre_as_an_artist(self):
        with self.assertRaises(ValueError):
            decode({'kind':'artist','query':'jazz'},'Хочу джаз',None,local_intent('Хочу джаз'))
        i=decode({'kind':'genre','query':'post punk'},'постпанк с холодным звучанием',None,Intent())
        self.assertEqual(i.mode,'mix');self.assertEqual(i.query,'');self.assertIn('post punk',i.genres)

    def test_model_language_is_compiled_and_conflicting_old_mood_removed(self):
        i=decode({'kind':'mix','query':'нуар фильм'},'герой нуарного фильма',None,Intent())
        self.assertIn('noir',i.search);self.assertNotIn('фильм',i.search)
        base=Intent(search='sad melancholy jazz',genres=('jazz',),mood='melancholy')
        prompt='А теперь повеселее'
        i=decode({'kind':'mix','query':'upbeat jazz'},prompt,base,local_intent(prompt,base))
        self.assertEqual(i.mood,'happy');self.assertNotIn('sad',i.search);self.assertIn('jazz',i.search)


class RecommendationTests(unittest.TestCase):
    def test_similar_uses_real_source_relationships_instead_of_a_name_search(self):
        calls=[]
        def request(method,**kw):
            calls.append((method,kw))
            return {'items':[song(i,artist='Related '+str(i//4),genres=['Electronic'],_dj_related='Daft Punk') for i in range(24)]}
        host=SimpleNamespace(apple_mode='native',apple_web=SimpleNamespace(request=request))
        c=DJCatalog(SimpleNamespace(host=host,repository=SimpleNamespace(load=lambda *_a,**_k:self.fail('Literal name search'))))
        c.personal=lambda *_:self.fail('Unrelated personal enrichment')
        try:
            i=local_intent('что-то похожее на daft punk')
            values,_,_=c.collect('apple-music',i,{})
            result=rank(values+[song(999,_personal=True)],'apple-music',i,{}, {})
            self.assertEqual(len(result),14)
            self.assertTrue(all(v['_dj_related']=='Daft Punk' for v in result))
            self.assertEqual(calls,[('artistSection',{'section':'dj-similar','name':'daft punk'})])
        finally:c.close()

    def test_a_song_title_and_artist_name_are_not_genre_evidence(self):
        values=[song(1,title='Jazz'),song(2,artist='Jazztronik'),
                song(3,genres=['Jazz']),song(4,_context='Лучший джаз для вечера')]
        result=rank(values,'apple-music',Intent(genres=('jazz',)),{}, {'jazztronik':100})
        self.assertEqual({v['id'] for v in result},{'3','4'})

    def test_taste_personalization_only_operates_inside_the_requested_genre(self):
        values=[song(1,_personal=True,genres=['Metal']),song(2,genres=['Jazz']),song(3,genres=['Jazz'])]
        profile={values[0]['uri']:{'vote':1,'listen':50}}
        i=Intent(genres=('jazz',))
        result=rank(values,'apple-music',i,profile,{'artist 1':100,'artist 3':6})
        self.assertEqual([v['id'] for v in result],['3','2'])

    def test_exclusions_use_metadata_not_substrings_of_names(self):
        values=[song(1,artist='Metallica',genres=['Rock']),song(2,genres=['Heavy Metal'])]
        result=rank(values,'apple-music',Intent(avoid=('metal',)),{}, {})
        self.assertEqual([v['id'] for v in result],['1'])

    def test_explicit_track_never_queries_the_artist_endpoint(self):
        calls=[]
        def load(source,category,**kw):
            calls.append(category)
            if category!='search':raise AssertionError('A title was resolved as an artist')
            return {'items':[song(1,title='Happy')]}
        c=DJCatalog(SimpleNamespace(host=SimpleNamespace(),repository=SimpleNamespace(load=load)))
        try:
            values,_,_=c.collect('apple-music',local_intent('Песню Happy'),{})
            self.assertEqual([v['id'] for v in values],['1']);self.assertEqual(calls,['search'])
        finally:c.close()

    def test_genre_search_loads_matching_collections_not_title_hits(self):
        loaded=[]
        def request(method,**kw):
            if method=='search':return {'items':[
                {'id':'bad','kind':'playlists','title':'Rockstar','description':'Hip Hop'},
                {'id':'ok','kind':'playlists','title':'Рок на каждый день'}]}
            loaded.append(kw['id']);return {'tracks':[song(1,genres=['Rock'])]}
        h=SimpleNamespace(apple_mode='native',apple_web=SimpleNamespace(request=request))
        c=DJCatalog(SimpleNamespace(host=h,repository=SimpleNamespace()))
        c.personal=lambda *_:{'tracks':[song(2,_personal=True,genres=['Pop'])]}
        try:
            i=local_intent('Хочу рок');values,_,_=c.collect('apple-music',i,{})
            result=rank(values,'apple-music',i,{}, {'artist 2':100})
            self.assertEqual(loaded,['ok']);self.assertEqual([v['id'] for v in result],['1'])
        finally:c.close()

    def test_request_does_not_label_unrelated_playlist_as_verified_mood(self):
        h=SimpleNamespace(apple_mode='native',apple_web=SimpleNamespace(request=lambda method,**kw:
            {'items':[{'id':'x','kind':'playlists','title':'Heavy Metal'}]} if method=='search' else {'tracks':[song(1)]}))
        c=DJCatalog(SimpleNamespace(host=h,repository=SimpleNamespace()))
        try:
            values=c.themed('apple-music','calm',Intent(mood='relax'))['items']
            self.assertFalse(values[0]['_dj_mood'])
        finally:c.close()

    def test_discovery_prefers_unheard_candidates_when_context_is_equal(self):
        values=[song(1,_context='Jazz'),song(2,_context='Jazz')]
        result=rank(values,'apple-music',Intent(mood='discover',genres=('jazz',),familiarity=.2),
            {values[0]['uri']:{'listen':4}},{'artist 1':6})
        self.assertEqual(result[0]['id'],'2')

    def test_long_descriptions_have_a_bounded_genre_and_mood_fallback(self):
        terms=[]
        def request(method,**kw):
            if method=='search':
                terms.append(kw['term'])
                if kw['term']=='jazz chill':return {'items':[{'id':'ok','kind':'playlists','title':'Jazz Chill'}]}
                return {'items':[]}
            return {'tracks':[song(i,genres=['Jazz']) for i in range(20)]}
        h=SimpleNamespace(apple_mode='native',apple_web=SimpleNamespace(request=request))
        c=DJCatalog(SimpleNamespace(host=h,repository=SimpleNamespace()))
        c.personal=lambda *_:{'tracks':[]}
        try:
            i=local_intent('Хочу джаз для уютного вечера')
            values,_,_=c.collect('apple-music',i,{})
            self.assertEqual(terms,[i.search,'jazz chill'])
            self.assertEqual(len(rank(values,'apple-music',i,{}, {})),14)
        finally:c.close()


if __name__=='__main__':unittest.main()
