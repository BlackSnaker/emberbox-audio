"""Source identity and prose boundaries for the fullscreen artist journal."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from artist_catalog import ArtistRepository,artist_ref,plain,sanitize


class Artists(unittest.TestCase):
    def test_prose_is_text_and_preserves_paragraphs(self):
        value=plain('<p>A &amp; B</p><script>credential</script><p><b>Second</b> line</p>')
        self.assertEqual(value,'A & B\n\nSecond line')
        self.assertEqual(plain('x'*100000,20),'x'*20)

    def test_capture_current_recording_and_clicked_recording_separately(self):
        host=SimpleNamespace(source='apple-music',apple_mode='native',artist=MagicMock(),
            apple_web=SimpleNamespace(state={'id':'i.old','catalogId':'123'}))
        host.artist.get_text.return_value='A & B'
        current=artist_ref(host);self.assertEqual(current['songId'],'123');self.assertTrue(current['current'])
        clicked=artist_ref(host,{'id':'456','uri':'apple:albums:456','kind':'albums','artist':'Another artist'})
        self.assertEqual(clicked['songId'],'456');self.assertEqual(clicked['songKind'],'albums')
        self.assertEqual(clicked['name'],'Another artist')
        self.assertNotIn('current',clicked)

    def test_apple_uses_existing_engine_and_only_typed_params(self):
        host=SimpleNamespace(apple_mode='native',apple_web=MagicMock())
        host.apple_web.request.return_value={'artist':{'id':'100','bio':'<b>Story</b>'}}
        repo=ArtistRepository(host)
        result=repo.load('apple-music','artist',{'songId':'123','name':'Artist','unrelated':'NEVER_EXPORT'})
        host.apple_web.request.assert_called_once_with('artist',songId='123',name='Artist',offset=0)
        self.assertEqual(result['artist']['bio'],'Story')
        host.apple_mode='browser'
        with self.assertRaises(RuntimeError):repo.load('apple-music','artist',{'id':'100'})

    def test_yandex_and_youtube_do_not_borrow_another_catalogue(self):
        host=SimpleNamespace(yandex_web=MagicMock())
        host.yandex_web.request.return_value={'items':[]}
        repo=ArtistRepository(host)
        repo.load('yandex-music','artist-section',{'id':'321','section':'compilations'},24)
        host.yandex_web.request.assert_called_once_with('artistSection',id='321',section='compilations',offset=24)
        result=repo.load('youtube','artist',{'name':'A channel'})
        self.assertTrue(result['searchOnly']);self.assertEqual(result['sections'],[])

    def test_response_sizes_are_bounded(self):
        result=sanitize({'items':[{}]*500,'choices':[{}]*100,'sections':[{'items':[{}]*200}],
                         'release':{'description':'<i>Original notes</i>'}})
        self.assertEqual(len(result['items']),200);self.assertEqual(len(result['choices']),20)
        self.assertEqual(len(result['sections'][0]['items']),30)
        self.assertEqual(result['release']['description'],'Original notes')


if __name__=='__main__':unittest.main()
