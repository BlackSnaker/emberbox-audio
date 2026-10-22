"""Source adapters and asynchronous queue playback with no account access."""
from pathlib import Path
from types import SimpleNamespace
import sys,tempfile,threading,time,unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import GLib
from music_library import MusicRepository,MusicService
from test_listening_queue import song


class Name:
    def __init__(self,value):self.value=value
    def get_text(self):return self.value


def host():
    return SimpleNamespace(source='spotify',title=Name('Song A'),artist=Name('Artist'),playing=True,
        length=180_000_000,position=12_000_000,session=None,sessions=[],browser_binding='',youtube_binding='',
        apple_mode='native',youtube_mode='native',monitor=MagicMock(),seek_to=MagicMock(),
        apple_web=MagicMock(),apple=MagicMock(),yandex_web=MagicMock(),
        youtube=SimpleNamespace(queue=[],current=None,eof=False,paused=True,mpv=None))


def drain(predicate,seconds=2):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        if predicate():return True
        time.sleep(.005)
    return False


class Adapters(unittest.TestCase):
    def test_apple_library_album_and_catalogue_requests(self):
        h=host();r=MusicRepository(h)
        for category,expected in [('home','playlists'),('albums','albums')]:
            r.load('apple-music',category)
            h.apple_web.request.assert_called_with('browse',category=expected,offset=0)
        r.load('apple-music','search','Song')
        h.apple_web.request.assert_called_with('search',term='Song')
        r.load('apple-music','albums',collection={'kind':'library-albums','id':'l.fixture'},offset=100)
        h.apple_web.request.assert_called_with('tracks',kind='library-albums',id='l.fixture',offset=100)
        h.apple_mode='browser'
        with self.assertRaises(RuntimeError):r.load('apple-music','search','Song')
    def test_spotify_search_album_filter_and_background_play(self):
        h=host();r=MusicRepository(h)
        with patch('music_library.LocalSpotify') as api:
            client=api.return_value.__enter__.return_value
            client.home.return_value={'shelves':[{'items':[
                {'uri':'spotify:album:ALB','title':'Album'},{'uri':'spotify:playlist:PL','title':'Mix'}]}]}
            self.assertEqual([i['kind'] for i in r.load('spotify','albums')['items']],['album'])
            r.load('spotify','search','Song');client.search.assert_called_once_with('Song')
            r.play(dict(song(),source='spotify'),lambda:False);client.play.assert_not_called()
            r.play(dict(song(),source='spotify'),lambda:True);client.play.assert_called_once_with('spotify:track:A')
    def test_yandex_queue_relocates_exact_track_before_play(self):
        h=host();h.source='yandex-music';r=MusicRepository(h)
        item={'source':'yandex-music','id':'123','title':'Evening','artist':'Artist'}
        h.yandex_web.request.return_value={'items':[{'id':'999','title':'Other version'}]}
        with self.assertRaises(RuntimeError):r.play(item,lambda:True)
        self.assertEqual(h.yandex_web.request.call_count,1)
        h.yandex_web.request.reset_mock();h.yandex_web.request.return_value={'items':[{'id':'123'}]}
        r.play(item,lambda:True)
        self.assertEqual(h.yandex_web.request.call_args_list[0].args,('search',))
        h.yandex_web.request.assert_called_with('play',id='123')


