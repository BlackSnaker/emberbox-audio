"""The paused print must keep colour and the complete picture."""
from pathlib import Path
import sys
import unittest
import gi
gi.require_version('Gtk','3.0');gi.require_version('GdkPixbuf','2.0')
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from cover_pause import cover_frames


def paused(image):
    size=image.width
    frames=cover_frames((image.tobytes(),size,size,True,size*4),size,8)
    return np.frombuffer(frames[0],dtype=np.uint8).reshape(size,size,4),frames[2]


class PausedMaterial(unittest.TestCase):
    def test_light_dark_and_saturated_pictures_keep_their_colour(self):
        for colour in ((255,255,255),(8,8,8),(225,38,145),(27,135,230)):
            with self.subTest(colour=colour):
                pixels,_=paused(Image.new('RGBA',(128,128),colour+(255,)))
                self.assertLessEqual(np.abs(pixels[32:96,32:96,:3].astype(int)-colour).max(),1)

    def test_all_four_picture_edges_remain_visible(self):
        image=Image.new('RGBA',(128,128),(120,120,120,255));draw=ImageDraw.Draw(image)
        colours=((255,0,0),(0,255,0),(0,0,255),(255,255,0))
        for (x,y),colour in zip(((4,60),(120,60),(60,4),(60,120)),colours):
            draw.rectangle((x,y,x+3,y+3),fill=colour+(255,))
        pixels,_=paused(image)
        for colour in colours:
            self.assertGreater(np.count_nonzero(np.max(np.abs(pixels[...,:3].astype(int)-colour),axis=2)<10),2)

    def test_transparency_has_a_quiet_bounded_material(self):
        pixels,material=paused(Image.new('RGBA',(128,128),(0,0,0,0)))
        self.assertEqual(pixels[0,0,3],0);self.assertEqual(pixels[64,64,3],255)
        self.assertLessEqual(np.max(np.abs(np.asarray(material)*255-(38,37,33))),5)


if __name__=='__main__':unittest.main()
