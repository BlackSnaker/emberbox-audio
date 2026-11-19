#!/usr/bin/env python3
"""Compose Ember's original, sample-free 40-second promotional sound bed.

All oscillators, notes, envelopes and percussion are generated locally. No
recordings, service audio, model output or third-party samples are used.
Requires NumPy, SciPy and FFmpeg. The final WAV is 48 kHz, stereo, PCM 24-bit.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from scipy import signal
from scipy.io import wavfile


RATE = 48_000
BPM = 96
BEAT = 60 / BPM


def frequency(note):
    return 440 * 2 ** ((note - 69) / 12)


def compose(duration=40):
    """D-major jazz voicings, rounded FM keys, gentle pulse and soft bass."""
    result = np.zeros((round(RATE * duration), 2), dtype=np.float64)
    rng = np.random.default_rng(20261119)

    def add(value, start, level=1, pan=0):
        offset = max(0, round(start * RATE))
        length = min(len(value), len(result) - offset)
        if length <= 0:
            return
        # Equal-power pan; both channels always contain the same positive-phase
        # source, so collapsing to mono cannot cancel the note.
        left = math.cos((pan + 1) * math.pi / 4)
        right = math.sin((pan + 1) * math.pi / 4)
        result[offset:offset + length, 0] += value[:length] * level * left
        result[offset:offset + length, 1] += value[:length] * level * right

    def key(note, length, velocity=.8):
        t = np.arange(round(length * RATE)) / RATE
        f = frequency(note)
        attack = 1 - np.exp(-t / .014)
        decay = .7 * np.exp(-t / 1.7) + .3 * np.exp(-t / 4)
        release = np.minimum(1, np.maximum(0, (length - t) / .65)) ** 2
        # Quiet inharmonic bell at onset plus a rounded fundamental body.
        fm = np.sin(2 * np.pi * f * t + .62 * np.exp(-t / .16) *
                    np.sin(2 * np.pi * f * 2 * t))
        body = fm + .17 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t / .8)
        body += .055 * np.sin(2 * np.pi * f * 3 * t) * np.exp(-t / .3)
        return body * attack * decay * release * velocity

    # Two bars per harmony; compact middle voicings leave room for narration
    # or interface sound. The final Dmaj9 resolves before the ending fade.
    chords = (
        (0, 38, (54, 57, 61, 64, 69)),       # Dmaj9
        (5, 35, (54, 57, 61, 62, 66)),      # Bm9
        (10, 31, (54, 57, 59, 62, 66)),     # Gmaj9
        (15, 33, (55, 59, 61, 66, 69)),     # A13
        (20, 30, (52, 57, 61, 64, 68)),     # F#m9
        (25, 35, (54, 57, 61, 62, 66)),     # Bm9
        (30, 33, (55, 59, 61, 66, 69)),     # A13
        (35, 38, (54, 57, 61, 64, 69)),     # Dmaj9
    )
    for start, bass_note, notes in chords:
        for n, note in enumerate(notes):
            add(key(note, 6, .73 + n * .025), start + .05 + n * .019,
                .047, (n - 2) * .22)
            # A softer second touch gives the chord a human, unhurried breath.
            add(key(note, 3.8, .48), start + 2.58 + n * .022,
                .026, (2 - n) * .18)
        for beat in (0, 3, 4, 7):
            length = 1.45 if beat in (0, 4) else .8
            t = np.arange(round(length * RATE)) / RATE
            f = frequency(bass_note)
            bass = (np.sin(2 * np.pi * f * t) +
                    .12 * np.sin(2 * np.pi * f * 2 * t))
            bass *= (1 - np.exp(-t / .018)) * np.exp(-t / .52)
            bass *= np.minimum(1, (length - t) / .12)
            add(bass, start + .07 + beat * BEAT, .058 if beat in (0, 4) else .036)

    # An original sparse melody, with space between phrases.
    melody = ((2, 76), (3.25, 73), (6.9, 74), (8.15, 73),
              (11.9, 71), (13.15, 69), (17, 73), (18.25, 71),
              (21.9, 73), (23.15, 76), (27, 74), (28.25, 73),
              (31.9, 71), (33.15, 73), (36.25, 74))
    for start, note in melody:
        value = key(note, 2.8, .55)
        add(value, start, .034, -.15 if note % 2 else .15)
        add(value, start + BEAT * .75, .008, .2 if note % 2 else -.2)

    # Soft low pulse with no bright transient; very quiet filtered brush.
    for beat in range(math.ceil(duration / BEAT)):
        start = beat * BEAT + .07
        if beat % 2 == 0:
            t = np.arange(round(.24 * RATE)) / RATE
            phase = 2 * np.pi * (48 * t + 16 * .018 * (1 - np.exp(-t / .018)))
            kick = np.sin(phase) * np.exp(-t / .065) * (1 - np.exp(-t / .002))
            add(kick, start, .035)
        if beat % 4 in (1, 3):
            t = np.arange(round(.14 * RATE)) / RATE
            noise = rng.normal(0, 1, len(t))
            sos = signal.butter(2, (1200, 4000), btype='bandpass', fs=RATE, output='sos')
            brush = signal.sosfilt(sos, noise) * np.exp(-t / .037)
            brush *= 1 - np.exp(-t / .006)
            add(brush, start + .004, .008, -.2 if beat % 4 == 1 else .2)

    # A short, centred room remains fully mono compatible, with no wide
    # phase tricks. Static coefficients make this reproducible.
    direct = result.copy()
    for delay, gain in ((.041, .08), (.079, .055), (.127, .035), (.193, .018)):
        samples = round(delay * RATE)
        result[samples:] += direct[:-samples] * gain
    result = signal.sosfilt(signal.butter(2, 6500, fs=RATE, output='sos'), result, axis=0)
    result = signal.sosfilt(signal.butter(2, 28, btype='highpass', fs=RATE, output='sos'), result, axis=0)
    time = np.arange(len(result)) / RATE
    fade_in = np.sin(np.minimum(1, time / 1.6) * np.pi / 2) ** 2
    fade_out = np.sin(np.minimum(1, (duration - time) / 2.9) * np.pi / 2) ** 2
    result *= (fade_in * fade_out)[:, None]
    result *= .65 / max(.001, np.max(np.abs(result)))
    return result.astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=40)
    args = parser.parse_args()
    if not 5 <= args.duration <= 300:
        parser.error('duration must be between 5 and 300 seconds')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ember-original-music-') as folder:
        raw = Path(folder) / 'original-float.wav'
        wavfile.write(raw, RATE, compose(args.duration))
        analyse = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(raw),
            '-af', 'loudnorm=I=-18:TP=-1.5:LRA=8:print_format=json', '-f', 'null', '-'],
            check=True, capture_output=True, text=True)
        report, _ = json.JSONDecoder().raw_decode(analyse.stderr[analyse.stderr.rfind('{'):])
        normalise = ('loudnorm=I=-18:TP=-1.5:LRA=8:linear=true:'
                     f'measured_I={report["input_i"]}:measured_TP={report["input_tp"]}:'
                     f'measured_LRA={report["input_lra"]}:measured_thresh={report["input_thresh"]}:'
                     f'offset={report["target_offset"]}')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
            '-i', str(raw), '-af', normalise, '-ar', str(RATE), '-ac', '2',
            '-c:a', 'pcm_s24le', str(args.output)], check=True)
    print(args.output)


if __name__ == '__main__':
    main()
