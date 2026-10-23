"""The clear artist photo must retain all four edges and original proportions."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PIL import Image,ImageDraw
import numpy as np
import gi
gi.require_version('Gtk','3.0')
from artist_header import compose

class ArtistPortraits(unittest.TestCase):
    def test_all_four_photo_corners_survive_landscape_square_and_tall_sources(self):
        colors=((255,0,0),(0,255,0),(0,0,255),(255,255,0))
        for size in ((240,360),(360,240),(240,240),(720,120)):
            source=Image.new('RGB',size,(130,130,130));draw=ImageDraw.Draw(source)
            w,h=size;bw,bh=w//5,h//5
            for bounds,color in zip(((0,0,bw,bh),(w-bw-1,0,w-1,bh),
                                      (0,h-bh-1,bw,h-1),(w-bw-1,h-bh-1,w-1,h-1)),colors):draw.rectangle(bounds,fill=color)
            pixels=(source.tobytes(),size,False,w*3)
            for width,height in ((1744,220),(928,152)):
                with self.subTest(source=size,banner=(width,height)):
                    result=np.asarray(Image.frombytes('RGBA',(width,height),compose(pixels,width,height)))
                    corners=[]
                    for color in colors:
                        ys,xs=np.where(np.all(result[:,:,:3]==color,axis=2)&(result[:,:,3]==255))
                        self.assertGreater(len(xs),0,f'Photo corner {color} was cropped or faded')
                        corners.append((xs.min(),ys.min(),xs.max(),ys.max()))
                    left=min(c[0] for c in corners);right=max(c[2] for c in corners)
                    top=min(c[1] for c in corners);bottom=max(c[3] for c in corners)
                    self.assertGreater(left,width*.65,'The clear photo must stay away from the reading area')
                    self.assertGreater(top,7);self.assertLess(bottom,height-8)
                    self.assertAlmostEqual((right-left+1)/(bottom-top+1),w/h,delta=.07,
                        msg='The full photograph must not be stretched')
                    self.assertLess(corners[0][2],corners[1][0]);self.assertLess(corners[0][3],corners[2][1])
                    self.assertEqual(int(result[0,0,3]),0,'The outer banner retains rounded corners')

if __name__=='__main__':unittest.main()
