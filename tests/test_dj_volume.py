"""Temporary speech attenuation must not alter the dial or persist a low volume."""
import sys,unittest
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from spotify_volume import SpotifyVolume


class DuckingTests(unittest.TestCase):
    def sound(self):
        s=object.__new__(SpotifyVolume)
        s.closed=False;s.configured=True;s.volume=.8;s.muted=False;s.ducking=s.duck_target=1.;s.duck_timer=0
        s.revision=0;s.dirty=False;s.timer=42;s.busy=False;s.refresh_again=False;s.stream_ids=set();s.changed=lambda *_:None
        s._schedule_save=lambda:None
        return s
    def test_smooth_gain_leaves_saved_volume_untouched(self):
        s=self.sound()
        with patch('spotify_volume.GLib.timeout_add',return_value=42),patch('spotify_volume.time.monotonic',return_value=10):s.set_ducking(.28)
        with patch('spotify_volume.time.monotonic',return_value=10.11):self.assertTrue(s._duck_step())
        self.assertAlmostEqual(s.ducking,.64);self.assertEqual(s.volume,.8)
        with patch('spotify_volume.time.monotonic',return_value=10.3):self.assertFalse(s._duck_step())
        self.assertAlmostEqual(s.ducking,.28);self.assertEqual(s.volume,.8)
    def test_stream_readback_recovers_base_volume(self):
        s=self.sound();s.ducking=.25
        f=Future();f.set_result(([{'index':1,'volume':{'left':{'value':round(.2*65536)}},'mute':False}],set()))
        s._done(0,f);self.assertAlmostEqual(s.volume,.8,places=3)
    def test_user_volume_change_during_speech_is_kept(self):
        s=self.sound();s.ducking=s.duck_target=.28;s._change=lambda:None;s.set_volume(.45)
        with patch('spotify_volume.GLib.timeout_add',return_value=42),patch('spotify_volume.time.monotonic',return_value=20):s.set_ducking(1)
        with patch('spotify_volume.time.monotonic',return_value=20.3):s._duck_step()
        self.assertEqual(s.volume,.45);self.assertEqual(s.ducking,1)
    def test_no_stream_configuration_does_not_write_a_default_volume(self):
        s=self.sound();s.configured=False;s.set_ducking(.2)
        self.assertEqual(s.duck_target,1)

if __name__=='__main__':unittest.main()
