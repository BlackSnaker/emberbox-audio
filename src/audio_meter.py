"""Read the selected application's PipeWire output and measure nine actual frequency bands."""

import json
import math
import os
import select
import subprocess
import threading
import time

import numpy as np
from stream_target import Target, output_nodes


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
        self.target = Target()
        self.process = None
        self.thread = None
        self.levels = (0.0,) * 9
        self.last_sample = 0.0

    def set_target(self, target):
        if target != self.target:
            self.stop()
            self.target = target

    def start(self):
        if self.process and self.process.poll() is None:
            return
        self.stop()
        properties = f'{{ node.name = {self.node_name} application.name = "Emberbox Audio" }}'
        self.process = subprocess.Popen(
            ['pw-record', '--target', '0', '-P', properties, '--latency', '50ms',
             '--raw', '--format', 'f32', '--rate', str(RATE), '--channels', '2', '-'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.thread = threading.Thread(target=self._read, args=(self.process, self.target), daemon=True)
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

    def _link_player(self, process, target, linked):
        try:
            graph = json.loads(subprocess.run(['pw-dump'], capture_output=True, text=True,
                                              timeout=2, check=True).stdout)
            sources = output_nodes(graph, target)
            targets = {str(item['id']) for item in graph
                       if item.get('info', {}).get('props', {}).get('node.name') == self.node_name}
            inputs, outputs = {}, []
            for item in graph:
                props = item.get('info', {}).get('props', {})
                channel, node = props.get('audio.channel'), str(props.get('node.id'))
                if channel not in ('FL', 'FR', 'MONO'):
                    continue
                if node in targets and props.get('port.direction') == 'in':
                    inputs[channel] = str(item['id'])
                if node in sources and props.get('port.direction') == 'out':
                    outputs.append((str(item['id']), channel))
            desired = {(port, inputs[channel]) for port, channel in outputs if channel in inputs}
            desired |= {(port, inputs[channel]) for port, c in outputs if c == 'MONO'
                        for channel in ('FL', 'FR') if channel in inputs}
            if self.process is not process:
                return linked
            for source, destination in linked - desired:
                subprocess.run(['pw-link', '-d', source, destination],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            for source, destination in desired - linked:
                subprocess.run(['pw-link', source, destination],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            return desired
        except (OSError, ValueError, subprocess.SubprocessError):
            return linked

    def _read(self, process, target):
        buffer = bytearray()
        last_link = 0.0
        linked = set()
        while self.process is process and process.poll() is None:
            now = time.monotonic()
            if now - last_link > 0.8:
                linked = self._link_player(process, target, linked)
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
            while self.process is process and len(buffer) >= WINDOW_BYTES:
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
