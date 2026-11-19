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
            assert abs(nv-v)<1e-8
            if s:assert abs((nh-h+.5)%1-.5)<=.076
            else:assert ns==0


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
