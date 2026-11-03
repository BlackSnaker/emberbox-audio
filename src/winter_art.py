"""Original winter ornaments, drawn once as vectors and cached at display size."""
from functools import lru_cache
import math
import gi
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf


def pixbuf(svg,width,height):
    loader=GdkPixbuf.PixbufLoader.new_with_type('svg');loader.set_size(width,height)
    loader.write(svg.encode());loader.close();return loader.get_pixbuf()

DEFS='''
<linearGradient id="needle" x2=".3" y2="1"><stop stop-color="#718776"/><stop offset=".42" stop-color="#355746"/><stop offset="1" stop-color="#152e25"/></linearGradient>
<radialGradient id="red" cx=".29" cy=".25" r=".85"><stop stop-color="#d58978"/><stop offset=".22" stop-color="#a34542"/><stop offset=".6" stop-color="#6a252d"/><stop offset="1" stop-color="#2a101c"/></radialGradient>
<radialGradient id="gold" cx=".28" cy=".23" r=".85"><stop stop-color="#fff1bb"/><stop offset=".2" stop-color="#d9b77a"/><stop offset=".55" stop-color="#98703d"/><stop offset="1" stop-color="#332c1e"/></radialGradient>
<linearGradient id="brass" x2="1" y2=".3"><stop stop-color="#755c35"/><stop offset=".3" stop-color="#edcd86"/><stop offset=".55" stop-color="#b89a61"/><stop offset="1" stop-color="#6a502d"/></linearGradient>
<radialGradient id="glow"><stop stop-color="#ffdc8f" stop-opacity=".6"/><stop offset=".26" stop-color="#f2b358" stop-opacity=".19"/><stop offset="1" stop-color="#eea550" stop-opacity="0"/></radialGradient>
<radialGradient id="bulb"><stop stop-color="#fff9dc"/><stop offset=".4" stop-color="#ffe4a4"/><stop offset="1" stop-color="#cd8a3e"/></radialGradient>
<linearGradient id="pineback" x2="1" y2="1"><stop stop-color="#263e32"/><stop offset=".5" stop-color="#192a24"/><stop offset="1" stop-color="#101b1b"/></linearGradient>
'''


def branch(x,y,scale=1,angle=0):
    needles=[]
    # Individually tapered, layered needles. No raster textures or live blur.
    for n in range(20):
        t=n/19;px=t*130;py=math.sin(t*2)*10;length=23*(1-t)+7
        for side in (-1,1):
            for j in range(3):
                dx=length*(.65+j*.16);dy=side*(length*(.52+j*.14))
                needles.append(f'<path d="M{px:.2f} {py:.2f}q{-dx*.5:.2f} {dy*.3:.2f} {-dx:.2f} {dy:.2f}" stroke="{"#637e68" if j==0 else "#3b5d49" if j==1 else "#294c3a"}" stroke-opacity="{.62+j*.13}" stroke-width="{1.25-j*.2}"/>')
    return f'<g transform="translate({x},{y}) rotate({angle}) scale({scale})" fill="none" stroke-linecap="round"><path d="M-4 0Q66 13 137 8" stroke="#8c7648" stroke-width="1.3"/>{"".join(needles)}</g>'


def bauble(x,y,r,color='red',length=25):
    # Reflections, engraved bands and a brushed brass cap give the ornament
    # material depth without adding a heavy image filter.
    return f'''<g transform="translate({x},{y})">
      <path d="M0 {-length-r}V{-r-6}" stroke="#bdaa78" stroke-opacity=".65" stroke-width=".75"/>
      <ellipse cy="{r*.88}" rx="{r*.8}" ry="{r*.18}" fill="#060d0b" opacity=".3"/>
      <circle r="{r}" fill="url(#{color})" stroke="#edd19b" stroke-opacity=".18" stroke-width=".7"/>
      <ellipse cx="{-r*.35}" cy="{-r*.4}" rx="{r*.22}" ry="{r*.32}" transform="rotate(28)" fill="#fff0c5" opacity=".16"/>
      <path d="M{-r*.77} {-r*.1}Q0 {r*.32} {r*.77} {-r*.1}M{-r*.79} {r*.07}Q0 {r*.49} {r*.79} {r*.07}" fill="none" stroke="#f1d28b" stroke-opacity=".42" stroke-width=".65"/>
      <path d="M{-r*.56} {-r*.7}Q{-r*.1} {-r*.98} {r*.3} {-r*.86}" fill="none" stroke="#fff3cb" stroke-opacity=".48" stroke-width=".8" stroke-linecap="round"/>
      <rect x="-3.8" y="{-r-4}" width="7.6" height="5.5" rx="1.4" fill="url(#brass)"/>
      <path d="M-1.8 {-r-4}q0-4 1.8-4t1.8 4" stroke="#cdb37a" stroke-width=".8" fill="none"/>
    </g>'''


