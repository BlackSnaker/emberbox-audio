"""Spotify native routing must not depend on a desktop client or its profile."""
import sys,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from accounts import Accounts
from music_library import MusicRepository,snapshot,MusicService
from artist_catalog import ArtistRepository,artist_ref,album_ref
from spotify_web import SpotifyClient,prepare
from stream_target import Target,matches

class SpotifyWebTests(unittest.TestCase):
    def host(self):
        player=SimpleNamespace(state={'ready':True,'authorized':True,'id':'TRACK','uri':'spotify:track:TRACK','albumId':'ALBUM','album':'Release','artists':[{'id':'ARTIST','name':'Artist'}]},request=Mock(return_value={'items':[],'tracks':[]}),action=Mock(),connected=True)
        return SimpleNamespace(spotify_mode='native',spotify_web=player,source='spotify',title=SimpleNamespace(get_text=lambda:'Song'),artist=SimpleNamespace(get_text=lambda:'Artist'),album=SimpleNamespace(get_text=lambda:'Release'),length=240000000,position=2000000,playing=False)
    def test_accounts_opens_embedded_login_without_installing_or_launching_spotify(self):
        h=self.host();a=Accounts(None,Mock(),Mock(),Mock(),Mock(),spotify=h.spotify_web)
        try:
            with patch('accounts.spotify_command',return_value=None),patch('accounts.launch') as launch:
                a.connect('spotify');h.spotify_web.action.assert_called_once_with('show');launch.assert_not_called()
                state=a.state('spotify');self.assertTrue(state['ready']);self.assertIn('Spotify',state['button'])
        finally:a.close()
    def test_collections_search_play_and_pause_use_native_transport(self):
        h=self.host();r=MusicRepository(h)
        with patch('music_library.LocalSpotify',side_effect=AssertionError('Desktop client used')):
            r.load('spotify','search',term='Fixture');h.spotify_web.request.assert_called_with('search',term='Fixture')
            r.load('spotify','home',collection={'uri':'spotify:playlist:LIST'},offset=50);h.spotify_web.request.assert_called_with('tracks',uri='spotify:playlist:LIST',offset=50)
            r.play({'source':'spotify','uri':'spotify:track:TRACK'},lambda:True);h.spotify_web.request.assert_called_with('play',uri='spotify:track:TRACK')
            MusicService.pause(SimpleNamespace(host=h),'spotify');h.spotify_web.action.assert_called_with('transport',action='pause')
        self.assertEqual(snapshot(h)['uri'],'spotify:track:TRACK')
    def test_artist_and_album_references_stay_tied_to_native_recording(self):
        h=self.host();self.assertEqual(artist_ref(h)['id'],'ARTIST');self.assertEqual(album_ref(h)['id'],'ALBUM')
        ArtistRepository(h).load('spotify','release',album_ref(h));self.assertEqual(h.spotify_web.request.call_args.args[0],'release')
        self.assertEqual(h.spotify_web.request.call_args.kwargs['id'],'ALBUM')
    def test_shared_components_never_reuse_another_sources_signed_in_profile(self):
        shared={'runtime':'fixture-engine','cdm_module':'fixture-module','profile':'apple-private-profile'}
        with patch('spotify_web.apple_setup.configured',side_effect=[None,shared]),patch('spotify_web.apple_setup.save') as save:
            result=prepare();self.assertNotEqual(result['profile'],shared['profile']);self.assertTrue(result['profile'].endswith('spotify-web-profile'));save.assert_called_once()
    def test_native_stream_does_not_fall_back_to_all_spotify_client_outputs(self):
        target=Target('spotify',123,'','spotify-native')
        props={'application.name':'Spotify','application.process.id':'456'}
        with patch('stream_target.descendant',return_value=False):self.assertFalse(matches(props,target))
        with patch('stream_target.descendant',return_value=True):self.assertTrue(matches(props,target))
    def test_shelves_interface_uses_typed_requests_only(self):
        h=self.host();c=SpotifyClient(h.spotify_web);c.home();h.spotify_web.request.assert_called_with('browse',category='home')
        c.play('spotify:track:TRACK');h.spotify_web.request.assert_called_with('play',uri='spotify:track:TRACK')

if __name__=='__main__':unittest.main()
