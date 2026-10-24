"""Fetch real source tracks and rank them against local taste and musical wishes."""
import hashlib,json,re,subprocess,time
from concurrent.futures import wait,FIRST_COMPLETED
from contextlib import nullcontext
from dj_lookups import Lookups
from dj_intent import artist_key,same_artist
from discovery import LocalSpotify,cached_home
from listening_queue import track
from music_library import youtube_item
from youtube_search import yt_dlp_executable,js_runtime_args

MOOD_QUERY={'any':'music','relax':'chill','focus':'focus','happy':'feel good','energy':'motivation',
            'party':'dance party','romance':'romantic','melancholy':'sad','discover':'new music'}
MOOD_MATCH={'relax':r'chill|calm|relax|soft|ambient|acoustic|lo.?fi|спокой|расслаб',
    'focus':r'focus|study|ambient|instrumental|piano|lo.?fi|концентр|фокус|работ',
    'happy':r'happy|happiness|cheerful|upbeat|feel.good|positiv|uplift|весел|радост|позитив',
    'energy':r'energy|energetic|workout|power|motivation|бодр|энерг|трениров',
    'party':r'dance|party|funk|disco|house|dance.?pop|танц|вечерин',
    'romance':r'romantic|romance|love songs|романт|любов|свидани',
    'melancholy':r'melanchol|sad|dream.?pop|slow|груст|меланхол'}
INSTRUMENTAL=r'instrumental|no vocals|without vocals|solo piano|без (?:слов|вокала)|инструменталь'


def normalized(value):return re.sub(r'\W+',' ',str(value).casefold()).strip()


def hints(value):
    genres=value.get('genres') or []
    return ' '.join([str(value.get('title','')),str(value.get('subtitle','')),str(value.get('_context','')),
                     ' '.join(str(g) for g in genres[:8]) if isinstance(genres,list) else '']).casefold()


def context_score(value,intent,affinity):
    info=hints(value);score=0.
    if intent.search:
        words=set(normalized(intent.search).split())-{'music','songs','playlist','instrumental'}
        score+=min(12,len(words.intersection(normalized(info).split()))*4)
    if intent.mood in MOOD_MATCH and re.search(MOOD_MATCH[intent.mood],info):score+=8
    for genre in intent.genres:
        if normalized(genre) in normalized(info):score+=6
    for artist,weight in affinity.items():
        if weight>0 and artist and artist in info:score+=min(5,weight)
    for avoid in intent.avoid:
        if normalized(avoid) in normalized(info):score-=15
    return score


