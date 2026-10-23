"""Original cover selection and exact-release motion lookup, with no network."""
from pathlib import Path
import io
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GLib
from cover_sources import still_candidates, apple_page, is_motion_url, motion_rendition, ApplePage, AppleMotion
from artwork import Artwork

SONG='https://music.apple.com/us/song/12345'
ALBUM='https://music.apple.com/us/album/fixture/45678'
VIDEO='https://mvod.itunes.apple.com/itunes-assets/HLSMusic/fixture/default.m3u8'


def drain(predicate, seconds=2):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():return True
        time.sleep(.005)
    return False


class Covers(unittest.TestCase):
    def test_known_sizes_upgrade_without_corrupting_signed_or_unknown_urls(self):
        url='https://is1-ssl.mzstatic.com/image/thumb/Music123/fixture/cover.jpg/180x180bb.webp?test=1'
        result=still_candidates(url)
        self.assertEqual(result,[url.replace('180x180bb.webp','1200x1200bb.jpg'),url])
        self.assertIn('/1200x1200',still_candidates(url.replace('180x180bb.webp','{w}x{h}bb.{f}'))[0])
        spotify='https://i.scdn.co/image/ab67616d00004851abcdef'
        self.assertIn('ab67616d0000b273abcdef',still_candidates(spotify)[0])
        self.assertTrue(still_candidates('https://avatars.yandex.net/get-music-content/123/id/400x400')[0].endswith('/1000x1000'))
        self.assertTrue(still_candidates('https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg')[0].endswith('/maxresdefault.jpg'))
        unknown='https://example.invalid/image/180x180.jpg?signature=unchanged'
        self.assertEqual(still_candidates(unknown),[unknown])
        self.assertEqual(still_candidates('file:///tmp/cover.jpg'),['file:///tmp/cover.jpg'])

    def test_public_url_checks_and_song_schema_ignore_recommendations(self):
        page=ApplePage()
        page.feed('<script type="application/ld+json">'+
            '{"@type":"MusicComposition","audio":{"inAlbum":{"url":"'+ALBUM+'"}}}</script>'+
            '<a href="https://music.apple.com/us/album/wrong/99999">Related release</a>'+
            '<video src="'+VIDEO+'"></video>')
        self.assertEqual(page.album,ALBUM)
        self.assertEqual(page.motion,'')
        page.feed('<amp-ambient-video class="editorial-video editorial-video--cover" src="'+VIDEO+'"></amp-ambient-video>')
        self.assertEqual(page.motion,VIDEO)
        self.assertEqual(apple_page(SONG+'?anything=discard'),SONG)
        for bad in ('https://music.apple.com.evil.invalid/us/song/12345','https://user:password@music.apple.com/us/song/12345',
                    'https://music.apple.com/us/artist/12345','file:///tmp/cover.m3u8'):
            self.assertFalse(apple_page(bad))
        for bad in ('file:///tmp/cover.mp4','https://example.invalid/clip.mp4',
                    'https://mvod.itunes.apple.com:9000/clip.mp4'):
            self.assertFalse(is_motion_url(bad))
        self.assertTrue(is_motion_url(VIDEO))
        unrelated=ApplePage()
        unrelated.feed('<h1>Album without motion</h1><amp-ambient-video class="editorial-video--cover" src="'+VIDEO+'">')
        self.assertEqual(unrelated.motion,'')

    def test_hls_uses_one_sufficient_square_sdr_stream_instead_of_probing_all(self):
        manifest='''#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=200000,CODECS="avc1.64001f",RESOLUTION=360x360
small.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1000000,CODECS="hvc1.2",RESOLUTION=2160x2160
hdr.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2000000,CODECS="avc1.64001f",RESOLUTION=768x768
square.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3000000,CODECS="avc1.64001f",RESOLUTION=768x1024
portrait.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=900000,CODECS="avc1.64001f",RESOLUTION=768x768
https://unrelated.invalid/injected.m3u8
'''
        self.assertEqual(motion_rendition(manifest,VIDEO),VIDEO.replace('default.m3u8','square.m3u8'))
        self.assertEqual(motion_rendition('#EXTM3U\n#EXTINF:5\nsegment.ts',VIDEO),VIDEO)

    def test_exact_album_lookup_cancel_and_cache_keep_gui_thread_safe(self):
        changes=[]
        client=AppleMotion(lambda value:changes.append((threading.get_ident(),value)))
        entered,release=threading.Event(),threading.Event()
        calls=[]
        def page(url,generation):
            calls.append(url)
            if url==SONG:
                entered.set();release.wait(1)
                return SimpleNamespace(album=ALBUM,motion='')
            return SimpleNamespace(album='',motion=VIDEO)
        try:
            with patch.object(client,'_page',side_effect=page):
                client.set_track(SONG,'fixture-cover')
                self.assertTrue(entered.wait(1))
                client.set_track('')
                release.set()
                client.future.result(timeout=1)
                drain(lambda:False,.04)
                self.assertNotIn(VIDEO,[v for _,v in changes])
                client.set_track(ALBUM,'fixture-cover')
                self.assertTrue(drain(lambda:changes[-1][1]==VIDEO))
                before=len(calls)
                client.set_track('')
                client.set_track(SONG,'fixture-cover')
                self.assertEqual(changes[-1][1],VIDEO)
                self.assertEqual(len(calls),before)
                self.assertTrue(all(ident==threading.get_ident() for ident,_ in changes))
        finally:
            release.set();client.close()

    def test_failed_motion_is_optional_and_preserves_still(self):
        changes=[]
        client=AppleMotion(changes.append)
        try:
            with patch.object(client,'_page',side_effect=OSError('offline')):
                client.set_track(SONG,'fixture-cover')
                self.assertTrue(drain(lambda:bool(client.cache)))
                self.assertEqual(changes[-1],'')
        finally:client.close()

    def test_artist_photo_cache_keeps_aspect_and_source_edges(self):
        loader=Artwork()
        try:
            with tempfile.TemporaryDirectory() as folder:
                loader.folder=Path(folder)/'cache';loader.folder.mkdir()
                photo=Image.new('RGB',(200,400),'green')
                for y in range(20):
                    for x in range(200):photo.putpixel((x,y),(255,0,0));photo.putpixel((x,399-y),(0,0,255))
                path=Path(folder)/'portrait.png';photo.save(path)
                token=(path.as_uri(),400,0,'original-v1','aspect-v1')
                widget=SimpleNamespace(_art_token=token)
                with patch('artwork.GLib.idle_add'):loader._fetch(widget,token,None)
                saved=next(loader.folder.glob('*.png'))
                with Image.open(saved) as output:
                    self.assertEqual(output.size,(200,400))
                    self.assertEqual(output.getpixel((100,0)),(255,0,0,255))
                    self.assertEqual(output.getpixel((100,399)),(0,0,255,255))
        finally:loader.pool.shutdown(wait=False,cancel_futures=True)

    def test_high_quality_fetch_uses_original_and_falls_back_to_larger_response(self):
        def png(size,color):
            buffer=io.BytesIO();Image.new('RGB',size,color).save(buffer,format='PNG');return buffer.getvalue()
        loader=Artwork()
        with tempfile.TemporaryDirectory() as folder:
            loader.folder=Path(folder)
            url='https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg'
            token=(url,400,22,'original-v1')
            image=SimpleNamespace(_art_token=token)
            requested=[]
            def request(candidate,**options):
                requested.append(candidate)
                # A 200 response may still be a missing-HD thumbnail.
                return io.BytesIO(png((120,90),'red') if 'maxresdefault' in candidate else png((640,480),'green'))
            with patch('artwork.urllib.request.urlopen',side_effect=request),patch('artwork.GLib.idle_add'):
                loader._fetch(image,token,None)
            self.assertEqual(len(requested),2)
            saved=next(Path(folder).glob('*.png'))
            with Image.open(saved) as output:
                self.assertEqual(output.size,(400,400))
                self.assertEqual(output.getpixel((200,200))[:3],(0,128,0))
                self.assertEqual(output.getpixel((0,0))[3],0)
            loader.pool.shutdown(wait=False,cancel_futures=True)


if __name__=='__main__':unittest.main()
