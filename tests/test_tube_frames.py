"""The shipped sprites preserve the glass artwork without live SVG rendering."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
gi.require_version('Gdk','3.0')
gi.require_version('Atk','1.0')
gi.require_version('GdkPixbuf','2.0')
from hardware_controls import pixbuf
from tube_meter import tube_frame,tube_frames,tube_svg,FRAME_WIDTH,FRAME_HEIGHT


class TubeFramesTests(unittest.TestCase):
    def test_every_level_is_shipped_without_live_svg_rendering(self):
        tube_frames.cache_clear()
        with patch('hardware_controls.pixbuf',side_effect=AssertionError('Live SVG render')), \
             patch('tube_meter.tube_svg',side_effect=AssertionError('Live SVG render')):
            for index in range(201):
                image=tube_frame(index)
                self.assertEqual((image.get_width(),image.get_height()),(146,66))
                self.assertIs(tube_frame(index),image)

    def test_cached_glass_matches_original_artwork_exactly(self):
        for index in (0,50,100,150,200):
            expected=pixbuf(tube_svg(index),FRAME_WIDTH,FRAME_HEIGHT)
            actual=tube_frame(index)
            a,b=actual.get_pixels(),expected.get_pixels()
            # Subpixbuf rows retain the atlas stride; padding is not pixel data.
            for y in range(FRAME_HEIGHT):
                self.assertEqual(a[y*actual.get_rowstride():y*actual.get_rowstride()+FRAME_WIDTH*4],
                    b[y*expected.get_rowstride():y*expected.get_rowstride()+FRAME_WIDTH*4])


if __name__=='__main__':unittest.main()
