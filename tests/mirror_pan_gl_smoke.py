"""Offline real-framebuffer checks for the sideways mirror-room renderer.

Run on an isolated X display. Software GL is enabled only in this fixture;
production keeps its normal renderer selection. All textures are generated.
No desktop windows, audio, account data or network media are accessed.
"""
import ctypes as C
from pathlib import Path
import sys
import time
from unittest.mock import patch

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mirror_pan_gl import MirrorPanGL
from mirror_facet_atlas import bake

WIDTH, HEIGHT = 384, 216


def settle(predicate, limit=7):
    until = time.monotonic() + limit
    context = GLib.MainContext.default()
    while not predicate() and time.monotonic() < until:
        for _ in range(12):
            if not context.pending():
                break
            context.iteration(False)
        time.sleep(.002)
    assert predicate(), 'The isolated mirror GL frame did not arrive'


def synthetic():
    """Periodic horizontal colours plus a vertical orientation reference."""
    yy, xx = np.mgrid[:HEIGHT, :WIDTH]
    rgba = np.empty((HEIGHT, WIDTH, 4), np.uint8)
    rgba[..., 0] = 110 + 80 * np.cos(xx * np.pi * 10 / WIDTH)
    rgba[..., 1] = 30 + 165 * yy / (HEIGHT - 1)
    rgba[..., 2] = 75 + 40 * np.sin(xx * np.pi * 6 / WIDTH)
    rgba[..., 3] = 192
    bgra = np.empty_like(rgba)
    for target, source in enumerate((2, 1, 0)):
        bgra[..., target] = (rgba[..., source].astype(np.uint16) * 192 + 127) // 255
    bgra[..., 3] = 192
    return WIDTH, HEIGHT, (bgra.tobytes(),)


def straight(pixels):
    return pixels[..., :3].astype(float) * 255 / np.maximum(1, pixels[..., 3, None])


class Frames:
    def __init__(self):
        self.window = Gtk.Window(title='Ember mirror panorama · isolated fixture')
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.area = Gtk.GLArea()
        self.area.set_required_version(3, 2)
        self.area.set_use_es(False)
        self.area.set_has_alpha(True)
        self.area.set_auto_render(False)
        self.area.set_size_request(WIDTH, HEIGHT)
        self.window.add(self.area)
        self.area.connect('render', self.render)
        self.area.connect('unrealize', self.release)
        self.driver = self.sentinel = None
        self.buffer = 0
        self.request = self.result = self.error = None
        self.serial = self.uploads = self.state_checks = 0
        self.released = False
        self.window.show_all()
        settle(lambda: self.area.get_realized())

    def prepare(self):
        self.driver = MirrorPanGL(allow_software=True)
        self.sentinel = MirrorPanGL(allow_software=True)
        original = self.driver.functions['TexImage2D']
        def upload(*args):
            self.uploads += 1
            return original(*args)
        self.driver.functions['TexImage2D'] = upload
        for name, result, args in (
                ('GenBuffers', None, (C.c_int, C.POINTER(C.c_uint))),
                ('DeleteBuffers', None, (C.c_int, C.POINTER(C.c_uint)))):
            function = getattr(self.driver.lib, 'gl' + name)
            function.restype, function.argtypes = result, args
            self.driver.functions[name] = function
        value = C.c_uint()
        self.driver.call('GenBuffers', 1, C.byref(value))
        self.buffer = value.value

    def state(self):
        driver = self.driver
        viewport = (C.c_int * 4)()
        driver.call('GetIntegerv', 0x0BA2, viewport)
        active = driver.integer(0x84E0)
        bindings = []
        for unit in (0x84C0, 0x84C3):
            driver.call('ActiveTexture', unit)
            bindings.append(driver.integer(0x8069))
        driver.call('ActiveTexture', active)
        return (driver.integer(0x8B8D), driver.integer(0x85B5), active,
                tuple(bindings), bool(driver.call('IsEnabled', 0x0BE2)),
                tuple(viewport), tuple(driver.integer(key) for key in
                                      (0x0CF5, 0x0CF2, 0x0CF3, 0x0CF4, 0x88EF)))

    def set_sentinel_state(self):
        driver, sentinel = self.driver, self.sentinel
        driver.call('UseProgram', sentinel.program)
        driver.call('BindVertexArray', sentinel.vao)
        driver.call('ActiveTexture', 0x84C0)
        driver.call('BindTexture', 0x0DE1, sentinel.room_texture)
        driver.call('ActiveTexture', 0x84C3)
        driver.call('BindTexture', 0x0DE1, sentinel.previous_texture)
        driver.call('Enable', 0x0BE2)
        driver.call('Viewport', 7, 9, WIDTH - 17, HEIGHT - 21)
        for key, value in ((0x0CF5, 8), (0x0CF2, 17), (0x0CF3, 2), (0x0CF4, 3)):
            driver.call('PixelStorei', key, value)
        driver.call('BindBuffer', 0x88EC, self.buffer)

    def render(self, area, _context):
        try:
            if area.get_error():
                raise RuntimeError(str(area.get_error()))
            if self.driver is None:
                self.prepare()
            if self.request is None:
                return True
            width = area.get_allocated_width() * area.get_scale_factor()
            height = area.get_allocated_height() * area.get_scale_factor()
            assert (width, height) == (WIDTH, HEIGHT), 'Run with GDK_SCALE=1'
            self.set_sentinel_state()
            before = self.state()
            atlas, drift, optics, palette = self.request
            self.driver.draw(width, height, atlas, drift, optics, palette)
            assert self.state() == before, 'Mirror draw leaked state into the GTK GL context'
            self.state_checks += 1
            self.driver.call('Finish')
            read = self.driver.lib.glReadPixels
            read.restype = None
            read.argtypes = [C.c_int, C.c_int, C.c_int, C.c_int,
                             C.c_uint, C.c_uint, C.c_void_p]
            raw = (C.c_ubyte * (width * height * 4))()
            read(0, 0, width, height, 0x1908, 0x1401, raw)
            self.result = np.frombuffer(raw, np.uint8).reshape(height, width, 4)[::-1].copy()
            error = self.driver.lib.glGetError
            error.restype, error.argtypes = C.c_uint, []
            assert error() == 0, 'Mirror fixture left an OpenGL error'
        except Exception as error:
            self.error = error
        finally:
            self.serial += 1
        return True

    def capture(self, atlas, drift=0., optics=None, palette=None):
        serial = self.serial
        self.request = atlas, drift, optics, palette
        self.area.queue_render()
        settle(lambda: self.serial > serial)
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result.copy()

    def release(self, area):
        area.make_current()
        if not area.get_error():
            if self.sentinel is not None:
                self.sentinel.close()
            if self.driver is not None:
                if self.buffer:
                    self.driver.call('DeleteBuffers', 1, C.byref(C.c_uint(self.buffer)))
                self.driver.close()
        self.driver = self.sentinel = None
        self.buffer = 0
        self.released = True

    def close(self):
        self.window.destroy()


