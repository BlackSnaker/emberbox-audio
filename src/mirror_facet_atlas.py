"""One seamless glass panorama, baked once off GTK and translated continuously."""
import math
import numpy as np
from PIL import Image

WIDTH, HEIGHT = 768, 432


def _frame():
    # Oversampling keeps hairline silver bevels soft when the small cached
    # material is enlarged. All periodic functions close exactly along x.
    aa = 2
    yy, xx = np.mgrid[:HEIGHT*aa, :WIDTH*aa].astype(np.float32)
    u, v = (xx + .5) / (WIDTH*aa), (yy + .5) / (HEIGHT*aa)
    gy = v * 18
    row = np.floor(gy)
    gx = u * 32 + (row % 2) * .5 + .21 * np.sin(v * math.tau)
    column = np.floor(gx) % 32
    x, y = gx % 1, gy % 1
    edge = np.minimum.reduce((x, 1-x, y, 1-y))
    face = np.clip(edge / .023, 0, 1)
    reflected = (.5 + .5 * np.cos(column * math.tau / 8 + row * .72)) ** 3
    # A reflected softbox traverses a gently tilted silver face. It has a
    # narrow champagne edge and a broad cool shoulder, not flat stone fills.
    stripe = .18 + .57 * (.5 + .5 * np.sin(column * math.tau / 8 - row * .41))
    slope = x * .72 + y * .28
    silver = np.exp(-((slope-stripe) / .19)**2) * (.25 + .75*reflected)
    gold = np.exp(-((slope-stripe-.12) / .042)**2) * reflected
    cool = (.5 + .5*np.cos(u*math.tau*4 + v*4.1))**4
    base = np.empty((*u.shape, 3), np.float32)
    base[:] = (29, 39, 53)
    base += silver[...,None] * np.array((130, 137, 144))
    base += gold[...,None] * np.array((95, 70, 30))
    base += cool[...,None] * np.array((17, 26, 40))
    base *= (.83 + .17*y)[...,None]
    bevel = np.exp(-((edge-.028)/.013)**2)
    base += bevel[...,None] * np.array((69, 68, 59))
    alpha = (.40 + .12*reflected) * face
    rgba = np.empty((*u.shape, 4), np.uint8)
    rgba[...,:3] = np.clip(base, 0, 255)
    rgba[...,3] = np.clip(alpha*255, 0, 255)
    # Resize straight RGBA with Pillow's premultiplied-aware filter, then keep
    # native premultiplied BGRA for Cairo. No decoded image survives the job.
    image = Image.fromarray(rgba).resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)
    pixels = np.asarray(image,dtype=np.uint8)
    a = pixels[...,3].astype(np.uint16)
    bgra = np.empty_like(pixels)
    for target,source in enumerate((2,1,0)):
        bgra[...,target] = (pixels[...,source].astype(np.uint16)*a+127)//255
    bgra[...,3] = pixels[...,3]
    return bgra.tobytes()


def bake():
    """768 x 432 immutable BGRA, 1.27 MiB independent of window size."""
    return WIDTH, HEIGHT, (_frame(),)


def vignette(width=384,height=216):
    """Fixed A8 mask; the centre stays quiet while glass passes behind it."""
    yy,xx = np.mgrid[:height,:width].astype(np.float32)
    x,y = (2*xx+1)/width-1,(2*yy+1)/height-1
    t = np.clip((np.abs(x)-.50)/.48,0,1)
    return width,height,(255*t*t*(3-2*t)).astype(np.uint8).tobytes()
