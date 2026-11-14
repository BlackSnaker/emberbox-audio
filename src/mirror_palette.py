"""Small cached cover swatches and a continuous reflection-colour transition."""
import colorsys
import math

NEUTRAL=(1.,.81,.51,.69,.80,.96,0.)


def swatches(picture):
    if picture is None:return NEUTRAL
    from gi.repository import GdkPixbuf
    image=picture.scale_simple(24,24,GdkPixbuf.InterpType.BILINEAR)
    data=image.get_pixels();stride=image.get_rowstride();channels=image.get_n_channels()
    bins=[[0.,0.,0.,0.] for _ in range(12)];total=colourful=0
    for y in range(24):
        for x in range(24):
            i=y*stride+x*channels
            if channels==4 and data[i+3]<192:continue
            total+=1
            rgb=tuple(c/255 for c in data[i:i+3]);h,s,v=colorsys.rgb_to_hsv(*rgb)
            if s<.15 or v<.10:continue
            colourful+=1;weight=s*(.4+.6*v);bucket=bins[int(h*12)%12]
            bucket[0]+=weight
            for j in range(3):bucket[j+1]+=rgb[j]*weight
    order=sorted(range(12),key=lambda i:bins[i][0],reverse=True)
    if not total or not bins[order[0]][0]:return NEUTRAL
    first=order[0];second=next((i for i in order if min((i-first)%12,(first-i)%12)>=2 and bins[i][0]>0),first)
    def pigment(index):
        bucket=bins[index];rgb=tuple(c/bucket[0] for c in bucket[1:]);h,s,v=colorsys.rgb_to_hsv(*rgb)
        return colorsys.hsv_to_rgb(h,min(.80,s),.92)
    return pigment(first)+pigment(second)+(min(.85,colourful/total),)


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
