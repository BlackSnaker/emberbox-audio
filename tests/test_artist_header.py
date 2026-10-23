"""The clear artist photo must retain all four edges and original proportions."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PIL import Image,ImageDraw
import numpy as np
import gi
gi.require_version('Gtk','3.0')
from artist_header import compose,portrait_rect,portrait_slot

class ArtistPortraits(unittest.TestCase):
    def test_all_four_photo_corners_survive_landscape_square_and_tall_sources(self):
        colors=((255,0,0),(0,255,0),(0,0,255),(255,255,0))
        for size in ((240,360),(360,240),(240,240),(720,120)):
            source=Image.new('RGB',size,(130,130,130));draw=ImageDraw.Draw(source)
            w,h=size;bw,bh=w//5,h//5
            for bounds,color in zip(((0,0,bw,bh),(w-bw-1,0,w-1,bh),
                                      (0,h-bh-1,bw,h-1),(w-bw-1,h-bh-1,w-1,h-1)),colors):draw.rectangle(bounds,fill=color)
            pixels=(source.tobytes(),size,False,w*3)
            for width,height in ((1744,360),(1104,248),(928,212)):
                with self.subTest(source=size,banner=(width,height)):
                    result=np.asarray(Image.frombytes('RGBA',(width,height),compose(pixels,width,height)))
                    corners=[]
                    for color in colors:
                        ys,xs=np.where(np.all(result[:,:,:3]==color,axis=2)&(result[:,:,3]==255))
                        self.assertGreater(len(xs),0,f'Photo corner {color} was cropped or faded')
                        corners.append((xs.min(),ys.min(),xs.max(),ys.max()))
                    left=min(c[0] for c in corners);right=max(c[2] for c in corners)
                    top=min(c[1] for c in corners);bottom=max(c[3] for c in corners)
                    self.assertGreaterEqual(left,width-portrait_slot(width,height)+8,
                        'The complete photograph must remain inside its reserved bay')
                    self.assertGreater(top,7);self.assertLess(bottom,height-8)
                    self.assertAlmostEqual((right-left+1)/(bottom-top+1),w/h,delta=.07,
                        msg='The full photograph must not be stretched')
                    self.assertLess(corners[0][2],corners[1][0]);self.assertLess(corners[0][3],corners[2][1])
                    self.assertEqual(int(result[0,0,3]),0,'The outer banner retains rounded corners')
                    px,py,pw,ph=portrait_rect(size,width,height)
                    self.assertEqual((left,top,right-left+1,bottom-top+1),(px,py,pw,ph),
                        'Painted photograph and text exclusion geometry must agree')
                    if w==h:
                        self.assertGreaterEqual(bottom-top+1,320 if width>=1200 else 160,
                            'The artist photograph must be a substantial focal point, not a thumbnail')
                    if w/h>=5 and width>=1200:
                        self.assertGreaterEqual(right-left+1,600,
                            'Wide photographs must use the generous photo bay instead of a height-limited thumbnail')

    def test_portrait_bay_keeps_text_space_without_pushing_photos_to_the_outer_edge(self):
        for width,height in ((1744,360),(1104,248),(928,212)):
            with self.subTest(banner=(width,height)):
                slot=portrait_slot(width,height)
                self.assertGreaterEqual(width-slot,width*.5,'The heading and actions need their own half')
                self.assertGreaterEqual(slot,width*.39,'Reserve a real photo bay rather than a narrow corner')
                for size in ((640,640),(640,960),(960,640),(1200,200)):
                    x,y,w,h=portrait_rect(size,width,height)
                    self.assertGreater(x,width-slot)
                    self.assertGreater(y,0)
                    self.assertLess(x+w,width)
                    self.assertLess(y+h,height)
                    self.assertAlmostEqual(x+w/2,width-slot/2,delta=1,
                        msg='The clear photograph must be centered in its bay')
                    self.assertAlmostEqual(y+h/2,height/2,delta=1)

if __name__=='__main__':unittest.main()
