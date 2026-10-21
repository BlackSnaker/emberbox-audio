"""A passive glass discharge VU, driven by measured stereo PCM energy."""
import math
from functools import lru_cache

from gi.repository import Atk, Gtk
from hardware_controls import pixbuf


@lru_cache(maxsize=201)
def tube_frame(index):
    level = index / 200
    end = 17 + 112 * level
    glow = min(1., level * 5)
    mesh = ''.join(f'<path d="M{x} 17v23"/>' for x in range(22, 130, 6))
    ticks = ''.join(f'<path d="M{17+n*28} 46v{3 if n%2 else 4}"/>' for n in range(5))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="146" height="66" viewBox="0 0 146 66">
      <defs>
        <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
          <stop stop-color="#33352b"/><stop offset=".48" stop-color="#141a13"/>
          <stop offset="1" stop-color="#27291e"/>
        </linearGradient>
        <linearGradient id="fire"><stop stop-color="#cb6218"/>
          <stop offset=".5" stop-color="#ff9d2e"/><stop offset="1" stop-color="#ffe1a1"/>
        </linearGradient>
        <filter id="bloom" x="-30%" y="-200%" width="160%" height="500%"><feGaussianBlur stdDeviation="4"/></filter>
        <filter id="halo" x="-20%" y="-100%" width="140%" height="300%"><feGaussianBlur stdDeviation="1.5"/></filter>
      </defs>
      <rect x="5" y="9" width="136" height="35" rx="17.5" fill="#0e130e" opacity=".5"/>
      <rect x="4" y="7" width="138" height="35" rx="17.5" fill="url(#glass)" stroke="#8d8467" stroke-opacity=".34"/>
      <path d="M20 11h105" stroke="#fff1c7" stroke-opacity=".14" stroke-linecap="round"/>
      <path d="M15 39h116" stroke="#edc686" stroke-opacity=".08" stroke-linecap="round"/>
      <g stroke="#b6a37a" stroke-opacity=".13" stroke-width=".6">{mesh}</g>
      <path d="M17 25h112" stroke="#b86b28" stroke-opacity=".12" stroke-width="2"/>
      <g opacity="{glow:.4f}">
        <rect x="16" y="20" width="{end-15:.3f}" height="10" rx="5" fill="#ff8c24" filter="url(#bloom)"/>
        <rect x="16" y="22" width="{end-15:.3f}" height="6" rx="3" fill="#ff7519" filter="url(#halo)"/>
        <rect x="16" y="23.75" width="{end-15:.3f}" height="2.5" rx="1.25" fill="url(#fire)"/>
        <ellipse cx="{end:.3f}" cy="25" rx="1.2" ry="2.3" fill="#fff0bd"/>
      </g>
      <g stroke="#bdae93" stroke-opacity=".36" stroke-width=".7">{ticks}</g>
      <g fill="#a89984" font-family="monospace" font-size="6.5" text-anchor="middle">
        <text x="17" y="60">−60</text><text x="45" y="60">−45</text>
        <text x="73" y="60">−30</text><text x="101" y="60">−15</text><text x="129" y="60">0 dB</text>
      </g>
    </svg>'''
    return pixbuf(svg, 146, 66)


class TubeMeter(Gtk.Image):
    """No click/scroll handlers: this is a meter, never a volume control."""
    def __init__(self):
        super().__init__()
        self.level = self.velocity = 0.
        self.frame = None
        self.set_valign(Gtk.Align.CENTER)
        self.set_can_focus(False)
        self.set_has_tooltip(False)
        self.get_accessible().set_role(Atk.Role.LEVEL_BAR)
        self.get_accessible().set_name('VU · dBFS')
        self.advance(0., 0.)

    def advance(self, target, dt):
        # Critically damped motion keeps velocity continuous at sample edges.
        target = max(0., min(1., target))
        rate = 26. if target > self.level else 9.
        offset = self.level - target
        momentum = self.velocity + rate * offset
        decay = math.exp(-rate * dt)
        self.level = max(0., min(1., target + (offset + momentum * dt) * decay))
        self.velocity = (self.velocity - rate * momentum * dt) * decay
        index = round(self.level * 200)
        if index != self.frame:
            self.set_from_pixbuf(tube_frame(index))
            self.frame = index
