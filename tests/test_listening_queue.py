"""Queue state, source isolation and natural-end handling without a player."""
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from listening_queue import QueueBook,EndWatch,track,matches,LIMIT


def song(id='A',**kw):return dict(uri='spotify:track:'+id,title='Song '+id,artist='Artist',**kw)
def state(id='A',position=12,playing=True,**kw):
    return dict(id=id,uri='spotify:track:'+id,title='Song '+id,artist='Artist',position=position,
                duration=180,playing=playing,valid=True,**kw)


class QueueState(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.book=QueueBook(Path(self.folder.name)/'queue.json')
    def test_restore_never_autoplays_and_preserves_private_file(self):
        b=self.book;b.add('spotify',[song('A'),song('B')]);b.select('spotify',0)
        restored=QueueBook(b.path)
        self.assertIsNone(restored.active)
        self.assertEqual(restored.indices['spotify'],0)
        self.assertEqual(restored.upcoming('spotify')[0][1]['uri'],'spotify:track:B')
        self.assertEqual(b.path.stat().st_mode&0o777,0o600)
    def test_source_validation_and_bounded_queue(self):
        for uri in ('file:///tmp/music','spotify:album:ABC','spotify:track:../bad','javascript:play'):
            self.assertIsNone(track(dict(uri=uri,title='Invalid'),'spotify'))
        self.assertIsNone(track({'uri':'apple:songs:123','title':'Wrong source'},'spotify'))
        self.book.add('spotify',[song(str(i)) for i in range(LIMIT+5)])
        self.assertEqual(len(self.book.queues['spotify']),LIMIT)
        self.assertEqual(self.book.add('spotify',[song('more')]),0)
    def test_reorder_and_remove_only_pending_tracks(self):
        b=self.book;b.add('spotify',[song('A'),song('B'),song('C')]);b.select('spotify',0)
        b.move('spotify',2,-1)
        self.assertEqual([i['id'] for i in b.queues['spotify']],['A','C','B'])
        b.remove('spotify',0);b.move('spotify',1,-1)
        self.assertEqual(b.current('spotify')['id'],'A')
        b.remove('spotify',2);b.clear('spotify')
        self.assertEqual([i['id'] for i in b.queues['spotify']],['A'])
    def test_other_source_and_duplicate_entries_survive(self):
        b=self.book;b.add('spotify',[song('A'),song('A')]);b.add('apple-music',[{'uri':'apple:songs:123','title':'Apple'}])
        self.assertNotEqual(b.queues['spotify'][0]['entry'],b.queues['spotify'][1]['entry'])
        b.replace('spotify',[song('B')]);self.assertEqual(len(b.queues['apple-music']),1)
    def test_corrupt_restore_is_empty(self):
        self.book.path.write_text('{incomplete')
        self.assertFalse(QueueBook(self.book.path).queues['spotify'])


class Ends(unittest.TestCase):
    def test_pause_does_not_skip_even_near_end(self):
        w=EndWatch();s=track(song(),'spotify');w.observe(s,state(position=177))
        self.assertIsNone(w.observe(s,state(position=179.5,playing=False)))
        self.assertIsNone(w.observe(s,state(position=179.8,playing=False)))
        self.assertEqual(w.observe(s,state(position=180,playing=False)),'next')
        self.assertIsNone(w.observe(s,state(position=180,playing=False)))
    def test_ended_flag_and_metadata_gaps(self):
        w=EndWatch();s=track(song(),'spotify');w.observe(s,state(position=179))
        self.assertIsNone(w.observe(s,{'valid':False}))
        self.assertEqual(w.observe(s,state(position=0,playing=False,ended=True)),'next')
    def test_natural_context_advance_is_replaced_with_our_next(self):
        w=EndWatch();s=track(song(),'spotify');w.observe(s,state(position=179))
        self.assertEqual(w.observe(s,state('Other',position=0)),'next')
    def test_external_selection_mid_song_releases_queue(self):
        w=EndWatch();s=track(song(),'spotify');w.observe(s,state(position=40))
        self.assertEqual(w.observe(s,state('Other',position=0)),'external')
    def test_library_to_catalog_metadata_match_uses_names(self):
        item=track({'uri':'apple:library-songs:i.test','title':'Тихий вечер','artist':'Исполнитель'},'apple-music')
        self.assertTrue(matches(item,{'id':'123','title':'Тихий вечер','artist':'Исполнитель'}))
        self.assertFalse(matches(item,{'id':'124','title':'Иная запись','artist':'Исполнитель'}))

if __name__=='__main__':unittest.main()
