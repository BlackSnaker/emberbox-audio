"""Deterministic cadence and backpressure checks, independent of CPU speed."""
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('GdkPixbuf','2.0')
from motion_artwork import FrameQueue, FPS


class MotionClock(unittest.TestCase):
    def queue(self,count=12):
        queue=FrameQueue(12)
        for index in range(count):queue.put(index,index)
        return queue

    def test_60fps_presentation_does_not_follow_decoder_arrival_times(self):
        queue=self.queue()
        self.assertEqual(queue.take(10),0)
        self.assertIsNone(queue.take(10+.4/FPS))
        self.assertEqual(queue.take(10+1/FPS),1)
        self.assertEqual(queue.take(10+2/FPS),2)
        self.assertEqual(queue.take(10+4/FPS),4)  # A missed display frame is bounded.

    def test_pause_and_obscured_window_resume_without_catching_up(self):
        queue=self.queue();queue.take(10)
        queue.set_playing(False)
        self.assertIsNone(queue.take(25))
        queue.set_playing(True)
        self.assertEqual(queue.take(25),1)
        self.assertEqual(queue.take(100),2)

    def test_small_vsync_jitter_does_not_repeat_then_skip_frames(self):
        queue=self.queue()
        self.assertEqual(queue.take(10),0)
        for index in range(1,10):
            jitter=-.04 if index%2 else .04
            self.assertEqual(queue.take(10+(index+jitter)/FPS),index)

    def test_rebuffer_holds_frame_then_resumes_in_order(self):
        queue=FrameQueue(8)
        queue.put(0,0);queue.put(1,1)
        self.assertIsNone(queue.take(0),'Start only after the preroll is ready')
        queue.put(2,2);queue.put(3,3)
        self.assertEqual(queue.take(0),0)
        self.assertEqual(queue.take(3/FPS),3)
        self.assertIsNone(queue.take(4/FPS))
        for index in range(4,8):queue.put(index,index)
        self.assertEqual(queue.take(1),4)
        self.assertEqual(queue.rebuffers,1)

    def test_producer_backpressure_and_nonblocking_close(self):
        queue=self.queue();finished=threading.Event()
        producer=threading.Thread(target=lambda:(queue.put(12,12),finished.set()),daemon=True)
        producer.start()
        self.assertFalse(finished.wait(.03),'A full queue must bound decoded-frame memory')
        queue.close()
        self.assertTrue(finished.wait(.5),'Closing must wake a blocked producer')
        self.assertFalse(queue.frames)
        producer.join(.5)

    def test_failed_decoder_drains_short_tail_instead_of_waiting_forever(self):
        queue=FrameQueue(12);queue.put(7,7);queue.put(8,8);queue.finish()
        self.assertEqual(queue.take(0),7)
        self.assertEqual(queue.take(1/FPS),8)


if __name__=='__main__':unittest.main()
