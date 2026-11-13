import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from audio_meter import CHANNELS, FRAMES, RATE, SpotifyAudioMeter


class MeterRhythmInterestTests(unittest.TestCase):
    def test_consumers_share_history_and_release_only_their_own_interest(self):
        meter = SpotifyAudioMeter()
        meter.request_rhythm('mirrorball', 'track-a')
        tap = meter.rhythm
        meter.set_rhythm('track-a')
        meter.request_rhythm('mirrorball', None)
        self.assertIs(meter.rhythm, tap)

        meter.request_rhythm('mirrorball', 'track-a')
        meter.set_rhythm(None)
        meter.set_rhythm(None)
        meter.request_rhythm('mirrorball', 'track-a')
        self.assertIs(meter.rhythm, tap)
        self.assertEqual(meter.rhythm_key, 'track-a')

        meter.request_rhythm('mirrorball', None)
        self.assertIsNone(meter.rhythm)
        self.assertIsNone(meter.rhythm_key)

    def test_flow_priority_and_visual_order_reset_only_for_effective_track_changes(self):
        meter = SpotifyAudioMeter()
        meter.request_rhythm('mirrorball', 'track-a')
        first = meter.rhythm
        grid = {'bpm': 120}
        meter.beat_grid = grid
        meter.rhythm_check = meter.beat_grid_at = 12.

        meter.request_rhythm('spectrum', 'track-b')
        meter.request_rhythm('spectrum', 'track-c')
        self.assertIs(meter.rhythm, first)
        self.assertIs(meter.beat_grid, grid)
        self.assertEqual(meter.beat_grid_at, 12.)

        meter.set_rhythm('track-c')
        flow = meter.rhythm
        self.assertIsNot(flow, first)
        self.assertEqual(meter.rhythm_key, 'track-c')
        self.assertIsNone(meter.beat_grid)
        self.assertEqual(meter.rhythm_check, 0.)
        self.assertEqual(meter.beat_grid_at, 0.)
        meter.request_rhythm('mirrorball', None)
        meter.set_rhythm('track-c')
        self.assertIs(meter.rhythm, flow)
        meter.set_rhythm(None)
        self.assertIs(meter.rhythm, flow)

        meter.request_rhythm('mirrorball', 'track-a')
        self.assertIs(meter.rhythm, flow)
        meter.request_rhythm('spectrum', None)
        self.assertEqual(meter.rhythm_key, 'track-a')
        self.assertIsNot(meter.rhythm, flow)

    def test_stop_discards_every_consumer_and_grid(self):
        meter = SpotifyAudioMeter()
        meter.request_rhythm('mirrorball', 'track-a')
        meter.request_rhythm('spectrum', 'track-b')
        meter.set_rhythm('track-c')
        meter.beat_grid = {'bpm': 120}
        meter.rhythm_check = meter.beat_grid_at = 12.
        meter.stop()
        self.assertIsNone(meter.rhythm)
        self.assertIsNone(meter.rhythm_key)
        self.assertIsNone(meter.beat_grid)
        self.assertEqual(meter.rhythm_check, 0.)
        self.assertEqual(meter.beat_grid_at, 0.)

        meter.set_rhythm('track-d')
        meter.set_rhythm(None)
        self.assertIsNone(meter.rhythm)
        meter.request_rhythm('spectrum', None)
        self.assertIsNone(meter.rhythm)

    def test_unconfident_estimates_update_freshness_without_a_grid(self):
        meter = SpotifyAudioMeter()
        meter.request_rhythm('mirrorball', 'silent-track')
        raw = np.zeros((FRAMES, CHANNELS), dtype='<f4').tobytes()
        with patch('audio_meter.time.monotonic', return_value=4.):
            meter._measure(raw, 4.)
        self.assertIsNone(meter.beat_grid)
        self.assertEqual(meter.beat_grid_at, 4.)
        self.assertEqual(meter.rhythm_check, 4.)
        with patch('audio_meter.time.monotonic', return_value=4.5):
            meter._measure(raw, 4.5)
        self.assertEqual(meter.beat_grid_at, 4.)

    def test_retired_tap_cannot_publish_after_track_change_or_stop(self):
        raw = np.zeros((FRAMES, CHANNELS), dtype='<f4').tobytes()
        for action in ('track-change', 'stop'):
            with self.subTest(action=action):
                meter = SpotifyAudioMeter()
                meter.request_rhythm('mirrorball', 'track-a')

                class RetiredTap:
                    def feed(self, samples, end):
                        pass

                    def result(self):
                        if action == 'stop':
                            meter.stop()
                        else:
                            meter.request_rhythm('mirrorball', 'track-b')
                        return {'bpm': 120}

                meter.rhythm = RetiredTap()
                with patch('audio_meter.time.monotonic', return_value=4.):
                    meter._measure(raw, 4.)
                self.assertIsNone(meter.beat_grid)
                self.assertEqual(meter.beat_grid_at, 0.)
                self.assertEqual(meter.rhythm_check, 0.)

    def test_stereo_beat_estimation_continues_after_flow_releases(self):
        meter = SpotifyAudioMeter()
        meter.set_rhythm('generated-track')
        meter.request_rhythm('mirrorball', 'generated-track')
        tap = meter.rhythm
        t = np.arange(RATE * 8) / RATE
        envelope = np.exp(-((t - .14) % .5) / .035)
        signal = .5 * np.sin(t * 2 * np.pi * 85) * envelope
        pcm = np.column_stack((signal, -signal)).astype('<f4')
        now = 0.
        with patch('audio_meter.time.monotonic', side_effect=lambda: now):
            for end in range(FRAMES, len(pcm) + 1, FRAMES // 2):
                now = end / RATE
                if now >= 3.:
                    meter.set_rhythm(None)
                meter._measure(pcm[end - FRAMES:end].tobytes(), now)

        self.assertIs(meter.rhythm, tap)
        self.assertIsNotNone(meter.beat_grid)
        self.assertAlmostEqual(meter.beat_grid['bpm'], 120., delta=.5)
        self.assertGreater(meter.beat_grid_at, 7.)
        self.assertEqual(meter.beat_grid_at, meter.rhythm_check)
        meter.request_rhythm('mirrorball', None)
        self.assertIsNone(meter.rhythm)
        self.assertIsNone(meter.beat_grid)
        self.assertEqual(meter.beat_grid_at, 0.)


if __name__ == '__main__':
    unittest.main()
