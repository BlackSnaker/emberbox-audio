"""The mirror panorama travels left to right without orbiting or deforming."""
import math
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mirror_facet_model import DRIFT_PERIOD, PERIOD, facets


def centre(points):
    return tuple(sum(point[axis] for point in points) / len(points) for axis in (0, 1))


class MirrorFacets(unittest.TestCase):
    def test_finite_bounded_geometry_at_supported_and_tiny_sizes(self):
        for width, height in ((1920, 1080), (1280, 720), (1024, 600), (1, 1), (1, 200)):
            for age in (0, PERIOD / 4, DRIFT_PERIOD * 1.01):
                with self.subTest(size=(width, height), age=age):
                    scales = facets(age, width, height)
                    self.assertEqual(len(scales), 576)
                    for points, shade, alpha in scales:
                        self.assertEqual(len(points), 4)
                        self.assertTrue(all(math.isfinite(value) for point in points for value in point))
                        self.assertTrue(0 <= shade <= 1)
                        self.assertTrue(0 <= alpha <= 1)
                        for x, y in points:
                            self.assertTrue(-width * .1 <= x <= width * 1.1)
                            self.assertTrue(-height * .1 <= y <= height * 1.1)

    def test_empty_or_nonfinite_allocations_have_no_geometry(self):
        for size in ((0, 100), (100, 0), (-1, 10), (10, -1), (math.inf, 100), (100, math.nan)):
            self.assertEqual(facets(0, *size), [])
        self.assertEqual(facets(math.inf, 1920, 1080), facets(0, 1920, 1080))
        self.assertEqual(facets(math.nan, 1920, 1080), facets(0, 1920, 1080))

    def test_each_quad_stays_convex_through_the_pan(self):
        for width, height in ((1920, 1080), (1024, 600), (1, 200)):
            for step in range(13):
                for points, _, _ in facets(step * DRIFT_PERIOD / 12, width, height):
                    crosses = []
                    for index in range(4):
                        a, b, c = (points[(index + offset) % 4] for offset in range(3))
                        crosses.append((b[0] - a[0]) * (c[1] - b[1])
                                       - (b[1] - a[1]) * (c[0] - b[0]))
                    self.assertTrue(all(cross > 0 for cross in crosses)
                                    or all(cross < 0 for cross in crosses))

    def test_motion_is_horizontal_translation_with_no_rotation_or_shape_change(self):
        for age in (0, 6, DRIFT_PERIOD - .01):
            before, after = facets(age, 1920, 1080), facets(age + .02, 1920, 1080)
            forward = []
            for old, new in zip(before, after):
                changes = [b[0] - a[0] for a, b in zip(old[0], new[0])]
                self.assertLess(max(changes) - min(changes), 1e-8)
                for a, b in zip(old[0], new[0]):
                    self.assertAlmostEqual(a[1], b[1], places=10)
                if changes[0] > 0:
                    forward.append(changes[0])
                else:
                    # Index wrapping belongs only at the panorama's edges.
                    self.assertGreater(centre(old[0])[0], 1920 * .9)
                    self.assertLess(centre(new[0])[0], 1920 * .1)
            self.assertGreater(len(forward), len(before) * .9)
            self.assertLess(max(forward) - min(forward), 1e-8)

    def test_visible_tiles_advance_about_forty_pixels_per_second_at_120_bpm(self):
        # Rhythm timing supplies 1.5 source seconds in one 120-BPM second.
        # Test geometric travel rather than a change in light intensity.
        before = facets(0, 1920, 1080)
        after = facets(1.5, 1920, 1080)
        movement = []
        for old, new in zip(before, after):
            a, b = centre(old[0]), centre(new[0])
            if all(192 < point[0] < 1728 for point in (a, b)):
                self.assertAlmostEqual(a[1], b[1], places=10)
                movement.append(b[0] - a[0])
        self.assertGreater(len(movement), 100)
        self.assertGreater(statistics.median(movement), 35.)
        self.assertLess(statistics.median(movement), 45.)

    def test_panorama_covers_all_four_edges_and_its_middle(self):
        for age in (0, DRIFT_PERIOD / 3, DRIFT_PERIOD * .99):
            positions = [centre(points) for points, _, _ in facets(age, 1920, 1080)]
            for low_x, high_x, low_y, high_y in (
                    (0, .12, .4, .6), (.88, 1, .4, .6),
                    (.4, .6, 0, .12), (.4, .6, .88, 1), (.4, .6, .4, .6)):
                self.assertTrue(any(low_x * 1920 <= x <= high_x * 1920
                                    and low_y * 1080 <= y <= high_y * 1080 for x, y in positions))

    def test_complete_pan_repeats_without_a_drift_or_lighting_jump(self):
        self.assertGreater(DRIFT_PERIOD, PERIOD)
        for age in (-.1, 0, 3.25, DRIFT_PERIOD - .001):
            first, repeated = facets(age, 1920, 1080), facets(age + DRIFT_PERIOD, 1920, 1080)
            self.assertEqual(len(first), len(repeated))
            for old, new in zip(first, repeated):
                for a, b in zip(old[0], new[0]):
                    self.assertAlmostEqual(a[0], b[0], places=9)
                    self.assertAlmostEqual(a[1], b[1], places=9)
                self.assertAlmostEqual(old[1], new[1], places=10)
                self.assertAlmostEqual(old[2], new[2], places=10)


if __name__ == '__main__':
    unittest.main()
