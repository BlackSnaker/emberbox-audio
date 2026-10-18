from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from sources import Session, choose_session
from stream_target import Target, matches, output_nodes


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.spotify=Session('org.mpris.MediaPlayer2.spotify','Spotify','spotify')
        self.firefox=Session('org.mpris.MediaPlayer2.firefox.instance1','Firefox','firefox')
        self.youtube=Session('org.mpris.MediaPlayer2.chromium.instance2','Chromium','chromium',
            properties={'Metadata':{'xesam:url':'https://www.youtube.com/watch?v=123'}})

    def test_no_implicit_browser_selection_or_fallback_to_spotify(self):
        items=[self.spotify,self.firefox,self.youtube]
        self.assertIs(choose_session(items,'spotify'),self.spotify)
        self.assertIsNone(choose_session(items,'apple-music'))
        self.assertIs(choose_session(items,'apple-music','firefox'),self.firefox)
        self.assertIsNone(choose_session(items,'apple-music','chromium'))
        self.assertIsNone(choose_session([self.spotify],'apple-music','firefox'))

    def test_exact_apple_url_and_ambiguous_instances(self):
        apple=Session('org.mpris.MediaPlayer2.firefox.instance3','Firefox','firefox',
            properties={'Metadata':{'xesam:url':'https://music.apple.com/us/song/123'}})
        self.assertIs(choose_session([apple,self.youtube],'apple-music'),apple)
        self.assertIsNone(choose_session([apple,self.firefox],'apple-music','firefox'))
        self.assertIs(choose_session([apple,self.firefox],'apple-music','firefox',apple.name),apple)
        spoof=Session('org.mpris.MediaPlayer2.firefox','Firefox','firefox',
            properties={'Metadata':{'xesam:url':'https://music.apple.com.evil.example/song'}})
        self.assertIsNone(choose_session([spoof],'apple-music'))

    def test_audio_matches_only_selected_source(self):
        spotify={'application.name':'Spotify'}
        browser={'application.name':'Firefox','application.process.id':99999999}
        self.assertTrue(matches(spotify,Target('spotify',player=self.spotify.name)))
        self.assertFalse(matches(browser,Target('spotify',player=self.spotify.name)))
        self.assertFalse(matches(spotify,Target('apple-music',123,'firefox',self.firefox.name)))
        with patch('stream_target.descendant',return_value=False), patch('pathlib.Path.resolve',return_value=Path('/usr/bin/firefox')):
            self.assertFalse(matches(browser,Target('apple-music',123,'firefox',self.firefox.name)))
        self.assertFalse(matches(browser,Target('apple-music',0,'firefox','')))
        with patch('stream_target.descendant',return_value=True):
            self.assertTrue(matches(browser,Target('apple-music',123,'firefox',self.firefox.name)))

    def test_pipewire_native_client_identity(self):
        target=Target('spotify',player=self.spotify.name)
        graph=[{'id':10,'type':'PipeWire:Interface:Client','info':{'props':{'application.name':'Spotify'}}},
               {'id':20,'type':'PipeWire:Interface:Node','info':{'props':{'client.id':10,'media.class':'Stream/Output/Audio'}}},
               {'id':21,'type':'PipeWire:Interface:Node','info':{'props':{'application.name':'Firefox','media.class':'Stream/Output/Audio'}}}]
        self.assertEqual(output_nodes(graph,target),{'20'})

    def test_stale_volume_work_cannot_write_to_another_source(self):
        from spotify_volume import SpotifyVolume
        sound=object.__new__(SpotifyVolume)
        old=Target('spotify',player=self.spotify.name)
        sound.target=Target('apple-music',0,'firefox',self.firefox.name)
        sound.closed=False
        with patch('spotify_volume.source_streams',return_value=[{'index':5}]), patch('spotify_volume.subprocess.run') as run:
            sound._sync(old,.5,False,True,True,set())
            run.assert_not_called()

    def test_separate_volume_profiles(self):
        from spotify_volume import SpotifyVolume
        sound=object.__new__(SpotifyVolume)
        sound.target=Target('spotify',player=self.spotify.name)
        sound.volume=.4;sound.muted=True;sound.configured=True
        sound.saved={};sound.revision=0;sound.busy=True;sound.timer=0;sound.available=True
        sound.changed=lambda obj:None
        sound.refresh(Target('apple-music',0,'firefox',self.firefox.name))
        self.assertEqual(sound.saved['spotify'],{'volume':.4,'muted':True})
        self.assertEqual((sound.volume,sound.muted),(1.,False))
        sound.volume=.7;sound.muted=False;sound.configured=True
        sound.refresh(Target('spotify',player=self.spotify.name))
        self.assertEqual((sound.volume,sound.muted),(.4,True))
        self.assertEqual(sound.saved['apple-music'],{'volume':.7,'muted':False})
