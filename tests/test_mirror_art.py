"""Optical atlas bounds, steady exposure and transparent architectural edges."""
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mirror_art import materials,PHASES
from mirror_glints import glints


class Mirrors(unittest.TestCase):
    def test_unconfirmed_acceleration_keeps_the_cairo_path(self):
        from unittest.mock import patch
        import mirror_facets
        for result,expected in ((True,True),(False,False),(None,False)):
            with patch('mirror_pan_gl.hardware_available',return_value=result) as probe,patch.object(mirror_facets,'_ACCELERATED',None):
                self.assertEqual(mirror_facets.accelerated(),expected)
                self.assertEqual(mirror_facets.accelerated(),expected)
                probe.assert_called_once()

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
    def test_reflections_move_only_right_and_fade_smoothly_before_wrapping(self):
        for t in np.linspace(0,150,180):
            before=glints(t,1920,1080);after=glints(t+1/60,1920,1080)
            self.assertEqual(len(before),12)
            for a,b in zip(before,after):
                x,y,w,h,alpha,_=a
                self.assertTrue(0<=alpha<=.32+1e-12)
                self.assertEqual(a[1],b[1])
                if b[0]>=a[0]:self.assertLess(b[0]-a[0],.3)
                else:self.assertLess(max(a[4],b[4]),.00001)
                self.assertLess(abs(a[4]-b[4]),.0002)
        np.testing.assert_allclose(np.array([v[:5] for v in glints(0,1920,1080)]),
                                   np.array([v[:5] for v in glints(72/.55,1920,1080)]),atol=1e-10)



if __name__=='__main__':unittest.main()
