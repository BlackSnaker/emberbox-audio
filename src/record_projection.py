"""Project the jacket in one filtered pass into a reusable Cairo image."""
import ctypes as C
from ctypes.util import find_library
from functools import lru_cache
import math


ARGB32 = 0x20028888
PAINT_SOURCE, REPEAT_PAD, BILINEAR = 1, 2, 4
Transform = (C.c_int32 * 3) * 3


@lru_cache(maxsize=1)
def pixman_bindings():
    lib = C.CDLL(find_library('pixman-1') or 'libpixman-1.so.0')
    pointer, integer = C.c_void_p, C.c_int
    signatures = {
        'create_bits': (pointer, C.c_uint32, integer, integer, pointer, integer),
        'unref': (integer, pointer),
        'set_transform': (integer, pointer, C.POINTER(Transform)),
        'set_filter': (integer, pointer, integer, pointer, integer),
        'set_repeat': (None, pointer, integer),
        'composite32': (None, integer, pointer, pointer, pointer, *([integer] * 8)),
    }
    for name, (result, *args) in signatures.items():
        fn = getattr(lib, 'pixman_image_'+name)
        fn.restype, fn.argtypes = result, args
    return lib


class RecordProjection:
    def __init__(self, cairo):
        self.c = cairo
        self.lib = pixman_bindings()
        self.sources = {}
        self.surface = self.image = None
        self.capacity = 0

    def wrap(self, surface, size):
        self.c.cairo_surface_flush(surface)
        pixels = self.c.cairo_image_surface_get_data(surface)
        return self.lib.pixman_image_create_bits(ARGB32, size, size, pixels, size*4) if pixels else None

    def project(self, surface, texture_size, size, span, taper, bounds, scale):
        left, right, height = bounds
        x, y = math.floor(left*scale), math.floor(-height*scale)
        width, height = math.ceil(right*scale)-x, math.ceil(height*scale)-y
        required = max(width, height)
        if required > self.capacity:
            self.clear_buffer()
            capacity = (required+63)//64*64
            self.surface = self.c.cairo_image_surface_create(0, capacity, capacity)
            self.image = self.wrap(self.surface, capacity)
            if not self.image:
                self.clear_buffer()
                return None
            self.capacity = capacity
        source = self.sources.get(surface)
        if source is None:
            source = self.wrap(surface, texture_size)
            if not source:
                return None
            self.lib.pixman_image_set_repeat(source, REPEAT_PAD)
            self.lib.pixman_image_set_filter(source, BILINEAR, None, 0)
            self.sources[surface] = source

        x_step = 1/(size*span*scale)
        y_step = 1/(size*scale)
        self.c.cairo_surface_flush(self.surface)
        # Invert perspective in short spans using Pixman's fast bilinear
        # scaler. Bound the height error across a span to half a device pixel.
        band = max(1, min(24, int(1.2*span/abs(taper))))
        for column in range(0, width, band):
            count = min(band, width-column)
            start = (x+column)*x_step
            end = start+count*x_step
            u0 = start/(1+taper*start)
            u1 = end/(1+taper*end)
            sx = texture_size*(u1-u0)/count
            sy = texture_size*y_step/(1+taper*(start+end)/2)
            fixed = Transform((round(sx*65536), 0, round(texture_size*(.5+u0)*65536)),
                              (0, round(sy*65536), round((texture_size/2+y*sy)*65536)),
                              (0, 0, 65536))
            if not self.lib.pixman_image_set_transform(source, C.byref(fixed)):
                return None
            self.lib.pixman_image_composite32(PAINT_SOURCE, source, None, self.image,
                                               0, 0, 0, 0, column, 0, count, height)
        self.c.cairo_surface_mark_dirty(self.surface)
        return self.surface, x/scale, y/scale

    def release(self, surface):
        image = self.sources.pop(surface, None)
        if image:
            self.lib.pixman_image_unref(image)

    def clear_buffer(self):
        if self.image:
            self.lib.pixman_image_unref(self.image)
        if self.surface:
            self.c.cairo_surface_destroy(self.surface)
        self.surface = self.image = None
        self.capacity = 0
