"""Bounded requests and caches, measured independently of public network speed."""
import sys,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dj_lookups import Lookups
from dj_catalog import DJCatalog,rank
from dj_intent import Intent,local_intent
from dj_brain import LocalBrain
from music_library import MusicRepository
from concurrent.futures import ThreadPoolExecutor


def song(i):return {'uri':'spotify:track:'+str(i),'title':'Evening '+str(i),'artist':'Artist '+str(i)}


class PerformanceTests(unittest.TestCase):
    def test_cache_single_flight_and_repeat(self):
        cache=Lookups();release=threading.Event();calls=[]
        def load():calls.append(1);release.wait(1);return {'items':[song(1)]}
        try:
            a=cache.get(('spotify','x'),load);b=cache.get(('spotify','x'),load)
            self.assertIs(a,b);release.set();a.result(timeout=1)
            deadline=time.monotonic()+1
            while cache.pending and time.monotonic()<deadline:time.sleep(.001)
            c=cache.get(('spotify','x'),load)
            self.assertEqual(c.result(),a.result());self.assertEqual(len(calls),1)
        finally:release.set();cache.close()
    def test_request_flood_is_bounded(self):
        cache=Lookups();release=threading.Event()
        try:
            for i in range(100):cache.get(('x',i),lambda:release.wait(1))
            self.assertLessEqual(len(cache.pending),3)
        finally:release.set();cache.close()
    def test_slow_personal_feed_does_not_delay_search(self):
        calls=[];release=threading.Event()
        def search(*_a,**_kw):calls.append(1);return {'items':[song(i) for i in range(8)]}
        music=SimpleNamespace(host=SimpleNamespace(),repository=SimpleNamespace(load=search))
        catalog=DJCatalog(music)
        def personal(*_a):release.wait(2);return {'tracks':[song(50)]}
        catalog.personal=personal
        try:
            start=time.monotonic();values,_,_=catalog.collect('spotify',Intent(),{})
            self.assertLess(time.monotonic()-start,.8);self.assertEqual(len(values),8)
            start=time.monotonic();catalog.collect('spotify',Intent(),{})
            self.assertLess(time.monotonic()-start,.8);self.assertEqual(calls,[1])
        finally:release.set();catalog.close()
    def test_slow_source_has_a_response_budget(self):
        release=threading.Event()
        def search(*_a,**_kw):release.wait(2);return {'items':[song(1)]}
        music=SimpleNamespace(host=SimpleNamespace(),repository=SimpleNamespace(load=search))
        catalog=DJCatalog(music);catalog.BUDGET=.12;catalog.personal=lambda *_:{'tracks':[]}
        try:
            start=time.monotonic();values,_,warnings=catalog.collect('spotify',Intent(),{})
            self.assertLess(time.monotonic()-start,.4);self.assertFalse(values);self.assertIn('pending',warnings)
        finally:release.set();catalog.close()
    def test_cancelled_wait_is_prompt(self):
        release=threading.Event();alive=threading.Event();alive.set()
        music=SimpleNamespace(host=SimpleNamespace(),repository=SimpleNamespace(load=lambda *_a,**_kw:release.wait(2)))
        catalog=DJCatalog(music);catalog.personal=lambda *_:{'tracks':[]}
        threading.Timer(.06,alive.clear).start()
        try:
            start=time.monotonic()
            with self.assertRaises(InterruptedError):catalog.collect('spotify',Intent(),{},alive.is_set)
            self.assertLess(time.monotonic()-start,.35)
        finally:release.set();catalog.close()
    def test_spotify_transport_does_not_wait_for_metadata_lock(self):
        repository=MusicRepository(SimpleNamespace());lock=repository.locks['spotify'];lock.acquire()
        try:
            with patch('music_library.LocalSpotify') as spotify,ThreadPoolExecutor(1) as pool:
                future=pool.submit(repository.play,dict(song(1),source='spotify'),lambda:True)
                future.result(timeout=.3)
                spotify.return_value.__enter__.return_value.play.assert_called_once_with('spotify:track:1')
        finally:lock.release()
    def test_local_wish_and_rank_are_lightweight(self):
        values=[song(i) for i in range(250)];brain=LocalBrain()
        start=time.perf_counter();cpu=time.process_time()
        with patch.object(brain,'models',side_effect=AssertionError('Heavy model started')):
            for _ in range(20):
                intent,_=brain.interpret('Хочу расслабляющую музыку')
                rank(values,'spotify',intent,{}, {})
        elapsed=(time.perf_counter()-start)/20;used=(time.process_time()-cpu)/20
        self.assertLess(elapsed,.15);self.assertLess(used,.1)
        print(f'\nDJ local intent + 250 candidates: wall {elapsed*1000:.1f} ms, CPU {used*1000:.1f} ms')

if __name__=='__main__':unittest.main()
