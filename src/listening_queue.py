"""A private, source-specific listening queue; restoring it never starts music."""
import json
import re
import uuid
from pathlib import Path

SOURCES=('spotify','apple-music','youtube','yandex-music')
LIMIT=200
HISTORY=20


def track(value,source):
    if source not in SOURCES or not isinstance(value,dict):return None
    result={key:str(value.get(key) or '')[:500] for key in ('id','uri','title','artist','album','image','kind','url')}
    uri=result['uri']
    valid=(re.fullmatch(r'spotify:track:[A-Za-z0-9]{1,64}',uri) if source=='spotify' else
           re.fullmatch(r'apple:(library-songs|songs):[\w.-]{1,200}',uri) if source=='apple-music' else
           re.fullmatch(r'youtube:[A-Za-z0-9_-]{11}',uri) if source=='youtube' else
           re.fullmatch(r'yandex:track:\d{1,20}',uri))
    if not valid or not result['title'] or value.get('playable') is False:return None
    result['source']=source;result['id']=uri.rsplit(':',1)[-1]
    result['origin']=value.get('origin') if value.get('origin') in ('context','dj') else 'manual'
    if source=='apple-music':result['kind']=uri.split(':')[1]
    if source=='youtube':result['url']='https://www.youtube.com/watch?v='+result['id']
    try:result['duration_ms']=max(0,min(86400000,int(value.get('duration_ms') or 0)))
    except (ValueError,TypeError,OverflowError):result['duration_ms']=0
    result['entry']=str(value.get('entry') or uuid.uuid4().hex)[:64]
    return result


def matches(item,snapshot):
    if snapshot.get('uri')==item['uri']:return True
    if snapshot.get('id')==item['id']:return True
    if snapshot.get('catalogId')==item['id']:return True
    clean=lambda s:re.sub(r'[\W_]+','',str(s).casefold())
    title,artist=clean(snapshot.get('title')),clean(snapshot.get('artist'))
    expected=clean(item['artist'])
    return bool(title and title==clean(item['title']) and
                (not expected or not artist or expected in artist or artist in expected))


class QueueBook:
    def __init__(self,path):
        self.path=Path(path);self.queues={s:[] for s in SOURCES};self.indices={s:-1 for s in SOURCES}
        self.active=None;self.revision=0
        try:
            if self.path.stat().st_size>5_000_000:return
            data=json.loads(self.path.read_text())
            for source in SOURCES:
                self.queues[source]=[item for value in data.get(source,{}).get('tracks',[])[:LIMIT]
                                     if (item:=track(value,source))]
                index=int(data.get(source,{}).get('index',-1))
                self.indices[source]=index if -1<=index<len(self.queues[source]) else -1
        except (OSError,ValueError,TypeError,AttributeError):pass

    def save(self):
        self.revision+=1
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.next.json')
        temporary.write_text(json.dumps({s:{'tracks':self.queues[s],'index':self.indices[s]} for s in SOURCES},ensure_ascii=False))
        temporary.chmod(0o600);temporary.replace(self.path)

    def add(self,source,values):
        items=[item for value in values if (item:=track(value,source))]
        self.compact(source,reserve=min(len(items),LIMIT))
        room=LIMIT-len(self.queues[source]);items=items[:max(0,room)]
        for item in items:item['entry']=uuid.uuid4().hex
        self.queues[source].extend(items)
        self.save();return len(items)

    def compact(self,source,reserve=0):
        index=self.indices[source]
        # Adding a song must not erase Previous. Keep recent history whenever
        # it fits; reclaim older played entries before rejecting pending music.
        drop=min(max(0,index),max(0,index-HISTORY,len(self.queues[source])+reserve-LIMIT))
        if drop:self.queues[source]=self.queues[source][drop:];self.indices[source]-=drop

    def replace(self,source,values):
        self.active=None;self.queues[source]=[];self.indices[source]=-1
        return self.add(source,values)

    def upcoming(self,source):return list(enumerate(self.queues[source]))[self.indices[source]+1:]

    def remove(self,source,index):
        if self.indices[source]<index<len(self.queues[source]):del self.queues[source][index];self.save()

    def move(self,source,index,delta):
        target=index+delta
        if self.indices[source]<min(index,target) and max(index,target)<len(self.queues[source]):
            self.queues[source][index],self.queues[source][target]=self.queues[source][target],self.queues[source][index]
            self.save()

    def clear(self,source):
        self.queues[source]=self.queues[source][:self.indices[source]+1]
        self.save()

    def select(self,source,index):
        if not 0<=index<len(self.queues[source]):return None
        self.indices[source]=index;self.active=source;self.save()
        return self.queues[source][index]

    def current(self,source):
        index=self.indices[source]
        return self.queues[source][index] if 0<=index<len(self.queues[source]) else None


class EndWatch:
    """Advance at a real end/near-end track change; ordinary pauses never skip."""
    def __init__(self):self.reset()
    def reset(self):self.seen=False;self.previous={}
    def observe(self,item,state):
        if self.seen and state.get('ended') and (matches(item,state) or not state.get('valid')):
            self.reset();return 'next'
        if not state.get('valid'):return None
        if matches(item,state):
            old=self.previous
            if state.get('playing'):self.seen=True
            self.previous=dict(state)
            if self.seen and (state.get('ended') or (not state.get('playing') and
                    state.get('duration',0)>0 and (state.get('position',0)>=state['duration']-.1 or
                    state.get('position',0)<.5 and old.get('playing') and old.get('position',0)>=state['duration']-2))):
                self.reset();return 'next'
            return None
        old=self.previous
        if self.seen and old.get('playing') and old.get('duration',0)>0 and old.get('position',0)>=old['duration']-2.:
            self.reset();return 'next'
        if self.seen:self.reset();return 'external'
        return None
