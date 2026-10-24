"""Opt-in, bounded two-deck crossfades for Ember's shared listening queue."""
import json,time
from listening_queue import matches
from source_picker import text


class EmberFlow:
    DURATION=4.
    def __init__(self,music,path):
        self.music=music;self.host=music.host;self.path=path;self.enabled=False;self.closed=False
        self.context=None;self.ready=False;self.busy=False;self.preparing=False;self.attempted=False
        self.error='';self.youtube=None;self.apple=None;self.pending_item=None
        self.last_position=None;self.last_time=None;self.mixing_until=0.;self.clock=time.monotonic
        try:
            if path.stat().st_size<4096:self.enabled=json.loads(path.read_text()).get('enabled') is True
        except (OSError,ValueError,TypeError,AttributeError):pass

    @property
    def supported(self):
        h=self.host
        return h.source=='youtube' and h.youtube_mode=='native' or (h.source=='apple-music' and h.apple_mode=='native'
            and getattr(h.apple_web,'state',{}).get('emberFlow') is True)

    @property
    def message(self):
        if not self.supported:return text('Available with in-player Apple Music and YouTube','Для встроенных Apple Music и YouTube')
        if not self.enabled:return text('Gentle blends between tracks','Мягкое смешивание треков')
        karaoke=getattr(getattr(getattr(self.host,'fullscreen',None),'karaoke',None),'audio',None)
        if karaoke and (karaoke.active or karaoke.starting):return text('Flow waits while vocal reduction is on','Flow ждёт, пока включено приглушение вокала')
        if self.error:return self.error
        if self.busy or self.mixing_until>self.clock():return text('Two songs, one flow','Две песни — один поток')
        if self.preparing:return text('Preparing the next track','Готовим следующий трек')
        if self.music.book.active!=self.host.source or not self.music.book.upcoming(self.host.source):
            return text('Add a next track to the Ember queue','Добавь следующий трек в очередь Ember')
        return text('A smooth four-second transition','Плавный переход · 4 секунды')

    def set_enabled(self,enabled):
        self.enabled=bool(enabled);self.error='';self.cancel()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.next.json')
        temporary.write_text(json.dumps({'enabled':self.enabled}));temporary.chmod(0o600);temporary.replace(self.path)
        self.music.changed()

    def cancel(self):
        self.context=None;self.ready=self.busy=self.preparing=self.attempted=False;self.pending_item=None
        self.last_position=self.last_time=None;self.mixing_until=0.
        if self.youtube:self.youtube.cancel()
        if self.apple:self.apple.cancel()

    def adopt(self,item,duration,extra=0.):
        s=self.music;source=self.host.source;pending=s.book.upcoming(source)
        if not pending or pending[0][1]['entry']!=item['entry']:
            self.cancel();return
        s.book.select(source,pending[0][0]);s.watch.reset();s.started=time.monotonic();s.loading=False
        self.context=None;self.pending_item=None;self.mixing_until=self.clock()+duration+extra+.3;s.changed()

    def tick(self,state):
        if self.closed:return
        h=self.host;s=self.music;source=h.source;now=self.clock()
        if self.enabled and self.supported and s.book.active is None and state.get('playing') and not s.loading:
            current=s.book.current(source)
            if current and s.book.upcoming(source) and matches(current,state):
                s.book.active=source;s.watch.reset();s.started=time.monotonic();s.changed()
        karaoke=getattr(getattr(getattr(h,'fullscreen',None),'karaoke',None),'audio',None)
        if not self.enabled or not self.supported or s.book.active!=source or s.loading or (
                karaoke and (karaoke.active or karaoke.starting)):
            if self.context or self.mixing_until or self.busy:self.cancel();s.changed()
            return
        if self.busy:
            # MusicKit can mark its old SDK player paused while its authorized
            # HTML tail continues. Wait for the engine's confirmed promotion.
            try:
                result=self.apple.result()
                if result is None:return
                self.busy=False
                if result.get('started') is True:self.adopt(self.pending_item,float(result.get('duration',self.DURATION)))
            except Exception:
                self.busy=False;self.error=text('The transition was not ready; continuing normally','Переход не готов — продолжаем обычное воспроизведение')
            s.changed();return
        if self.mixing_until>now:
            # The 750 ms source snapshot may still describe the outgoing track.
            current=s.book.current(source)
            if current and not matches(current,state):return
            if state.get('playing'):return
        if not state.get('playing'):
            if self.context or self.mixing_until:self.cancel();s.changed()
            return
        current=s.book.current(source);pending=s.book.upcoming(source)
        if not current or not pending or not matches(current,state) or state.get('duration',0)<20:return
        next_item=pending[0][1];context=(current['entry'],next_item['entry'])
        if self.context!=context:self.cancel();self.context=context;self.error=''
        remaining=state['duration']-state.get('position',0);position=state.get('position',0)
        if self.last_position is not None and abs(position-self.last_position)>max(1.5,now-self.last_time+1.5):
            self.cancel();return
        self.last_position=position;self.last_time=now
        if not self.attempted and 7<remaining<=28:
            self.attempted=True;self.preparing=True;self.prepare_started=now
            if source=='apple-music':
                if self.apple is None:
                    from flow_apple import AppleDecks
                    self.apple=AppleDecks(h)
                deck=self.apple
            else:
                if self.youtube is None:
                    from flow_youtube import YouTubeDecks
                    self.youtube=YouTubeDecks(h)
                deck=self.youtube
            try:deck.prepare(next_item)
            except Exception:self.preparing=False;deck.cancel()
            s.changed()
        deck=self.apple if source=='apple-music' else self.youtube
        if self.preparing:
            failed=self.apple.failed if source=='apple-music' else bool(deck.standby and deck.standby.failed)
            if deck.ready:self.ready=True;self.preparing=False;s.changed()
            elif failed or now-self.prepare_started>20:
                self.preparing=False;deck.cancel();self.error=text('Next track is not ready; using the normal transition',
                    'Следующий трек не готов — обычное переключение');s.changed()
        lead=6.5 if source=='apple-music' else self.DURATION+.4
        if self.ready and .5<remaining<=lead:
            self.busy=True;self.ready=False;duration=min(self.DURATION,remaining-.2)
            if source=='apple-music':self.pending_item=next_item;deck.transition(duration)
            else:
                try:
                    if deck.transition(duration):self.adopt(next_item,duration,2.)
                except Exception:deck.cancel()
                self.busy=False
            s.changed()

    def close(self):
        if self.closed:return
        self.cancel();self.closed=True
        if self.apple:self.apple.close()
