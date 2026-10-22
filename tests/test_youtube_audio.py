from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import youtube_audio
from youtube_search import video_url
from sources import Session,choose_session
from stream_target import Target,matches

A={'id':'jNQXAC9IVRw','url':'https://www.youtube.com/watch?v=jNQXAC9IVRw','title':'First','channel':'Fixture','duration':19}
B={'id':'mNLJMTRvyj8','url':'https://www.youtube.com/watch?v=mNLJMTRvyj8','title':'Second','channel':'Fixture','duration':103}


class FakeMPV:
    def __init__(self,version=(0,41,0)):
        self.mpv_version_tuple=version;self.calls=[]
    def command_async(self,*args):self.calls.append(args)
    def terminate(self):pass


class YouTubeAudioTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='emberbox-tube-')
        self.state=patch.object(youtube_audio,'STATE',Path(self.folder.name)/'youtube.json')
        self.state.start()
        self.audio=youtube_audio.YouTubeAudio(lambda:None)
        self.audio.mpv=FakeMPV()

    def tearDown(self):
        self.audio.close();self.state.stop();self.folder.cleanup()

    def test_links_music_subdomain_and_host_validation(self):
        self.assertEqual(video_url('https://music.youtube.com/watch?v=jNQXAC9IVRw'),(A['url'],0))
        self.assertEqual(video_url('https://youtu.be/jNQXAC9IVRw?t=1m2s'),(A['url'],62))
        self.assertIsNone(video_url('https://youtube.com.evil.example/watch?v=jNQXAC9IVRw'))
        with self.assertRaises(ValueError):video_url('https://www.youtube.com/playlist?list=123')

    def test_loadfile_compatibility_and_no_autoplay_after_source_switch(self):
        for version,extra in [((0,37,0),[]),((0,41,0),[-1])]:
            self.audio.mpv=FakeMPV(version)
            self.audio.set_enabled(True)
            self.audio.play(A,[A,B],start=3)
            self.assertEqual(self.audio.mpv.calls[-1],tuple(['loadfile',A['url'],'replace']+extra+['start=3.0,pause=yes']))
            self.audio.set_enabled(False)
            self.audio._loaded()
            self.assertEqual(self.audio.mpv.calls[-1],('set','pause','yes'))

    def test_loaded_play_queue_and_eof(self):
        self.audio.set_enabled(True);self.audio.play(A,[A,B]);self.audio._loaded()
        self.assertEqual(self.audio.mpv.calls[-1],('set','pause','no'))
        self.audio._on_property('eof-reached',True)
        self.assertEqual(self.audio.current['id'],B['id'])
        self.assertEqual(self.audio.index,1)

    def test_quality_is_decoder_data_and_clears_for_next_track(self):
        self.audio.set_enabled(True);self.audio.play(A,[A,B])
        self.audio._on_property('audio-codec-name','opus')
        self.audio._on_property('audio-params',{'samplerate':48000,'channel-count':2,'format':'floatp'})
        self.audio._on_property('audio-bitrate',128000)
        self.audio._loaded()
        self.assertEqual(self.audio.quality['sampleRate'],48000)
        self.assertNotIn('bitDepth',self.audio.quality)
        self.audio.play(B);self.assertEqual(self.audio.quality,{})
        self.audio._failure('Fixture error');self.assertEqual(self.audio.quality,{})

    def test_restart_retains_queue_but_never_starts_playback(self):
        self.audio.set_enabled(True);self.audio.play(A,[A,B]);self.audio.position=8.;self.audio.save()
        restored=youtube_audio.YouTubeAudio(lambda:None)
        self.assertIsNone(restored.mpv)
        self.assertEqual(restored.current['id'],A['id'])
        self.assertEqual(restored.position,8.)
        self.assertTrue(restored.paused)
        self.assertFalse(restored.enabled)

    def test_browser_source_is_separate_from_apple_music(self):
        apple=Session('org.mpris.MediaPlayer2.firefox.apple','Firefox','firefox',properties={'Metadata':{'xesam:url':'https://music.apple.com/us/song/123'}})
        tube=Session('org.mpris.MediaPlayer2.firefox.youtube','Firefox','firefox',properties={'Metadata':{'xesam:url':'https://music.youtube.com/watch?v=jNQXAC9IVRw'}})
        spoof=Session('org.mpris.MediaPlayer2.chromium','Chromium','chromium',properties={'Metadata':{'xesam:url':'https://youtube.com.evil.example'}})
        self.assertIs(choose_session([apple,tube,spoof],'youtube'),tube)
        self.assertIs(choose_session([apple,tube,spoof],'apple-music'),apple)
        self.assertIsNone(choose_session([apple,spoof],'youtube'))

    def test_native_audio_does_not_match_another_widgets_mpv(self):
        import os
        target=Target('youtube',os.getpid(),'','youtube-native')
        self.assertTrue(matches({'application.process.id':os.getpid(),'application.name':youtube_audio.CLIENT_NAME},target))
        self.assertFalse(matches({'application.process.id':99999999,'application.name':'Emberbox Video'},target))

    def test_node_runtime_and_paths_survive_libmpv_suboption_parsing(self):
        try:import mpv
        except (ImportError,OSError):self.skipTest('libmpv is optional in this test environment')
        from youtube_search import ytdl_raw_options,mpv_quoted
        node='/tmp/тёплый, runtime/node'
        with patch('youtube_search.shutil.which',return_value=node):
            player=mpv.MPV(config=False,idle=True,vo='null',ao='null',
                ytdl_raw_options=ytdl_raw_options(),
                script_opts='ytdl_hook-ytdl_path='+mpv_quoted('/tmp/space and, comma/yt-dlp'))
        try:
            self.assertEqual(player['ytdl-raw-options']['js-runtimes'],'node:'+node)
            self.assertEqual(player['script-opts']['ytdl_hook-ytdl_path'],'/tmp/space and, comma/yt-dlp')
        finally:player.terminate()
