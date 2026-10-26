"""Exact reviewed SVG/pixel references, independent of the CI SVG renderer."""
import hashlib
import json
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
from tube_meter import ATLAS,tube_frame,tube_frames,tube_svg,FRAME_COLUMNS,FRAME_WIDTH,FRAME_HEIGHT


def pixel_digest(image):
    # Subpixbuf rows retain the atlas stride; padding is not pixel data.
    raw=image.get_pixels();stride=image.get_rowstride()
    rgba=b''.join(raw[y*stride:y*stride+image.get_width()*4] for y in range(image.get_height()))
    return hashlib.sha256(rgba).hexdigest()


class TubeFramesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference=json.loads((Path(__file__).parent/'fixtures/tube-meter-v1.json').read_text())

    def test_every_level_is_shipped_without_live_svg_rendering(self):
        tube_frames.cache_clear()
        with patch('hardware_controls.pixbuf',side_effect=AssertionError('Live SVG render')), \
             patch('tube_meter.tube_svg',side_effect=AssertionError('Live SVG render')):
            for index in range(201):
                image=tube_frame(index)
                self.assertEqual((image.get_width(),image.get_height()),(146,66))
                self.assertTrue(image.get_has_alpha());self.assertEqual(image.get_n_channels(),4)
                self.assertIs(tube_frame(index),image)

    def test_atlas_is_the_exact_reviewed_asset(self):
        self.assertEqual(self.reference['schema'],1)
        self.assertEqual((self.reference['width'],self.reference['height'],self.reference['columns']),
                         (FRAME_WIDTH,FRAME_HEIGHT,FRAME_COLUMNS))
        self.assertEqual(hashlib.sha256(ATLAS.read_bytes()).hexdigest(),self.reference['atlas_sha256'])

    def test_every_source_and_pixel_matches_the_reviewed_artwork_exactly(self):
        self.assertEqual(len(self.reference['frames']),201)
        for index,expected in enumerate(self.reference['frames']):
            with self.subTest(level=index):
                self.assertEqual(hashlib.sha256(tube_svg(index).encode('utf-8')).hexdigest(),expected['svg_sha256'],
                                 'Artwork changed: regenerate and review the atlas and its reference together')
                self.assertEqual(pixel_digest(tube_frame(index)),expected['rgba_sha256'])

    def test_pixel_reference_is_independent_of_atlas_row_padding(self):
        for index in (0,50,100,150,200):
            image=tube_frame(index)
            self.assertEqual(pixel_digest(image),pixel_digest(image.copy()))
        self.assertNotEqual(pixel_digest(tube_frame(0)),pixel_digest(tube_frame(200)))


if __name__=='__main__':unittest.main()
