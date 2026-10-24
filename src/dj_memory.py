"""Private, bounded listening preferences. No credentials, audio or training data."""
from copy import deepcopy
import json,math,os,re,threading,time
from pathlib import Path


def identity(value):
    return str(value.get('uri') or value.get('id') or re.sub(r'\W+','',
        (str(value.get('artist',''))+' '+str(value.get('title',''))).casefold()))[:400]


class ListeningMemory:
    def __init__(self,path,clock=time.time):
        self.path=Path(path);self.clock=clock;self.lock=threading.RLock();self.write_lock=threading.Lock();self.dirty=False
        self.sources={};self.settings={'voice':True,'language':'ru','ai':True,'model':'qwen3.5:2b','enabled':False}
        self.current=None;self.heard=0.;self.last_tick=None;self.credited=False
        try:
            if self.path.stat().st_size<2_000_000:
                data=json.loads(self.path.read_text());sources=data.get('sources',{})
                if isinstance(sources,dict):
                    for source in ('spotify','apple-music','youtube','yandex-music'):
                        values=sources.get(source,{})
                        if isinstance(values,dict):
                            self.sources[source]={}
                            for k,v in list(values.items())[-400:]:
                                if not isinstance(v,dict):continue
                                clean={field:str(v.get(field) or '')[:400] for field in ('title','artist','uri')}
                                for field in ('listen','skip','vote','last'):
                                    try:
                                        number=float(v.get(field,0))
                                        clean[field]=number if math.isfinite(number) else 0
                                    except (ValueError,TypeError,OverflowError):clean[field]=0
                                clean['vote']=max(-1,min(1,int(clean['vote'])))
                                self.sources[source][str(k)[:400]]=clean
                settings=data.get('settings',{})
                if isinstance(settings,dict):self.settings.update({k:v for k,v in settings.items() if k in self.settings and isinstance(v,type(self.settings[k]))})
        except (OSError,ValueError,TypeError,AttributeError):pass

    def profile(self,source):
        with self.lock:return deepcopy(self.sources.get(source,{}))

    def observe(self,source,state,now):
        key=(source,identity(state)) if state.get('valid') and state.get('title') else None
        if key!=self.current:
            self.current=key;self.heard=0.;self.credited=False;self.last_tick=None
        if key and state.get('playing'):
            if self.last_tick is not None:self.heard+=max(0,min(1.,now-self.last_tick))
            duration=float(state.get('duration') or 0)
            threshold=min(60,max(20,duration*.45)) if duration else 45
            if not self.credited and self.heard>=threshold:
                self.record(source,state,'listen');self.credited=True
        self.last_tick=now if state.get('playing') else None

    def record(self,source,value,event):
        if event not in ('listen','like','dislike','skip') or not value.get('title'):return
        key=identity(value)
        if not key:return
        with self.lock:
            values=self.sources.setdefault(source,{})
            item=values.setdefault(key,{'title':str(value.get('title',''))[:200],
                'artist':str(value.get('artist',''))[:200],'uri':str(value.get('uri',''))[:400]})
            if event in ('like','dislike'):item['vote']=1 if event=='like' else -1
            else:item[event]=min(200,int(item.get(event,0))+1)
            item['last']=self.clock()
            while len(values)>400:del values[min(values,key=lambda k:float(values[k].get('last',0)))]
            self.dirty=True

    def artist_affinity(self,source):
        artists={};now=self.clock()
        for item in self.profile(source).values():
            artist=str(item.get('artist','')).casefold().strip()
            if not artist:continue
            age=max(0,now-float(item.get('last',now)))/86400
            weight=(min(6,int(item.get('listen',0)))*.7+int(item.get('vote',0))*4-min(4,int(item.get('skip',0)))*.35)*math.exp(-age/45)
            artists[artist]=artists.get(artist,0)+weight
        return artists

    def clear(self):
        with self.lock:self.sources.clear();self.current=None;self.heard=0.;self.dirty=True

    def import_recent(self,source,values):
        for value in values[:30]:
            if not isinstance(value,dict) or not value.get('title'):continue
            key=identity(value)
            with self.lock:known=key in self.sources.get(source,{})
            if not known:self.record(source,value,'listen')

    def save(self):
        with self.write_lock:self._save()

    def _save(self):
        with self.lock:
            if not self.dirty:return
            data=json.dumps({'version':1,'settings':self.settings,'sources':self.sources},ensure_ascii=False)
            self.dirty=False
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.next.json')
        try:
            with temporary.open('w') as f:os.chmod(temporary,0o600);f.write(data)
            temporary.replace(self.path)
        except OSError:
            with self.lock:self.dirty=True
            raise
