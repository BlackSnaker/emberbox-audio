import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import gi
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf,GLib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mirror_palette import Palette,swatches,NEUTRAL

def image(colours):
    raw=bytes(c for y in range(24) for x in range(24) for c in colours[x*len(colours)//24])
    return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(raw),GdkPixbuf.Colorspace.RGB,True,8,24,24,96)

class Colours(unittest.TestCase):
    def test_two_dominant_colours_stay_distinct(self):
        result=swatches(image([(230,20,25,255),(15,30,240,255)]))
        hues=(result[:3],result[3:6])
        self.assertTrue(any(c[0]>c[2]*2 for c in hues))
        self.assertTrue(any(c[2]>c[0]*2 for c in hues))
        self.assertGreater(result[6],.7)
    def test_monochrome_and_transparency_remain_neutral(self):
        for colour in [(0,0,0,255),(255,0,0,0)]:
            self.assertEqual(swatches(image([colour])),NEUTRAL)
        self.assertEqual(swatches(None),NEUTRAL)
    def test_pixel_colours_are_preserved_at_full_strength(self):
        for colour in [(240,240,240,255),(100,100,100,255),(245,12,25,255),(30,55,110,255)]:
            result=swatches(image([colour]))
            for a,b in zip(result[:3],colour[:3]):self.assertAlmostEqual(a,b/255,places=6)
            self.assertEqual(result[6],1.)
    def test_cached_displayed_art_holds_until_new_cover_arrives(self):
        red=image([(240,0,0,255)]);blue=image([(0,0,240,255)])
        h=SimpleNamespace(art_url='first',cover=SimpleNamespace(get_pixbuf=lambda:red));p=Palette()
        with patch('mirror_palette.swatches',wraps=swatches) as extract:
            for _ in range(120):p.advance(1/60,h)
            self.assertEqual(extract.call_count,1)
            before=p.values;h.art_url='next';p.advance(.5,h)
            self.assertGreater(p.target[0],p.target[2])
            self.assertLess(max(abs(a-b) for a,b in zip(p.values,before)),.3)
            h.cover.get_pixbuf=lambda:blue;p.advance(.5,h)
            self.assertEqual(extract.call_count,2);self.assertGreater(p.target[2],p.target[0])
    def test_transition_is_smooth_and_invalid_time_holds(self):
        p=Palette();h=SimpleNamespace(art_url='a',cover=SimpleNamespace(get_pixbuf=lambda:image([(230,10,0,255)])))
        before=p.values;p.advance(1/60,h)
        self.assertLess(max(abs(a-b) for a,b in zip(p.values,before)),.01)
        for dt in (0,-1,float('nan'),float('inf'),None):
            before=p.values;p.advance(dt,h);self.assertEqual(p.values,before)
    def test_missing_cover_returns_to_neutral(self):
        p=Palette();h=SimpleNamespace(art_url='a',cover=SimpleNamespace(get_pixbuf=lambda:image([(230,10,0,255)])))
        p.advance(20,h);self.assertGreater(p.values[6],.8)
        p.advance(30,None);self.assertLess(p.values[6],1e-6)

if __name__=='__main__':unittest.main()
