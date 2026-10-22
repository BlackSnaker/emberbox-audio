from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from karaoke_timeline import HeardTimeline,PlaybackPoint


class TimelineTests(unittest.TestCase):
    def point(self,when,position,playing=True,key=('first',)):
        return PlaybackPoint(when,key,'Original fixture','Ember',position,180.,playing)

    def test_natural_next_keeps_old_lyrics_until_that_audio_finishes(self):
        timeline=HeardTimeline()
        timeline.observe(self.point(10,179), 'first lyrics')
        timeline.observe(self.point(11,0,key=('second',)), 'second loading')
        timeline.observe(self.point(11.2,.2,key=('second',)), 'second ready')
        point,state=timeline.at(11.4,1.2)
        self.assertEqual(point.key,('first',));self.assertAlmostEqual(point.position,179.2)
        self.assertEqual(state,'first lyrics')
        point,state=timeline.at(12.3,1.2)
        self.assertEqual(point.key,('second',));self.assertAlmostEqual(point.position,.1)
        self.assertEqual(state,'second ready')

    def test_pause_and_seek_follow_the_buffer_in_both_directions(self):
        timeline=HeardTimeline()
        timeline.observe(self.point(10,50),'words')
        timeline.observe(self.point(11,51,False),'words')
        self.assertTrue(timeline.at(11.4,1)[0].playing)
        self.assertFalse(timeline.at(12.4,1)[0].playing)
        self.assertEqual(timeline.at(12.4,1)[0].position,51)
        timeline.observe(self.point(13,8,True),'words')
        self.assertEqual(timeline.at(13.8,1)[0].position,51)
        self.assertAlmostEqual(timeline.at(14.2,1)[0].position,8.2)

    def test_bypass_uses_latest_state_and_history_is_bounded(self):
        timeline=HeardTimeline()
        for i in range(500):timeline.observe(self.point(i,i%180,key=(i,)),str(i))
        self.assertEqual(len(timeline.points),180);self.assertEqual(len(timeline.lyrics),8)
        self.assertEqual(timeline.at(499,0)[1],'499')
        timeline.clear();self.assertEqual(timeline.at(500),(None,None))


if __name__=='__main__':unittest.main()
