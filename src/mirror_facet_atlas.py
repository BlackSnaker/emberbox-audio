"""Bake the moving wall's projected mirror scales into two small edge strips.

The caller owns worker scheduling and the retained Cairo surfaces. Baking is
bounded and GTK-free; a live optical frame needs only four blended blits.
"""
import numpy as np
from PIL import Image, ImageDraw
from mirror_facet_model import PERIOD, facets


PHASES = 32
STRIP_WIDTH, STRIP_HEIGHT = 154, 360
_REFERENCE_WIDTH = 640
_ANTIALIAS = 2


def _rgba(red, green, blue, alpha):
    return tuple(round(255 * value) for value in (red, green, blue, alpha))


def _premultiplied_bgra(image):
    rgba = np.asarray(image, dtype=np.uint8)
    alpha = rgba[..., 3].astype(np.uint16)
    bgra = np.empty_like(rgba)
    for target, source in enumerate((2, 1, 0)):
        bgra[..., target] = (rgba[..., source].astype(np.uint16) * alpha + 127) // 255
    bgra[..., 3] = rgba[..., 3]
    return bgra.tobytes()


def _frame(age):
    size = (_REFERENCE_WIDTH * _ANTIALIAS, STRIP_HEIGHT * _ANTIALIAS)
    fill = Image.new('RGBA', size)
    upper = Image.new('RGBA', size)
    lower = Image.new('RGBA', size)
    face_draw, upper_draw, lower_draw = (ImageDraw.Draw(image) for image in (fill, upper, lower))
    line_width = max(1, round(.7 * _ANTIALIAS))
    for points, shade, alpha in facets(age, _REFERENCE_WIDTH, STRIP_HEIGHT):
        if alpha < .012:
            continue
        a, b, c, d = tuple((x * _ANTIALIAS, y * _ANTIALIAS) for x, y in points)
        face_draw.polygon((a, b, c, d), fill=_rgba(.115 + shade * .28,
                                                .14 + shade * .245,
                                                .18 + shade * .205, alpha))
        upper_draw.line((d, a, b), fill=_rgba(.92, .84, .68, alpha * (.06 + .16 * shade)),
                        width=line_width)
        lower_draw.line((b, c, d), fill=_rgba(.015, .025, .04, alpha * .6), width=line_width)
    # Separate planes reproduce source-over bevels instead of overwriting a
    # facet's alpha when ImageDraw strokes its translucent glass.
    fill.alpha_composite(upper)
    fill.alpha_composite(lower)
    strip = STRIP_WIDTH * _ANTIALIAS
    boxes = ((0, 0, strip, size[1]), (size[0] - strip, 0, size[0], size[1]))
    return tuple(_premultiplied_bgra(fill.crop(box).resize((STRIP_WIDTH, STRIP_HEIGHT),
                                                         Image.Resampling.LANCZOS))
                 for box in boxes)


def bake():
    """Return ``(154, 360, 32 (left_bytes, right_bytes) pairs)``.

    Each strip is premultiplied BGRA. Phase zero follows phase 31 smoothly;
    the duplicated endpoint at ``PERIOD`` is deliberately omitted. The atlas
    stores 14,192,640 bytes, independent of the eventual window dimensions.
    """
    return STRIP_WIDTH, STRIP_HEIGHT, tuple(_frame(phase * PERIOD / PHASES)
                                          for phase in range(PHASES))
