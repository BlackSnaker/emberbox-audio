"""The wall scales move smoothly, remain convex and leave the controls quiet."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mirror_facet_model import PERIOD, facets


class MirrorFacets(unittest.TestCase):
    def test_count_finite_values_and_clear_centre_at_supported_and_tiny_sizes(self):
        for width, height in ((1920, 1080), (1280, 720), (1024, 600), (1, 1), (1, 200)):
            for age in (0, PERIOD / 4, PERIOD / 2):
                with self.subTest(size=(width, height), age=age):
                    scales = facets(age, width, height)
                    self.assertEqual(len(scales), 252)
                    self.assertLessEqual(len(scales), 300)
                    for points, shade, alpha in scales:
                        self.assertEqual(len(points), 4)
                        self.assertTrue(all(math.isfinite(value) for point in points for value in point))
                        self.assertTrue(0 <= shade <= 1)
                        self.assertTrue(0 <= alpha <= 1)
                        self.assertTrue(all(x < width * .24 for x, _ in points)
                                        or all(x > width * .76 for x, _ in points))

    def test_empty_or_nonfinite_allocations_have_no_geometry(self):
        for size in ((0, 100), (100, 0), (-1, 10), (10, -1), (math.inf, 100), (100, math.nan)):
            self.assertEqual(facets(0, *size), [])
        self.assertEqual(facets(math.inf, 1920, 1080), facets(0, 1920, 1080))
        self.assertEqual(facets(math.nan, 1920, 1080), facets(0, 1920, 1080))

    def test_geometry_changes_even_without_painting_the_lighting(self):
        first = facets(0, 1920, 1080)
        later = facets(PERIOD / 4, 1920, 1080)
        changes = [max(math.dist(a, b) for a, b in zip(before[0], after[0]))
                   for before, after in zip(first, later)]
        self.assertGreater(min(changes), .5)
        self.assertGreater(max(changes), 3.)
        # The local outline also changes after subtracting center drift.
        before, after = first[0][0], later[0][0]
        edge_before = math.dist(before[0], before[1])
        edge_after = math.dist(after[0], after[1])
        self.assertGreater(abs(edge_before - edge_after), 1.)

    def test_every_scale_is_convex_and_never_inverts(self):
        for width, height in ((1920, 1080), (1024, 600), (1, 200)):
            for step in range(49):
                for points, _, _ in facets(step * PERIOD / 48, width, height):
                    for index in range(4):
                        a, b, c = (points[(index + offset) % 4] for offset in range(3))
                        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
                        self.assertGreater(cross, 0.)

    def test_motion_is_smooth_at_sixty_hz_including_the_loop_seam(self):
        for step in range(97):
            age = step * PERIOD / 96 - 1 / 120
            before, after = facets(age, 1920, 1080), facets(age + 1 / 60, 1920, 1080)
            for (points, shade, alpha), (next_points, next_shade, next_alpha) in zip(before, after):
                self.assertLess(max(math.dist(a, b) for a, b in zip(points, next_points)), .12)
                self.assertLess(abs(shade - next_shade), .003)
                self.assertLess(abs(alpha - next_alpha), .001)

    def test_deterministic_twenty_four_second_loop_and_bounded_centres(self):
        self.assertEqual(PERIOD, 24.)
        for age in (-.1, 0, 3.25, 11.9, 23.99):
            before, after = facets(age, 1920, 1080), facets(age + PERIOD, 1920, 1080)
            self.assertEqual(before, facets(age, 1920, 1080))
            for (points, shade, alpha), (next_points, next_shade, next_alpha) in zip(before, after):
                for a, b in zip(points, next_points):
                    self.assertAlmostEqual(a[0], b[0], places=10)
                    self.assertAlmostEqual(a[1], b[1], places=10)
                self.assertAlmostEqual(shade, next_shade, places=12)
                self.assertAlmostEqual(alpha, next_alpha, places=12)
            for index, (points, _, _) in enumerate(before):
                row, within_row = divmod(index, 14)
                side, edge_column = divmod(within_row, 7)
                column = edge_column if side == 0 else 31 - edge_column
                centre = (sum(point[0] for point in points) / 4,
                          sum(point[1] for point in points) / 4)
                origin = ((column + .5) * 1920 / 32, (row + .5) * 1080 / 18)
                self.assertLess(math.dist(centre, origin), 4.)


if __name__ == '__main__':
    unittest.main()
