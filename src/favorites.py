"""Private cross-source favourites; account writes never run on GTK."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
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
        self.path=Path(path);self.items={}
        try:
            if self.path.stat().st_size>10_000_000:return
            data=json.loads(self.path.read_text())
            for raw in data.get('tracks',[])[:LIMIT]:
                value=track(raw,raw.get('source'))
                if value:self.items[value['uri']]=dict(value,sync=raw.get('sync') if raw.get('sync') in ('synced','requested') else 'local')
        except (OSError,ValueError,TypeError,AttributeError):pass

    def set(self,item,saved,sync='local'):
        values=dict(self.items)
        if saved:
            if item['uri'] not in values and len(values)>=LIMIT:raise ValueError('FAVORITES_FULL')
            values[item['uri']]=dict(item,sync=sync)
        else:values.pop(item['uri'],None)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.next.json')
        # Metadata only: no signed stream URLs, tokens, cookies or audio files.
        raw=json.dumps({'version':1,'tracks':list(values.values())},ensure_ascii=False)
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as handle:handle.write(raw)
        temporary.chmod(0o600);temporary.replace(self.path);self.items=values


class Favorites:
    def __init__(self,music,path=None):
        self.music=music;self.book=FavoriteBook(path or CONFIG_DIR/'favorites.json')
        self.items=dict(self.book.items);self.pending=set();self.listeners=[];self.closed=False;self.revision=0
        self.messages={};self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='ember-favorites')

    def subscribe(self,callback):
        self.listeners.append(callback)
        return lambda:self.listeners.remove(callback) if callback in self.listeners else None

    def changed(self):
        if not self.closed:
            for callback in tuple(self.listeners):callback()

    def refresh(self):self.changed()
    def current(self):return current_track(self.music.host)
    def saved(self,item):return bool(item and item['uri'] in self.items)

    def client(self,source):
        host=self.music.host
        if source=='apple-music' and getattr(host,'apple_mode','native')=='native':return getattr(host,'apple_web',None)
        if source=='spotify' and getattr(host,'spotify_mode','native')=='native':return getattr(host,'spotify_web',None)
        if source=='yandex-music':return getattr(host,'yandex_web',None)
        return None

    def toggle(self,item):self.set(item,not self.saved(item))

    def set(self,item,saved):
        value=track(item,item.get('source')) if item else None
        if self.closed or not value or value['uri'] in self.pending or len(self.pending)>=16:return
        from gi.repository import GLib
        uri=value['uri'];client=self.client(value['source'])
        self.pending.add(uri);self.messages[uri]=text('Saving in Ember…','Сохраняю в Ember…');self.changed()
        def publish(items,message,finished=False):
            if self.closed:return False
            if tuple(self.items)!=tuple(items):self.revision+=1
            self.items=items;self.messages[uri]=message
            if finished:self.pending.discard(uri)
            self.changed();return False
        def work():
            try:self.book.set(value,saved)
            except Exception:
                GLib.idle_add(publish,dict(self.book.items),text('Could not save favourites on this device.','Не удалось сохранить избранное на этом устройстве.'),True);return
            GLib.idle_add(publish,dict(self.book.items),text('Saved in Ember · syncing account…','Сохранено в Ember · синхронизация…') if saved else text('Removed from Ember · syncing account…','Удалено из Ember · синхронизация…'))
            confirmed=False
            try:
                if not client or not client.connected:raise RuntimeError('LOCAL_ONLY')
                result=client.request('favorite',id=value['id'],kind=value['kind'],uri=uri,value=bool(saved))
                confirmed=result.get('confirmed') is True and result.get('favorite') is bool(saved)
                if not confirmed:raise RuntimeError('UNCONFIRMED')
                if saved:self.book.set(value,True,'synced')
            except Exception:pass
            name=NAMES[value['source']]
            message=(text('Saved in Ember and ','Сохранено в Ember и ')+name if saved else text('Removed from Ember and ','Удалено из Ember и ')+name) if confirmed else (
                text('Saved in Ember · account not confirmed','В Ember сохранено · аккаунт не подтвердил') if saved else text('Removed from Ember · account not confirmed','Из Ember удалено · аккаунт не подтвердил'))
            if not client:message=text('Saved in Ember · no account sync in this mode','Сохранено в Ember · в этом режиме без синхронизации') if saved else text('Removed from Ember','Удалено из Ember')
            GLib.idle_add(publish,dict(self.book.items),message,True)
        self.pool.submit(work)

    def play(self,item,context=None):
        host=self.music.host
        if host.source!=item['source']:host.select_source(item['source'])
        self.music.play_now(item,context=context)

    def close(self):
        self.closed=True;self.listeners.clear();self.pool.shutdown(wait=False,cancel_futures=True)
