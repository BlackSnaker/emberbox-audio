"""Theme subscriptions follow the playing song without owning audio transport."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mirror_rhythm import SongRhythm
from audio_meter import SpotifyAudioMeter


def host():
    return SimpleNamespace(source='apple-music',playing=True,sound=SimpleNamespace(muted=False),
        title='First',artist='Ember Sessions',album='Light',length=180000000,position=12000000,meter=SpotifyAudioMeter())


def measured(meter,now,bpm=120):
    meter.last_sample=now;meter.rms_level=.4;meter.beat_grid_at=now
    meter.beat_grid=dict(bpm=bpm,period=60/bpm,phase=.137,confidence=.95)


class Rhythm(unittest.TestCase):
    def test_new_song_never_uses_previous_tempo_and_locks_only_new_measurement(self):
        h=host();r=SongRhythm('fixture')
        measured(h.meter,100,120);r.advance(h,100,1/60)
        self.assertIsNone(r.timing.bpm)
        measured(h.meter,101,120);r.advance(h,101,1/60);self.assertEqual(r.timing.bpm,120)
        h.title='Second';h.position=0;r.advance(h,102,1/60);self.assertIsNone(r.timing.bpm)
        measured(h.meter,103,160);r.advance(h,103,1/60);self.assertEqual(r.timing.bpm,160)
        r.release();self.assertIsNone(h.meter.rhythm)
    def test_mute_pause_and_source_switch_release_the_right_meter(self):
        h=host();r=SongRhythm('fixture');r.advance(h,100,.02)
        measured(h.meter,101);r.advance(h,101,.02)
        old=h.meter;h.meter=SpotifyAudioMeter();h.source='youtube';r.advance(h,102,.02)
        self.assertIsNone(old.rhythm);self.assertIsNotNone(h.meter.rhythm)
        h.sound.muted=True;r.advance(h,103,.02);self.assertIsNone(h.meter.rhythm)
        h.sound.muted=False;h.playing=False;r.advance(h,104,.02);self.assertIsNone(r.timing.bpm)
    def test_stale_audio_and_old_estimates_cannot_drive_pulses(self):
        h=host();r=SongRhythm('fixture');r.advance(h,100,.02)
        measured(h.meter,101);r.advance(h,101,.02);self.assertEqual(r.timing.bpm,120)
        r.advance(h,104,.02);self.assertIsNone(r.timing.bpm)
        h.meter.last_sample=104;h.meter.rms_level=.4;r.advance(h,104,.02);self.assertIsNone(r.timing.bpm)
    def test_seek_restarts_visual_history_without_disabling_flow_consumer(self):
        h=host();r=SongRhythm('fixture');r.advance(h,100,.02);tap=h.meter.rhythm
        h.position=80000000;r.advance(h,101,.02);self.assertIsNot(h.meter.rhythm,tap)
        h.meter.set_rhythm('flow-next');flow=h.meter.rhythm
        r.release();self.assertIs(h.meter.rhythm,flow);self.assertEqual(h.meter.rhythm_key,'flow-next')
        h.meter.stop()


if __name__=='__main__':unittest.main()