class DJCatalog:
    BUDGET=5.

    def __init__(self,music):
        self.music=music;self.host=music.host;self.cache=Lookups();self.closed=False

    def guarded(self,source,call):
        # Spotify's UI-backed adapter must not navigate Home and Search together.
        lock=getattr(self.music.repository,'locks',{}).get(source) if source=='spotify' else None
        with lock if lock else nullcontext():
            if self.closed:raise InterruptedError('closed')
            return call()

    def personal(self,source,intent,affinity):
        h=self.host
        player=(h.apple_web if h.apple_mode=='native' else h.apple) if source=='apple-music' else None
        if source=='apple-music':feed=player.request('browse',category='dj')
        elif source=='spotify':
            feed=cached_home()
            if not feed:
                with LocalSpotify() as client:feed=client.home(deadline=time.monotonic()+2.5)
            feed={'items':[v for shelf in feed.get('shelves',[]) for v in shelf.get('items',[])][:40]}
        elif source=='yandex-music':feed=h.yandex_web.request('browse',category='collection')
        else:return {'tracks':[],'recent':[]}
        values=[dict(v,_personal=True) for v in feed.get('tracks',[]) if isinstance(v,dict)]
        recent=feed.get('recent',[])[:30];values.extend(dict(v,_personal=True) for v in recent if isinstance(v,dict))
        collections=sorted((v for v in feed.get('items',[]) if isinstance(v,dict)),
            key=lambda v:context_score(v,intent,affinity),reverse=True)
        # One personal collection per refresh; later requests reuse the tracks.
        if collections:
            collection=collections[0]
            try:
                if source=='apple-music':result=player.request('tracks',kind=collection.get('kind',''),id=collection['id'])
                elif source=='spotify':
                    with LocalSpotify() as client:result=client.tracks(collection,deadline=time.monotonic()+2.)
                else:result=h.yandex_web.request('tracks',id=collection['id'])
                values.extend(dict(v,_personal=True,_context=collection.get('title','')[:200])
                    for v in (result.get('tracks') or result.get('items') or [])[:100] if isinstance(v,dict))
            except Exception:pass
        return {'tracks':values[:150],'recent':recent}

    def specific(self,source,intent):
        """Resolve a requested artist before asking for tracks, not song-title hits."""
        term=intent.query or ' '.join(intent.artists[:1]);resolved=None
        if artist_key(term)=='beatles':term='The Beatles'
        if source!='youtube':
            try:
                result=self.music.repository.load(source,'artist',collection={'name':term})
                choices=([result['artist']] if result.get('artist') else result.get('choices') or [])
                exact=[v for v in choices if artist_key(v.get('name',''))==artist_key(term)]
                if len(exact)==1:
                    resolved=exact[0]
                    if source=='apple-music':
                        data=self.music.repository.load(source,'artist-section',collection={'id':resolved['id'],'section':'top-songs'})
                        songs=data.get('items',[])
                    else:
                        data=self.music.repository.load(source,'artist',collection={'id':resolved['id']})
                        songs=[v for section in data.get('sections',[]) if section.get('id')=='top-songs' for v in section.get('items',[])]
                    return {'items':[dict(v,_requested_artist=resolved['name'],_requested_artist_id=resolved['id'])
                        for v in songs if isinstance(v,dict) and same_artist(v.get('artist',''),resolved['name'])],
                        'artist':resolved}
            except Exception:
                # A failed exact-artist fetch must never silently switch to a
                # different act or a personal radio mix.
                if resolved:return {'items':[],'artist':resolved}
        if source=='youtube':result=self.youtube(term,lambda:not self.closed)
        else:result=self.music.repository.load(source,'search',term=term[:200])
        return {'items':[dict(v,_search_query=term) for v in (result.get('items') or result.get('tracks') or []) if isinstance(v,dict)]}

    def themed(self,source,query,intent):
        """A mood is a collection of songs, not a literal song-title request."""
        h=self.host
        apple=source=='apple-music' and getattr(h,'apple_mode','')=='native'
        player=h.apple_web if apple else None
        if apple:result=player.request('search',term=query,types='playlists')
        else:result=self.music.repository.load(source,'search',term=query[:200])
        items=result.get('items') or []
        collections=[v for v in items if isinstance(v,dict) and v.get('kind') in ('playlists','playlist','album','albums')]
        collections.sort(key=lambda v:context_score(v,intent,{}),reverse=True)
        tracks=[]
        for collection in collections[:2]:
            if self.closed:raise InterruptedError('closed')
            try:
                data=player.request('tracks',kind=collection['kind'],id=collection['id']) if apple else self.music.repository.load(source,'tracks',collection=collection)
                context=' '.join(str(collection.get(k,'') or '') for k in ('title','subtitle','description'))[:1500]
                tracks.extend(dict(v,_context=context,_dj_mood=intent.mood,_dj_genres=intent.genres,_dj_search=intent.search)
                    for v in (data.get('tracks') or data.get('items') or [])[:60] if isinstance(v,dict))
            except Exception:continue
        if tracks:return {'items':tracks[:120]}
        # Existing transports without collection search retain their ordinary
        # source search. Never mark title-only hits as verified mood metadata.
        if apple:result=player.request('search',term=query)
        return result

    def collect(self,source,intent,affinity,alive=lambda:True,progress=lambda *_:None):
        if not alive():raise InterruptedError('cancelled')
        started=time.monotonic();deadline=started+self.BUDGET;candidates=[];recent=[];warnings=[]
        requested=intent.query or ' '.join(intent.artists[:1])
        anchor=max(affinity,key=affinity.get) if affinity else ''
        query=requested or intent.search or ' '.join(intent.genres[:1]) or (anchor if intent.mood=='any' and affinity.get(anchor,0)>0 else MOOD_QUERY[intent.mood])
        if intent.instrumental is True and 'instrumental' not in query.casefold():query+=' instrumental'
        elif not requested and not intent.search and intent.genres and intent.mood in MOOD_MATCH:
            query+=' '+MOOD_QUERY[intent.mood]
        def search():
            if source=='youtube':return self.youtube(query,lambda:not self.closed)
            if intent.mode=='theme' or intent.search or not requested and (intent.mood in MOOD_MATCH or intent.mood=='discover' or intent.genres):
                return self.themed(source,query,intent)
            return self.music.repository.load(source,'search',term=query[:200])
        # Search takes priority over background enrichment on UI-backed sources.
        specific=intent.mode in ('lookup','artist')
        key=(source,'specific' if specific else 'search',query,intent.mood,intent.genres,intent.instrumental)
        search_future=self.cache.get(key,lambda:self.guarded(source,lambda:self.specific(source,intent) if specific else search()),ttl=180)
        personal_future=None if specific else self.cache.get((source,'personal',intent.mood,intent.genres,intent.instrumental),lambda:self.guarded(source,lambda:self.personal(source,intent,affinity)))
        pending={f for f in (search_future,personal_future) if f is not None};search_done=False;personal_done=False;first=None
        progress('catalogue')
        while pending and time.monotonic()<deadline:
            if not alive():raise InterruptedError('cancelled')
            done,_=wait(pending,timeout=min(.05,max(0,deadline-time.monotonic())),return_when=FIRST_COMPLETED)
            for future in done:
                pending.remove(future)
                if future is search_future:search_done=True
                if future is personal_future:personal_done=True
                try:data=future.result() or {}
                except Exception:warnings.append('source-unavailable');continue
                for value in (data.get('tracks') or data.get('items') or [])[:150]:
                    if isinstance(value,dict) and track(value,source):candidates.append(value)
                if future is personal_future:recent=data.get('recent',[])[:30]
            if candidates and first is None:first=time.monotonic()
            # Give a fast personal feed a short grace period, then play the real
            # search results; late enrichment is cached for the next wish/refill.
            if candidates and search_done and time.monotonic()-first>=.2:break
            if candidates and personal_done and not requested and not intent.search and not intent.genres and len(candidates)>=8 and intent.mood=='any':break
        if pending:warnings.append('pending')
        if not alive():raise InterruptedError('cancelled')
        return candidates,recent,warnings

    def close(self):self.closed=True;self.cache.close()

    @staticmethod
    def youtube(query,alive):
        process=subprocess.Popen([yt_dlp_executable(),'--ignore-config','--flat-playlist','--dump-single-json',
            '--no-warnings','--socket-timeout','8','--retries','0','--extractor-retries','0',*js_runtime_args(),
            '--','ytsearch10:'+query[:200]],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        try:
            deadline=time.monotonic()+12
            while True:
                if not alive():raise InterruptedError('cancelled')
                try:stdout,_=process.communicate(timeout=.15);break
                except subprocess.TimeoutExpired:
                    if time.monotonic()>deadline:raise TimeoutError('YouTube search timed out')
            if process.returncode:raise RuntimeError('YouTube search unavailable')
            if len(stdout)>3_000_000:raise ValueError('YouTube response too large')
            values=[]
            for item in json.loads(stdout).get('entries',[])[:25]:
                if not isinstance(item,dict) or not re.fullmatch(r'[\w-]{11}',str(item.get('id',''))):continue
                duration=float(item.get('duration') or 0)
                if item.get('live_status')=='is_live' or not 60<=duration<=900:continue
                values.append(youtube_item(dict(item,channel=item.get('channel') or item.get('uploader') or '')))
            return {'items':values}
        finally:
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=1)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=1)


