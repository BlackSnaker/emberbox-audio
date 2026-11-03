from pathlib import Path
import sys,tempfile,threading,time,unittest
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from favorites import FavoriteBook,Favorites
from listening_queue import track
from gi.repository import GLib


def song(ident='123',source='apple-music'):
    prefix={'apple-music':'apple:songs:','spotify':'spotify:track:','youtube':'youtube:','yandex-music':'yandex:track:'}[source]
    return track(dict(uri=prefix+ident,title='Original fixture',artist='Ember',album='Test record'),source)


def wait(until):
    end=time.monotonic()+4
    while not until() and time.monotonic()<end:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.005)
    assert until(),'Favourite operation did not finish'


class FavoriteTests(unittest.TestCase):
    def test_private_persistence_deduplication_and_removal(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'favorites.json';book=FavoriteBook(path)
            item=song();book.set(item,True);book.set(item,True,'synced')
            self.assertEqual(len(FavoriteBook(path).items),1)
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(FavoriteBook(path).items[item['uri']]['sync'],'synced')
            book.set(item,False);self.assertFalse(FavoriteBook(path).items)

    def test_local_save_precedes_network_and_captures_exact_track(self):
        release=threading.Event();calls=[]
        def request(method,**params):
            calls.append((method,params));release.wait(3)
            return {'favorite':params['value'],'confirmed':True}
        with tempfile.TemporaryDirectory() as root:
            client=NS(connected=True,request=request)
            host=NS(apple_mode='native',apple_web=client,source='apple-music')
            favorites=Favorites(NS(host=host),Path(root)/'favorites.json');item=song()
            try:
                favorites.set(item,True);favorites.set(item,True)
                wait(lambda:favorites.saved(item))
                self.assertIn(item['uri'],favorites.pending)
                self.assertEqual(favorites.items[item['uri']]['sync'],'local')
                host.source='spotify';release.set();wait(lambda:not favorites.pending)
                self.assertEqual(len(calls),1);self.assertEqual(calls[0][1]['id'],'123')
                self.assertEqual(favorites.items[item['uri']]['sync'],'synced')
            finally:release.set();favorites.close()

    def test_account_failure_retains_local_copy_and_never_claims_success(self):
        with tempfile.TemporaryDirectory() as root:
            client=NS(connected=True,request=lambda *_a,**_k:{'ok':True})
            f=Favorites(NS(host=NS(spotify_mode='native',spotify_web=client)),Path(root)/'favorites.json');item=song('TRACK','spotify')
            try:
                f.set(item,True);wait(lambda:not f.pending)
                self.assertTrue(f.saved(item));self.assertEqual(f.items[item['uri']]['sync'],'local')
                self.assertIn('not confirmed',f.messages[item['uri']])
                f.set(item,False);wait(lambda:not f.pending)
                self.assertFalse(f.saved(item));self.assertFalse(FavoriteBook(f.book.path).items)
            finally:f.close()

    def test_youtube_needs_no_account_and_keeps_its_playable_identity(self):
        with tempfile.TemporaryDirectory() as root:
            f=Favorites(NS(host=NS()),Path(root)/'favorites.json');item=song('abcdefghijk','youtube')
            try:
                f.toggle(item);wait(lambda:not f.pending)
                self.assertTrue(f.saved(item));self.assertEqual(f.items[item['uri']]['url'],'https://www.youtube.com/watch?v=abcdefghijk')
            finally:f.close()


if __name__=='__main__':unittest.main()
