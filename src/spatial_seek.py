"""Bounded, cancellable same-song decode passes; no second DRM session."""
import os
import select
import struct
import threading


class SeekCancelled(Exception):
    pass


class Seeks:
    def __init__(self):
        self.condition=threading.Condition();self.pending=None;self.active=None;self.closed=False
        self.processes=[]

    def submit(self,position,generation,selection=None):
        position=float(position);generation=int(generation)
        if not 0<=position<86400 or not 0<generation<2**32:raise ValueError('Invalid spatial seek')
        with self.condition:
            if self.closed:return
            self.pending=(position,generation,selection)
            self._cancel();self.condition.notify_all()

    def park(self):
        with self.condition:
            self.pending=None;self._cancel();self.condition.notify_all()

    def _cancel(self):
        if self.active:self.active.set()
        # A decoder can be blocked feeding ffmpeg while its PCM pipe is full.
        # Discard that codec process, too; an Event cannot wake a pipe write.
        # SIGTERM tries to flush into a reader that has already been cancelled.
        # The licensed host remains alive; only this disposable codec is killed.
        for process in self.processes:
            try:process.kill()
            except ProcessLookupError:pass

    def attach(self,decoder,cancelled):
        process=getattr(decoder,'process',None)
        if process is None:return
        with self.condition:
            self.processes.append(process)
            if cancelled.is_set():
                try:process.kill()
                except ProcessLookupError:pass

    def next(self):
        value=self.next_selection()
        return (value[0],value[1],value[3]) if value is not None else None

    def next_selection(self):
        with self.condition:
            while not self.closed and self.pending is None:self.condition.wait()
            if self.closed:return None
            value=self.pending;self.pending=None;self.processes=[]
            self.active=threading.Event()
            return (*value,self.active)

    def close(self):
        with self.condition:
            self.closed=True;self._cancel();self.condition.notify_all()


class PcmWriter:
    def __init__(self,fd,stopping):
        self.fd=fd;self.stopping=stopping;self.lock=threading.Lock();os.set_blocking(fd,False)

    def write(self,data,generation,cancelled):
        with self.lock:self._write(data,generation,cancelled)

    def _write(self,data,generation,cancelled):
        if cancelled.is_set():raise SeekCancelled()
        frame=memoryview(struct.pack('<II',generation,len(data))+data)
        started=False
        while frame and not self.stopping.is_set():
            # Finish an already-started frame before changing generations.
            # The parent discards it whole; its next header stays aligned.
            if not started and cancelled.is_set():raise SeekCancelled()
            if not select.select([], [self.fd], [], .05)[1]:continue
            try:count=os.write(self.fd,frame)
            except BlockingIOError:continue
            started=True;frame=frame[count:]
        if self.stopping.is_set() or cancelled.is_set():raise SeekCancelled()
