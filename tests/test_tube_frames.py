"""The shipped sprites preserve the glass artwork without live SVG rendering."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
gi.require_version('Gdk','3.0')
gi.require_version('Atk','1.0')
gi.require_version('GdkPixbuf','2.0')
from hardware_controls import pixbuf
from tube_meter import tube_frame,tube_frames,tube_svg,FRAME_WIDTH,FRAME_HEIGHT


def visible_difference(actual,expected):
    """Compare visible colour and opacity, allowing SVG renderer rounding."""
    def rgba(image):
        # Subpixbuf rows retain the atlas stride; padding is not pixel data.
        return np.ndarray((image.get_height(),image.get_width(),4),dtype=np.uint8,
            buffer=image.get_pixels(),strides=(image.get_rowstride(),4,1)).astype(np.int32)
    a,b=rgba(actual),rgba(expected)
    def composite(value,background):
        alpha=value[:,:,3:4]
        return (value[:,:,:3]*alpha+background*(255-alpha)+127)//255
    # Both backgrounds constrain alpha as well as colour. Near-transparent RGB
    # can differ by rounding/unpremultiplication without changing the artwork.
    return max(int(np.abs(composite(a,bg)-composite(b,bg)).max()) for bg in (0,255))


class TubeFramesTests(unittest.TestCase):
    def test_every_level_is_shipped_without_live_svg_rendering(self):
        tube_frames.cache_clear()
        with patch('hardware_controls.pixbuf',side_effect=AssertionError('Live SVG render')), \
             patch('tube_meter.tube_svg',side_effect=AssertionError('Live SVG render')):
            for index in range(201):
                image=tube_frame(index)
                self.assertEqual((image.get_width(),image.get_height()),(146,66))
                self.assertIs(tube_frame(index),image)

    def test_cached_glass_preserves_original_visible_artwork(self):
        for index in (0,50,100,150,200):
            expected=pixbuf(tube_svg(index),FRAME_WIDTH,FRAME_HEIGHT)
            actual=tube_frame(index)
            with self.subTest(level=index):
                self.assertLessEqual(visible_difference(actual,expected),2)

    def test_visual_comparison_rejects_an_incorrect_lamp_level(self):
        self.assertGreater(visible_difference(tube_frame(0),tube_frame(200)),32)


if __name__=='__main__':unittest.main()
