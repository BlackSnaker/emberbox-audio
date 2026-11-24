import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from listening_queue import track
from podcast_catalog import APPLE, PodcastCatalog, apple_feed, apple_shows, public_url
from podcast_discovery import LANGUAGES, PodcastDiscovery, showcase
from stream_target import Target, matches
from yandex_web import YandexWeb


class PodcastTests(unittest.TestCase):
    def test_featured_wall_prefills_all_supported_languages(self):
        for language in LANGUAGES.keys() - {'all'}:
            with self.subTest(language=language):
                cards = showcase(APPLE, language, 'science')
                self.assertGreaterEqual(len(cards), 3)
                self.assertTrue(all(item['language'] == language and 'science' in item['categories']
                                    for item in cards))
        self.assertTrue(all(item['uri'].startswith('spotify:show:') for item in showcase('spotify', 'ru', 'all')))
        self.assertTrue(showcase('yandex-music', 'ru', 'history'))
        self.assertGreater(len({item['language'] for item in showcase(APPLE, 'all', 'all')}), 1)

    def test_apple_language_filter_uses_feed_metadata_and_the_selected_storefront(self):
        from unittest.mock import patch
        catalogue = Mock()
        catalogue.load.return_value = [
            {'id':'90001','kind':'show','title':'English title','feed':'https://example.org/russian',
             'genre_ids':['1533']},
            {'id':'90002','kind':'show','title':'Русское название','feed':'https://example.org/english',
             'genre_ids':['1533']},
        ]
        with patch('podcast_discovery.feed_language', side_effect=['ru', 'en']):
            values = PodcastDiscovery(catalogue).search(APPLE, 'topic', 'ru', 'science')
        catalogue.load.assert_called_once_with(APPLE, 'topic', country='ru')
        self.assertEqual([item['id'] for item in values], ['90001'])

    def test_apple_catalogue_and_enclosures(self):
        data = {'results': [
            {'collectionId': 123, 'collectionName': 'Show', 'feedUrl': 'https://publisher.example/feed'},
            {'collectionId': 124, 'collectionName': 'Subscriber only'},
        ]}
        show, = apple_shows(data)
        rss = b'''<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
                       xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
          <description><![CDATA[<p>About the show.</p><p>Science &amp; people.</p>]]></description>
          <item><title>Episode</title><guid>stable</guid><itunes:duration>1:02:03</itunes:duration>
          <description>This is the short summary.</description>
          <content:encoded><![CDATA[<p>Full notes.</p><script>Hidden</script><p>Second paragraph.</p>]]></content:encoded>
          <enclosure type="audio/mpeg" url="https://publisher.example/one.mp3"/></item>
          <item><title>Repeated enclosure</title><enclosure url="https://publisher.example/one.mp3"/></item>
          <item><title>Video</title><enclosure type="video/mp4" url="https://publisher.example/video.mp4"/></item>
          <item><title>Local</title><enclosure url="file:///etc/passwd"/></item>
        </channel></rss>'''
        about, (episode,) = apple_feed(show, rss)
        self.assertEqual(about, 'About the show.\n\nScience & people.')
        self.assertEqual(episode['description'], 'Full notes.\n\nSecond paragraph.')
        self.assertEqual((episode['artist'], episode['title'], episode['duration_ms']), ('Show', 'Episode', 3723000))
        self.assertEqual(episode['id'], apple_feed(show, rss.replace(b'one.mp3', b'new.mp3'))[1][0]['id'])
        self.assertEqual(episode['uri'], APPLE + ':episode:' + episode['id'])
        with self.assertRaises(ValueError):
            apple_feed(show, '<!DOCTYPE rss><rss/>'.encode('utf-16'))

    def test_local_addresses_and_credentials_are_not_media_urls(self):
        for url in ('https://localhost/a', 'https://127.0.0.1/a', 'https://a.local/a',
                    'https://account:password@publisher.example/a', 'https://publisher.example:80/a'):
            self.assertEqual(public_url(url), '')

    def test_spotify_uses_typed_native_routes_and_preserves_episode_identity(self):
        entry = {'kind': 'episode', 'id': 'ABC', 'title': 'Episode', 'uri': 'spotify:episode:ABC'}
        spotify = Mock()
        spotify.request.return_value = {'items': [entry, {'kind': 'track', 'id': 'ABC', 'title': 'Song'}]}
        catalog = PodcastCatalog(SimpleNamespace(spotify_web=spotify))
        row, = catalog.load('spotify', 'Example')
        spotify.request.assert_called_once_with('search', term='Example', media='podcasts')
        self.assertEqual(track(row, 'spotify')['kind'], 'episode')
        catalog.load('spotify', '', {'uri': 'spotify:show:XYZ', 'title': 'Example'})
        spotify.request.assert_called_with('tracks', uri='spotify:show:XYZ')

    def test_yandex_catalogue_search_and_album_episodes(self):
        yandex = YandexWeb.__new__(YandexWeb)
        yandex.closed = False
        yandex.api = Mock()
        yandex.api.call.side_effect = [
            {'podcasts': {'results': [{'id': 22, 'title': 'Show'}]}},
            {'title': 'Show', 'description': {'text': 'Show <b>details</b>'},
             'volumes': [[{'id': 11, 'title': 'First episode', 'durationMs': 10000, 'shortDescription':'Episode notes'},
                                          {'id': 12, 'title': 'Unavailable', 'available': False}]]},
        ]
        catalog = PodcastCatalog(SimpleNamespace(yandex_web=yandex))
        show, = catalog.load('yandex-music', 'Show')
        yandex.api.call.assert_called_with('search', text='Show', type='podcast', page=0)
        show, (episode,) = catalog.open_show('yandex-music', show)
        yandex.api.call.assert_called_with('albums/22/with-tracks')
        self.assertEqual((episode['kind'], episode['uri'], episode['duration_ms']),
                         ('episode', 'yandex:track:11', 10000))
        self.assertEqual(track(episode, 'yandex-music')['kind'], 'episode')
        self.assertEqual(show['description'], 'Show details')
        self.assertEqual(episode['description'], 'Episode notes')

    def test_podcast_audio_matches_only_its_mpv_stream(self):
        import os
        target = Target(APPLE, os.getpid(), '', 'podcast-native')
        props = {'application.process.id': os.getpid()}
        podcast = dict(props, **{'application.name': 'Emberbox Apple Podcasts'})
        self.assertTrue(matches(podcast, target))
        self.assertFalse(matches(dict(props, **{'application.name': 'Emberbox Audio YouTube'}), target))
        self.assertFalse(matches(podcast, Target('youtube', os.getpid(), '', 'youtube-native')))


if __name__ == '__main__':
    unittest.main()
