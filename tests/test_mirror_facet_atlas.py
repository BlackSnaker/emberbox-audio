"""Bounded wall-strip bytes retain projected motion and a smooth loop seam."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import mirror_facet_atlas as atlas
from mirror_facet_model import facets


class MirrorFacetAtlas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.width, cls.height, cls.frames = atlas.bake()

    def pixels(self, raw):
        return np.frombuffer(raw, np.uint8).reshape(self.height, self.width, 4)

    def test_strip_dimensions_phase_count_and_memory_are_fixed(self):
        self.assertEqual((self.width, self.height), (154, 360))
        self.assertEqual(len(self.frames), 32)
        self.assertIsInstance(self.frames, tuple)
        self.assertTrue(all(isinstance(pair, tuple) and len(pair) == 2 for pair in self.frames))
        self.assertTrue(all(isinstance(raw, bytes) and len(raw) == 154 * 360 * 4
                            for pair in self.frames for raw in pair))
        self.assertEqual(sum(len(raw) for pair in self.frames for raw in pair), 14_192_640)

    def test_bgra_is_premultiplied_and_the_inner_edges_stay_transparent(self):
        for pair in self.frames:
            for side, raw in enumerate(pair):
                pixels = self.pixels(raw)
                self.assertTrue(np.all(pixels[..., :3] <= pixels[..., 3, None]))
                self.assertGreater(pixels[..., 3].max(), 50)
                inner = pixels[:, -6:, 3] if side == 0 else pixels[:, :6, 3]
                self.assertFalse(np.any(inner))
                self.assertTrue(np.any(pixels[..., 3] == 0))

    def test_projected_contours_move_even_with_constant_light_and_opacity(self):
        def geometry_only(age, width, height):
            return [(points, .5, .4) for points, _, _ in facets(age, width, height)]
        with patch.object(atlas, 'facets', side_effect=geometry_only):
            first, turned = atlas._frame(0), atlas._frame(atlas.PERIOD / 4)
        for before, after in zip(first, turned):
            old_contour = self.pixels(before)[..., 3] > 4
            new_contour = self.pixels(after)[..., 3] > 4
            self.assertGreater(np.count_nonzero(old_contour != new_contour), 1500)

    def test_loop_has_no_duplicate_end_and_the_seam_is_an_ordinary_step(self):
        self.assertNotEqual(self.frames[0], self.frames[-1])
        self.assertEqual(self.frames[0], atlas._frame(atlas.PERIOD))
        self.assertEqual(self.frames[0], atlas._frame(0))
        for side in (0, 1):
            changes = []
            for before, after in zip(self.frames, self.frames[1:] + self.frames[:1]):
                a, b = self.pixels(before[side]), self.pixels(after[side])
                changes.append(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())
            self.assertGreater(min(changes), .05)
            self.assertLess(max(changes), 1.8)
            self.assertLess(changes[-1], np.median(changes) * 1.5)


if __name__ == '__main__':
    unittest.main()
