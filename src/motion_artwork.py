"""Silent, buffered cover loops, paced by the display clock rather than I/O."""
from collections import deque
import math
import shutil
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit
from gi.repository import GdkPixbuf, GLib
from PIL import Image, ImageDraw
from cover_sources import is_motion_url, motion_rendition
from motion_cache import cached_clip


FPS=60
DECODE_SIZE=720
FRAME_MEMORY=24*1024*1024


class FrameQueue:
    """Bounded producer queue with a pauseable, rebuffering presentation clock."""
    def __init__(self,capacity):
        self.capacity=max(4,capacity);self.preroll=min(8,self.capacity//2)
        self.condition=threading.Condition();self.frames=deque()
        self.closed=False;self.ended=False;self.playing=True;self.epoch=None;self.last_tick=None;self.origin=0
        self.presented=0;self.rebuffers=0

    def put(self,index,pixels):
        with self.condition:
            self.condition.wait_for(lambda:self.closed or len(self.frames)<self.capacity)
            if self.closed:return False
            self.frames.append((index,pixels));return True

    def take(self,now):
        with self.condition:
            if self.closed or not self.playing:return None
            # These loops are decorative, not synced to the song. After an
            # obscured window or a layout transition, resume here, never race
            # through frames to catch up with elapsed wall time.
            if self.last_tick is not None and now-self.last_tick>.1:self.epoch=None
            self.last_tick=now
            if self.epoch is None:
                if not self.frames or len(self.frames)<self.preroll and not self.ended:return None
                self.epoch=now;self.origin=self.frames[0][0]
            # Sample nearest to this display tick. Flooring makes tiny clock
            # jitter around a 60 Hz boundary repeat one frame then skip one.
            due=self.origin+math.floor((now-self.epoch)*FPS+.5)
            frame=None
            while self.frames and self.frames[0][0]<=due:
                _,frame=self.frames.popleft()
            if frame is not None:self.presented+=1;self.condition.notify()
            elif not self.frames:
                self.epoch=None;self.rebuffers+=1
            return frame

    def set_playing(self,playing):
        with self.condition:
            if playing!=self.playing:self.epoch=None;self.last_tick=None
            self.playing=playing

    def close(self):
        with self.condition:
            self.closed=True;self.frames.clear();self.condition.notify_all()

    def finish(self):
        with self.condition:self.ended=True;self.condition.notify_all()


class MotionRun:
    def __init__(self, executable, url, size, radius, playing, rounded=True):
        self.stop_event=threading.Event();self.lock=threading.Lock()
        self.process=None;self.finished=False;self.size=size
        self.queue=FrameQueue(max(4,min(24,FRAME_MEMORY//(size*size*4))))
        self.queue.set_playing(playing)
        self.thread=threading.Thread(target=self._decode,args=(executable,url,size,radius,rounded),
                                     name='ember-motion-decode',daemon=True)
        self.thread.start()

    def process_changed(self,process):
        with self.lock:self.process=process

    def _decode(self,executable,url,size,radius,rounded):
        process=None
        try:
            if urlsplit(url).path.endswith('.m3u8'):
                try:
                    with urllib.request.urlopen(url,timeout=6) as response:raw=response.read(256_001)
                    if len(raw)<=256_000:url=motion_rendition(raw.decode('utf-8'),url,max(640,size))
                except (OSError,ValueError):pass
            if self.stop_event.is_set():return
            # Local files are used only by isolated fixtures; set_source still
            # restricts actual artwork to its existing public Apple allowlist.
            if not url.startswith('file:'):
                url=cached_clip(executable,url,self.stop_event,self.process_changed)
            if not url or self.stop_event.is_set():return
            command=[executable,'-nostdin','-loglevel','error','-threads','2','-filter_threads','1',
                     '-protocol_whitelist','file','-stream_loop','-1','-i',url,
                     '-map','0:v:0','-an','-sn','-dn',
                     '-vf',f'scale={size}:{size}:force_original_aspect_ratio=decrease,'
                           f'pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=0x20271d,'
                           'framerate=fps=60:interp_start=0:interp_end=255:scene=8.2,format=rgba',
                     '-threads','2','-f','rawvideo','pipe:1']
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL,bufsize=0)
            self.process_changed(process)
            if self.stop_event.is_set():return
            mask=Image.new('L',(size*2,size*2))
            ImageDraw.Draw(mask).rounded_rectangle((0,0,size*2-1,size*2-1),radius*2,fill=255)
            mask=mask.resize((size,size),Image.Resampling.LANCZOS)
            count=size*size*4;index=0
            while not self.stop_event.is_set():
                data=bytearray()
                while len(data)<count and not self.stop_event.is_set():
                    chunk=process.stdout.read(count-len(data))
                    if not chunk:break
                    data.extend(chunk)
                if len(data)!=count or self.stop_event.is_set():break
                raw=bytes(data)
                if rounded:
                    image=Image.frombytes('RGBA',(size,size),raw);image.putalpha(mask);raw=image.tobytes()
                # GI marshals bytes directly; passing bytearray here would
                # iterate millions of Python integers while holding the GIL.
                pixels=GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(raw),
                    GdkPixbuf.Colorspace.RGB,True,8,size,size,size*4)
                pixels._motion_rounded=rounded
                if not self.queue.put(index,pixels):break
                index+=1
        except (OSError,ValueError,subprocess.SubprocessError):pass
        finally:
            if process:
                try:
                    process.terminate();process.wait(timeout=1)
                except subprocess.TimeoutExpired:process.kill();process.wait()
                except ProcessLookupError:pass
                if process.stdout:process.stdout.close()
            self.queue.finish();self.finished=True

    def take_frame(self,now=None):return self.queue.take(time.monotonic() if now is None else now)

    def set_playing(self,playing):self.queue.set_playing(playing)

    def close(self):
        self.stop_event.set();self.queue.close()
        with self.lock:process=self.process
        if process:
            try:process.terminate()
            except ProcessLookupError:pass
        # Process waits and pipe cleanup belong to the decoder, never GTK.


class MotionCover:
    def __init__(self,image):
        self.image=image;self.run=None;self.key=None;self.frames=0;self.playing=False
        self.executable=shutil.which('ffmpeg')

    def set_source(self,url,size,radius=22,playing=True):
        self.playing=playing
        if hasattr(self.image,'resize'):self.image.resize(size,radius)
        if hasattr(self.image,'warmup'):self.image.warmup()
        key=url if is_motion_url(url) and self.executable else None
        if key==self.key:
            if self.run:self.run.set_playing(playing)
            return
        self.stop()
        if key:
            self.key=key
            self.run=MotionRun(self.executable,url,DECODE_SIZE,radius,playing,
                               rounded=not bool(getattr(self.image,'driver',None)))

    def set_playing(self,playing):
        self.playing=playing
        if self.run:self.run.set_playing(playing)

    def tick(self,now=None):
        if not self.run or not self.playing:return
        frame=self.run.take_frame(now)
        if frame:
            self.image.set_from_pixbuf(frame);self.image.show();self.frames+=1
        if self.run.finished and not self.run.queue.frames:self.image.hide()

    def stop(self):
        if self.run:self.run.close()
        self.run=None;self.key=None
        self.image.clear();self.image.hide()
