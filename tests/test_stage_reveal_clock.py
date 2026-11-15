"""A slow first paint must not skip a fullscreen transition."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from stage_reveal import StageReveal

class RevealClockTests(unittest.TestCase):
    def reveal(self,reverse=False):
        frames=[]
        reveal=SimpleNamespace(active=True,started=None,last_now=None,DURATION=StageReveal.DURATION,progress=1. if reverse else 0.,
            fallback=True,morphing=False,reversing=reverse,completed=None,
            queue_render=lambda:frames.append(reveal.progress))
        reveal.finish=lambda:setattr(reveal,'active',False)
        return reveal,frames

    def test_cold_paint_stall_keeps_intermediate_frames_and_still_finishes(self):
        for reverse in (False,True):
            reveal,frames=self.reveal(reverse)
            StageReveal.advance(reveal,1_000_000)
            StageReveal.advance(reveal,3_000_000)
            self.assertTrue(reveal.active)
            self.assertGreater(reveal.progress,0);self.assertLess(reveal.progress,1)
            self.assertGreater(frames[-1],0);self.assertLess(frames[-1],1)
            for frame in range(1,60):StageReveal.advance(reveal,3_000_000+frame*16_667)
            self.assertFalse(reveal.active)

    def test_old_frame_timestamp_cannot_rewind_the_transition(self):
        reveal,_=self.reveal()
        StageReveal.advance(reveal,1_000_000);StageReveal.advance(reveal,1_016_667)
        before=reveal.progress
        StageReveal.advance(reveal,500_000)
        self.assertEqual(reveal.progress,before)

if __name__=='__main__':unittest.main()