def star(x,y,size=4,opacity=.65):
    return f'<path d="M{x-size} {y}Q{x} {y} {x} {y-size}Q{x} {y} {x+size} {y}Q{x} {y} {x} {y+size}Q{x} {y} {x-size} {y}" fill="#f3d69a" opacity="{opacity}"/>'


def winter_svg(width,height,kind='top'):
    parts=[]
    if kind=='preview':
        parts.append(f'<rect width="{width}" height="{height}" rx="16" fill="url(#pineback)"/>')
        parts.extend([branch(2,9,.9,15),branch(width-3,4,.9,158),bauble(width-40,65,19,'red',35),bauble(width-79,42,11,'gold',28)])
        for x,y,r in [(20,62,32),(99,8,24),(168,77,40)]:parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#glow)"/>')
        for x in range(20,int(width)-10,28):
            y=13+6*math.sin(x/width*math.pi);parts.append(f'<circle cx="{x}" cy="{y:.2f}" r="10" fill="url(#glow)"/><circle cx="{x}" cy="{y:.2f}" r="1.7" fill="url(#bulb)"/>')
        parts.extend([star(23,67,3),star(121,38,2),star(width-16,25,3)])
    elif kind=='top':
        large=width>600
        # A layered evergreen garland, with glass lamps hanging below the wire.
        # Dedicated headroom in the widget keeps this away from the controls.
        for x in range(-40,width+100,92 if large else 70):
            parts.append(branch(x,3,.86 if large else .64,7))
            parts.append(branch(x+60,5,.65 if large else .5,172))
        y=10;drop=8 if large else 6
        parts.append(f'<path d="M12 {y}Q{width/2} {y+drop*2} {width-12} {y}" fill="none" stroke="#c3ac72" stroke-opacity=".62" stroke-width=".8"/>')
        gap=66 if large else 34
        for n,x in enumerate(range(20,width-12,gap)):
            v=(x-12)/(width-24);by=y+4*drop*v*(1-v);hang=6+(n%3)*2
            parts.append(f'<path d="M{x} {by:.2f}v{hang}" stroke="#baa477" stroke-width=".85"/><circle cx="{x}" cy="{by+hang+2:.2f}" r="{28 if large else 19}" fill="url(#glow)"/><ellipse cx="{x}" cy="{by+hang+2:.2f}" rx="{2.8 if large else 2.1}" ry="{4 if large else 3.1}" fill="url(#bulb)"/><path d="M{x-1} {by+hang+1:.2f}v2" stroke="#fff9d4" stroke-width=".8" stroke-linecap="round"/>')
        if large:
            parts.extend([branch(width-1,13,1.0,135),branch(0,11,.75,68),
                          bauble(width-33,130,23,'red',90),bauble(width-67,76,14,'gold',50),
                          bauble(27,124,19,'gold',90),bauble(60,79,12,'red',48),
                          star(38,169,5,.8),star(width-52,173,4,.7)])
        else:
            for n,x in enumerate((57,width//2,width-57)):
                if n==1 and width<380:continue
                parts.append(bauble(x,30 if n!=1 else 25,9 if n!=1 else 7,'red' if n%2==0 else 'gold',17))
            parts.extend([star(31,29,3,.8),star(width-30,30,2.6,.7)])
    elif kind=='corner':
        parts.extend([branch(width-3,height-3,.72,190),branch(width-5,height-2,.56,232),bauble(width-31,height-26,15,'red',20),star(width-67,height-15,2,.4)])
    elif kind=='seal':
        # A tiny engraved star for the settings theme row.
        parts.append(f'<circle cx="{width/2}" cy="{height/2}" r="{width/2-1}" fill="url(#gold)"/>')
        parts.append(star(width/2,height/2,width*.29,1))
    clip=''
    if kind=='top' and width<=600:
        clip=f'<clipPath id="edge"><path d="M22 0H{width-22}Q{width} 0 {width} 22V{height}H0V22Q0 0 22 0Z"/></clipPath>'
    drawing=''.join(parts)
    if clip:drawing=f'<g clip-path="url(#edge)">{drawing}</g>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><defs>{DEFS}{clip}</defs>{drawing}</svg>'


@lru_cache(maxsize=16)
def winter_image(width,height,kind='top'):
    return pixbuf(winter_svg(width,height,kind),width,height)
