"""Queue ownership, resource limits and a peak-safe two-stream envelope."""
import json,math,shutil,stat,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ember_flow import EmberFlow
from flow_youtube import curve,YouTubeDecks
from listening_queue import QueueBook


def song(letter):
    ident=letter*11
    return {'uri':'youtube:'+ident,'id':ident,'title':'Song '+letter,'artist':'Fixture','duration_ms':180000}


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.host=SimpleNamespace(source='youtube',youtube_mode='native',fullscreen=None,
            apple_mode='native',apple_web=SimpleNamespace(state={}))
        book=QueueBook(Path(self.tmp.name)/'queue.json');book.replace('youtube',[song(x) for x in 'ABC']);book.select('youtube',0)
        self.music=SimpleNamespace(host=self.host,book=book,loading=False,watch=SimpleNamespace(reset=Mock()),changed=Mock())
        self.flow=EmberFlow(self.music,Path(self.tmp.name)/'flow.json');self.addCleanup(self.flow.close)
        self.now=0.;self.flow.clock=lambda:self.now
        self.decks=Mock();self.decks.ready=True;self.decks.transition.return_value=True;self.decks.recovery=0.
        self.patch=patch('flow_youtube.YouTubeDecks',return_value=self.decks);self.patch.start();self.addCleanup(self.patch.stop)
    def state(self,position=154,letter='A',playing=True):
        return dict(song(letter),position=position,duration=180,valid=True,playing=playing)
    def test_spatial_apple_keeps_flow_without_claiming_beat_alignment(self):
        self.host.source='apple-music';self.host.apple_web.state={'emberFlow':True,'emberBeatSync':False}
        self.assertTrue(self.flow.supported);self.assertFalse(self.flow.beats_supported)
        self.assertTrue(self.flow.beat_sync,'Keep the ordinary-mode preference')
        values=[dict(song(x),uri='apple:songs:'+str(i),id=str(i)) for i,x in enumerate('ABC',100)]
        self.music.book.replace('apple-music',values);self.music.book.select('apple-music',0)
        deck=Mock();deck.ready=True;deck.failed=False;deck.result.return_value=None
        self.flow.enabled=True
        with patch('flow_apple.AppleDecks',return_value=deck):
            self.flow.tick(dict(values[0],position=154,duration=180,valid=True,playing=True))
            self.assertFalse(deck.beat_sync)
            self.now=16.;self.flow.tick(dict(values[0],position=170,duration=180,valid=True,playing=True))
            deck.transition.assert_called_once()
    def test_native_next_is_warmed_early_even_when_automatic_mixing_is_off(self):
        self.host.source='apple-music';self.host.apple_web.state={'emberFlow':True,'emberBeatSync':False,'spatial':{'fastSwitch':True}}
        values=[dict(song(x),uri='apple:songs:'+str(i),id=str(i)) for i,x in enumerate('ABC',100)]
        self.music.book.replace('apple-music',values);self.music.book.select('apple-music',0)
        deck=Mock();deck.ready=True;deck.failed=False
        with patch('flow_apple.AppleDecks',return_value=deck):
            self.flow.tick(dict(values[0],position=2,duration=180,valid=True,playing=True))
            deck.prepare.assert_called_once();self.assertFalse(self.flow.enabled)
            self.now=170;self.flow.tick(dict(values[0],position=172,duration=180,valid=True,playing=True))
            self.flow.tick(dict(values[0],position=173,duration=180,valid=True,playing=True))
            deck.transition.assert_not_called()
    def test_manual_selection_preserves_the_native_prepared_song(self):
        self.flow.apple=Mock();self.flow.cancel(preserve_apple=True)
        self.flow.apple.cancel.assert_called_once_with(preserve=True)
    def test_output_scene_change_reprepares_the_same_upcoming_song(self):
        self.host.source='apple-music';self.host.apple_web.state={'emberFlow':True,'spatial':{'fastSwitch':True,'scene':{'mode':'headphones','hrtf':0}}}
        values=[dict(song(x),uri='apple:songs:'+str(i),id=str(i)) for i,x in enumerate('ABC',100)]
        self.music.book.replace('apple-music',values);self.music.book.select('apple-music',0)
        deck=Mock();deck.ready=True;deck.failed=False
        with patch('flow_apple.AppleDecks',return_value=deck):
            self.flow.tick(dict(values[0],position=2,duration=180,valid=True,playing=True))
            self.host.apple_web.state['spatial']['scene']={'mode':'speakers','angle':30}
            self.now=1;self.flow.tick(dict(values[0],position=3,duration=180,valid=True,playing=True))
            self.assertEqual(deck.prepare.call_count,2);self.assertEqual(deck.prepare.call_args.args[0]['id'],'101')
            self.assertEqual(self.music.book.indices['apple-music'],0);deck.cancel.assert_called()
    def test_off_and_unsupported_sources_do_not_prepare_players(self):
        self.flow.tick(self.state());self.decks.prepare.assert_not_called()
        self.flow.enabled=True;self.host.source='apple-music'
        self.assertFalse(self.flow.supported);self.flow.tick(self.state());self.decks.prepare.assert_not_called()
    def test_preload_once_then_adopt_without_restarting_the_next_track(self):
        self.flow.enabled=True;self.flow.tick(self.state(80));self.decks.prepare.assert_not_called()
        self.now=74;self.flow.tick(self.state());self.flow.tick(self.state())
        self.decks.prepare.assert_called_once();self.assertEqual(self.music.book.indices['youtube'],0)
        self.now=96;self.flow.tick(self.state(176))
        self.decks.transition.assert_called_once();self.assertEqual(self.music.book.current('youtube')['id'],'B'*11)
        self.music.watch.reset.assert_called_once()
        self.now=97;self.flow.tick(self.state(1,'B'))
        self.decks.cancel.assert_not_called()  # The next poll must not cut the outgoing tail.
        self.flow.tick(self.state(1,'B',False));self.decks.cancel.assert_called_once()
    def test_reorder_replaces_only_the_prepared_deck_and_pause_frees_it(self):
        self.flow.enabled=True;self.flow.tick(self.state())
        self.music.book.move('youtube',1,1);self.flow.tick(self.state())
        self.assertEqual(self.decks.prepare.call_args.args[0]['id'],'C'*11)
        self.assertEqual(self.music.book.indices['youtube'],0)
        self.flow.tick(self.state(154,playing=False));self.assertFalse(self.flow.ready)
        self.decks.transition.assert_not_called()
    def test_seeking_does_not_turn_into_an_early_track_change(self):
        self.flow.enabled=True;self.flow.tick(self.state())
        self.now=.25;self.flow.tick(self.state(100));self.decks.transition.assert_not_called()
        self.assertEqual(self.music.book.indices['youtube'],0);self.assertIsNone(self.flow.context)
    def test_a_slow_preload_falls_back_to_the_ordinary_queue(self):
        self.decks.ready=False;self.decks.standby.failed=False
        self.flow.enabled=True;self.flow.tick(self.state())
        self.now=22;self.flow.tick(self.state(176))
        self.assertFalse(self.flow.preparing);self.assertTrue(self.flow.error)
        self.assertEqual(self.music.book.indices['youtube'],0);self.decks.transition.assert_not_called()
        self.flow.tick(self.state(177));self.decks.prepare.assert_called_once()
    def test_preference_is_private_and_restoring_it_never_starts_playback(self):
        self.flow.set_enabled(True)
        self.assertEqual(stat.S_IMODE(self.flow.path.stat().st_mode),0o600)
        restored=EmberFlow(self.music,self.flow.path)
        try:self.assertTrue(restored.enabled);self.assertIsNone(restored.youtube)
        finally:restored.close()
    def test_beat_switch_is_saved_independently_without_starting_a_deck(self):
        self.flow.set_enabled(True);self.flow.set_beat_sync(False)
        restored=EmberFlow(self.music,self.flow.path)
        try:
            self.assertTrue(restored.enabled);self.assertFalse(restored.beat_sync)
            self.assertIsNone(restored.youtube);self.assertIsNone(restored.apple)
        finally:restored.close()
    def test_envelope_has_no_gain_spike_or_endpoint_step(self):
        pairs=[curve(i/1000) for i in range(1001)]
        self.assertEqual(pairs[0],(1,0));self.assertEqual(pairs[-1],(0,1))
        for a,b in pairs:self.assertAlmostEqual(a+b,1);self.assertLessEqual(abs(a+b),1.)
        self.assertLess(pairs[1][1],.00001);self.assertLess(1-pairs[-2][1],.00001)
        self.assertEqual(pairs,sorted(pairs,reverse=True))
        self.assertAlmostEqual(curve(.38)[1],.18)
        self.assertAlmostEqual(curve(.62)[1],.82)
    @unittest.skipUnless(shutil.which('node'),'Node is needed for the cross-engine comparison')
    def test_apple_and_youtube_follow_the_same_audible_envelope(self):
        root=Path(__file__).resolve().parents[1]
        script="const {mixCurve}=require('./src/apple_web_host/flow.cjs');console.log(JSON.stringify(Array.from({length:1001},(_,i)=>mixCurve(i/1000))));"
        values=json.loads(subprocess.check_output(['node','-e',script],cwd=root,text=True))
        for i,value in enumerate(values):self.assertAlmostEqual(value,curve(i/1000)[1],places=12)
    def test_long_mix_begins_early_enough(self):
        self.flow.enabled=True;self.flow.tick(self.state())
        self.now=17.75;self.flow.tick(self.state(171.75))
        self.decks.transition.assert_called_once_with(8.)
    def test_short_next_track_uses_a_proportional_mix(self):
        self.music.book.upcoming('youtube')[0][1]['duration_ms']=20000
        self.flow.enabled=True;self.flow.tick(self.state())
        self.now=23.7;self.flow.tick(self.state(177.7))
        self.decks.transition.assert_called_once_with(2.)
    def test_already_quiet_outro_uses_a_shorter_entrance(self):
        self.host.meter=SimpleNamespace(last_sample=0,rms_level=.2)
        self.flow.enabled=True;self.flow.tick(self.state(170))
        self.now=.8;self.host.meter.last_sample=.8;self.flow.tick(self.state(170.8))
        self.now=7.5;self.host.meter.last_sample=7.5;self.flow.tick(self.state(177.5))
        self.decks.transition.assert_called_once_with(1.4)
    def test_stale_meter_cannot_mistake_an_outro_for_silence(self):
        self.host.meter=SimpleNamespace(last_sample=-1,rms_level=0)
        self.flow.enabled=True;self.flow.tick(self.state(170))
        self.now=2;self.flow.tick(self.state(172))
        self.decks.transition.assert_called_once_with(7.8)
    def test_deck_promotion_keeps_the_outgoing_state_from_overwriting_the_new_one(self):
        old=Mock();new=Mock();new.loaded=True;new.failed=False;new.position=.5
        self.host.youtube=old;self.host.on_youtube_changed=Mock()
        decks=YouTubeDecks(self.host);decks.standby=new
        with patch('flow_youtube.GLib.timeout_add',return_value=17),patch('flow_youtube.GLib.source_remove'):
            self.assertTrue(decks.transition(4));self.assertIs(self.host.youtube,new)
            self.assertFalse(old.persistent);self.assertTrue(new.persistent)
            decks.cancel();old.close.assert_called_once();new.close.assert_not_called()
            self.assertIsNone(new.flow_cancel)
    def test_lost_rhythm_restores_a_primed_deck_before_ordinary_blending(self):
        self.host.meter=SimpleNamespace(rhythm_key='A',beat_grid=None)
        self.host.youtube=Mock();self.host.on_youtube_changed=Mock()
        new=Mock();new.loaded=True;new.failed=False;new.position=.5
        decks=YouTubeDecks(self.host);decks.standby=new;decks.prepared_rate=.97
        decks.preview=SimpleNamespace(future=SimpleNamespace(done=lambda:True,result=lambda:None),cancel=Mock())
        self.assertTrue(decks.ready);self.assertEqual(decks.prepared_rate,1.)
        new.mpv.command_async.assert_any_call('set','speed',1.)
        with patch('flow_youtube.GLib.timeout_add',return_value=17),patch('flow_youtube.GLib.source_remove'):
            self.assertTrue(decks.transition(4));self.assertIsNone(decks.beat_plan);decks.cancel()
    def test_apple_waits_for_confirmation_and_tolerates_the_old_sdk_pause(self):
        self.host.source='apple-music';self.host.apple_web.state={'emberFlow':True}
        values=[dict(song(x),uri='apple:songs:'+str(i),id=str(i)) for i,x in enumerate('ABC',100)]
        self.music.book.replace('apple-music',values);self.music.book.select('apple-music',0)
        deck=Mock();deck.ready=True;deck.failed=False;deck.result.return_value=None
        state=dict(values[0],position=154,duration=180,valid=True,playing=True)
        self.flow.enabled=True
        with patch('flow_apple.AppleDecks',return_value=deck):
            self.flow.tick(state);deck.prepare.assert_called_once()
            self.now=20;self.flow.tick(dict(state,position=174))
            self.assertTrue(self.flow.busy);self.assertEqual(self.music.book.indices['apple-music'],0)
            self.flow.tick(dict(state,position=175,playing=False))
            self.assertTrue(self.flow.busy);deck.cancel.assert_not_called()
            deck.result.return_value={'started':True,'duration':4}
            self.flow.tick(dict(state,position=175,playing=False))
            self.assertFalse(self.flow.busy);self.assertEqual(self.music.book.current('apple-music')['id'],'101')
            self.flow.tick(dict(state,playing=False));deck.cancel.assert_not_called()
            self.flow.tick(dict(values[1],position=1,duration=180,valid=True,playing=False));deck.cancel.assert_called_once()


if __name__=='__main__':unittest.main()
