"""Quiet wine-coloured cloth and finite, artwork-owned lamplight.

Only a small static field is rasterised. No downloaded texture, random flicker,
beat response or continuous image generation is involved.
"""
from functools import lru_cache
import math
import numpy as np

BASE = (27, 13, 20)
NEUTRAL = (.76, .49, .28, .42, .22, .27)
DURATION = 3.2


def ease(value):
    t = max(0., min(1., value))
    return t*t*t*(t*(t*6.-15.)+10.)


def colours(swatches):
    """Retain artwork hue while bounding the emitted light, including white art."""
    if not swatches or len(swatches) < 7 or not swatches[6]:
        return NEUTRAL
    values = tuple(float(v) for v in swatches[:6])
    if not all(math.isfinite(v) for v in values):
        return NEUTRAL
    # The actual cover colours remain recognisable; a very small tungsten
    # component keeps cool/monochrome artwork at home in the wine material.
    tungsten = (1., .67, .36)
    return tuple(max(0., min(1., v))*.86+tungsten[i % 3]*.14 for i, v in enumerate(values))


class Light:
    """Retarget from the visible colour, with no jumps during rapid skips."""
    def __init__(self):
        self.values = self.start = self.target = NEUTRAL
        self.elapsed = DURATION

    @property
    def active(self):
        return self.elapsed < DURATION

    def set(self, target, animate=True):
        target = tuple(target)
        if target == self.target:
            return False
        self.start, self.target = self.values, target
        self.elapsed = 0. if animate else DURATION
        if not animate:
            self.values = target
        return True

    def advance(self, seconds):
        if not math.isfinite(seconds) or seconds <= 0.:
            return self.values
        self.elapsed = min(DURATION, self.elapsed+seconds)
        if self.elapsed >= DURATION:
            self.values = self.target
            return self.values
        t = ease(self.elapsed/DURATION)
        self.values = tuple(a+(b-a)*t for a, b in zip(self.start, self.target))
        return self.values

    def settle(self):
        self.elapsed = DURATION
        self.values = self.target


@lru_cache(maxsize=5)
def cloth(width, height):
    """RGB cloth at <=640px, stable nap with broad, irregular velvet folds."""
    ratio = min(1., 640/max(1, width, height))
    w, h = max(1, round(width*ratio)), max(1, round(height*ratio))
    x = np.linspace(0., 1., w, dtype=np.float32)[None, :]
    y = np.linspace(0., 1., h, dtype=np.float32)[:, None]
    broad = np.exp(-((x-.23)/.63)**2-((y-.26)/.90)**2)
    folds = (.5+.5*np.sin(x*18.8+.6*np.sin(x*7.1)+y*.22))**2
    folds = folds*(.8+.2*np.cos(y*2.1))
    pixels = np.empty((h, w, 3), dtype=np.float32)
    pixels[:] = BASE
    pixels += broad[..., None]*np.array((13., 3.7, 5.9), np.float32)
    pixels += folds[..., None]*np.array((3.0, .72, 1.25), np.float32)
    # Directional fine nap, not a repeating photographic curtain pattern.
    xx = np.arange(w, dtype=np.float32)[None, :]
    yy = np.arange(h, dtype=np.float32)[:, None]
    nap = np.sin(xx*2.13+yy*1.17)*np.sin(xx*.71-yy*2.71)*.38
    pixels += nap[..., None]
    lamp = np.exp(-((x-.91)/.34)**2-((y-.10)/.42)**2)
    pixels += lamp[..., None]*np.array((10.5, 6.3, 2.6), np.float32)
    vignette = np.clip(y*.46+((x-.5)**2)*.33, 0., .65)
    pixels = pixels*(1.-vignette[..., None])+np.array((15., 8., 13.))*vignette[..., None]
    return w, h, np.clip(pixels, 0, 255).astype(np.uint8).tobytes()
