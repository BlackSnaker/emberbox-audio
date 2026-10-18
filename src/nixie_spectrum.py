"""Gas discharge indicator tubes driven by the actual Spotify spectrum."""

from pathlib import Path
from paths import CACHE_DIR, CONFIG_DIR

from gi.repository import GdkPixbuf, Gtk


FRAME_COUNT = 384
WIDTH, HEIGHT = 40, 64
MINI_WIDTH, MINI_HEIGHT = 28, 45
_FRAMES = None


def tube_svg(level):
    height = 1.4 + level * 40
    top = 49 - height
    light = level ** 0.72
    glow = 0.17 + light * 0.77
    mesh = ''.join(f'<path d="M11 {y}h14"/>' for y in range(13, 49, 5))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 36 58">
      <defs>
        <linearGradient id="glass" x1="0" x2="1">
          <stop stop-color="#151512"/>
          <stop offset=".22" stop-color="#25231e"/>
          <stop offset=".6" stop-color="#111310"/>
          <stop offset="1" stop-color="#30291f"/>
        </linearGradient>
        <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1">
          <stop stop-color="#82715a" stop-opacity=".6"/>
          <stop offset=".45" stop-color="#4c4436" stop-opacity=".6"/>
          <stop offset="1" stop-color="#91816b" stop-opacity=".2"/>
        </linearGradient>
        <linearGradient id="neon" x1="0" y1="1" x2="0" y2="0">
          <stop stop-color="#ff650c"/>
          <stop offset=".5" stop-color="#ffa43a"/>
          <stop offset="1" stop-color="#ffe0a0"/>
        </linearGradient>
        <linearGradient id="edge-light" gradientUnits="userSpaceOnUse"
          x1="0" y1="{top - 5:.2f}" x2="0" y2="54">
          <stop stop-color="#ffb85c" stop-opacity="0"/>
          <stop offset=".3" stop-color="#ffae4d" stop-opacity=".35"/>
          <stop offset="1" stop-color="#ff8b28" stop-opacity=".85"/>
        </linearGradient>
        <linearGradient id="gas" x1="0" y1="0" x2="0" y2="1">
          <stop stop-color="#ffb85b" stop-opacity="0"/>
          <stop offset=".2" stop-color="#ff9b37" stop-opacity=".6"/>
          <stop offset="1" stop-color="#ff7518" stop-opacity=".8"/>
        </linearGradient>
        <filter id="bloom" x="-200%" y="-60%" width="500%" height="220%">
          <feGaussianBlur stdDeviation="2.8"/>
        </filter>
        <filter id="halo" x="-250%" y="-100%" width="600%" height="300%">
          <feGaussianBlur stdDeviation="4.5"/>
        </filter>
        <filter id="edge-bloom" x="-50%" y="-20%" width="200%" height="140%">
          <feGaussianBlur stdDeviation="1.25"/>
        </filter>
        <clipPath id="inside-glass">
          <rect x="7.4" y="3.4" width="21.2" height="50.2" rx="10.6"/>
        </clipPath>
      </defs>
      <rect x="13" y="{top:.2f}" width="10" height="{height:.2f}" rx="5"
        fill="#ff851f" opacity="{light * .24:.4f}" filter="url(#halo)"/>
      <rect x="7.4" y="3.4" width="21.2" height="50.2" rx="10.6" fill="none"
        stroke="url(#edge-light)" stroke-width="1.6" opacity="{.015 + light * .24:.4f}"
        filter="url(#edge-bloom)"/>
      <rect x="7" y="3" width="22" height="51" rx="11" fill="url(#glass)" stroke="url(#rim)" stroke-width=".8"/>
      <g clip-path="url(#inside-glass)">
        <rect x="9" y="{top - 3:.2f}" width="18" height="{height + 8:.2f}" rx="8"
          fill="url(#gas)" opacity="{light * .16:.4f}" filter="url(#bloom)"/>
      </g>
      <g fill="none" stroke="#70452b" stroke-width=".45" opacity=".3">{mesh}</g>
      <path d="M18 11v38" stroke="#6e3b23" stroke-width="1.1" opacity=".55"/>
      <rect x="13.8" y="{top:.2f}" width="8.4" height="{height:.2f}" rx="4.2"
        fill="#ff6909" opacity="{glow:.3f}" filter="url(#bloom)"/>
      <rect x="15.5" y="{top:.2f}" width="5" height="{height:.2f}" rx="2.5"
        fill="#ff7d16" opacity="{glow:.3f}"/>
      <rect x="17" y="{top + .4:.2f}" width="2" height="{max(.5,height - .8):.2f}" rx="1"
        fill="url(#neon)" opacity="{.28 + level * .72:.3f}"/>
      <ellipse cx="18" cy="49" rx="4.5" ry="1.2" fill="#ff8d22" opacity="{.35 + level * .5:.3f}"/>
      <rect x="7.8" y="3.8" width="20.4" height="49.4" rx="10.2" fill="none"
        stroke="url(#edge-light)" stroke-width=".85" opacity="{.025 + light * .40:.4f}"/>
      <path d="M10 16v24" stroke="#f4e5c8" stroke-opacity=".14" stroke-width="1.2" stroke-linecap="round"/>
      <path d="M11 10q3-5 7-5" fill="none" stroke="#fff1d0" stroke-opacity=".18" stroke-width=".7"/>
      <path d="M26 18v25" stroke="#d8bd8e" stroke-opacity=".07" stroke-width=".7"/>
    </svg>'''.encode()


def frames():
    global _FRAMES
    if _FRAMES is not None:
        return _FRAMES
    folder = CACHE_DIR / 'nixie-glass-v4-fluid'
    folder.mkdir(parents=True, exist_ok=True)
    result = []
    for index in range(FRAME_COUNT):
        path = folder / f'{index:03}.png'
        if path.exists():
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
        else:
            loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
            loader.write(tube_svg(index / (FRAME_COUNT - 1)))
            loader.close()
            pixbuf = loader.get_pixbuf()
            pixbuf.savev(str(path), 'png', [], [])
        result.append(pixbuf)
    _FRAMES = result
    return result


class NixieSpectrum(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.get_accessible().set_description('Газоразрядный спектр · 9 частотных полос звука Spotify')
        self.frames = frames()
        self.full_frames = self.frames
        self.mini_frames = None
        self.compact = False
        self.levels = [0.0] * 9
        self.indices = [-1] * 9
        self.tubes = []
        for _ in range(9):
            image = Gtk.Image()
            image.set_size_request(WIDTH, HEIGHT)
            self.pack_start(image, False, False, 0)
            self.tubes.append(image)
        self.set_levels([0.0] * 9)

    def set_levels(self, levels):
        self.levels = list(levels[:9])
        for index, level in enumerate(levels[:9]):
            frame = round(max(0.0, min(1.0, level)) * (FRAME_COUNT - 1))
            if frame != self.indices[index]:
                self.tubes[index].set_from_pixbuf(self.frames[frame])
                self.indices[index] = frame

    def set_compact(self, compact):
        if self.compact == compact:
            return
        self.compact = compact
        if compact and self.mini_frames is None:
            self.mini_frames = [p.scale_simple(MINI_WIDTH, MINI_HEIGHT, GdkPixbuf.InterpType.BILINEAR)
                                for p in self.full_frames]
        self.frames = self.mini_frames if compact else self.full_frames
        self.set_spacing(3 if compact else 5)
        for image in self.tubes:
            image.set_size_request(MINI_WIDTH if compact else WIDTH, MINI_HEIGHT if compact else HEIGHT)
        self.indices = [-1] * 9
        self.set_levels(self.levels)
