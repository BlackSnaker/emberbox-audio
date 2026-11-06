"""Transition identity, real engine routing, bounded analysis and privacy."""
import json,stat,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flow_plans import FlowPlans,playlist_key,recipe,duration
from listening_queue import track,QueueBook
from flow_youtube import curve
from spatial_mix import curve as pcm_curve
import test_ember_flow as fixture
from test_ember_flow import song
from test_music_service import host
from music_library import MusicService


class Recipes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=FlowPlans(Path(self.tmp.name)/'transitions.json')
        self.key=playlist_key('youtube',{'uri':'playlist:first'});self.a,self.b=song('A'),song('B')
    def test_exact_order_playlist_and_source_survive_restore(self):
        self.store.put(self.key,[(self.a,self.b,dict(mode='manual',seconds=3.5,shape='smooth',beats=False))])
        restored=FlowPlans(self.store.path);a=dict(self.a,flow_playlist=self.key);b=dict(self.b,flow_playlist=self.key)
        self.assertEqual(restored.for_tracks(a,b)['seconds'],3.5)
        self.assertIsNone(restored.for_tracks(b,a));self.assertIsNone(restored.for_tracks(a,self.b))
        self.assertIsNone(restored.for_tracks(a,dict(b,flow_playlist=playlist_key('youtube',{'uri':'playlist:other'}))))
        self.assertNotEqual(self.key,playlist_key('apple-music',{'uri':'playlist:first'}))
        self.assertEqual(stat.S_IMODE(self.store.path.stat().st_mode),0o600)
        self.assertNotIn('title',self.store.path.read_text());self.assertNotIn('image',self.store.path.read_text())
        normalized=track(a,'youtube');book=QueueBook(Path(self.tmp.name)/'queue.json');book.add('youtube',[normalized])
        self.assertEqual(QueueBook(book.path).queues['youtube'][0]['flow_playlist'],self.key)
    def test_invalid_and_oversized_recipes_do_not_replace_saved_state(self):
        for value in (dict(seconds=float('nan')),dict(seconds=float('inf')),dict(seconds=20),dict(shape='inject'),dict(mode='other')):
            with self.assertRaises(ValueError):self.store.put(self.key,[(self.a,self.b,value)])
        self.assertFalse(self.store.path.exists())
        self.store.path.write_text('{broken');self.assertEqual(FlowPlans(self.store.path).data,{})
        self.store.path.write_text(json.dumps({self.key:{'a'*64:{'seconds':'nan'},'b'*64:{'mode':'cut'}}}))
        self.assertEqual(len(FlowPlans(self.store.path).data[self.key]),1)
    def test_manual_duration_is_not_changed_by_silence_or_rhythm(self):
        grid={'bpm':160,'confidence':.95}
        self.assertEqual(duration(recipe(dict(mode='manual',seconds=6)),180,180,True,grid),6)
        self.assertEqual(duration(recipe({}),180,180,False,grid),3)
        self.assertEqual(duration(recipe({}),180,180,True,grid),1.4)
        self.assertEqual(duration(recipe({}),180,180,False,dict(bpm=160,confidence=.1)),8)
        self.assertEqual(duration(recipe(dict(mode='manual',seconds=8)),180,20),2)
    def test_both_curves_keep_headroom_and_match_all_three_engines(self):
        import shutil
        if not shutil.which('node'):self.skipTest('Node unavailable')
        script="const {mixCurve}=require('./src/apple_web_host/flow.cjs');console.log(JSON.stringify(['shared','smooth'].map(s=>Array.from({length:101},(_,i)=>mixCurve(i/100,s)))));"
        values=json.loads(subprocess.check_output(['node','-e',script],cwd=Path(__file__).resolve().parents[1],text=True))
        for shape,js in zip(('shared','smooth'),values):
            before=-1
            for i,value in enumerate(js):
                a,b=curve(i/100,shape);self.assertAlmostEqual(a+b,1);self.assertGreaterEqual(b,before);before=b
                self.assertAlmostEqual(value,b);self.assertAlmostEqual(float(pcm_curve(i/100,flow=True,shape=shape)),b)
        self.assertNotAlmostEqual(values[0][25],values[1][25])


class PlannedPlayback(unittest.TestCase):
    setUp=fixture.FlowTests.setUp
    state=fixture.FlowTests.state
    def plan(self,value):
        key=playlist_key('youtube',{'id':'first'})
        a,b=self.music.book.queues['youtube'][:2]
        a['flow_playlist']=b['flow_playlist']=key
        self.flow.plans.put(key,[(a,b,value)]);self.flow.enabled=True
    def test_manual_recipe_reaches_actual_deck_without_global_beat_override(self):
        self.plan(dict(mode='manual',seconds=3,shape='smooth',beats=False))
        self.flow.tick(self.state());self.assertFalse(self.decks.beat_sync);self.assertEqual(self.decks.shape,'smooth')
        self.now=22.5;self.flow.tick(self.state(176.5));self.decks.transition.assert_not_called()
        self.now=23;self.flow.tick(self.state(176.8));self.decks.transition.assert_called_once()
        self.assertAlmostEqual(self.decks.transition.call_args.args[0],3)
    def test_cut_preserves_ordinary_queue_and_never_starts_mixing(self):
        self.plan(dict(mode='cut'));self.flow.tick(self.state())
        self.now=25;self.flow.tick(self.state(179));self.decks.prepare.assert_not_called();self.decks.transition.assert_not_called()
        self.assertEqual(self.music.book.indices['youtube'],0)
    def test_changed_recipe_reprepares_without_starting_music(self):
        self.plan(dict(mode='manual',seconds=3));self.flow.tick(self.state())
        self.plan(dict(mode='manual',seconds=5,shape='smooth'));self.flow.tick(self.state())
        self.assertEqual(self.decks.prepare.call_count,2);self.assertEqual(self.decks.shape,'smooth')
        self.decks.transition.assert_not_called()


class Audition(unittest.TestCase):
    def test_preview_keeps_manual_queue_seeks_in_seconds_and_cancels_stale_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=host();h.source='youtube';h.play_youtube=Mock()
            service=MusicService(h,Path(tmp)/'queue.json')
            try:
                key=playlist_key('youtube',{'id':'preview'})
                items=[dict(song(x),flow_playlist=key) for x in 'ABC']
                service.add([song('D')])
                self.assertTrue(service.preview_transition(items,0))
                self.assertEqual([i['id'] for _,i in service.book.upcoming('youtube')],['B'*11,'D'*11,'C'*11])
                state=dict(items[0],duration=180,position=2,playing=True)
                service.flow.ready=True;service.poll_transition_preview(state)
                h.seek_to.assert_called_once_with(167)
                self.assertIsNone(service.transition_preview);self.assertFalse(service.flow.ready)
                service.transition_preview=(service.play_generation-1,'stale',0)
                service.poll_transition_preview(state);self.assertIsNone(service.transition_preview)
            finally:service.close()


if __name__=='__main__':unittest.main()
