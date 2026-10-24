"""Small single-flight metadata cache. Slow services cannot hold the DJ planner."""
from concurrent.futures import Future,ThreadPoolExecutor
import threading,time


class Lookups:
    def __init__(self):
        self.lock=threading.RLock();self.values={};self.pending={};self.closed=False
        self.pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix='ember-dj-catalogue')
    def get(self,key,call,ttl=300):
        with self.lock:
            if self.closed:return None
            cached=self.values.get(key)
            if cached and time.monotonic()-cached[0]<ttl:
                future=Future();future.set_result(cached[1]);return future
            if key in self.pending:return self.pending[key]
            # A flood of new wishes cannot create an unbounded request queue.
            if len(self.pending)>=3:return None
            future=self.pool.submit(call);self.pending[key]=future
            future.add_done_callback(lambda result:self.finished(key,result))
            return future
    def finished(self,key,future):
        with self.lock:
            self.pending.pop(key,None)
            try:value=future.result()
            except Exception:return
            if self.closed:return
            self.values[key]=(time.monotonic(),value)
            while len(self.values)>48:del self.values[next(iter(self.values))]
    def clear(self):
        with self.lock:self.values.clear()
    def close(self):
        with self.lock:self.closed=True;self.values.clear()
        self.pool.shutdown(wait=False,cancel_futures=True)
