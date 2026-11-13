"""Measured pulse affects wave speed smoothly without inventing a beat grid."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mirror_timing import Timing


def grid(bpm=120., phase=.137, confidence=.95):
    return dict(bpm=bpm, period=60 / bpm, phase=phase, confidence=confidence)


def run(timing, seconds, beat_grid=None, rate=60, **options):
    for step in range(1, round(seconds * rate) + 1):
        timing.advance(1 / rate, beat_grid, step / rate, **options)
    return timing


class MirrorTiming(unittest.TestCase):
    def test_initial_state_and_a_fresh_unknown_track_drift_gently(self):
        timing = Timing()
        self.assertEqual(timing.speed, .35)
        self.assertIsNone(timing.bpm)
        self.assertEqual(timing.accent, 0.)
        self.assertEqual(timing.gain, 1.)
        run(timing, 3)
        self.assertEqual((timing.speed, timing.bpm, timing.accent, timing.gain), (.35, None, 0., 1.))

    def test_faster_songs_move_the_same_wave_faster(self):
        for bpm, speed in ((80, 1.), (120, 1.5), (160, 2.), (180, 2.25)):
            timing = run(Timing(), 15, grid(bpm))
            self.assertAlmostEqual(timing.speed, speed, delta=.00001)
            self.assertEqual(timing.bpm, bpm)
            self.assertAlmostEqual(24 / speed, 32 * 60 / bpm)

    def test_tempo_changes_accelerate_smoothly_without_a_speed_jump(self):
        timing = run(Timing(), 15, grid(120))
        before = timing.speed
        timing.advance(1 / 60, grid(160), 15 + 1 / 60)
        self.assertGreater(timing.speed, before)
        self.assertLess(timing.speed - before, .01)
        self.assertEqual(timing.bpm, 160)
        for step in range(1, 121):
            before = timing.speed
            timing.advance(1 / 60, grid(160, phase=.35), 16 + step / 60)
            self.assertGreaterEqual(timing.speed, before)
            self.assertLess(timing.speed - before, .01)
        self.assertLess(timing.speed, 2.)

    def test_untrusted_and_inconsistent_grids_do_not_lock(self):
        wrong = [None, [], '120 BPM', {}, {'bpm': 120}]
        for field, value in (('bpm', 79.9), ('bpm', 180.1), ('bpm', math.nan),
                             ('period', 0), ('period', -.5), ('period', .4), ('period', math.inf),
                             ('phase', math.nan), ('phase', math.inf), ('phase', None),
                             ('confidence', .719), ('confidence', 1.1), ('confidence', math.inf)):
            wrong.append(dict(grid(), **{field: value}))
        for measured in wrong:
            with self.subTest(grid=measured):
                timing = Timing()
                timing.advance(.1, measured, 2.)
                self.assertIsNone(timing.bpm)
                self.assertEqual(timing.speed, .35)
                self.assertEqual(timing.accent, 0.)
                self.assertEqual(timing.gain, 1.)
        timing = Timing()
        timing.advance(.1, dict(grid(confidence=.72), period=.5001), 2.)
        self.assertEqual(timing.bpm, 120)

    def test_paused_and_stale_sources_settle_speed_and_accent(self):
        for options in ({'active': False}, {'fresh': False}):
            timing = run(Timing(), 5, grid())
            self.assertGreater(timing.speed, 1.4)
            run(timing, 15, grid(), **options)
            self.assertIsNone(timing.bpm)
            self.assertLess(timing.speed, .00001)
            self.assertLess(timing.accent, .00001)
            self.assertAlmostEqual(timing.gain, 1., places=10)

    def test_a_lost_grid_returns_to_gentle_motion_without_stopping(self):
        timing = run(Timing(), 15, grid(160))
        before = timing.speed
        timing.advance(1 / 60, None, 16)
        self.assertLess(timing.speed, before)
        self.assertGreater(timing.speed, .35)
        run(timing, 15)
        self.assertAlmostEqual(timing.speed, .35, delta=.00001)
        self.assertIsNone(timing.bpm)

    def test_accent_follows_the_known_beat_phase_with_soft_attack_and_release(self):
        timing = Timing()
        measured = grid(120, phase=.125)
        timing.advance(.035, measured, 10.125)
        self.assertAlmostEqual(timing.accent, 1 - math.exp(-1), places=12)
        on_beat = timing.accent
        timing.advance(.15, measured, 10.375)
        self.assertLess(timing.accent, on_beat)
        self.assertGreater(timing.accent, math.exp(-.25 / .1))
        late = timing.accent
        timing.advance(.035, measured, 10.625)
        self.assertGreater(timing.accent, late)

    def test_gain_and_envelope_remain_bounded_and_unlocked_gain_returns_to_one(self):
        timing = Timing()
        for step in range(1, 2401):
            timing.advance(1 / 120, grid(180), step / 120)
            self.assertTrue(0 <= timing.accent <= 1)
            self.assertTrue(.92 <= timing.gain <= 1.08)
        run(timing, 5)
        self.assertAlmostEqual(timing.gain, 1., places=10)

    def test_invalid_times_cannot_poison_state_and_large_finite_phases_are_safe(self):
        timing = run(Timing(), 2, grid())
        before = vars(timing).copy()
        for dt in (0, -.1, math.nan, math.inf, -math.inf, None, 'invalid'):
            self.assertEqual(timing.advance(dt, grid(160), 2.1), before['speed'])
            self.assertEqual(vars(timing), before)
        for now in (math.nan, math.inf, None):
            timing.advance(.1, grid(), now)
            self.assertEqual(vars(timing), before)
        timing.advance(.1, grid(phase=1e308), -1e308)
        self.assertTrue(all(math.isfinite(value) for value in (timing.speed, timing.accent, timing.gain)))
        timing.advance(1e308, grid(), 2.)
        self.assertTrue(all(math.isfinite(value) for value in (timing.speed, timing.accent, timing.gain)))

    def test_smoothing_is_reasonably_independent_of_frame_rate(self):
        slow = run(Timing(), 10.4, grid(), rate=30)
        fast = run(Timing(), 10.4, grid(), rate=60)
        self.assertAlmostEqual(slow.speed, fast.speed, places=12)
        self.assertAlmostEqual(slow.accent, fast.accent, delta=.04)
        self.assertAlmostEqual(slow.gain, fast.gain, delta=.015)


if __name__ == '__main__':
    unittest.main()
