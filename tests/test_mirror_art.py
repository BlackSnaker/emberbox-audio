"""Optical atlas bounds, steady exposure and transparent architectural edges."""
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mirror_art import materials,PHASES


class Mirrors(unittest.TestCase):
    def test_cached_facets_have_premultiplied_alpha_and_no_ball_silhouette(self):
        width,height,frames=materials(128)
        self.assertEqual(len(frames),PHASES);self.assertLess(height,width*.5)
        for raw in frames:
            rgba=np.frombuffer(raw,np.uint8).reshape(height,width,4)
            self.assertTrue(np.all(rgba[...,:3]<=rgba[...,3,None]))
            self.assertLess(rgba[:,0,3].max(),5);self.assertLess(rgba[0,:,3].max(),5)
        self.assertNotEqual(frames[0],frames[6])
    def test_light_moves_without_exposure_flashes_including_loop_seam(self):
        w,h,frames=materials(128)
        means=[np.frombuffer(raw,np.uint8).reshape(h,w,4)[...,:3].mean() for raw in frames]
        self.assertLess(max(abs(a-b) for a,b in zip(means,means[1:]+means[:1])),2.)
        self.assertLess(max(means)-min(means),8.)
    def test_widget_trim_and_memory_are_bounded(self):
        w,h,frames=materials(320,trim=True)
        self.assertEqual(h,22);self.assertLess(sum(map(len,frames)),1_000_000)
        self.assertTrue(any(np.frombuffer(raw,np.uint8).max()>50 for raw in frames))


if __name__=='__main__':unittest.main()
