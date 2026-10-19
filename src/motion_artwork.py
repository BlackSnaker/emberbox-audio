"""Silent cover loops decoded away from GTK; only the latest frame is retained."""
import shutil
import subprocess
import threading
import urllib.request
from urllib.parse import urlsplit
from gi.repository import GdkPixbuf, GLib
from PIL import Image, ImageDraw
from cover_sources import is_motion_url, motion_rendition


class MotionRun:
    def __init__(self, executable, url, size, radius, playing):
        self.stop_event = threading.Event()
        self.play_gate = threading.Event()
        if playing:
            self.play_gate.set()
        self.lock = threading.Lock()
        self.process = None
        self.frame = None
        self.finished = False
        self.size = size
        self.thread = threading.Thread(target=self._decode, args=(executable,url,size,radius),
                                       name='ember-motion-decode', daemon=True)
        self.thread.start()

    def _decode(self, executable, url, size, radius):
        process = None
        try:
            if urlsplit(url).path.endswith('.m3u8'):
                try:
                    with urllib.request.urlopen(url,timeout=6) as response:
                        raw=response.read(256_001)
                    if len(raw)<=256_000:
                        url=motion_rendition(raw.decode('utf-8'),url,max(640,size))
                except (OSError,ValueError):
                    pass
            if self.stop_event.is_set():return
            # No audio decoder/output, scripts, cookies, or playback controls.
            # The normal path accepts only Apple-hosted public artwork videos.
            protocols = 'file' if url.startswith('file:') else 'https,tls,tcp,crypto'
            command = [executable, '-nostdin', '-loglevel', 'error', '-threads', '2',
                       '-filter_threads', '1', '-protocol_whitelist', protocols,
                       '-rw_timeout', '7000000', '-analyzeduration', '1000000', '-probesize', '1000000',
                       '-re', '-stream_loop', '-1', '-i', url,
                       '-map', '0:v:0', '-an', '-sn', '-dn',
                       '-vf', f'fps=30,scale={size}:{size}:force_original_aspect_ratio=decrease,'
                              f'pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x20271d,format=rgba',
                       '-threads', '2', '-f', 'rawvideo', 'pipe:1']
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       stdin=subprocess.DEVNULL, bufsize=0)
            with self.lock:
                self.process = process
            if self.stop_event.is_set():
                return
            mask = Image.new('L', (size*2,size*2))
            ImageDraw.Draw(mask).rounded_rectangle((0,0,size*2-1,size*2-1), radius*2, fill=255)
            mask = mask.resize((size,size),Image.Resampling.LANCZOS)
            count = size*size*4
            while not self.stop_event.is_set():
                self.play_gate.wait()
                if self.stop_event.is_set():
                    break
                data = bytearray()
                while len(data)<count and not self.stop_event.is_set():
                    chunk = process.stdout.read(count-len(data))
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data)!=count or self.stop_event.is_set():
                    break
                image = Image.frombytes('RGBA', (size,size), bytes(data))
                image.putalpha(mask)
                frame = image.tobytes()
                with self.lock:
                    self.frame = frame
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        finally:
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                except ProcessLookupError:
                    pass
                if process.stdout:
                    process.stdout.close()
            self.finished = True

    def take_frame(self):
        with self.lock:
            frame, self.frame = self.frame, None
            return frame

    def set_playing(self, playing):
        self.play_gate.set() if playing else self.play_gate.clear()

    def close(self):
        self.stop_event.set()
        self.play_gate.set()
        with self.lock:
            process = self.process
        if process:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        # Process waits and pipe cleanup belong to the decoder, never GTK.


class MotionCover:
    def __init__(self, image):
        self.image = image
        self.run = None
        self.key = None
        self.frames = 0
        self.playing = False
        self.executable = shutil.which('ffmpeg')

    def set_source(self, url, size, radius=22, playing=True):
        self.playing = playing
        key = (url, size, radius) if is_motion_url(url) and self.executable else None
        if key == self.key:
            if self.run:
                self.run.set_playing(playing)
            return
        self.stop()
        if key:
            self.key = key
            self.run = MotionRun(self.executable, url, size, radius, playing)

    def set_playing(self, playing):
        self.playing = playing
        if self.run:
            self.run.set_playing(playing)

    def tick(self):
        if not self.run or not self.playing:
            return
        frame = self.run.take_frame()
        if frame:
            size = self.run.size
            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(frame),
                GdkPixbuf.Colorspace.RGB, True, 8, size, size, size*4)
            self.image.set_from_pixbuf(pixbuf)
            self.image.show()
            self.frames += 1
        if self.run.finished:
            self.image.hide()

    def stop(self):
        if self.run:
            self.run.close()
        self.run = None
        self.key = None
        self.image.clear()
        self.image.hide()
