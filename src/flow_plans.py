"""Private, bounded transition recipes. No audio or account credentials."""
import hashlib
import json
import math
import re
from pathlib import Path

MAX_PLAYLISTS=100
MAX_PAIRS=199


def playlist_key(source,item):
    identity=str(item.get('uri') or (str(item.get('kind',''))+':'+str(item.get('id',''))))
    return hashlib.sha256((source+'\0'+identity).encode()).hexdigest()


def pair_key(a,b):
    return hashlib.sha256((a['uri']+'\0'+b['uri']).encode()).hexdigest()


def valid_key(key):return isinstance(key,str) and re.fullmatch('[0-9a-f]{64}',key) is not None


def recipe(value):
    if not isinstance(value,dict):raise ValueError('Invalid transition')
    mode=value.get('mode','auto');shape=value.get('shape','shared')
    if mode not in ('auto','manual','cut') or shape not in ('shared','smooth'):raise ValueError('Invalid transition')
    seconds=float(value.get('seconds',8))
    if not math.isfinite(seconds) or not 1<=seconds<=8:raise ValueError('Invalid duration')
    eq_mode=value.get('eq_mode','off')
    if eq_mode not in ('off','auto','manual'):raise ValueError('Invalid transition EQ mode')
    # Validate without importing the DSP/SciPy stack into the GTK startup path.
    def cuts(name):
        raw=value.get(name,[0,0,0])
        if not isinstance(raw,(list,tuple)) or len(raw)!=3:raise ValueError('Invalid transition EQ')
        values=[float(v) for v in raw]
        if not all(math.isfinite(v) and -12<=v<=0 for v in values):raise ValueError('Invalid transition EQ')
        return values
    return dict(mode=mode,seconds=round(seconds,1),shape=shape,beats=value.get('beats',True) is True,
                eq_mode=eq_mode,eq_out=cuts('eq_out'),eq_in=cuts('eq_in'))


class FlowPlans:
    def __init__(self,path):
        self.path=Path(path);self.data={};self.revision=0
        try:
            if self.path.stat().st_size>10_000_000:return
            raw=json.loads(self.path.read_text())
            if not isinstance(raw,dict):return
            for key,values in list(raw.items())[:MAX_PLAYLISTS]:
                if not valid_key(key) or not isinstance(values,dict):continue
                pairs={}
                for pair,value in list(values.items())[:MAX_PAIRS]:
                    try:
                        if valid_key(pair):pairs[pair]=recipe(value)
                    except (ValueError,TypeError,OverflowError):pass
                self.data[key]=pairs
        except (OSError,ValueError,TypeError):pass

    def get(self,key,a,b):
        value=self.data.get(key,{}).get(pair_key(a,b))
        return recipe(value) if value else None

    def for_tracks(self,a,b):
        key=a.get('flow_playlist')
        return self.get(key,a,b) if key and key==b.get('flow_playlist') else None

    def put(self,key,pairs):
        if not valid_key(key):raise ValueError('Invalid playlist')
        if key not in self.data and len(self.data)>=MAX_PLAYLISTS:raise ValueError('Transition library is full (100 playlists)')
        values=dict(self.data.get(key,{}))
        for a,b,value in pairs:values[pair_key(a,b)]=recipe(value)
        if len(values)>MAX_PAIRS:raise ValueError('Transition library is full (199 pairs)')
        updated=dict(self.data);updated[key]=values
        if updated==self.data:return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.next.json')
        # Open with private permissions from the first byte, including failure paths.
        import os
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),0o600);json.dump(updated,stream)
        temporary.replace(self.path);self.data=updated;self.revision+=1


def duration(plan,outgoing,incoming,quiet=False,grid=None):
    """Conservative auto length; manual recipes preserve the chosen overlap.

    Auto uses real silence observations at runtime, never guesses BPM from a
    title. Unknown durations stay bounded; very short tracks retain headroom.
    """
    wanted=plan['seconds'] if plan and plan['mode']=='manual' else 8.
    if plan and plan['mode']=='auto' and isinstance(grid,dict):
        try:
            bpm=float(grid.get('bpm',0));confidence=float(grid.get('confidence',0))
            if 80<=bpm<=180 and .72<=confidence<=1:wanted=min(8.,480/bpm)
        except (ValueError,TypeError,OverflowError):pass
    result=min(wanted,max(2.,outgoing*.1),max(2.,incoming*.1) if incoming>0 else 8.)
    if quiet and (not plan or plan['mode']=='auto'):result=min(result,1.4)
    return result


def configuration(plan):
    if not plan or plan.get('eq_mode','off')=='off':return None
    if plan['eq_mode']=='auto':return {'out':[-9.,0.,0.],'in':[-6.,0.,0.]}
    return {'out':list(plan['eq_out']),'in':list(plan['eq_in'])}
