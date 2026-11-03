"""Original vector ornament bounds; no display, network or audio is required."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from winter_art import winter_image


class WinterArtTests(unittest.TestCase):
    def test_widget_corner_clipping_and_cached_vector_sizes(self):
        for width in (320,460):
            image=winter_image(width,43)
            self.assertEqual((image.get_width(),image.get_height()),(width,43))
            self.assertIs(image,winter_image(width,43))
            self.assertTrue(image.get_has_alpha())
            self.assertEqual(image.get_pixels()[3],0,'Garland must respect rounded widget corners')
        self.assertEqual(winter_image.cache_info().maxsize,16)

    def test_fullscreen_ornament_strip_and_preview_have_bounded_storage(self):
        for width,height,kind in ((1920,186,'top'),(88,70,'corner'),(222,86,'preview')):
            image=winter_image(width,height,kind)
            self.assertEqual((image.get_width(),image.get_height()),(width,height))
            self.assertLessEqual(image.get_byte_length(),width*height*4)
