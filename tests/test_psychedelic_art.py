"""Palette fidelity, bounded neighbouring hues and continuous retargeting."""
import colorsys
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from psychedelic_art import palette,composition,LiquidState


def test_cover_hues():
    for rgb in ((.9,.2,.1),(.1,.6,.8),(.2,.2,.2),(0.,0.,0.),(1.,1.,1.)):
        result=palette(rgb+(.2,.4,.3))
        assert result[:3]==rgb and result[3:6]==(.2,.4,.3)
        h,s,v=colorsys.rgb_to_hsv(*rgb)
        for i in (6,9,12):
            nh,ns,nv=colorsys.rgb_to_hsv(*result[i:i+3])
            assert all(0<=value<=1 for value in result[i:i+3])
            if s>.15 and v>.08:
                assert abs(nv-v)<1e-8
                assert abs((nh-h+.5)%1-.5)<=.076


def test_song_shapes_and_retargeting():
    assert composition('a')==composition('a')
    assert composition('a')!=composition('b')
    state=LiquidState();before=state.values
    state.retarget((.8,.2,.1,.6,.3,.1),'a')
    assert state.values==before
    state.advance(.1);visible=state.values
    assert visible!=before and visible!=state.target
    state.retarget((.1,.5,.8,.2,.4,.7),'b')
    assert state.values==visible
    state.advance(4);assert state.values==state.target


if __name__=='__main__':
    test_cover_hues();test_song_shapes_and_retargeting()
    print('PASS cover palette, adjacent hues, unique song geometry and continuous retargeting')

# unittest discovery is used by the repository's CI.
import unittest
class PsychedelicArtTests(unittest.TestCase):
    def test_colours(self):
        test_cover_hues()

    def test_transitions(self):
        test_song_shapes_and_retargeting()


class FramePacingTests(unittest.TestCase):
    def test_vsync_cadence(self):
        from psychedelic_art import FramePacer
        for hz in (60,120,144,165):
            pacer=FramePacer()
            count=sum(pacer.due(i/hz + (.0002 if i%2 else -.0002)) for i in range(hz*10))
            self.assertLessEqual(abs(count-600),1,(hz,count))

    def test_no_catchup_burst(self):
        from psychedelic_art import FramePacer
        pacer=FramePacer()
        self.assertTrue(pacer.due(0.))
        self.assertTrue(pacer.due(5.))
        self.assertFalse(pacer.due(5.0001))
        pacer.reset()
        self.assertTrue(pacer.due(5.0002))

class SilhouetteTests(unittest.TestCase):
    def test_distinct_cached_masks(self):
        from psychedelic_art import lens_masks,silhouettes
        masks=lens_masks()
        self.assertEqual(len(set(masks)),5)
        self.assertTrue(all(len(mask)==128*128 and 0<max(mask)<100 for mask in masks))
        weights=silhouettes('a')
        self.assertNotEqual(weights,silhouettes('b'))
        self.assertTrue(all(sum(weights[i:i+5])==1 for i in range(0,25,5)))

    def test_masks_blend_continuously(self):
        from psychedelic_art import LiquidState
        state=LiquidState()
        state.retarget((.5,.3,.2,.4,.2,.1),'new song')
        visible=state.values
        state.advance(.4)
        self.assertNotEqual(state.values,visible)
        for i in range(35,60,5):
            self.assertAlmostEqual(sum(state.values[i:i+5]),1.)


class SparsePaletteTests(unittest.TestCase):
    def test_monochrome_has_visible_muted_harmony(self):
        for rgb in ((0.,)*3,(.03,)*3,(.5,)*3,(1.,)*3):
            result=palette(rgb+rgb,'neutral cover')
            self.assertEqual(result[:6],rgb+rgb)
            shades=[colorsys.rgb_to_hsv(*result[i:i+3]) for i in (6,9,12)]
            self.assertTrue(all(.20<s<.51 and .4<v<.7 for h,s,v in shades))
            self.assertLess(max(h for h,s,v in shades)-min(h for h,s,v in shades),.20)
            self.assertEqual(result,palette(rgb+rgb,'neutral cover'))

    def test_single_hue_keeps_related_colour(self):
        for rgb in ((.8,.1,.15),(.1,.55,.8),(.1,.5,.2)):
            h=colorsys.rgb_to_hsv(*rgb)[0]
            result=palette(rgb+rgb)
            for i in (6,9,12):
                nh,ns,nv=colorsys.rgb_to_hsv(*result[i:i+3])
                self.assertLess(abs((nh-h+.5)%1-.5),.106)

    def test_rich_cover_keeps_original_neighbours(self):
        rgb=(.8,.1,.15);other=(.1,.5,.6)
        result=palette(rgb+other)
        self.assertEqual(result[:6],rgb+other)
        h,s,v=colorsys.rgb_to_hsv(*rgb)
        for offset,i in zip((-.055,.035,.075),(6,9,12)):
            self.assertEqual(result[i:i+3],colorsys.hsv_to_rgb((h+offset)%1.,s*.92,v))


class AudioEnvelopeTests(unittest.TestCase):
    def test_attack_is_soft_at_fixed_frame_steps(self):
        from types import SimpleNamespace
        from mirror_optics import Optics
        optics=Optics()
        rhythm=SimpleNamespace(fresh=True,key=None,
            meter=SimpleNamespace(rms_level=1.,levels=(.3,)*9),
            timing=SimpleNamespace(bpm=None,accent=0.))
        values=[]
        for _ in range(6):
            optics.advance(1/60,rhythm);values.append(optics.values[1])
        self.assertTrue(all(a<b for a,b in zip(values,values[1:])))
        self.assertTrue(0<values[-1]<.25,values)
        rhythm.fresh=False
        optics.advance(1/60,rhythm)
        self.assertTrue(0<optics.values[1]<values[-1])
