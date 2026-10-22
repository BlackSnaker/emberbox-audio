"""Display the metadata/lyrics belonging to the audio heard after AI buffering."""
from collections import OrderedDict,deque
from dataclasses import dataclass,replace


@dataclass(frozen=True)
class PlaybackPoint:
    when: float
    key: tuple
    title: str
    artist: str
    position: float
    length: float
    playing: bool
    art_url: str = ''


class HeardTimeline:
    def __init__(self):
        self.points=deque(maxlen=180);self.lyrics=OrderedDict()

    def clear(self):self.points.clear()

    def observe(self,point,state):
        self.points.append(point)
        self.lyrics[point.key]=state;self.lyrics.move_to_end(point.key)
        while len(self.lyrics)>8:self.lyrics.popitem(last=False)

    def at(self,now,delay=0.):
        if not self.points:return None,None
        wanted=now-max(0,min(8,delay))
        point=next((p for p in reversed(self.points) if p.when<=wanted),self.points[0])
        delta=max(0,min(1.8,wanted-point.when)) if point.playing else 0.
        position=max(0,min(point.length or point.position+delta,point.position+delta))
        return replace(point,position=position),self.lyrics.get(point.key)