class Playback(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.host=host();self.service=MusicService(self.host,Path(self.folder.name)/'queue.json')
        self.addCleanup(self.service.close)
        self.calls=[];self.service.repository.play=lambda item,alive:self.calls.append(item['id']) if alive() else None
    def test_add_does_not_play_natural_end_advances_without_a_view(self):
        s=self.service;s.add([song('A'),song('B')]);self.assertFalse(self.calls)
        s.start();self.assertTrue(drain(lambda:not s.loading));self.assertEqual(self.calls,['A'])
        s.poll();self.host.position=180_000_000;self.host.playing=False;s.poll()
        self.assertTrue(drain(lambda:not s.loading));self.assertEqual(self.calls,['A','B'])
    def test_pause_does_not_consume_next_and_manual_next_uses_queue(self):
        s=self.service;s.add([song('A'),song('B')]);s.start();drain(lambda:not s.loading);s.poll()
        self.host.playing=False;s.poll();self.assertEqual(self.calls,['A'])
        s.step(1);drain(lambda:not s.loading);self.assertEqual(self.calls,['A','B'])
    def test_pending_track_is_inserted_without_replaying_history(self):
        s=self.service;s.add([song('A'),song('B'),song('C')]);s.book.select('spotify',1)
        s.play_now(song('A'));drain(lambda:not s.loading)
        self.assertEqual(s.book.current('spotify')['id'],'A')
        self.assertEqual([i['id'] for _,i in s.book.upcoming('spotify')],['C'])
    def test_search_click_starts_at_selection_and_continues_after_end(self):
        s=self.service;items=[song('A'),song('B'),song('C')]
        s.play_now(items[1],context=items);self.assertTrue(drain(lambda:not s.loading))
        self.assertEqual(self.calls,['B']);self.assertEqual(s.book.current('spotify')['id'],'B')
        self.assertEqual([i['id'] for _,i in s.book.upcoming('spotify')],['C'])
        self.host.title.value='Song B';s.poll()
        self.host.position=180_000_000;self.host.playing=False;s.poll()
        self.assertTrue(drain(lambda:not s.loading));self.assertEqual(self.calls,['B','C'])
    def test_new_search_replaces_automatic_tail_and_keeps_explicit_additions(self):
        s=self.service;first=[song('A'),song('B'),song('C')]
        s.play_now(first[0],context=first);drain(lambda:not s.loading)
        s.add([song('D')]);second=[song('E'),song('F'),song('G')]
        s.play_now(second[1],context=second);drain(lambda:not s.loading)
        self.assertEqual(s.book.current('spotify')['id'],'F')
        self.assertEqual([i['id'] for _,i in s.book.upcoming('spotify')],['D','G'])
        restored=type(s.book)(s.book.path)
        self.assertEqual([i['origin'] for _,i in restored.upcoming('spotify')],['manual','context'])
        self.assertIsNone(restored.active)
    def test_context_capacity_preserves_selection_and_manual_tracks(self):
        s=self.service;s.add([song('M'+str(i)) for i in range(200)])
        items=[song(str(i)) for i in range(250)]
        s.play_now(items[220],context=items)
        self.assertEqual(self.calls,[]);self.assertTrue(s.error)
        self.assertEqual(s.book.queues['spotify'][-1]['id'],'M199')
        s.book.remove('spotify',199)
        s.play_now(items[220],context=items);drain(lambda:not s.loading)
        self.assertEqual(len(s.book.queues['spotify']),200)
        self.assertEqual(s.book.current('spotify')['id'],'220')
        self.assertEqual(len(s.book.upcoming('spotify')),199)
    def test_context_keeps_the_clicked_duplicate_occurrence(self):
        s=self.service;items=[song('A'),song('B'),song('A'),song('C')]
        s.play_now(items[2],context=items);drain(lambda:not s.loading)
        self.assertEqual(s.book.indices['spotify'],2)
        self.assertEqual([i['id'] for _,i in s.book.upcoming('spotify')],['C'])
    def test_youtube_without_duration_advances_from_real_eof(self):
        s=self.service;h=self.host;h.source='youtube';s.source_changed()
        items=[{'uri':'youtube:jNQXAC9IVRw','title':'Live first'}, {'uri':'youtube:mNLJMTRvyj8','title':'Next'}]
        h.play_youtube=MagicMock()
        s.play_now(items[0],context=items)
        h.youtube.current={'id':'jNQXAC9IVRw'};h.length=0;h.playing=True;s.poll()
        h.youtube.eof=True;h.playing=False;s.poll()
        self.assertEqual(h.play_youtube.call_args.args[0]['id'],'mNLJMTRvyj8')
        self.assertEqual(h.play_youtube.call_count,2)
    def test_apple_catalogue_search_uses_catalogue_id_for_continuation(self):
        s=self.service;h=self.host;h.source='apple-music';s.source_changed()
        items=[{'uri':'apple:songs:'+id,'title':'Apple '+id,'artist':'Artist'} for id in ('123','456')]
        s.play_now(items[0],context=items);drain(lambda:not s.loading)
        h.apple_web.state={'id':'i.library','catalogId':'123'}
        h.title.value='Localised title';s.poll()
        self.assertTrue(s.watch.seen)
        h.position=h.length;h.playing=False;s.poll();drain(lambda:not s.loading)
        self.assertEqual(self.calls,['123','456'])
    def test_late_browse_result_cannot_replace_new_source(self):
        entered=threading.Event();release=threading.Event();results=[]
        def load(*args):entered.set();release.wait(1);return {'items':[song()]}
        self.service.repository.load=load
        self.service.load('home',lambda *args:results.append(args));self.assertTrue(entered.wait(1))
        self.host.source='apple-music';self.service.source_changed();release.set()
        drain(lambda:False,.08);self.assertFalse(results)
    def test_failed_play_can_retry_current_item(self):
        s=self.service;s.add([song('A'),song('B')])
        def failed(*_):raise RuntimeError('fixture unavailable')
        s.repository.play=failed;s.start();drain(lambda:not s.loading)
        self.assertIn('fixture unavailable',s.error)
        s.repository.play=lambda item,alive:self.calls.append(item['id'])
        s.start();drain(lambda:not s.loading);self.assertEqual(self.calls,['A'])
    def test_cancelled_queue_does_not_pause_a_new_manual_selection(self):
        entered=threading.Event();release=threading.Event();s=self.service
        s.repository.play=lambda *_:(entered.set(),release.wait(1))
        s.add([song()]);s.start();self.assertTrue(entered.wait(1))
        s.pause=MagicMock();s.stop();release.set()
        self.assertTrue(drain(lambda:s.play_future.done()));drain(lambda:False,.04)
        s.pause.assert_not_called()
    def test_explicit_pause_cancels_late_playback(self):
        entered=threading.Event();release=threading.Event();s=self.service
        s.repository.play=lambda *_:(entered.set(),release.wait(1))
        s.add([song()]);s.start();self.assertTrue(entered.wait(1))
        s.pause=MagicMock();s.stop(pause_pending=True);release.set()
        self.assertTrue(drain(lambda:s.pause.called))
        s.pause.assert_called_once_with('spotify')

if __name__=='__main__':unittest.main()
