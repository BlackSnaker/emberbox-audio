"""Fetch real source tracks and rank them against local taste and musical wishes."""
import hashlib,json,re,subprocess,time
from concurrent.futures import wait,FIRST_COMPLETED
from contextlib import nullcontext
from dj_lookups import Lookups
from dj_intent import artist_key,same_artist,GENRES
from discovery import LocalSpotify,cached_home
from spotify_web import client_for
from listening_queue import track
from music_library import youtube_item
from youtube_search import yt_dlp_executable,js_runtime_args

MOOD_QUERY={'any':'music','relax':'chill','focus':'focus','happy':'feel good','energy':'motivation',
            'party':'dance party','romance':'romantic','melancholy':'sad','discover':'new music'}
MOOD_MATCH={'relax':r'chill|calm|relax|soft|gentle|mellow|ambient|acoustic|lo.?fi|спокой|расслаб|мягк',
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


def style_hints(value):
    """A recording title or an artist's name is not a genre annotation."""
    collection=value.get('kind') in ('playlist','playlists','album','albums')
    genres=value.get('genres') or []
    return ' '.join([str(value.get('_context') or ''),str(value.get('description') or ''),
        str(value.get('title') or '') if collection else '',
        str(value.get('subtitle') or '') if collection else '',
        ' '.join(str(g) for g in genres[:12]) if isinstance(genres,(tuple,list)) else str(genres)]).casefold()


def genre_match(genre,info):
    return bool(re.search(GENRES.get(genre,r'(?<!\w)'+re.escape(genre)+r'(?!\w)'),info,re.I))


def context_score(value,intent,affinity):
    info=style_hints(value);score=0.
    if intent.search:
        words=set(normalized(intent.search).split())-{'music','songs','playlist','instrumental'}
        score+=min(12,len(words.intersection(normalized(info).split()))*4)
    if intent.mood in MOOD_MATCH and re.search(MOOD_MATCH[intent.mood],info):score+=8
    for genre in intent.genres:
        if genre_match(genre,info):score+=6
    for artist,weight in affinity.items():
        if weight>0 and artist and same_artist(value.get('artist',''),artist):score+=min(5,weight)
    for avoid in intent.avoid:
        if genre_match(avoid,info):score-=15
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
            feed=cached_home() if getattr(h,'spotify_mode','desktop')!='native' else None
            if not feed:
                with (client_for(h) if getattr(h,'spotify_mode','desktop')=='native' else LocalSpotify()) as client:feed=client.home(deadline=time.monotonic()+2.5)
            feed={'items':[v for shelf in feed.get('shelves',[]) for v in shelf.get('items',[])][:40]}
        elif source=='yandex-music':feed=h.yandex_web.request('browse',category='collection')
        else:return {'tracks':[],'recent':[]}
        values=[dict(v,_personal=True) for v in feed.get('tracks',[]) if isinstance(v,dict)]
        recent=feed.get('recent',[])[:30];values.extend(dict(v,_personal=True) for v in recent if isinstance(v,dict))
        collections=sorted((v for v in feed.get('items',[]) if isinstance(v,dict) and
            not any(genre_match(g,style_hints(v)) for g in intent.avoid)),
            key=lambda v:context_score(v,intent,affinity),reverse=True)
        # One personal collection per refresh; later requests reuse the tracks.
        if collections:
            collection=collections[0]
            try:
                if source=='apple-music':result=player.request('tracks',kind=collection.get('kind',''),id=collection['id'])
                elif source=='spotify':
                    with (client_for(h) if getattr(h,'spotify_mode','desktop')=='native' else LocalSpotify()) as client:result=client.tracks(collection,deadline=time.monotonic()+2.)
                else:result=h.yandex_web.request('tracks',id=collection['id'])
                context=' '.join(str(collection.get(k) or '') for k in ('title','subtitle','description'))[:1500]
                values.extend(dict(v,_personal=True,_context=context)
                    for v in (result.get('tracks') or result.get('items') or [])[:100] if isinstance(v,dict))
            except Exception:pass
        return {'tracks':values[:150],'recent':recent}

    def specific(self,source,intent):
        """Resolve a requested artist before asking for tracks, not song-title hits."""
        term=intent.query or ' '.join(intent.artists[:1]);resolved=None
        if artist_key(term)=='beatles':term='The Beatles'
        if source!='youtube' and intent.target_kind!='track':
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
        if intent.target_kind=='artist' or intent.mode=='artist':
            # Explicit artist requests may not become tracks whose TITLE
            # happens to contain that name when the artist endpoint fails.
            if source!='youtube':return {'items':[]}
        if source=='youtube':result=self.youtube(term,lambda:not self.closed)
        else:result=self.music.repository.load(source,'search',term=term[:200])
        return {'items':[dict(v,_search_query=term) for v in (result.get('items') or result.get('tracks') or []) if isinstance(v,dict)]}

    def similar(self,source,intent,deadline):
        name=intent.artists[0] if intent.artists else intent.query
        if source=='apple-music' and getattr(self.host,'apple_mode','')=='native':
            try:
                data=self.host.apple_web.request('artistSection',section='dj-similar',name=name)
                if data.get('items'):return data
            except Exception:
                if time.monotonic()>=deadline:raise
        # Other connections can use a source-curated "inspired by" collection.
        # Plain name hits and unrelated personal shelves are not similarity.
        return self.themed(source,name+' inspired',intent,deadline)

    def themed(self,source,query,intent,deadline=None):
        """Try a concise fallback only when the detailed wish has no matches."""
        deadline=deadline or time.monotonic()+self.BUDGET
        direction=MOOD_QUERY.get(intent.mood,'') if intent.mood!='any' else ''
        simpler=' '.join((*intent.genres[:1],direction)).strip()
        if not simpler and intent.search:simpler=' '.join(intent.search.split()[:2])
        if simpler and intent.instrumental is True and 'instrumental' not in simpler:simpler+=' instrumental'
        queries=list(dict.fromkeys(q for q in (query,simpler) if q))
        result={}
        for term in queries:
            if self.closed:raise InterruptedError('closed')
            if time.monotonic()>=deadline:break
            found=self._themed(source,term,intent)
            if found.get('items') or found.get('tracks'):result=found
            if rank(found.get('tracks') or found.get('items') or [],source,intent,{}, {},limit=1):return found
        return result

    def _themed(self,source,query,intent):
        """A mood is a collection of songs, not a literal song-title request."""
        h=self.host
        apple=source=='apple-music' and getattr(h,'apple_mode','')=='native'
        player=h.apple_web if apple else None
        if apple:result=player.request('search',term=query,types='playlists')
        else:result=self.music.repository.load(source,'search',term=query[:200])
        items=result.get('items') or []
        collections=[v for v in items if isinstance(v,dict) and v.get('kind') in ('playlists','playlist','album','albums')
            and (not intent.genres or any(genre_match(g,style_hints(v)) for g in intent.genres))
            and not any(genre_match(g,style_hints(v)) for g in intent.avoid)]
        collections.sort(key=lambda v:context_score(v,intent,{}),reverse=True)
        tracks=[]
        for collection in collections[:2]:
            if self.closed:raise InterruptedError('closed')
            try:
                data=player.request('tracks',kind=collection['kind'],id=collection['id']) if apple else self.music.repository.load(source,'tracks',collection=collection)
                context=' '.join(str(collection.get(k,'') or '') for k in ('title','subtitle','description'))[:1500]
                mood=intent.mood if intent.mood in MOOD_MATCH and re.search(MOOD_MATCH[intent.mood],context,re.I) else ''
                genres=tuple(g for g in intent.genres if genre_match(g,context))
                search=intent.search if context_score(collection,intent,{})>0 else ''
                related=''
                if intent.mode=='similar' and intent.artists:
                    anchor=intent.artists[0]
                    if (normalized(anchor) in normalized(context) and
                            re.search(r'inspired|influenc|similar|похож|в духе',context,re.I)):related=anchor
                tracks.extend(dict(v,_context=context,_dj_mood=mood,_dj_genres=genres,_dj_search=search,_dj_related=related)
                    for v in (data.get('tracks') or data.get('items') or [])[:60] if isinstance(v,dict))
            except Exception:continue
        if tracks:return {'items':tracks[:120]}
        # Existing transports without collection search retain their ordinary
        # source search. Never mark title-only hits as verified mood metadata.
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
            if intent.mode=='similar':return self.similar(source,intent,deadline)
            if source=='youtube':return self.youtube(query,lambda:not self.closed)
            if intent.mode=='theme' or intent.search or not requested and (intent.mood in MOOD_MATCH or intent.mood=='discover' or intent.genres):
                return self.themed(source,query,intent,deadline)
            return self.music.repository.load(source,'search',term=query[:200])
        # Search takes priority over background enrichment on UI-backed sources.
        specific=intent.mode in ('lookup','artist')
        key=(source,'specific' if specific else 'search',query,intent.mode,intent.target_kind,intent.mood,intent.genres,intent.avoid,intent.instrumental)
        search_future=self.cache.get(key,lambda:self.guarded(source,lambda:self.specific(source,intent) if specific else search()),ttl=180)
        taste=tuple((name,round(weight,1)) for name,weight in sorted(affinity.items(),key=lambda p:p[1],reverse=True)[:12])
        personal_future=None if specific or intent.mode=='similar' else self.cache.get((source,'personal',intent.mood,intent.genres,intent.search,intent.avoid,intent.instrumental,taste),lambda:self.guarded(source,lambda:self.personal(source,intent,affinity)))
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
        info=hints(value);style=style_hints(value);artist=normalized(valid['artist'])
        if source=='youtube':style+=' '+str(valid.get('title','')).casefold()
        if requested and not same_artist(valid['artist'],requested):continue
        if intent.mode=='lookup' and not requested:
            terms=set(normalized(intent.query).split());actual=set((normalized(valid['title'])+' '+artist).split())
            if not terms or len(terms&actual)/len(terms)<.75:continue
        if intent.mode=='similar' and not any(artist_key(value.get('_dj_related',''))==artist_key(a) for a in intent.artists):continue
        mood_match=intent.mood in MOOD_MATCH and (value.get('_dj_mood')==intent.mood or re.search(MOOD_MATCH[intent.mood],style))
        if not direct and intent.genres and not any(genre_match(g,style) for g in intent.genres):continue
        # Favourite tracks from a cached personal feed cannot overrule a new
        # explicit mood. Collection context remains grounded in source metadata.
        if not direct and intent.mood in MOOD_MATCH and not mood_match:continue
        if not direct and intent.search and not (context_score(value,intent,{})>0 or
                source=='youtube' and set(normalized(intent.search).split())&set(normalized(style).split())):continue
        preference=profile.get(valid['uri']) or by_song.get((artist,normalized(valid['title'])),{})
        if int(preference.get('vote',0))<0:continue
        if any(genre_match(word,style) for word in intent.avoid):continue
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
        if not direct and intent.mood=='discover' and (preference or affinity.get(valid['artist'].casefold(),0)>0):score-=12
        if preference and now-float(preference.get('last',0))<7200:score-=9*(1-intent.familiarity*.6)
        if intent.mood in ('relax','focus') and re.search(r'metal|hardcore|heavy|workout|speed|дэт|тяжел',info):score-=18
        if artist and intent.artists and any(normalized(a) in artist or artist in normalized(a) for a in intent.artists):score+=14
        jitter=int(hashlib.sha256((seed+valid['uri']).encode()).hexdigest()[:8],16)/0xffffffff
        score+=jitter*(3 if intent.mood=='discover' else 1)
        reason='requested-artist' if requested else 'requested-track' if intent.mode=='lookup' else 'similar' if intent.mode=='similar' else 'personal' if value.get('_personal') else 'artist' if affinity.get(valid['artist'].casefold(),0)>0 else 'catalogue'
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