with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected fixture network access')):
    frames = Frames()
    atlas = synthetic()
    try:
        still = frames.capture(atlas)
        print('Mirror GL renderer:',frames.driver.renderer,flush=True)
        assert frames.uploads == 1, 'A mirror panorama uploads once when first selected'
        assert np.all(still[..., :3] <= still[..., 3, None] + 1), 'Shader output must remain premultiplied'
        centre = still[HEIGHT // 3:HEIGHT * 2 // 3, WIDTH * 3 // 8:WIDTH * 5 // 8]
        assert np.max(centre) == 0, 'The fixed listening area must remain transparent and quiet'
        assert still[0, 0, 3] >= 190, 'The edge must show the actual glass material'
        assert np.count_nonzero((still[..., 3] > 0) & (still[..., 3] < 190)) > WIDTH * HEIGHT * .2, \
            'The vignette needs a soft shoulder rather than a hard transparent cutout'

        shift = 24
        moved = frames.capture(atlas, shift / WIDTH)
        assert np.max(np.abs(moved[..., 3].astype(int) - still[..., 3].astype(int))) <= 1, \
            'The vignette must stay fixed while the material moves'
        old, new = straight(still), straight(moved)
        shifted = np.roll(old, shift, axis=1)
        valid = (moved[..., 3] > 64) & (np.roll(still[..., 3], shift, axis=1) > 64)
        error = np.abs(new[..., 0] - shifted[..., 0])[valid]
        assert error.mean() < 2 and np.percentile(error, 99) < 6, \
            ('Glass must move positively along x, retaining its original colour', error.mean())
        wrong = np.roll(old, -shift, axis=1)
        assert np.abs(new[..., 0] - wrong[..., 0])[valid].mean() > 15, \
            'The fixture must distinguish a leftward movement from the requested rightward pan'
        assert np.max(np.abs(moved[..., 1].astype(int) - still[..., 1].astype(int))) <= 1, \
            'Horizontal motion must not move the vertical texture reference'
        assert old[HEIGHT - 20, 10, 1] - old[20, 10, 1] > 100, \
            'The source must retain its top-to-bottom orientation'
        wrapped = frames.capture(atlas, 1.)
        assert np.max(np.abs(wrapped.astype(int) - still.astype(int))) <= 1, \
            'A whole horizontal period must close without a seam or flash'
        before = frames.capture(atlas, 1. - 1 / (WIDTH * 100))
        after = frames.capture(atlas, 1. + 1 / (WIDTH * 100))
        assert np.max(np.abs(before.astype(int) - after.astype(int))) <= 2, \
            'Crossing the repeat seam must preserve fractional-pixel continuity'

        uploads = frames.uploads
        for index in range(60):
            current = frames.capture(atlas, .12 + index / (WIDTH * 3))
            assert np.all(current[..., :3] <= current[..., 3, None] + 1)
        assert frames.uploads == uploads, 'Uniform animation must not upload a texture on each frame'
        assert frames.state_checks >= 65, 'Every real frame must preserve its caller GL state'

        actual = bake()
        glass = frames.capture(actual, .137)
        assert frames.uploads == uploads + 1, 'A replacement material uploads exactly once'
        assert np.max(glass[..., 3]) > 50
        visible = glass[..., 3] > 30
        assert np.count_nonzero(visible) > WIDTH * HEIGHT * .15
        detail = straight(glass)[visible].mean(axis=1)
        assert np.percentile(detail, 95) - np.percentile(detail, 5) > 20, \
            'The actual generated material must retain visible bright and dark glass faces'
        assert np.max(glass[HEIGHT // 3:HEIGHT * 2 // 3, WIDTH * 3 // 8:WIDTH * 5 // 8]) == 0
        assert np.all(glass[..., :3] <= glass[..., 3, None] + 1)
        frames.capture(actual, .14)
        assert frames.uploads == uploads + 1

        # The optical weave evolves even at a fixed panorama position. Audio
        # changes light locally, without moving the room vertically or making
        # a whole-window exposure flash. All sources remain the same texture.
        response=(0.,.55,.45,.35)
        character=(.65,.40,.55)
        phases=(.5,1.2,2.3)
        optics=(response,character,phases)
        quiet=frames.capture(actual,.137,optics)
        evolved=frames.capture(actual,.137,(response,character,(1.2,1.6,2.55)))
        other=frames.capture(actual,.137,(response,(.25,.75,.25),phases))
        for candidate in (quiet,evolved,other):
            assert np.max(candidate[HEIGHT//3:HEIGHT*2//3,WIDTH*3//8:WIDTH*5//8])==0
            assert np.all(candidate[...,:3]<=candidate[...,3,None]+1)
        assert np.abs(evolved[...,:3].astype(int)-quiet[...,:3].astype(int)).mean()>.2, \
            'The reflected pattern must evolve beyond a plain sliding wallpaper'
        assert np.abs(other[...,:3].astype(int)-quiet[...,:3].astype(int)).mean()>.15, \
            'Different song profiles must produce distinct optical compositions'
        beat=frames.capture(actual,.137,((1.,.55,.45,.35),character,phases))
        difference=beat[...,:3].astype(int)-quiet[...,:3].astype(int)
        assert difference.min()>=-1 and difference.max()<30
        assert np.count_nonzero(difference.max(axis=2)>2)>200, \
            'A measured beat should broaden visible local reflections'
        assert np.mean(np.abs(difference))<3, 'Beat accents must not flash the whole room'
        previous=quiet
        for index in range(1,61):
            phase=tuple(a+index/60*1.5*rate for a,rate in zip(phases,(.19,.113,.071)))
            current=frames.capture(actual,.137,(response,character,phase))
            assert np.abs(current[...,:3].astype(int)-previous[...,:3].astype(int)).max()<=5, \
                'A continuous optical phase must not snap between display frames'
            previous=current
        loop=frames.capture(actual,.137,(response,character,tuple(a+np.pi*2 for a in phases)))
        assert np.abs(loop.astype(int)-quiet.astype(int)).max()<=1, 'Wrapped light phases must be seamless'
        assert frames.uploads==uploads+1, 'Light, beat and profile changes must update uniforms only'

        red=frames.capture(actual,.137,optics,(.95,.2,.2,.95,.3,.2,.85))
        blue=frames.capture(actual,.137,optics,(.2,.3,.95,.2,.3,.95,.85))
        assert red[...,0].mean()>blue[...,0].mean()+.3
        assert blue[...,2].mean()>red[...,2].mean()+.3
        assert np.all(red[...,:3]<=red[...,3,None]+1) and np.all(blue[...,:3]<=blue[...,3,None]+1)
        assert np.max(red[HEIGHT//3:HEIGHT*2//3,WIDTH*3//8:WIDTH*5//8])==0
        restored=frames.capture(actual,.137,optics)
        assert np.abs(restored.astype(int)-quiet.astype(int)).max()<=1,'Missing artwork must clear previous palette uniforms'
        assert frames.uploads==uploads+1,'Artwork reflections must not upload another texture'

        driver = frames.driver
        textures = (driver.texture, driver.room_texture, driver.previous_texture)
        program, vao = driver.program, driver.vao
        frames.area.make_current()
        is_texture = driver.lib.glIsTexture
        is_texture.restype, is_texture.argtypes = C.c_ubyte, [C.c_uint]
        is_program = driver.lib.glIsProgram
        is_program.restype, is_program.argtypes = C.c_ubyte, [C.c_uint]
        is_vao = driver.lib.glIsVertexArray
        is_vao.restype, is_vao.argtypes = C.c_ubyte, [C.c_uint]
        assert is_texture(textures[0]) and is_program(program) and is_vao(vao)
        driver.close()
        driver.close()
        assert not any(is_texture(value) for value in textures)
        assert not is_program(program) and not is_vao(vao)
        assert driver.atlas is None
        frames.close()
        settle(lambda: frames.released)
        assert frames.driver is None, 'Unrealize must release the isolated renderer'
        print('PASS mirror panorama framebuffer: positive horizontal travel, fixed soft vignette, '
              'premultiplied detail, seamless repeat, varied optical weave, soft beat accents, '
              'uniform-only animation, GL state and cleanup')
    finally:
        frames.close()
