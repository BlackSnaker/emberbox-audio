"""Small cached cover swatches and a continuous reflection-colour transition."""
import math

NEUTRAL=(1.,.81,.51,.69,.80,.96,0.)


def swatches(picture):
    if picture is None:return NEUTRAL
    from gi.repository import GdkPixbuf
    image=picture.scale_simple(24,24,GdkPixbuf.InterpType.BILINEAR)
    data=image.get_pixels();stride=image.get_rowstride();channels=image.get_n_channels()
    bins={}
    for y in range(24):
        for x in range(24):
            i=y*stride+x*channels
            if channels==4 and data[i+3]<192:continue
            rgb=tuple(c/255 for c in data[i:i+3])
            key=tuple(min(3,int(c*4)) for c in rgb)
            bucket=bins.setdefault(key,[0.,0.,0.,0.]);bucket[0]+=1
            for j in range(3):bucket[j+1]+=rgb[j]
    if not bins:return NEUTRAL
    ranked=sorted(bins.values(),key=lambda b:b[0],reverse=True)
    colours=[tuple(c/b[0] for c in b[1:]) for b in ranked]
    primary=colours[0]
    secondary=next((c for c in colours[1:] if math.dist(c,primary)>=.22),primary)
    if max(primary+secondary)<.06:return NEUTRAL
    # Preserve the actual pixel colours, including neutral shades. Do not
    # force saturation/value or dilute a colourful detail by its image area.
    return primary+secondary+(1.,)



class Palette:
    def __init__(self):
        self.values=NEUTRAL;self.target=NEUTRAL;self.picture=None;self.key=None;self.elapsed=.5

    def advance(self,dt,host):
        if not isinstance(dt,(int,float)) or not math.isfinite(dt) or dt<=0:return self.values
        self.elapsed+=dt
        if self.elapsed>=.5:
            self.elapsed=0.
            key=str(getattr(host,'art_url','') or '')
            cover=getattr(host,'cover',None)
            picture=cover.get_pixbuf() if cover and hasattr(cover,'get_pixbuf') else None
            changed=picture!=self.picture
            if key!=self.key:
                self.key=key
            if changed:
                self.picture=picture;self.target=swatches(picture)
            if not key or picture is None:self.target=NEUTRAL
        weight=-math.expm1(-dt/1.8)
        self.values=tuple(a+(b-a)*weight for a,b in zip(self.values,self.target))
        return self.values
