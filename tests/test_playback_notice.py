from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
import gi
gi.require_version('Gtk','3.0')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from playback_notice import playback_notice


class LoadingStages(unittest.TestCase):
    def host(self,source='apple-music'):
        client=NS(state={},connected=False,error='')
        return NS(source=source,native_web=lambda:client,music=NS(loading=False,error=''),
                  equalizer=NS(frames_ready=True),startup_pending=False)

    def test_connect_load_signin_then_ready_are_distinct(self):
        for source in ('apple-music','spotify','yandex-music'):
            h=self.host(source);c=h.native_web()
            self.assertEqual(playback_notice(h).phase,'connect')
            c.connected=True;self.assertEqual(playback_notice(h).phase,'service')
            c.state={'ready':True,'authorized':False}
            self.assertEqual(playback_notice(h).action,'accounts');self.assertFalse(playback_notice(h).busy)
            c.state['authorized']=True;self.assertEqual(playback_notice(h).phase,'')

    def test_native_loading_is_visible_even_without_a_queue_request(self):
        h=self.host();c=h.native_web();c.connected=True
        c.state={'ready':True,'authorized':True,'spatial':{'enabled':True,'phase':'preparing'}}
        self.assertEqual(playback_notice(h).phase,'track');self.assertTrue(playback_notice(h).busy)
        c.state['spatial']={'phase':'playing'}
        self.assertFalse(playback_notice(h).busy)

    def test_errors_stop_busy_and_lamp_preparation_does_not_claim_music_is_loading(self):
        h=self.host();c=h.native_web();c.connected=True;c.state={'ready':True,'authorized':True}
        h.equalizer.frames_ready=False;self.assertEqual(playback_notice(h).phase,'lamps')
        h.music.loading=True;self.assertEqual(playback_notice(h).phase,'track')
        h.music.error='Friendly fixture error';notice=playback_notice(h)
        self.assertFalse(notice.busy);self.assertEqual(notice.action,'track')

    def test_youtube_without_login_and_browser_sessions(self):
        h=self.host('youtube');h.native_web=lambda:None;h.youtube_native=lambda:True
        h.youtube=NS(loading=True,error='');self.assertTrue(playback_notice(h).busy)
        h.youtube.loading=False;self.assertFalse(playback_notice(h).busy)
        h.startup_pending=True;self.assertEqual(playback_notice(h).phase,'startup')


if __name__=='__main__':unittest.main()
