"""Cover-owned hues and continuous, reproducible liquid compositions."""
import colorsys
import hashlib
import math
from velvet_art import Light


def palette(swatches, identity='ember'):
    """Preserve artwork pigments; enrich scarce hues with quiet analogues."""
    primary, secondary = tuple(swatches[:3]), tuple(swatches[3:6])
    hsv = tuple(colorsys.rgb_to_hsv(*rgb) for rgb in (primary, secondary))
    chromatic = [item for item in hsv if item[1] > .15 and item[2] > .08]
    rich = (len(chromatic) == 2 and
            abs((chromatic[0][0]-chromatic[1][0]+.5)%1.-.5) > .10)
    if rich:
        h, s, v = hsv[0]
        neighbours = tuple(colorsys.hsv_to_rgb((h+offset)%1., s*.92, v)
                           for offset in (-.055, .035, .075))
    else:
        if chromatic:
            h, s, v = max(chromatic, key=lambda item:item[1]*item[2])
            s = max(.26, min(.50, s*.65))
        else:
            # Warm/cool monochrome retains its temperature. Truly neutral
            # art gets a subdued, stable harmony, rather than random RGB.
            warmth = sum(rgb[0]-rgb[2] for rgb in (primary,secondary))/2
            seed = hashlib.sha256(str(identity).encode('utf-8')).digest()
            h = .09 if warmth > .025 else .62 if warmth < -.025 else (.08,.34,.57,.73)[seed[0]%4]
            h += (seed[1]/255-.5)*.025
            s, v = .32, max(hsv[0][2],hsv[1][2])
        # Black art still has visible coloured ribbons; white art gains soft
        # pigment, not an extra white glare. Original swatches stay untouched.
        v = max(.46,min(.68,v*.78+.16))
        neighbours = tuple(colorsys.hsv_to_rgb((h+offset)%1., s*factor, v*value)
                           for offset,factor,value in ((-.075,.92,.93),(.035,1.,1.),(.105,.86,.96)))
    return primary+secondary+tuple(channel for colour in neighbours for channel in colour)


def composition(identity):
    raw=hashlib.sha256(str(identity).encode('utf-8')).digest()
    # Five independent lenses: phase, aspect, spread and ribbon shoulder.
    return tuple(.15+.7*value/255 for value in raw[:20])


class LiquidState(Light):
    def __init__(self):
        super().__init__()
        self.values=self.start=self.target=palette((.48,.32,.39,.24,.42,.40))+composition('ember')+silhouettes('ember')
        self.identity=None

    def retarget(self, swatches, identity, animate=True):
        self.identity=identity
        return self.set(palette(swatches,identity)+composition(identity)+silhouettes(identity),animate)


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


class FramePacer:
    """Vsync-owned 60 Hz deadlines, without drift or a busy timer.

    A missed deadline is dropped rather than replayed in a CPU-heavy burst.
    Keep fractional time so tiny vsync jitter cannot halve the frame rate.
    """
    interval=1/60

    def __init__(self):
        self.reset()

    def reset(self):
        self.deadline=None

    def due(self, now):
        if self.deadline is None:
            self.deadline=now+self.interval
            return True
        if now+.0005<self.deadline:
            return False
        self.deadline+=self.interval
        if self.deadline<now:
            self.deadline=now+self.interval
        return True


def silhouettes(identity):
    """Per-lens mask weights interpolate, unlike a jumping integer selector."""
    seed=hashlib.sha256(('silhouette:'+str(identity)).encode()).digest()
    return tuple(float(shape==seed[lens]%5) for lens in range(5) for shape in range(5))


def lens_masks(size=128):
    """Five feathered A8 silhouettes, baked once; <=80 KiB combined."""
    import numpy as np
    y,x=np.mgrid[-1:1:complex(size),-1:1:complex(size)]
    r=np.sqrt(x*x+y*y);angle=np.arctan2(y,x)
    # Match the broad original lens, with soft shoulders instead of outlines.
    ring=np.interp(r,(0.,.24,.39,.56,.75,1.),(0.,.13,.27,.12,.035,0.))
    ribbon=.25*np.exp(-((y-.28*np.sin(x*3.8)-x*.12)/.19)**2)*np.exp(-(x/.85)**6)
    petals=.25*np.exp(-((r-(.55+.13*np.sin(angle*3)))/.13)**2)
    crescent=.27*np.exp(-((r-.56)/.18)**2)*np.clip(.45+x*.9-y*.2,0,1)
    veil=.21*np.exp(-((y+.22*np.sin(x*2.7))/.33)**2)*np.exp(-(x/.84)**4)
    edge=np.clip((1-r)/.16,0,1)
    return tuple(np.clip(mask*edge*255+.5,0,255).astype('uint8').tobytes()
                 for mask in (ring,ribbon,petals,crescent,veil))
