"""Nonblocking commands to Ember's own authorized MusicKit two-deck engine."""
from concurrent.futures import ThreadPoolExecutor


class AppleDecks:
    def __init__(self,host):
        self.host=host;self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='emberflow-apple')
        self.prepared=None;self.transitioning=None;self.reset=None;self.active=False;self.key='';self.beat_sync=True
    def request(self,operation,**params):return self.host.apple_web.request('flow',operation=operation,**params)
    def prepare(self,item):
        self.cancel();self.active=True;self.key=item['entry']
        reset=self.reset;key=self.key
        def load():
            if reset:reset.result(timeout=4)
            return self.request('prepare',key=key,kind=item['kind'],id=item['id'],beatSync=self.beat_sync)
        self.prepared=self.pool.submit(load)
    @property
    def ready(self):
        if not self.prepared or not self.prepared.done():return False
        try:return self.prepared.result().get('ready') is True
        except Exception:return False
    @property
    def failed(self):
        return bool(self.prepared and self.prepared.done() and not self.ready)
    def transition(self,duration):
        self.transitioning=self.pool.submit(self.request,'transition',key=self.key,duration=duration)
    def result(self):
        if not self.transitioning or not self.transitioning.done():return None
        future=self.transitioning;self.transitioning=None
        return future.result()
    def cancel(self,preserve=False):
        if self.active and (not self.reset or self.reset.done()):
            self.reset=self.pool.submit(self.request,'cancel',**({'preserve':True} if preserve else {}))
        self.active=False;self.key='';self.prepared=self.transitioning=None
    def close(self):
        self.cancel();self.pool.shutdown(wait=False,cancel_futures=False)