def rank(values,source,intent,profile,affinity,exclude=(),limit=14,seed=''):
    seen=set(exclude);pool=[];now=time.time()
    resolved=next((v.get('_requested_artist') for v in values if v.get('_requested_artist')),None)
    requested=resolved or (intent.artists[0] if intent.mode=='artist' and intent.artists else '')
    direct=bool(requested or intent.mode=='lookup')
    by_song={(normalized(v.get('artist','')),normalized(v.get('title',''))):v for v in profile.values()}
    for value in values:
        valid=track(value,source)
        if not valid or valid['uri'] in seen:continue
        info=hints(value);artist=normalized(valid['artist'])
        if requested and not same_artist(valid['artist'],requested):continue
        if intent.mode=='lookup' and not requested:
            terms=set(normalized(intent.query).split());actual=set((normalized(valid['title'])+' '+artist).split())
            if not terms or len(terms&actual)/len(terms)<.75:continue
        mood_match=intent.mood in MOOD_MATCH and (value.get('_dj_mood')==intent.mood or re.search(MOOD_MATCH[intent.mood],info))
        # Favourite tracks from a cached personal feed cannot overrule a new
        # explicit mood. Collection context remains grounded in source metadata.
        if not direct and value.get('_personal') and intent.mood in MOOD_MATCH and not mood_match:continue
        if not direct and intent.search and value.get('_personal') and context_score(value,intent,{})<=0:continue
        preference=profile.get(valid['uri']) or by_song.get((artist,normalized(valid['title'])),{})
        if int(preference.get('vote',0))<0:continue
        if any(normalized(word) in normalized(info) for word in intent.avoid):continue
        if intent.instrumental is True and not re.search(INSTRUMENTAL,info):continue
        if source=='youtube' and re.search(r'full album|reaction|podcast|interview|час(?:а|ов)?|\b1 ?hour',info):continue
        score=context_score(value,intent,{})
        if intent.search and value.get('_dj_search')==intent.search:score+=18
        if value.get('_dj_mood')==intent.mood and intent.mood in MOOD_MATCH:score+=18
        if value.get('_dj_genres') and set(value['_dj_genres'])&set(intent.genres):score+=10
        if intent.query and not intent.artists:
            terms=set(normalized(intent.query).split());title=normalized(valid['title']);description=title+' '+artist
            overlap=len(terms.intersection(description.split()))/max(1,len(terms))
            score+=overlap*24+(16 if normalized(intent.query) in title else 0)
        score+=min(9,affinity.get(valid['artist'].casefold(),0))*(.4+intent.familiarity)
        score+=int(preference.get('vote',0))*7+min(3,int(preference.get('listen',0)))*intent.familiarity
        if value.get('_personal'):score+=2+intent.familiarity*3
        if preference and now-float(preference.get('last',0))<7200:score-=9*(1-intent.familiarity*.6)
        if intent.mood in ('relax','focus') and re.search(r'metal|hardcore|heavy|workout|speed|дэт|тяжел',info):score-=18
        if artist and intent.artists and any(normalized(a) in artist or artist in normalized(a) for a in intent.artists):score+=14
        jitter=int(hashlib.sha256((seed+valid['uri']).encode()).hexdigest()[:8],16)/0xffffffff
        score+=jitter*(3 if intent.mood=='discover' else 1)
        reason='requested-artist' if requested else 'requested-track' if intent.mode=='lookup' else 'personal' if value.get('_personal') else 'artist' if affinity.get(valid['artist'].casefold(),0)>0 else 'catalogue'
        if intent.instrumental is True:reason='instrumental'
        elif mood_match:reason='mood'
        pool.append((score,dict(value,_reason=reason)))
    pool.sort(key=lambda pair:pair[0],reverse=True)
    selected=[];artists={};titles=set()
    for _,value in pool:
        if value['uri'] in seen:continue
        artist=normalized(value.get('artist',''));title=normalized(value.get('title',''))
        title=re.sub(r'\b(?:remaster(?:ed)?|\d{4})\b','',title).strip()
        if (artist,title) in titles or artists.get(artist,0)>=(limit if direct else 4 if intent.artists else 2):continue
        artists[artist]=artists.get(artist,0)+1;titles.add((artist,title));seen.add(value['uri']);selected.append(value)
        if len(selected)>=limit:break
    return selected
