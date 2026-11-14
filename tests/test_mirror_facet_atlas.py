"""A single periodic glass surface supports sharp, continuous horizontal pan."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import mirror_facet_atlas as atlas


class MirrorFacetAtlas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.width, cls.height, cls.frames = atlas.bake()

    def pixels(self, raw):
        return np.frombuffer(raw, np.uint8).reshape(self.height, self.width, 4)

    def test_one_immutable_surface_has_a_small_fixed_memory_budget(self):
        self.assertEqual((self.width, self.height), (768, 432))
        self.assertIsInstance(self.frames, tuple)
        self.assertEqual(len(self.frames), 1)
        self.assertTrue(all(isinstance(raw, bytes) and len(raw) == self.width * self.height * 4
                            for raw in self.frames))
        self.assertLessEqual(sum(len(raw) for raw in self.frames), 2_000_000)
        mask_width, mask_height, mask = atlas.vignette()
        self.assertIsInstance(mask, bytes)
        self.assertEqual(len(mask), mask_width * mask_height)
        self.assertLess(sum(len(raw) for raw in self.frames) + len(mask), 1_500_000)

    def test_bgra_is_premultiplied_and_faces_have_bright_and_dark_detail(self):
        pixels = self.pixels(self.frames[0])
        self.assertTrue(np.all(pixels[..., :3] <= pixels[..., 3, None]))
        visible = pixels[..., 3] > 16
        self.assertGreater(np.count_nonzero(visible), self.width * self.height * .5)
        light = pixels[..., :3].mean(axis=2)[visible]
        self.assertGreater(np.percentile(light, 95) - np.percentile(light, 5), 8.)
        self.assertGreater(light.std(), 3.)

    def test_horizontal_repeat_seam_is_an_ordinary_neighbouring_column_step(self):
        pixels = self.pixels(self.frames[0]).astype(np.float32)
        adjacent = np.abs(np.diff(pixels, axis=1)).mean(axis=(0, 2))
        seam = np.abs(pixels[:, 0] - pixels[:, -1]).mean()
        # Opposite columns need not be identical: the next column after the
        # rightmost must simply continue the normal texture, without a stripe.
        self.assertLessEqual(seam, np.percentile(adjacent, 95) * 1.5 + 1.)
        self.assertGreater(np.count_nonzero(adjacent > .1), self.width // 4)

    def test_vignette_is_not_baked_into_the_moving_texture(self):
        alpha = self.pixels(self.frames[0])[..., 3]
        centre = alpha[self.height * 2 // 5:self.height * 3 // 5,
                       self.width * 2 // 5:self.width * 3 // 5]
        self.assertGreater(np.count_nonzero(centre), centre.size * .5)

    def test_fixed_vignette_keeps_the_centre_quiet_without_a_hard_rim(self):
        width, height, raw = atlas.vignette()
        mask = np.frombuffer(raw, np.uint8).reshape(height, width)
        centre = mask[height // 3:height * 2 // 3, width // 3:width * 2 // 3]
        self.assertFalse(np.any(centre))
        self.assertGreater(mask[0, 0], 240)
        shoulder = mask[height // 2, width // 2:]
        self.assertTrue(np.all(np.diff(shoulder.astype(np.int16)) >= 0))
        self.assertLess(np.abs(np.diff(shoulder.astype(np.int16))).max(), 8)
        self.assertGreater(np.count_nonzero((shoulder > 0) & (shoulder < 255)), width // 8)

    def test_cached_surface_is_deterministic_and_immutable(self):
        before = tuple(self.frames)
        self.assertEqual(self.frames[0], atlas._frame())
        self.assertEqual(self.frames, before)


if __name__ == '__main__':
    unittest.main()
