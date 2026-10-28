"""Artist photographs must belong to the requested artist, not Spotify's UI."""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import spotify_artwork as artwork

ARTIST = 'ARTIST123'
PAGE = 'https://open.spotify.com/artist/' + ARTIST
PHOTO = 'https://i.scdn.co/image/ab6761610000e5eb' + 'a' * 24
DECORATION = 'https://open.spotifycdn.com/cdn/images/player-loading-strip.png'


class Response(io.BytesIO):
    def geturl(self):
        return PAGE


class SpotifyArtworkTests(unittest.TestCase):
    def setUp(self):
        artwork._cache.clear()

    def test_public_identity_and_photo_are_read_without_account_headers(self):
        page = ('<head><meta content="' + PHOTO + '" property="og:image">'
                '<meta property="og:url" content="' + PAGE + '"></head>').encode()
        opener = Mock()
        opener.open.return_value = Response(page)
        with patch.object(artwork, 'build_opener', return_value=opener):
            self.assertEqual(artwork.artist_image(ARTIST, DECORATION), PHOTO)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, PAGE)
        self.assertNotIn('Cookie', request.headers)
        self.assertNotIn('Authorization', request.headers)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 2.5)

    def test_another_artists_open_graph_image_is_rejected(self):
        page = ('<head><meta property="og:url" content="' + PAGE + 'OTHER">'
                '<meta property="og:image" content="' + PHOTO + '"></head>').encode()
        with patch.object(artwork, 'build_opener') as build:
            build.return_value.open.return_value = Response(page)
            self.assertEqual(artwork.artist_image(ARTIST, DECORATION), '')

    def test_decorative_assets_and_album_covers_are_not_portrait_fallbacks(self):
        album = PHOTO.replace('ab676161', 'ab67616d')
        with patch.object(artwork, 'public_image', side_effect=OSError('offline')):
            for value in (DECORATION, album, 'https://evil.invalid/image/' + 'a' * 40):
                self.assertEqual(artwork.artist_image(ARTIST, value), '')
            self.assertEqual(artwork.artist_image(ARTIST, PHOTO), PHOTO)

    def test_successful_photo_is_cached_by_artist_identity(self):
        with patch.object(artwork, 'public_image', return_value=PHOTO) as read:
            self.assertEqual(artwork.artist_image(ARTIST), PHOTO)
            self.assertEqual(artwork.artist_image(ARTIST), PHOTO)
            read.assert_called_once_with(ARTIST)
            artwork.artist_image('OTHER123')
            self.assertEqual(read.call_count, 2)

    def test_temporary_failure_expires_and_can_recover(self):
        with patch.object(artwork, 'public_image', side_effect=['', PHOTO]) as read, \
                patch.object(artwork.time, 'monotonic', return_value=100):
            self.assertEqual(artwork.artist_image(ARTIST), '')
            self.assertEqual(artwork.artist_image(ARTIST), '')
            self.assertEqual(read.call_count, 1)
            with patch.object(artwork.time, 'monotonic', return_value=121):
                self.assertEqual(artwork.artist_image(ARTIST), PHOTO)

    def test_invalid_identity_does_not_make_a_request(self):
        with patch.object(artwork, 'public_image') as read:
            for value in ('../account', 'https://evil.invalid/', '', 'a?token=private'):
                self.assertEqual(artwork.artist_image(value), '')
            read.assert_not_called()
        self.assertEqual(artwork.artist_id(PAGE.replace('spotify.com', 'spotify.com.evil.invalid')), '')
        self.assertEqual(artwork.artist_id(PAGE.replace('spotify.com', 'spotify.com:8443')), '')
        self.assertEqual(artwork.artist_id(PAGE.replace('/artist/', '/intl-ru/artist/')), ARTIST)

    def test_redirect_cannot_leave_the_requested_artist(self):
        redirect = artwork.ArtistRedirect(ARTIST)
        self.assertIsNone(redirect.redirect_request(None, None, 302, '', {}, PAGE + 'OTHER'))
        self.assertIsNone(redirect.redirect_request(None, None, 302, '', {}, 'https://evil.invalid/'))

    def test_body_metadata_and_oversized_html_are_ignored(self):
        page = ('<head>' + ' ' * artwork.MAX_HEAD + '</head><body>'
                '<meta property="og:url" content="' + PAGE + '">'
                '<meta property="og:image" content="' + PHOTO + '"></body>').encode()
        response = Response(page)
        with patch.object(artwork, 'build_opener') as build:
            build.return_value.open.return_value = response
            self.assertEqual(artwork.artist_image(ARTIST), '')
        parser = artwork.ArtistMetadata()
        parser.feed('<head></head><body><meta property="og:image" content="' + PHOTO + '">')
        self.assertEqual(parser.image, '')


if __name__ == '__main__':
    unittest.main()
