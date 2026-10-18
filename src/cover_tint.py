"""A restrained cover tint, animated by GTK without repainting CSS every frame."""

import colorsys
import math

from gi.repository import GdkPixbuf, Gtk


BASE_COLOR = (44, 44, 41)
# Grunesphism keeps the dark surface legible: cover colour may shift it only gently.
MAX_TINT = 9


def cover_color(pixbuf):
    if pixbuf is None:
        return BASE_COLOR
    sample = pixbuf.scale_simple(24, 24, GdkPixbuf.InterpType.BILINEAR)
    pixels = sample.get_pixels()
    channels = sample.get_n_channels()
    stride = sample.get_rowstride()
    hues = []
    total = 0
    chroma = 0.0
    for y in range(sample.get_height()):
        for x in range(sample.get_width()):
            start = y * stride + x * channels
            if channels == 4 and pixels[start + 3] < 192:
                continue
            total += 1
            red, green, blue = (value / 255 for value in pixels[start:start + 3])
            hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
            if saturation < 0.12 or value < 0.12:
                continue
            weight = saturation ** 1.5 * (0.5 + 0.5 * value)
            hues.append((hue, weight))
            chroma += saturation
    if not hues or not total:
        return BASE_COLOR
    horizontal = sum(math.cos(hue * math.tau) * weight for hue, weight in hues)
    vertical = sum(math.sin(hue * math.tau) * weight for hue, weight in hues)
    weight_sum = sum(weight for _hue, weight in hues)
    if math.hypot(horizontal, vertical) < weight_sum * 0.12:
        hue = max(hues, key=lambda item: item[1])[0]
    else:
        hue = math.atan2(vertical, horizontal) / math.tau % 1.0
    pigment = colorsys.hsv_to_rgb(hue, 0.75, 1.0)
    luminance = sum(component * weight for component, weight
                    in zip(pigment, (0.2126, 0.7152, 0.0722)))
    direction = tuple(component - luminance for component in pigment)
    scale = max(abs(component) for component in direction)
    strength = min(1.0, chroma / total * 2.5)
    return tuple(round(base + component / scale * MAX_TINT * strength)
                 for base, component in zip(BASE_COLOR, direction))


class CoverTint:
    def __init__(self, card):
        self.color = None
        self.provider = Gtk.CssProvider()
        card.get_style_context().add_provider(
            self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.set_cover(None)

    def set_cover(self, pixbuf):
        color = cover_color(pixbuf)
        if color == self.color:
            return
        self.color = color
        red, green, blue = color
        self.provider.load_from_data(f'''
          .card {{
            background-color: rgb({red}, {green}, {blue});
            background-image: linear-gradient(to bottom right,
                rgba(255, 241, 206, 0.022), rgba(0, 0, 0, 0.08));
            transition-property: background-color;
            transition-duration: 1400ms;
            transition-timing-function: ease-in-out;
          }}
        '''.encode())
