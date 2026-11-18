"""Bounded cloth, truthful cover colours and interruption-safe finite light."""
import math
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from velvet_art import BASE, NEUTRAL, DURATION, Light, cloth, colours


class VelvetArtTests(unittest.TestCase):
    def test_dark_wine_cloth_is_static_bounded_and_not_flat(self):
        for width,height in ((1920,1080),(3840,2160),(320,180),(1,1)):
            w,h,data=cloth(width,height)
            self.assertLessEqual(max(w,h),640)
            self.assertEqual(len(data),w*h*3)
            a=np.frombuffer(data,np.uint8).reshape(h,w,3)
            self.assertLess(int(a.max()),60)
            self.assertGreater(a[:,:,0].mean(),a[:,:,1].mean()*1.5)
            if w>1:self.assertGreater(float(a[:,:,0].std()),2.)
            self.assertIs(cloth(width,height)[2],data)

    def test_real_cover_hues_remain_distinct_and_light_is_bounded(self):
        red=colours((1.,0.,0.,.8,.1,.1,1.))
        blue=colours((0.,0.,1.,.1,.1,.8,1.))
        self.assertGreater(red[0],red[2]+.7)
        self.assertGreater(blue[2],blue[0]+.7)
        self.assertTrue(all(0<=v<=1 for v in red+blue))
        self.assertEqual(colours(None),NEUTRAL)
        self.assertEqual(colours((1.,1.,1.,1.,1.,1.,0.)),NEUTRAL)
        self.assertEqual(colours((math.nan,)*6+(1.,)),NEUTRAL)

    def test_finite_transition_and_retarget_from_visible_colour(self):
        light=Light();target=colours((1.,.1,.1,.8,.3,.1,1.))
        self.assertTrue(light.set(target));start=light.values
        light.advance(DURATION*.4)
        visible=light.values
        self.assertNotEqual(visible,start)
        self.assertNotEqual(visible,target)
        next_target=colours((.1,.2,1.,.1,.5,.9,1.))
        self.assertTrue(light.set(next_target))
        self.assertEqual(light.values,visible)
        self.assertEqual(light.start,visible)
        light.advance(DURATION)
        self.assertEqual(light.values,next_target)
        self.assertFalse(light.active)
        self.assertFalse(light.set(next_target))
        light.set(target,animate=False)
        self.assertEqual(light.values,target)
        self.assertFalse(light.active)


if __name__=='__main__':unittest.main()
