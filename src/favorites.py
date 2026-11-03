"""Private cross-source favourites; account writes never run on GTK."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from listening_queue import track
from paths import CONFIG_DIR
from source_picker import text

NAMES={'spotify':'Spotify','apple-music':'Apple Music','yandex-music':'Яндекс Музыка','youtube':'YouTube'}
LIMIT=5000


def current_track(host):
    from music_library import snapshot
    state=snapshot(host);source=host.source
    if not state.get('valid') or not state.get('title'):return None
    ident=state.get('catalogId') or state.get('id','');uri=state.get('uri','')
    if source=='spotify':
        if uri.startswith('https://open.spotify.com/track/'):ident=urlparse(uri).path.split('/')[-1]
        uri=uri if uri.startswith('spotify:track:') else 'spotify:track:'+ident
    elif source=='apple-music':
        # A browser MPRIS object path is not an Apple catalogue identifier.
        if not str(ident).isdecimal() and not str(ident).startswith('i.'):return None
        kind='library-songs' if str(ident).startswith('i.') else 'songs'
        uri='apple:'+kind+':'+str(ident)
    elif source=='youtube':
        if uri.startswith('https://'):
            parsed=urlparse(uri)
            if parsed.hostname in ('www.youtube.com','youtube.com','music.youtube.com'):ident=parse_qs(parsed.query).get('v',[''])[0]
            elif parsed.hostname=='youtu.be':ident=parsed.path.strip('/')
        uri='youtube:'+str(ident)
    elif source=='yandex-music':uri='yandex:track:'+str(ident)
    return track(dict(state,uri=uri,album=host.album.get_text(),image=host.art_url or '',
                      duration_ms=round(state.get('duration',0)*1000)),source)


class FavoriteBook:
    def __init__(self,path):
        self.path=Path(path);self.items={};self.operations={}
        try:
            if self.path.stat().st_size>10_000_000:return
            data=json.loads(self.path.read_text())
            for raw in data.get('tracks',[])[:LIMIT]:
                value=track(raw,raw.get('source'))
                if value:self.items[value['uri']]=dict(value,sync=raw.get('sync') if raw.get('sync') in ('synced','requested') else 'local')
            for raw in data.get('operations',[])[:LIMIT]:
                value=track(raw.get('track'),(raw.get('track') or {}).get('source'))
                if value and value['source']!='youtube' and type(raw.get('saved')) is bool:
                    self.operations[value['uri']]={'track':value,'saved':raw['saved']}
            # Older releases kept failed account writes only as local tracks.
            # Recover those explicit saves without touching confirmed records.
            for uri,value in self.items.items():
                if value['source']!='youtube' and value['sync']!='synced' and uri not in self.operations:
                    self.operations[uri]={'track':value,'saved':True}
        except (OSError,ValueError,TypeError,AttributeError):pass

    def write(self,values,operations):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.next.json')
        # Metadata and desired actions only: never account credentials or audio.
        raw=json.dumps({'version':2,'tracks':list(values.values()),'operations':list(operations.values())},ensure_ascii=False)
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as handle:handle.write(raw)
        temporary.chmod(0o600);temporary.replace(self.path)
        self.items=values;self.operations=operations

    def set(self,item,saved,sync='local',queue=False):
        values=dict(self.items);operations=dict(self.operations);uri=item['uri']
        if saved:
            if uri not in values and len(values)>=LIMIT:raise ValueError('FAVORITES_FULL')
            values[uri]=dict(item,sync=sync)
        else:values.pop(uri,None)
        if queue and item['source']!='youtube':
            if uri not in operations and len(operations)>=LIMIT:raise ValueError('FAVORITES_FULL')
            operations[uri]={'track':item,'saved':bool(saved)}
        else:operations.pop(uri,None)
        self.write(values,operations)

    def confirm(self,item,saved):
        # Only a verified account response can retire the persistent operation.
        self.set(item,saved,'synced')


class Favorites:
    def __init__(self,music,path=None):
        self.music=music;self.book=FavoriteBook(path or CONFIG_DIR/'favorites.json')
        self.items=dict(self.book.items);self.pending=set();self.listeners=[];self.closed=False;self.revision=0
        self.operations=dict(self.book.operations);self.retry_at={};self.attempts={};self.account_states={}
        self.messages={};self.feedback={};self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-favorites')

    def subscribe(self,callback):
        self.listeners.append(callback)
        return lambda:self.listeners.remove(callback) if callback in self.listeners else None

    def changed(self):
        if not self.closed:
            for callback in tuple(self.listeners):callback()

    def refresh(self):
        if self.closed:return
        now=time.monotonic()
        # Polling is already driven by the player. No extra timer, network
        # thread or process is created for an idle/empty favourites queue.
        for uri,operation in tuple(self.operations.items()):
            if uri in self.pending or len(self.pending)>=16:continue
            value=operation['track'];client=self.client(value['source'])
            if not client:continue
            state=getattr(client,'state',{})
            ready=bool(client.connected and state.get('ready',True) and state.get('authorized',True)
                       and not getattr(client,'upgrading',False))
            previous=self.account_states.get(value['source'])
            self.account_states[value['source']]=ready
            if not ready:continue
            # A reconnect or newly authorized account bypasses an old backoff.
            if previous is False:self.retry_at={k:v for k,v in self.retry_at.items() if self.operations.get(k,{}).get('track',{}).get('source')!=value['source']}
            if now<self.retry_at.get(uri,0):continue
            # DOM-only adapters must not navigate or like a replacement song.
            # Retry their exact song when it is current again.
            if value['source'] in ('spotify','yandex-music') and state.get('id') and str(state['id'])!=value['id']:continue
            self._submit(value,operation['saved'],client,local=False)
        self.changed()
    def current(self):return current_track(self.music.host)
    def saved(self,item):return bool(item and item['uri'] in self.items)

    def client(self,source):
        host=self.music.host
        if source=='apple-music' and getattr(host,'apple_mode','native')=='native':return getattr(host,'apple_web',None)
        if source=='spotify' and getattr(host,'spotify_mode','native')=='native':return getattr(host,'spotify_web',None)
        if source=='yandex-music':return getattr(host,'yandex_web',None)
        return None

    def toggle(self,item):self.set(item,not self.saved(item))

    def retry(self,item):
        operation=self.operations.get(item['uri']) if item else None
        if operation:self.set(operation['track'],operation['saved'])

    def set(self,item,saved):
        value=track(item,item.get('source')) if item else None
        if self.closed or not value or value['uri'] in self.pending or len(self.pending)>=16:return
        self.retry_at.pop(value['uri'],None);self.attempts.pop(value['uri'],None)
        self._submit(value,bool(saved),self.client(value['source']),local=True)

    def _submit(self,value,saved,client,local):
        from gi.repository import GLib
        uri=value['uri'];self.pending.add(uri)
        if local:
            self.messages[uri]=text('Saving in Ember…','Сохраняю в Ember…')
            self.feedback[uri]={'phase':'saving','saved':saved};self.changed()
        def publish(items,operations,message,finished=False,phase='local'):
            if self.closed:return False
            if tuple(self.items)!=tuple(items):self.revision+=1
            self.items=items;self.operations=operations;self.messages[uri]=message
            self.feedback[uri]={'phase':phase,'saved':saved}
            if finished:
                self.pending.discard(uri)
                if phase=='synced':self.attempts.pop(uri,None);self.retry_at.pop(uri,None)
                else:
                    attempt=min(6,self.attempts.get(uri,0)+1);self.attempts[uri]=attempt
                    self.retry_at[uri]=time.monotonic()+min(300,5*2**(attempt-1))
            self.changed();return False
        def emit(message,finished=False,phase='local'):
            GLib.idle_add(publish,dict(self.book.items),dict(self.book.operations),message,finished,phase)
        def work():
            if self.closed:return
            if local:
                try:self.book.set(value,saved,queue=True)
                except Exception:
                    emit(text('Could not save favourites on this device.','Не удалось сохранить избранное на этом устройстве.'),True,'error');return
                emit(text('Saved in Ember · syncing account…','Сохранено в Ember · синхронизация…') if saved else text('Removed from Ember · syncing account…','Удалено из Ember · синхронизация…'))
            confirmed=False
            try:
                if not client or not client.connected:raise RuntimeError('LOCAL_ONLY')
                result=client.request('favorite',id=value['id'],kind=value['kind'],uri=uri,value=saved)
                confirmed=result.get('confirmed') is True and result.get('favorite') is saved
                if not confirmed:raise RuntimeError('UNCONFIRMED')
                self.book.confirm(value,saved)
            except Exception:confirmed=False
            name=NAMES[value['source']]
            message=(text('Saved in Ember and ','Сохранено в Ember и ')+name if saved else text('Removed from Ember and ','Удалено из Ember и ')+name) if confirmed else (
                text('Saved in Ember · account sync queued','В Ember сохранено · синхронизация в очереди') if saved else text('Removed from Ember · account sync queued','Из Ember удалено · синхронизация в очереди'))
            if not client:message=text('Saved in Ember · no account sync in this mode','Сохранено в Ember · в этом режиме без синхронизации') if saved else text('Removed from Ember','Удалено из Ember')
            emit(message,True,'synced' if confirmed else 'unconfirmed' if client else 'local-only')
        self.pool.submit(work)

    def play(self,item,context=None):
        host=self.music.host
        if host.source!=item['source']:host.select_source(item['source'])
        self.music.play_now(item,context=context)

    def close(self):
        self.closed=True;self.listeners.clear();self.pool.shutdown(wait=False,cancel_futures=True)
