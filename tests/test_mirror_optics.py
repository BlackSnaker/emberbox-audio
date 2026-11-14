"""Optical expression follows measured sound and changes songs without a jump."""
import math
import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from mirror_optics import Optics


def rhythm(key=('apple-music', 'First', 'Ember Sessions', 'Light', 180000000), fresh=True,
           energy=.7, levels=(.6, .7, .8, .4, .3, .2, .1, .2, .3), bpm=120., accent=.6):
    return SimpleNamespace(key=key, fresh=fresh,
        meter=SimpleNamespace(rms_level=energy, levels=levels),
        timing=SimpleNamespace(bpm=bpm, accent=accent))


def run(optics, source, seconds, rate=60):
    for _ in range(round(seconds*rate)):
        optics.advance(1/rate, source)
    return optics.values


class MirrorOptics(unittest.TestCase):
    def test_initial_state_and_response_channels_use_real_meter_inputs(self):
        optics = Optics()
        self.assertEqual(optics.values, (0., 0., 0., 0., .5, .5, .5))
        result = run(optics, rhythm(), 15)
        for actual, target in zip(result[:4], (.6, .7, .7, .2)):
            self.assertAlmostEqual(actual, target, places=9)
        self.assertTrue(all(.2 <= value <= .8 for value in result[4:]))

    def test_profiles_are_deterministic_and_vary_with_song_metadata(self):
        keys = [('apple-music', title, artist, 'Record', 180000000)
                for title, artist in (('First', 'Ember Sessions'), ('Second', 'Ember Sessions'),
                                      ('First', 'Other Artist'), ('Ночной свет', 'Эмбер'))]
        profiles = []
        for key in keys:
            first, second = Optics(), Optics()
            profiles.append(run(first, rhythm(key), 50)[4:])
            self.assertEqual(first.values, run(second, rhythm(key), 50))
        self.assertEqual(len(set(profiles)), len(keys))
        self.assertGreater(max(math.dist(a, b) for a in profiles for b in profiles), .15)

    def test_same_song_hashes_once_and_new_song_fades_from_current_character(self):
        first, second = rhythm(), rhythm(('spotify', 'Second', 'Artist', 'Album', 240000000))
        optics = Optics()
        with patch('mirror_optics.hashlib.blake2s', wraps=hashlib.blake2s) as digest:
            run(optics, first, 10)
            self.assertEqual(digest.call_count, 1)
            before = optics.values[4:]
            after = optics.advance(1/60, second)[4:]
            self.assertEqual(digest.call_count, 2)
            self.assertTrue(any(a != b for a, b in zip(before, after)))
            self.assertLess(max(abs(a-b) for a, b in zip(before, after)), .003)
            settled = run(optics, second, 40)[4:]
            self.assertGreater(math.dist(before, settled), .03)
            run(optics, second, 1)
            self.assertEqual(digest.call_count, 2)

    def test_pause_or_stale_audio_releases_responses_but_holds_character(self):
        optics = Optics()
        run(optics, rhythm(), 8)
        before = optics.values
        paused = rhythm(key=('spotify', 'New song while paused'), fresh=False)
        first = optics.advance(1/60, paused)
        self.assertEqual(first[4:], before[4:])
        self.assertTrue(all(0 < after < old for after, old in zip(first[:4], before[:4])))
        final = run(optics, paused, 25)
        self.assertTrue(all(0 <= value < 1e-7 for value in final[:4]))
        self.assertEqual(final[4:], before[4:])
        resumed = optics.advance(1/60, rhythm(key=paused.key))
        self.assertLess(max(abs(a-b) for a,b in zip(resumed[4:], final[4:])), .003)

    def test_pulse_requires_a_trusted_tempo_and_does_not_invent_beats(self):
        for bpm in (None, 0, 79.9, 180.1, math.nan, math.inf, 'invalid'):
            optics = Optics()
            result = run(optics, rhythm(bpm=bpm, accent=1.), 2)
            self.assertEqual(result[0], 0.)
            self.assertGreater(result[1], .6)
        for bpm in (80, 120, 180):
            self.assertGreater(run(Optics(), rhythm(bpm=bpm), 1)[0], .59)
        self.assertEqual(run(Optics(), rhythm(accent=0.), 2)[0], 0.)

    def test_attack_and_release_are_bounded_and_continuous(self):
        optics = Optics()
        bright = rhythm(energy=1., levels=(1.,)*9, accent=1.)
        previous = optics.values
        for _ in range(120):
            current = optics.advance(1/60, bright)
            self.assertTrue(all(0 <= value <= 1 for value in current))
            self.assertLess(current[0]-previous[0], .16)
            self.assertLess(max(current[i]-previous[i] for i in (1,2,3)), .031)
            previous = current
        silent = rhythm(fresh=False)
        after = optics.advance(1/60, silent)
        self.assertLess(previous[0]-after[0], .05)
        self.assertLess(max(previous[i]-after[i] for i in (1,2,3)), .013)

    def test_invalid_time_leaves_all_state_untouched_and_large_time_converges(self):
        optics = Optics()
        optics.advance(.1, rhythm())
        snapshot = vars(optics).copy()
        for dt in (None, 0, -.1, math.nan, math.inf, -math.inf, 'invalid'):
            self.assertEqual(optics.advance(dt, rhythm(key=('new',))), optics.values)
            self.assertEqual(vars(optics), snapshot)
        final = optics.advance(1e308, rhythm())
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in final))
        for actual,target in zip(final[:4], (.6, .7, .7, .2)):
            self.assertAlmostEqual(actual,target,places=14)
        stopped = optics.advance(1e308, None)
        self.assertTrue(all(value == 0 for value in stopped[:4]))

    def test_missing_and_malformed_meter_fields_are_safe_and_clamped(self):
        cases = [None, SimpleNamespace(fresh=True),
                 rhythm(energy=math.nan, levels=None, accent=math.nan),
                 rhythm(energy=math.inf, levels='123456789', accent='bad'),
                 rhythm(energy=-10, levels=(math.nan, math.inf, -1), accent=-1)]
        for source in cases:
            with self.subTest(source=source):
                result = run(Optics(), source, 20)
                self.assertEqual(result[:4], (0.,)*4)
                self.assertTrue(all(math.isfinite(value) for value in result))
        result = run(Optics(), rhythm(energy=20, levels=(10.,)*9, accent=5), 20)
        self.assertTrue(all(abs(value-1.) < 1e-9 for value in result[:4]))
        partial = run(Optics(), rhythm(levels=(1., .5)), 20)
        self.assertAlmostEqual(partial[2], .5, places=9)
        self.assertEqual(partial[3], 0.)

    def test_malformed_metadata_does_not_change_the_visual_character(self):
        optics = Optics()
        held = optics.values[4:]
        for key in (None, '', (), ('track', math.nan), ('track', object()), {'track': 'name'}):
            run(optics, rhythm(key=key), 2)
            self.assertEqual(optics.values[4:], held)

    def test_smoothing_is_independent_of_frame_rate_for_the_same_sound(self):
        answers = []
        for rate in (30, 60, 144):
            optics = Optics()
            run(optics, rhythm(), 2, rate)
            run(optics, rhythm(key=('next',), energy=.3, levels=(.2,)*9, accent=.1), 1, rate)
            answers.append(run(optics, rhythm(fresh=False), 1, rate))
        for result in answers[1:]:
            for actual, reference in zip(result, answers[0]):
                self.assertAlmostEqual(actual, reference, places=12)


if __name__ == '__main__':
    unittest.main()
