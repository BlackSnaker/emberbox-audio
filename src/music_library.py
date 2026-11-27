"""Async collection browsing and a persistent listening queue shared by modes."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from gi.repository import GLib
from discovery import LocalSpotify
from sources import choose_session
from listening_queue import QueueBook,EndWatch,track,LIMIT,matches
from paths import CONFIG_DIR
from source_picker import text
from youtube_search import Search,video_url
from artist_catalog import ArtistRepository

NAMES={'spotify':'Spotify','apple-music':'Apple Music','youtube':'YouTube','yandex-music':'Яндекс Музыка'}


def youtube_item(item):
    return dict(item,uri='youtube:'+str(item.get('id','')),kind='track',artist=item.get('channel',''),
                image=f"https://i.ytimg.com/vi/{item.get('id','')}/hqdefault.jpg",duration_ms=int(item.get('duration') or 0)*1000)


class MusicRepository:
    def __init__(self,host):self.host=host;self.locks={s:threading.RLock() for s in NAMES}

    def load_apple(self,category,term,collection,offset):
        h=self.host;native=h.apple_mode=='native'
        player=h.apple_web if native else h.apple
        if category=='release' and (collection or {}).get('kind')=='library-albums':
            result=player.request('tracks',kind='library-albums',id=collection['id'],offset=offset)
            return {'release':collection,'items':result.get('tracks',[]),'next':result.get('next')}
        if category in ('artist','artist-section','release'):
            return ArtistRepository(h).load('apple-music',category,collection,offset)
        if collection:return player.request('tracks',kind=collection['kind'],id=collection['id'],offset=offset)
        if category=='search':
            if not native:raise RuntimeError(text('Connect Apple Music in Accounts to search its catalogue.','Подключи Apple Music в Аккаунтах для поиска по каталогу.'))
            return player.request('search',term=term)
        return player.request('browse',category='albums' if category=='albums' else 'playlists',offset=offset)

    def load(self,source,category,term='',collection=None,offset=0):
        h=self.host
        if category=='whole-album':
            return self.load_whole_album(source,collection)
        # The native Apple bridge matches concurrent replies by request ID.
        # Album reads can run beside a previous catalogue request safely.
        if source=='apple-music' and (h.apple_mode=='native' or (collection or {}).get('kind')=='library-albums'):
            return self.load_apple(category,term,collection,offset)
        with self.locks[source]:
            if category in ('artist','artist-section','release'):
                return ArtistRepository(h).load(source,category,collection,offset)
            if source=='spotify':
                if getattr(h,'spotify_mode','desktop')=='native':
                    player=h.spotify_web
                    if collection:return player.request('tracks',uri=collection.get('uri',''),offset=offset)
                    if category=='search':return player.request('search',term=term)
                    return player.request('browse',category='albums' if category=='albums' else 'home',offset=offset)
                with LocalSpotify() as client:
                    if collection:return client.tracks(collection)
                    if category=='search':return client.search(term)
                    if category=='albums':return client.saved_albums()
                    data=client.home()
                shelves=data.get('shelves',[])
                items=[];seen=set()
                for shelf in shelves:
                    for value in shelf.get('items',[]):
                        if value['uri'] in seen:continue
                        seen.add(value['uri'])
                        item=dict(value,kind='album' if ':album:' in value['uri'] else 'playlist')
                        items.append(item)
                return {'items':items,'note':text('Your personal Spotify picks','Твои персональные подборки Spotify')}
            if source=='apple-music':return self.load_apple(category,term,collection,offset)
            if source=='yandex-music':
                player=h.yandex_web
                if collection:return player.request('tracks',id=collection['id'])
                if category=='search':return player.request('search',term=term)
                if category=='albums':return player.request('browse',category='albums',offset=offset)
                personal=player.request('browse',category='personal')
                owned=player.request('browse',category='collection')
                items=[];seen=set()
                for value in personal.get('items',[])+owned.get('items',[]):
                    ident=value.get('id')
                    if ident and ident not in seen:
                        seen.add(ident);items.append(value)
                return {'items':items,'note':personal.get('note','')}
            if source=='youtube':
                if category=='albums':return {'items':[],'note':text('YouTube videos have no album catalogue here. Search for an artist and album title.',
                    'Здесь у видео YouTube нет каталога альбомов. Введи исполнителя и название альбома в Поиске.')}
                return {'items':[youtube_item(i) for i in h.youtube.queue[-50:]],'note':text('Recently chosen in Emberbox','Недавно выбранное в Emberbox')}
        return {'items':[]}

    def load_whole_album(self, source, collection):
        """Resolve every page of the exact release before starting playback."""
        from album_shelf_data import release_reference
        ref = release_reference(source, collection)
        if not ref:
            raise ValueError(text('This source does not identify the album.', 'Источник не указал точное издание альбома.'))
        offset, items, expected = 0, [], int(ref.get('trackCount') or 0)
        for _ in range(40):
            result = self.load(source, 'release', collection=ref, offset=offset)
            values = result.get('items', result.get('tracks', []))
            items.extend(values or [])
            expected = max(expected, int(result.get('total') or (result.get('release') or {}).get('trackCount') or 0))
            next_offset = result.get('next')
            if next_offset is None and len(items) >= expected:
                return {'title': ref['title'], 'items': items}
            if type(next_offset) is not int or next_offset <= offset or not values:
                break
            offset = next_offset
        raise ValueError(text('Could not load the complete track list. Try again.', 'Не удалось загрузить альбом целиком. Попробуй ещё раз.'))

    def play(self,item,alive):
        source=item['source'];h=self.host
        if source=='spotify':
            if getattr(h,'spotify_mode','desktop')=='native':
                if alive():return h.spotify_web.request('play',uri=item['uri'])
                return
            # URI playback calls the desktop player's transport directly. It
            # does not navigate the UI and must not queue behind Home/Search.
            with LocalSpotify() as client:
                if alive():client.play(item['uri'])
            return
        if source=='apple-music':
            # Catalogue reads never own the transport. A slow artist or
            # discography request must not delay Next or Previous.
            player=h.apple_web if h.apple_mode=='native' else h.apple
            if alive():return player.request('play',kind='songs' if item.get('catalogId') else item['kind'],
                                              id=item.get('catalogId') or item['id'])
            return
        with self.locks[source]:
            if not alive():return
            if source=='yandex-music':
                options = {'playlistId': item['playlistId']} if item.get('playlistId') else {}
                if item.get('kind') == 'episode':
                    options['episode'] = True
                if alive():return h.yandex_web.request('play',id=item['id'],**options)


def snapshot(host):
    source=host.source
    state={'title':host.title.get_text(),'artist':host.artist.get_text(),'playing':host.playing,
           'duration':host.length/1e6,'position':host.position/1e6,'valid':host.length>0,'id':'','uri':''}
    podcast = getattr(host, 'podcast_audio', None)
    if podcast and podcast.enabled:
        data=podcast.state;state.update(id=data.get('id', ''),uri=data.get('uri', ''),kind='episode',ended=bool(data.get('ended')))
    elif source=='spotify' and getattr(host,'spotify_mode','desktop')=='native':
        data=host.spotify_web.state;state.update(id=str(data.get('id') or ''),uri=str(data.get('uri') or ''),kind=data.get('kind'),ended=bool(data.get('ended')))
    elif source=='apple-music' and host.apple_mode=='native':
        data=host.apple_web.state;state['id']=str(data.get('id') or data.get('catalogId') or '')
        state['catalogId']=str(data.get('catalogId') or '')
        state['ended']=bool(data.get('ended'))
    elif source=='yandex-music':
        state['id']=str(host.yandex_web.state.get('id') or '')
        state['kind']=host.yandex_web.state.get('kind')
        state['ended']=bool(host.yandex_web.state.get('ended'))
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
        self.saved_book=None;self.album_title=''
        self.listeners=[];self.closed=False;self.browse_generation=0;self.play_generation=0
        self.loading=False;self.error='';self.started=0.;self.source=host.source
        self.browse_future=None;self.play_future=None
        self.awaiting_native=None
        self.prime_timer=0
        self.pause_after=set()
        self.previous_restart=None
        self.transition_preview=None
        self.browse_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-collection')
        self.album_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='ember-apple-album')
        self.play_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-queue')
        self.youtube=Search(self._youtube_results);self.youtube_done=None
        from ember_flow import EmberFlow
        self.flow=EmberFlow(self,self.book.path.with_name('ember-flow.json'))
        from favorites import Favorites
        self.favorites=Favorites(self,self.book.path.with_name('favorites.json'))
        self.timer=GLib.timeout_add(250,self.poll)

    def subscribe(self,callback):
        self.listeners.append(callback)
        return lambda:self.listeners.remove(callback) if callback in self.listeners else None

    def changed(self):
        for callback in tuple(self.listeners):callback()

    def load(self,category,done,term='',collection=None,offset=0):
        if self.source!=self.host.source:self.source_changed()
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
        apple_album=(source=='apple-music' and self.host.apple_mode=='native' and
                     (category in ('release','whole-album') or (collection or {}).get('kind') in ('albums','library-albums')))
        pool=self.album_pool if apple_album else self.browse_pool
        future=pool.submit(self.repository.load,source,category,term,collection,offset)
        self.browse_future=future
        def complete(result):
            if self.closed or generation!=self.browse_generation or source!=self.host.source:return False
            try:data,error=result.result(),None
            except Exception as exc:data,error=None,exc
            done(data,error);return False
        future.add_done_callback(lambda result:GLib.idle_add(complete,result,priority=GLib.PRIORITY_DEFAULT))

    def _youtube_results(self,items,error):
        value=self.youtube_done
        if value and not self.closed and value[:2]==(self.browse_generation,self.host.source):
            value[2]({'items':[youtube_item(i) for i in items]},RuntimeError(error) if error else None)

    def cancel_browse(self):
        self.browse_generation+=1;self.youtube.cancel();self.youtube_done=None
        if self.browse_future:self.browse_future.cancel()

    def start_yandex_wave(self,*,playlist=None,recording=None):
        if self.host.source!='yandex-music':return False
        if getattr(self.host, 'exit_apple_podcast', None):self.host.exit_apple_podcast()
        params={}
        if playlist is not None:
            if not playlist.get('id'):return False
            params={'id':str(playlist['id'])}
            if playlist.get('title'):params['title']=str(playlist['title'])
        elif recording is not None:
            if not recording.get('id'):return False
            params={'trackId':str(recording['id']),'title':str(recording.get('title') or '')}
        self.stop(pause_pending=True)
        self.host.yandex_web.action('wave',**params)
        return True

    def queue_snapshot(self,source):
        """Current track and upcoming entries from the queue owning playback."""
        if self.book.active!=source:return None
        values=self.book.queues[source]
        index=max(0,self.book.indices[source])
        return [dict(value) for value in values[index:]]

    def add(self,items):
        book=self.saved_book or self.book
        count=book.add(self.host.source,[dict(item,origin='manual') for item in items]);self.error='';self.changed();return count

    @property
    def album_listening(self):
        return self.saved_book is not None

    def play_album(self, title, items):
        source=self.host.source
        songs=[song for item in items if (song:=track(item,source)) and song['kind']!='episode']
        if not songs:return 0
        self.restore_queue()
        self.saved_book=self.book
        self.book=QueueBook(None)
        self.book.queues[source]=songs
        self.album_title=title
        self._start(0)
        return len(songs)

    def restore_queue(self):
        if self.album_listening:
            self.book=self.saved_book
            self.book.active=None
            self.saved_book=None;self.album_title=''

    def exit_album(self):
        if not self.album_listening:return
        self.stop(pause_pending=True)
        self.pause(self.host.source)

    def cancel_prime(self):
        if self.prime_timer:GLib.source_remove(self.prime_timer);self.prime_timer=0

    def prime(self,item):
        self.cancel_prime()
        h=self.host
        if self.closed or self.loading or self.album_listening or h.source!='apple-music' or h.apple_mode!='native':return
        value=track(item,h.source)
        if not value:return
        generation=self.play_generation
        def prepare():
            self.prime_timer=0
            if not self.closed and not self.loading and h.source=='apple-music' and generation==self.play_generation:
                h.apple_web.action('spatial',operation='prime',kind='songs' if value.get('catalogId') else value['kind'],
                                   id=value.get('catalogId') or value['id'])
            return False
        self.prime_timer=GLib.timeout_add(180,prepare)

    def play_now(self,item,context=None):
        source=self.host.source;value=track(item,source)
        if not value:return
        self.restore_queue()
        if context is not None and self.play_context(item,context):return
        self.book.compact(source,reserve=1)
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
        self.restore_queue()
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
        self.restore_queue()
        self.play_generation+=1;self.loading=False;self.watch.reset()
        self.book.replace(self.host.source,[dict(item,origin='context') for item in items])
        if self.book.queues[self.host.source]:self.start(0)
        else:self.changed()

    def preview_transition(self,items,index):
        """Audition through the real decks; keep manually queued songs."""
        if self.album_listening or not self.flow.supported or not 0<=index<len(items)-1:return False
        source=self.host.source
        before=self.play_generation
        if not self.play_context(items[index],items) or before==self.play_generation:return False
        current=self.book.indices[source];queue=self.book.queues[source]
        if current<0 or queue[current]['uri']!=items[index]['uri']:return False
        self.flow.set_enabled(True)
        target=next((i for i in range(current+1,len(queue)) if queue[i]['uri']==items[index+1]['uri']),None)
        if target is None:return False
        item=queue.pop(target);item['flow_playlist']=queue[current].get('flow_playlist','')
        queue.insert(current+1,item);self.book.save()
        self.transition_preview=(self.play_generation,queue[current]['entry'],time.monotonic()+25)
        self.changed();return True

    def poll_transition_preview(self,state):
        pending=self.transition_preview
        if not pending:return
        generation,entry,deadline=pending;item=self.book.current(self.host.source)
        if generation!=self.play_generation or not item or item['entry']!=entry:
            self.transition_preview=None;return
        if time.monotonic()>deadline:
            self.transition_preview=None
            self.error=text('Preview preparation timed out; normal playback continues.',
                            'Не удалось подготовить прослушивание вовремя — музыка продолжает играть.')
            self.changed();return
        following=self.book.upcoming(self.host.source)
        if not following:self.transition_preview=None;return
        plan=self.flow.plans.for_tracks(item,following[0][1])
        if self.loading or not matches(item,state) or not state.get('playing') or state.get('duration',0)<20:return
        if not self.flow.ready and (plan or {}).get('mode')!='cut':return
        self.transition_preview=None
        from flow_plans import duration
        seconds=duration(plan,state['duration'],following[0][1].get('duration_ms',0)/1000)
        # Leave enough real playback for the authorized MusicKit intro probe.
        lead=12 if self.host.source=='apple-music' and self.flow.beats_supported else 5
        target=max(0,state['duration']-seconds-lead)
        self.flow.cancel()
        self.host.seek_to(target)
        self.changed()

    def play_dj(self,items):
        """Start a DJ block while preserving every pending non-DJ entry."""
        source=self.host.source
        values=[dict(value,origin='dj') for value in items if track(value,source)]
        book=self.saved_book or self.book
        pending=[dict(value) for _,value in book.upcoming(source) if value.get('origin')!='dj']
        current=book.current(source);before=[dict(current)] if current else []
        room=LIMIT-len(pending)-len(before)
        if room<1 or not values:return False
        values=values[:room]
        self.restore_queue()
        self.play_generation+=1;self.loading=False;self.watch.reset()
        self.book.replace(source,before+values+pending);self.start(len(before));return True

    def extend_dj(self,items,before_pending=False):
        if self.album_listening:return 0
        source=self.host.source;existing={value['uri'] for _,value in self.book.upcoming(source)}
        values=[dict(value,origin='dj') for value in items if value.get('uri') not in existing]
        count=self.book.add(source,values)
        if count and before_pending:
            queue=self.book.queues[source];added=queue[-count:];del queue[-count:]
            insertion=next((i for i,v in self.book.upcoming(source) if v.get('origin')!='dj'),len(queue))
            queue[insertion:insertion]=added;self.book.save()
        self.changed();return count

    def clear_dj(self,source):
        book=self.saved_book or self.book
        index=book.indices[source];values=book.queues[source]
        book.queues[source]=values[:index+1]+[v for v in values[index+1:] if v.get('origin')!='dj']
        book.save();self.changed()

    def start(self,index=None):
        if not self.album_listening:self._start(index)

    def _start(self,index=None):
        self.cancel_prime()
        self.transition_preview=None
        self.flow.cancel(preserve_apple=True)
        self.awaiting_native=None
        self.previous_restart=None
        source=self.host.source
        if source=='youtube' and self.host.youtube_mode!='native':
            self.error=text('Choose the in-player YouTube source to play this queue.','Выбери встроенный YouTube в меню источников для воспроизведения очереди.')
            self.restore_queue();self.book.active=None;self.changed();return
        if index is None:
            pending=self.book.upcoming(source)
            index=self.book.indices[source] if self.error and self.book.current(source) else pending[0][0] if pending else max(0,self.book.indices[source])
        item=self.book.select(source,index)
        if not item:return
        if getattr(self.host, 'exit_apple_podcast', None):self.host.exit_apple_podcast()
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
            try:
                ack=result.result()
                if source=='apple-music' and self.host.apple_mode=='native' and isinstance(ack,dict) and 'preparing' in ack:
                    self.awaiting_native=(generation,item);self.loading=True
            except Exception as error:
                self.restore_queue()
                self.error=str(error);self.book.active=None
            self.changed();return False
        future.add_done_callback(lambda result:GLib.idle_add(complete,result))

    def step(self,direction,*,automatic=False):
        source=self.host.source;index=self.book.indices[source]
        if self.album_listening:
            if automatic and direction==1:
                if index+1<len(self.book.queues[source]):self._start(index+1)
                else:self.exit_album()
            return
        item=self.book.current(source);state=snapshot(self.host);now=time.monotonic()
        restart=self.previous_restart
        repeated=bool(item and restart and restart[0]==item['entry'] and now-restart[1]<20)
        # A pending selection still displays the outgoing song's position.
        # Never seek that song instead of stepping back through our queue.
        if direction<0 and item and not self.loading and matches(item,state) and state['position']>3 and not repeated:
            self.previous_restart=(item['entry'],now)
            self.watch.reset();self.host.seek_to(0);return
        self.previous_restart=None
        if 0<=index+direction<len(self.book.queues[source]):self.start(index+direction)
        elif direction<0:self.host.seek_to(0)
        elif source=='yandex-music' and item and item.get('playlistId'):
            self.start_yandex_wave(playlist={'id':item['playlistId']})
        else:self.book.active=None;self.pause(source);self.changed()

    def pause(self,source):
        h=self.host
        if source=='spotify' and getattr(h,'spotify_mode','desktop')=='native':
            h.spotify_web.action('transport',action='pause');return
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
        self.transition_preview=None
        self.flow.cancel()
        self.awaiting_native=None
        self.previous_restart=None
        if self.loading and pause_pending:self.pause_after.add(self.play_generation)
        self.restore_queue()
        self.play_generation+=1;self.loading=False;self.book.active=None;self.error='';self.watch.reset();self.changed()

    def source_changed(self):
        self.cancel_prime()
        self.stop();self.cancel_browse();self.source=self.host.source

    def poll(self):
        self.favorites.refresh()
        if self.closed:return False
        if self.source!=self.host.source:self.source_changed()
        source=self.host.source
        if source=='apple-music' and self.host.apple_mode=='native':
            failed=self.host.apple_web.state.get('spatial',{}).get('switchError')
            item=self.book.current(source)
            if isinstance(failed,dict) and item and self.book.active==source and failed.get('id')==item['id']:
                self.stop();self.error=text('This track could not start. Try it again; your previous song is still available.',
                    'Не удалось включить этот трек. Попробуй ещё раз — предыдущая песня остаётся доступной.');self.changed();return True
            pending=self.awaiting_native
            if pending and pending[0]==self.play_generation:
                state=snapshot(self.host);spatial=self.host.apple_web.state.get('spatial') or {}
                if spatial.get('error') and spatial.get('phase')!='playing' and not spatial.get('switching'):
                    self.stop();self.error=text('This track could not be prepared. Try it again.',
                                               'Не удалось подготовить трек. Попробуй включить его ещё раз.');self.changed();return True
                if matches(pending[1],state) and not spatial.get('switching') and spatial.get('phase')=='playing':
                    self.awaiting_native=None;self.loading=False;self.changed()
                elif time.monotonic()-self.started>25:
                    self.stop();self.error=text('Playback was not confirmed. Try this track again.','Запуск трека не подтверждён. Попробуй включить его ещё раз.');self.changed();return True
        if self.previous_restart:
            item=self.book.current(source);state=snapshot(self.host)
            if item and matches(item,state) and state['position']<=3:self.previous_restart=None
        state = snapshot(self.host)
        upcoming = self.book.upcoming(source)
        if not self.album_listening and state.get('kind') != 'episode' and not (upcoming and upcoming[0][1].get('kind') == 'episode'):
            self.flow.tick(state)
            self.poll_transition_preview(state)
        if self.flow.busy:return True
        if self.book.active==source and not self.loading:
            item=self.book.current(source);result=self.watch.observe(item,state) if item else None
            if result=='next':
                if self.album_listening:self.step(1,automatic=True)
                else:self.step(1)
            elif result=='external':self.stop()
            elif not self.watch.seen and time.monotonic()-self.started>20:
                self.stop();self.error=text('Playback was not confirmed. Try this track again.','Запуск трека не подтверждён. Попробуй включить его ещё раз.');self.changed()
        return True

    def close(self):
        self.cancel_prime();self.closed=True;self.flow.close();self.favorites.close();self.play_generation+=1;self.cancel_browse()
        GLib.source_remove(self.timer);self.youtube.close();self.listeners.clear()
        self.browse_pool.shutdown(wait=False,cancel_futures=True);self.album_pool.shutdown(wait=False,cancel_futures=True)
        self.play_pool.shutdown(wait=False,cancel_futures=True)
