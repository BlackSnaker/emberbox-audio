"""Baked mirror normals and moving softboxes; never synthesize pixels per frame."""
from functools import lru_cache
import math
import numpy as np

PHASES=24
PERIOD=28.


def materials(size=320,trim=False,single=False):
    """Premultiplied BGRA atlas. One bounded worker job, two Cairo blits per optical frame."""
    size=max(64,min(384,int(size)));height=22 if trim else round(size*.45)
    yy,xx=np.mgrid[:height,:size].astype(np.float32)
    u=(xx+.5)/size;v=(yy+.5)/height
    # A gently curved architectural mirror field, never a literal ball.
    # Planar facets share a quiet continuous shoulder with the dark casing.
    longitude=(u-.5)*.65;latitude=(.5-v)*.38
    alpha=np.sin(u*math.pi)**1.5*np.sin(v*math.pi)**1.5
    if not trim:alpha*=.55
    # Each facet owns one planar normal; fine bevels catch a thin silver rim.
    rows=v*(3 if trim else 9);cols=u*(32 if trim else 30)+v*.8
    lat=latitude+.045*np.sin(np.floor(cols)*3+np.floor(rows)*2)
    lon=longitude+.07*np.cos(np.floor(cols)*7-np.floor(rows)*3)
    nx=np.cos(lat)*np.sin(lon);ny=np.sin(lat);nz=np.cos(lat)*np.cos(lon)
    edge=np.minimum.reduce((rows%1,1-rows%1,cols%1,1-cols%1))
    joint=np.clip(edge/.055,0,1)
    variation=.86+.14*np.sin(np.floor(rows)*17+np.floor(cols)*31)**2
    frames=[]
    for phase in ([4] if single else range(PHASES)):
        t=phase/PHASES*math.tau
        base=np.full((height,size,3),0.,np.float32)
        ambient=(.25+.36*np.maximum(0,nz)+.07*ny)*variation
        base+=ambient[...,None]*np.array((65,70,73))
        # Broad, reflected softboxes rather than random flashing pixels.
        for light,tone,power in ((np.array((-.6+.23*math.sin(t),.5,.7)),(232,196,132),1.25),
                                  (np.array((.8,.1+.25*math.cos(t),.5)),(141,168,191),.9),
                                  (np.array((.2,-.6,.7+.18*math.sin(t))),(140,111,166),.48)):
            light=light/np.linalg.norm(light);half=light+np.array((0,0,1));half/=np.linalg.norm(half)
            spec=np.maximum(0,nx*half[0]+ny*half[1]+nz*half[2])**42
            reflected=np.maximum(0,nx*light[0]+ny*light[1]+nz*light[2])**9
            base+=(spec*power+reflected*.13)[...,None]*np.array(tone)
        # A broad travelling reflection catches consecutive glass facets.
        centre=.5+.48*math.sin(t)
        sheen=np.exp(-((u-centre+.18*(v-.5))/.14)**2)
        base+=sheen[...,None]*np.array((94,76,49))
        base=base*joint[...,None]+np.array((4,7,10))*(1-joint[...,None])
        bevel=np.exp(-((edge-.07)/.025)**2)*np.maximum(0,nz)*.12
        base+=bevel[...,None]*np.array((187,184,165))
        out=np.empty((height,size,4),np.uint8)
        out[...,:3]=np.clip(base[...,::-1],0,255)*alpha[...,None];out[...,3]=(alpha*255).astype(np.uint8)
        frames.append(out.tobytes())
    return size,height,tuple(frames)


@lru_cache(maxsize=1)
def preview():
    from gi.repository import GdkPixbuf,GLib
    from PIL import Image
    w,h=222,86
    atlas=materials(222,single=True);frame=atlas[2][0]
    image=Image.new('RGBA',(w,h),(17,21,27,255))
    glass=Image.frombytes('RGBA',atlas[:2],frame,'raw','BGRa')
    image.alpha_composite(glass,(0,-7))
    from PIL import ImageDraw
    draw=ImageDraw.Draw(image)
    draw.line((14,24,55,24),fill=(219,188,132),width=1)
    draw.text((14,34),'M I R R O R',fill=(240,218,180))
    draw.text((14,49),'B A L L',fill=(161,169,180))
    raw=image.tobytes()
    return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(raw),GdkPixbuf.Colorspace.RGB,True,8,w,h,w*4)


def room(width,height):
    """Static distant caustics. Small image, prepared off GTK and scaled once."""
    from gi.repository import GdkPixbuf,GLib
    ratio=min(1,960/max(width,height));w=max(1,round(width*ratio));h=max(1,round(height*ratio))
    y,x=np.mgrid[:h,:w].astype(np.float32);x/=w;y/=h
    field=np.zeros((h,w,3),np.float32)+np.array((12,16,21))
    for cx,cy,sx,sy,tone in ((.83,.19,.45,.7,(19,18,22)),(.12,.68,.5,.7,(9,17,20)),(.6,.1,.6,.4,(14,10,12))):
        wash=np.exp(-3*(((x-cx)/sx)**2+((y-cy)/sy)**2))
        field+=wash[...,None]*np.array(tone)
    cols=x*46+y*3;rows=y*29
    edge=np.minimum.reduce((cols%1,1-cols%1,rows%1,1-rows%1))
    facets=.5+.5*np.sin(np.floor(cols)*7.1+np.floor(rows)*4.9)
    wall=np.exp(-((x-.96)/.30)**2-((y-.3)/.55)**2)+.65*np.exp(-((x-.05)/.18)**2-((y-.67)/.45)**2)
    field+=(facets*np.clip(edge/.09,0,1)*wall)[...,None]*np.array((10,12,15))
    # Soft, distant rectangular caustics, never a flashing star field.
    for k in range(28):
        angle=k*2.39996;distance=.25+.50*((k*13%37)/37)
        cx=.72+math.cos(angle)*distance;cy=.30+math.sin(angle)*distance*.8
        size=.0018+.001*(k%4);stretch=1.2+max(0,cx-.7)*4
        dx=(x-cx)/size;dy=(y-cy)/(size*stretch*width/height)
        dot=np.exp(-(np.maximum(abs(dx),abs(dy))**4)*1.4)
        aura=np.exp(-(dx*dx+dy*dy)/9)*.06
        strength=.08 if .20<cx<.75 else .3
        field+=(dot+aura)[...,None]*np.array((92,83,67) if k%3 else (72,90,113))*strength
    raw=np.clip(field,0,255).astype(np.uint8).tobytes()
    p=GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(raw),GdkPixbuf.Colorspace.RGB,False,8,w,h,w*3)
    return p.scale_simple(width,height,GdkPixbuf.InterpType.BILINEAR)
