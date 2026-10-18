"""Read Spotify's PipeWire output and measure nine actual frequency bands."""

import math
import os
import re
import select
import subprocess
import threading
import time

import numpy as np


RATE = 48000
FRAMES = 4096
CHANNELS = 2
FRAME_BYTES = CHANNELS * 4
WINDOW_BYTES = FRAMES * FRAME_BYTES
HOP_BYTES = (FRAMES // 2) * FRAME_BYTES
EDGES = (55, 100, 180, 320, 570, 1000, 1800, 3200, 5800, 11000)
GAIN = (1.0, 1.0, 1.12, 1.30, 1.60, 2.0, 2.7, 4.0, 6.0)
WINDOW = np.hanning(FRAMES).astype(np.float32)
FREQUENCIES = np.fft.rfftfreq(FRAMES, 1 / RATE)
BANDS = [(np.searchsorted(FREQUENCIES, low), np.searchsorted(FREQUENCIES, high))
         for low, high in zip(EDGES[:-1], EDGES[1:])]


class SpotifyAudioMeter:
    def __init__(self):
        self.node_name = f'emberbox-audio-visualizer-{os.getpid()}'
        self.process = None
        self.thread = None
        self.levels = (0.0,) * 9
        self.last_sample = 0.0

    def start(self):
        if self.process and self.process.poll() is None:
            return
        self.stop()
        properties = f'{{ node.name = {self.node_name} application.name = "Emberbox Audio" }}'
        self.process = subprocess.Popen(
            ['pw-record', '--target', '0', '-P', properties, '--latency', '50ms',
             '--raw', '--format', 'f32', '--rate', str(RATE), '--channels', '2', '-'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.thread = threading.Thread(target=self._read, args=(self.process,), daemon=True)
        self.thread.start()

    def stop(self):
        process = self.process
        self.process = None
        self.levels = (0.0,) * 9
        self.last_sample = 0.0
        if process:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.5)
            if process.stdout:
                process.stdout.close()

    def _link_spotify(self):
        try:
            inputs = subprocess.run(['pw-link', '-i'], capture_output=True, text=True,
                                    timeout=1, check=True).stdout.splitlines()
            outputs = subprocess.run(['pw-link', '-o'], capture_output=True, text=True,
                                     timeout=1, check=True).stdout.splitlines()
            for channel in ('FL', 'FR'):
                target = f'{self.node_name}:input_{channel}'
                if target not in inputs:
                    return
                source = next((port for port in outputs
                               if re.fullmatch(r'spotify(?:-\d+)?:output_' + channel, port,
                                               flags=re.IGNORECASE)), None)
                if source:
                    subprocess.run(['pw-link', source, target], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=1)
        except (OSError, subprocess.SubprocessError):
            pass

    def _read(self, process):
        buffer = bytearray()
        last_link = 0.0
        while self.process is process and process.poll() is None:
            now = time.monotonic()
            if now - last_link > 0.4 and now - self.last_sample > 0.35:
                self._link_spotify()
                last_link = now
            try:
                readable, _, _ = select.select([process.stdout], [], [], 0.25)
                if not readable:
                    continue
                chunk = os.read(process.stdout.fileno(), 32768)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            buffer.extend(chunk)
            while len(buffer) >= WINDOW_BYTES:
                self._measure(bytes(buffer[:WINDOW_BYTES]))
                del buffer[:HOP_BYTES]

    def _measure(self, raw):
        samples = np.frombuffer(raw, dtype='<f4').reshape(FRAMES, CHANNELS)
        mono = samples.mean(axis=1)
        spectrum = np.abs(np.fft.rfft(mono * WINDOW)) * (2 / WINDOW.sum())
        levels = []
        for (start, stop), gain in zip(BANDS, GAIN):
            energy = math.sqrt(float(np.mean(spectrum[start:stop] ** 2)))
            decibels = 20 * math.log10(max(1e-8, energy * gain))
            levels.append(max(0.0, min(1.0, (decibels + 70) / 50)))
        self.levels = tuple(levels)
        self.last_sample = time.monotonic()
