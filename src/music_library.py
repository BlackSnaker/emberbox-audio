"""Async collection browsing and a persistent listening queue shared by modes."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from gi.repository import GLib
from discovery import LocalSpotify
from sources import choose_session
from listening_queue import QueueBook,EndWatch,track,LIMIT
from paths import CONFIG_DIR
from source_picker import text
from youtube_search import Search,video_url

NAMES={'spotify':'Spotify','apple-music':'Apple Music','youtube':'YouTube','yandex-music':'Яндекс Музыка'}


def youtube_item(item):
    return dict(item,uri='youtube:'+str(item.get('id','')),kind='track',artist=item.get('channel',''),
                image=f"https://i.ytimg.com/vi/{item.get('id','')}/hqdefault.jpg",duration_ms=int(item.get('duration') or 0)*1000)


class MusicRepository:
    def __init__(self,host):self.host=host;self.locks={s:threading.RLock() for s in NAMES}

    def load(self,source,category,term='',collection=None,offset=0):
        h=self.host
        with self.locks[source]:
            if source=='spotify':
                with LocalSpotify() as client:
                    if collection:return client.tracks(collection)
                    if category=='search':return client.search(term)
                    data=client.home()
                shelves=data.get('shelves',[])
                items=[];seen=set()
                for shelf in shelves:
                    for value in shelf.get('items',[]):
                        if value['uri'] in seen:continue
                        seen.add(value['uri'])
                        item=dict(value,kind='album' if ':album:' in value['uri'] else 'playlist')
                        if category!='albums' or item['kind']=='album':items.append(item)
                return {'items':items,'note':text('Your personal Spotify picks','Твои персональные подборки Spotify') if category!='albums' else text('Albums from your personal picks','Альбомы из твоих подборок')}
            if source=='apple-music':
                player=h.apple_web if h.apple_mode=='native' else h.apple
                if collection:return player.request('tracks',kind=collection['kind'],id=collection['id'],offset=offset)
                if category=='search':
                    if h.apple_mode!='native':raise RuntimeError(text('Connect Apple Music in Accounts to search its catalogue.','Подключи Apple Music в Аккаунтах для поиска по каталогу.'))
                    return player.request('search',term=term)
                return player.request('browse',category='albums' if category=='albums' else 'playlists',offset=offset)
            if source=='yandex-music':
                player=h.yandex_web
                if collection:return player.request('tracks',id=collection['id'])
                if category=='search':return player.request('search',term=term)
                if category=='albums':return {'items':[],'note':text('This connection exposes playlists and tracks. Find an album by title in Search.',
                    'Это подключение показывает плейлисты и треки. Альбом можно найти по названию в Поиске.')}
                return player.request('browse',category='collection')
            if source=='youtube':
                if category=='albums':return {'items':[],'note':text('YouTube videos have no album catalogue here. Search for an artist and album title.',
                    'Здесь у видео YouTube нет каталога альбомов. Введи исполнителя и название альбома в Поиске.')}
                return {'items':[youtube_item(i) for i in h.youtube.queue[-50:]],'note':text('Recently chosen in Emberbox','Недавно выбранное в Emberbox')}
        return {'items':[]}

    def play(self,item,alive):
        source=item['source'];h=self.host
        with self.locks[source]:
            if not alive():return
            if source=='spotify':
                with LocalSpotify() as client:
                    if alive():client.play(item['uri'])
            elif source=='apple-music':
                player=h.apple_web if h.apple_mode=='native' else h.apple
                player.request('play',kind=item['kind'],id=item['id'])
            elif source=='yandex-music':
                # Website rows are virtualised. Relocate this exact ID rather
                # than keeping a stale DOM row from a previous search page.
                result=h.yandex_web.request('search',term=(item['title']+' '+item['artist'])[:200])
                if not any(str(i.get('id'))==item['id'] for i in result.get('items',[])):
                    raise RuntimeError(text('This track could not be found again. Refresh the search.',
                                            'Не удалось снова найти этот трек. Обнови поиск.'))
                if alive():h.yandex_web.request('play',id=item['id'])


def snapshot(host):
    source=host.source
    state={'title':host.title.get_text(),'artist':host.artist.get_text(),'playing':host.playing,
           'duration':host.length/1e6,'position':host.position/1e6,'valid':host.length>0,'id':'','uri':''}
    if source=='apple-music' and host.apple_mode=='native':
        data=host.apple_web.state;state['id']=str(data.get('id') or data.get('catalogId') or '')
        state['catalogId']=str(data.get('catalogId') or '')
        state['ended']=bool(data.get('ended'))
    elif source=='yandex-music':
        state['id']=str(host.yandex_web.state.get('id') or '')
    elif source=='youtube' and host.youtube_mode=='native':
        state['id']=str((host.youtube.current or {}).get('id',''));state['ended']=host.youtube.eof
    elif getattr(host,'session',None):
        meta=host.session.metadata
        state['uri']=str(meta.get('xesam:url') or '')
        state['id']=str(meta.get('mpris:trackid') or '').rsplit('/',1)[-1]
    state['valid']=bool(state['duration']>0 or state['id'] or state['uri'])
    return state


class MusicService:
    def __init__(self,host,path=None):
        self.host=host;self.repository=MusicRepository(host)
        self.book=QueueBook(path or CONFIG_DIR/'listening-queue.json');self.watch=EndWatch()
        self.listeners=[];self.closed=False;self.browse_generation=0;self.play_generation=0
        self.loading=False;self.error='';self.started=0.;self.source=host.source
        self.browse_future=None;self.play_future=None
        self.pause_after=set()
        self.browse_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-collection')
        self.play_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-queue')
        self.youtube=Search(self._youtube_results);self.youtube_done=None
        self.timer=GLib.timeout_add(250,self.poll)

    def subscribe(self,callback):
        self.listeners.append(callback)
        return lambda:self.listeners.remove(callback) if callback in self.listeners else None

    def changed(self):
        for callback in tuple(self.listeners):callback()

    def load(self,category,done,term='',collection=None,offset=0):
        if self.browse_future:self.browse_future.cancel()
        self.browse_generation+=1;generation=self.browse_generation;source=self.host.source
        self.youtube.cancel();self.youtube_done=None
        if source=='youtube' and category=='search':
            try:parsed=video_url(term)
            except ValueError as error:done(None,error);return
            if parsed:
                ident=parsed[0].rsplit('=',1)[-1]
                done({'items':[youtube_item({'id':ident,'url':parsed[0],'title':text('YouTube link','Ссылка YouTube'),'duration':0})]},None)
                return
            self.youtube_done=(generation,source,done);self.youtube.start(term);return
        future=self.browse_pool.submit(self.repository.load,source,category,term,collection,offset)
        self.browse_future=future
        def complete(result):
            if self.closed or generation!=self.browse_generation or source!=self.host.source:return False
            try:data,error=result.result(),None
            except Exception as exc:data,error=None,exc
            done(data,error);return False
        future.add_done_callback(lambda result:GLib.idle_add(complete,result))

    def _youtube_results(self,items,error):
        value=self.youtube_done
        if value and not self.closed and value[:2]==(self.browse_generation,self.host.source):
            value[2]({'items':[youtube_item(i) for i in items]},RuntimeError(error) if error else None)

    def cancel_browse(self):
        self.browse_generation+=1;self.youtube.cancel();self.youtube_done=None
        if self.browse_future:self.browse_future.cancel()

    def add(self,items):
        count=self.book.add(self.host.source,[dict(item,origin='manual') for item in items]);self.error='';self.changed();return count

    def play_now(self,item,context=None):
        source=self.host.source;value=track(item,source)
        if not value:return
        if context is not None and self.play_context(item,context):return
        self.book.compact(source)
        current=self.book.current(source)
        found=self.book.indices[source] if current and current['uri']==value['uri'] else next(
            (i for i,v in self.book.upcoming(source) if v['uri']==value['uri']),None)
        if found is None:
            # Insert ahead of pending music, preserving the user's custom tail.
            found=self.book.indices[source]+1
            self.book.queues[source].insert(found,value)
            self.book.queues[source]=self.book.queues[source][:200]
        self.start(found)

    def play_context(self,item,context):
        """Continue the clicked result's visible list, retaining explicit additions."""
        source=self.host.source;raw=list(context)
        index=next((i for i,v in enumerate(raw) if v is item),None)
        if index is None:index=next((i for i,v in enumerate(raw) if isinstance(v,dict) and v.get('uri')==item.get('uri')),None)
        if index is None:return False
        selected=raw[index];values=[];chosen=None
        for value in raw[max(0,index-LIMIT+1):index+LIMIT]:
            normalized=track(value,source)
            if normalized:
                normalized['origin']='context'
                if value is selected:chosen=len(values)
                values.append(normalized)
        if chosen is None:return False
        selected=values[chosen]
        manual=[dict(value) for _,value in self.book.upcoming(source) if value.get('origin')!='context']
        # If this click selects an explicitly queued song, consume that entry
        # once; deliberately queued repeats remain in the manual tail.
        for i,value in enumerate(manual):
            if value['uri']==selected['uri']:del manual[i];break
        if len(manual)>=LIMIT:
            self.error=text('The queue is full. Remove a track before starting a new list.',
                            'Очередь заполнена. Убери один трек, чтобы запустить новый список.')
            self.changed();return True
        manual=manual[:LIMIT-1];manual_uris={value['uri'] for value in manual}
        room=LIMIT-1-len(manual)
        after=[value for value in values[chosen+1:] if value['uri'] not in manual_uris][:room]
        room-=len(after);before=values[:chosen][-room:] if room else []
        self.play_generation+=1;self.loading=False;self.watch.reset()
        self.book.replace(source,before+[selected]+manual+after)
        self.start(len(before));return True

    def play_all(self,items):
        self.play_generation+=1;self.loading=False;self.watch.reset()
        self.book.replace(self.host.source,[dict(item,origin='context') for item in items])
        if self.book.queues[self.host.source]:self.start(0)
        else:self.changed()

    def start(self,index=None):
        source=self.host.source
        if source=='youtube' and self.host.youtube_mode!='native':
            self.error=text('Choose the in-player YouTube source to play this queue.','Выбери встроенный YouTube в меню источников для воспроизведения очереди.')
            self.book.active=None;self.changed();return
        if index is None:
            pending=self.book.upcoming(source)
            index=self.book.indices[source] if self.error and self.book.current(source) else pending[0][0] if pending else max(0,self.book.indices[source])
        item=self.book.select(source,index)
        if not item:return
        self.play_generation+=1;generation=self.play_generation
        if self.play_future:self.play_future.cancel()
        self.loading=True;self.error='';self.started=time.monotonic();self.watch.reset();self.changed()
        alive=lambda:not self.closed and generation==self.play_generation and self.host.source==source
        if source=='youtube':
            video=dict(item,channel=item['artist'],duration=item['duration_ms']/1000)
            self.host.play_youtube(video,[video],managed=True);self.loading=False;self.changed();return
        future=self.play_pool.submit(self.repository.play,item,alive);self.play_future=future
        def complete(result):
            if self.closed:return False
            if not alive():
                if self.host.source!=source:self.pause(source)
                elif generation in self.pause_after and not self.loading:self.pause(source)
                self.pause_after.discard(generation)
                return False
            self.loading=False
            try:result.result()
            except Exception as error:
                self.error=str(error);self.book.active=None
            self.changed();return False
        future.add_done_callback(lambda result:GLib.idle_add(complete,result))

    def step(self,direction):
        source=self.host.source;index=self.book.indices[source]
        if direction<0 and self.host.position>3_000_000:self.host.seek_to(0);return
        if 0<=index+direction<len(self.book.queues[source]):self.start(index+direction)
        elif direction<0:self.host.seek_to(0)
        else:self.book.active=None;self.pause(source);self.changed()

    def pause(self,source):
        h=self.host
        if source in ('apple-music','yandex-music'):
            player=h.yandex_web if source=='yandex-music' else h.apple_web if h.apple_mode=='native' else None
            if player:player.action('transport',action='pause');return
        if source=='youtube' and h.youtube_mode=='native':
            h.youtube.paused=True
            if h.youtube.mpv:h.youtube.mpv.command_async('set','pause','yes')
        else:
            binding=h.youtube_binding if source=='youtube' else h.browser_binding
            session=choose_session(h.sessions,source,binding)
            if session:h.monitor.call(session,'Pause')

    def stop(self,pause_pending=False):
        if self.loading and pause_pending:self.pause_after.add(self.play_generation)
        self.play_generation+=1;self.loading=False;self.book.active=None;self.error='';self.watch.reset();self.changed()

    def source_changed(self):
        self.stop();self.cancel_browse();self.source=self.host.source

    def poll(self):
        if self.closed:return False
        if self.source!=self.host.source:self.source_changed()
        source=self.host.source
        if self.book.active==source and not self.loading:
            item=self.book.current(source);result=self.watch.observe(item,snapshot(self.host)) if item else None
            if result=='next':self.step(1)
            elif result=='external':self.stop()
            elif not self.watch.seen and time.monotonic()-self.started>20:
                self.stop();self.error=text('Playback was not confirmed. Try this track again.','Запуск трека не подтверждён. Попробуй включить его ещё раз.');self.changed()
        return True

    def close(self):
        self.closed=True;self.play_generation+=1;self.cancel_browse()
        GLib.source_remove(self.timer);self.youtube.close();self.listeners.clear()
        self.browse_pool.shutdown(wait=False,cancel_futures=True);self.play_pool.shutdown(wait=False,cancel_futures=True)
