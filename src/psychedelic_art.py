"""Cover-owned hues and continuous, reproducible liquid compositions."""
import colorsys
import hashlib
import math
from velvet_art import Light


def palette(swatches):
    """Two original swatches plus three neighbouring hues, never complements."""
    primary, secondary = tuple(swatches[:3]), tuple(swatches[3:6])
    h, s, v = colorsys.rgb_to_hsv(*primary)
    # Neutral artwork stays neutral: no artificial rainbow on monochrome art.
    neighbours = tuple(colorsys.hsv_to_rgb((h+offset)%1., s*.92, v)
                       for offset in (-.055, .035, .075))
    return primary+secondary+tuple(channel for colour in neighbours for channel in colour)


def composition(identity):
    raw=hashlib.sha256(str(identity).encode('utf-8')).digest()
    # Five independent lenses: phase, aspect, spread and ribbon shoulder.
    return tuple(.15+.7*value/255 for value in raw[:20])


class LiquidState(Light):
    def __init__(self):
        super().__init__()
        self.values=self.start=self.target=palette((.48,.32,.39,.24,.42,.40))+composition('ember')
        self.identity=None

    def retarget(self, swatches, identity, animate=True):
        self.identity=identity
        return self.set(palette(swatches)+composition(identity),animate)


def cover_swatches(picture):
    """Keep the dominant pigment and a substantial chromatic artwork accent."""
    from mirror_palette import swatches
    base=swatches(picture)
    data=picture.get_pixels();stride=picture.get_rowstride();channels=picture.get_n_channels()
    buckets={}
    for y in range(picture.get_height()):
        for x in range(picture.get_width()):
            start=y*stride+x*channels
            if channels==4 and data[start+3]<192:continue
            rgb=tuple(v/255 for v in data[start:start+3])
            key=tuple(int(v*7) for v in rgb)
            entry=buckets.setdefault(key,[0,0.,0.,0.]);entry[0]+=1
            for i,value in enumerate(rgb):entry[i+1]+=value
    if not buckets:return base
    dominant=max(buckets.values(),key=lambda b:b[0])
    primary=tuple(v/dominant[0] for v in dominant[1:])
    secondary=base[3:6] if base[6] else primary
    best=0.
    for count,*totals in buckets.values():
        colour=tuple(value/count for value in totals)
        _,s,v=colorsys.rgb_to_hsv(*colour)
        score=count**.65*s*(.5+v)
        if count>=3 and math.dist(colour,primary)>.22 and score>best:
            secondary=colour;best=score
    return primary+tuple(secondary)+(1.,)
