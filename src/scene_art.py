"""Bounded vector frames for the listening-scene card; no audio or GTK layout work."""
from functools import lru_cache
import math
import gi
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf


def pixbuf(svg,width,height):
    loader=GdkPixbuf.PixbufLoader.new_with_type('svg');loader.set_size(width,height)
    loader.write(svg.encode());loader.close();return loader.get_pixbuf()


@lru_cache(maxsize=16)
def scene_frame(headphones,angle,opening):
    mix=headphones/100;reveal=opening/100;spread=66+(angle-20)*2
    speaker_opacity=(1-mix)**1.4;ear_opacity=mix**1.3
    def speaker(x,sign):
        return f'''<g transform="translate({x:.2f},32) rotate({sign*9},0,30)" opacity="{speaker_opacity:.4f}">
          <ellipse cx="0" cy="73" rx="32" ry="8" fill="url(#shadow)"/>
          <rect x="-21" y="0" width="42" height="67" rx="11" fill="url(#case)" stroke="#727660" stroke-opacity=".35"/>
          <path d="M-15 7Q-16 4-9 4H9" fill="none" stroke="#eee2be" stroke-opacity=".14"/>
          <rect x="-16" y="6" width="32" height="54" rx="8" fill="#1a2019" stroke="#10150f"/>
          <circle cy="38" r="12" fill="url(#cone)" stroke="#555d46" stroke-width="1.3"/>
          <circle cy="38" r="7.4" fill="#2b3023" stroke="#9f8e52" stroke-opacity=".55"/>
          <circle cy="38" r="3.3" fill="url(#metal)"/>
          <circle cy="16" r="4.4" fill="#333b2a" stroke="#6b7256" stroke-width=".7"/>
          <rect x="-5" y="56" width="10" height="1.5" rx=".7" fill="#f3ba55"/>
        </g>'''
    waves=[]
    for sign in (-1,1):
        x=180+sign*spread
        waves.append(f'<path d="M{x:.1f} 98 Q{180+sign*spread*.7:.1f} 124 180 145" stroke="url(#ray)" stroke-width="1" fill="none" opacity="{speaker_opacity*.55:.3f}"/>')
    points=[]
    for i in range(10):
        a=math.tau*i/10;x=180+math.cos(a)*103;y=91+math.sin(a)*47
        points.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{2 if i%2 else 2.8}" fill="#dcaf59" opacity="{ear_opacity*(.5 if i%2 else .85):.3f}"/>')
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="360" height="180" viewBox="0 0 360 180">
     <defs>
      <linearGradient id="back" x2="0" y2="1"><stop stop-color="#1b211a"/><stop offset="1" stop-color="#23291f"/></linearGradient>
      <radialGradient id="aura"><stop stop-color="#c08b37" stop-opacity=".22"/><stop offset="1" stop-color="#8a672a" stop-opacity="0"/></radialGradient>
      <radialGradient id="shadow"><stop stop-color="#0b100b" stop-opacity=".7"/><stop offset="1" stop-color="#0b100b" stop-opacity="0"/></radialGradient>
      <linearGradient id="case" x2="1" y2="1"><stop stop-color="#535744"/><stop offset=".45" stop-color="#353c2c"/><stop offset="1" stop-color="#252d21"/></linearGradient>
      <radialGradient id="cone"><stop stop-color="#1d241a"/><stop offset=".65" stop-color="#363e2b"/><stop offset="1" stop-color="#171e15"/></radialGradient>
      <linearGradient id="metal" x2="1" y2="1"><stop stop-color="#a8af8c"/><stop offset=".5" stop-color="#535f44"/><stop offset="1" stop-color="#313b29"/></linearGradient>
      <linearGradient id="ray" x2="0" y2="1"><stop stop-color="#efbc58" stop-opacity=".65"/><stop offset="1" stop-color="#efbc58" stop-opacity=".08"/></linearGradient>
     </defs>
     <rect x=".5" y=".5" width="359" height="179" rx="23" fill="url(#back)" stroke="#e6d39d" stroke-opacity=".065"/>
     <ellipse cx="180" cy="79" rx="168" ry="87" fill="url(#aura)" opacity="{reveal:.3f}"/>
     <g opacity=".13" stroke="#bba679" fill="none" stroke-width=".55">
      <ellipse cx="180" cy="138" rx="44" ry="12"/><ellipse cx="180" cy="138" rx="83" ry="24"/>
      <ellipse cx="180" cy="138" rx="127" ry="38"/><path d="M26 159L180 95L334 159M180 95V177"/>
     </g>
     <g transform="translate(0,{(1-reveal)*11:.2f})" opacity="{reveal:.3f}">
      {''.join(waves)}{speaker(180-spread,-1)}{speaker(180+spread,1)}
      <g opacity="{ear_opacity:.3f}">
       <ellipse cx="180" cy="91" rx="103" ry="47" fill="none" stroke="#bc9a55" stroke-opacity=".22" stroke-dasharray="2 7"/>
       {''.join(points)}
       <ellipse cx="180" cy="123" rx="42" ry="12" fill="url(#shadow)"/>
       <path d="M149 93V74C149 32 211 32 211 74V93" fill="none" stroke="#11180f" stroke-width="14" stroke-linecap="round"/>
       <path d="M149 91V74C149 35 211 35 211 74V91" fill="none" stroke="url(#case)" stroke-width="10" stroke-linecap="round"/>
       <path d="M152 64C161 39 199 39 208 64" fill="none" stroke="#d3c295" stroke-opacity=".25" stroke-width="1.2"/>
       <rect x="140" y="76" width="17" height="35" rx="8" fill="url(#metal)" stroke="#778265" stroke-opacity=".3"/>
       <rect x="203" y="76" width="17" height="35" rx="8" fill="url(#metal)" stroke="#778265" stroke-opacity=".3"/>
       <path d="M146 88V101M214 88V101" stroke="#e8b154" stroke-width="1.5" stroke-linecap="round"/>
      </g>
      <ellipse cx="180" cy="146" rx="17" ry="10" fill="#172014" stroke="#a4aa7b" stroke-opacity=".16"/>
      <circle cx="180" cy="141" r="4" fill="#b6b58b"/>
      <path d="M173 149Q180 144 187 149" stroke="#b6b58b" stroke-width="1.5" fill="none" stroke-linecap="round"/>
     </g>
    </svg>'''
    return pixbuf(svg,360,180)
