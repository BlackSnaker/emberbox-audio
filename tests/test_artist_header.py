"""The clear artist photo must retain all four edges and original proportions."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PIL import Image,ImageDraw
import numpy as np
import gi
gi.require_version('Gtk','3.0')
from artist_header import atmospheric_backdrop,compose,portrait_rect,portrait_slot

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

    def test_bright_photographs_keep_cream_text_readable_at_each_reading_width(self):
        def luminance(rgb):
            rgb=np.asarray(rgb,dtype=np.float32)/255
            return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)@np.array((.2126,.7152,.0722))
        cream=luminance((251,241,199))
        for width,height in ((1744,360),(1104,248),(928,212)):
            with self.subTest(banner=(width,height)):
                background=np.asarray(atmospheric_backdrop(Image.new('RGBA',(640,640),'white'),width,height))
                edge=width-portrait_slot(width,height)-24
                contrast=(cream+.05)/(luminance(background[24:-24,24:edge,:3])+.05)
                self.assertGreaterEqual(float(contrast.min()),4.5,
                    'Photo-derived light must not wash out the heading and actions')

    def test_ambient_light_retains_source_colour_and_monochrome_depth(self):
        width,height=928,212
        fields=[np.asarray(atmospheric_backdrop(Image.new('RGBA',(320,320),color),width,height))
                for color in ('red','blue')]
        # Read outside the clear photograph, where a fixed bronze wash would
        # otherwise make unrelated artists look identical.
        red,blue=[rgb[24:-24,width//2:width*2//3,:3].mean(axis=(0,1)) for rgb in fields]
        self.assertGreater(red[0]-red[2],25)
        self.assertGreater(blue[2]-blue[0],25)
        mono=Image.linear_gradient('L').rotate(90).resize((640,640)).convert('RGBA')
        result=np.asarray(atmospheric_backdrop(mono,width,height))
        self.assertGreater(float(result[24:-24,width//2:width*2//3,:3].std()),7,
            'Monochrome photos still need visible light and shadow')

    def test_cached_composition_has_static_grain_and_untinted_clear_photo(self):
        source=Image.linear_gradient('L').resize((480,640)).convert('RGB')
        pixels=(source.tobytes(),source.size,False,source.width*3)
        width,height=1104,248
        first=compose(pixels,width,height)
        self.assertEqual(first,compose(pixels,width,height),'Static matte grain cannot flicker between renders')
        x,y,w,h=portrait_rect(source.size,width,height)
        image=Image.frombytes('RGBA',(width,height),first)
        expected=source.resize((w,h),Image.Resampling.LANCZOS)
        self.assertEqual(image.crop((x,y,x+w,y+h)).convert('RGB').tobytes(),expected.tobytes(),
            'The new lighting and texture must never tint the actual photograph')

if __name__=='__main__':unittest.main()
