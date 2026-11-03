"""Cached snow materials must match GTK pixels and leave children live."""
import os,sys,time,tempfile
from pathlib import Path
import gi
gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0')
from gi.repository import Gtk,GLib
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from winter_surface_cache import MaterialCache
import ctypes as C
from room_snapshot import bindings


def settle(seconds=.1):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        for _ in range(5):
            if not GLib.MainContext.default().pending():break
            GLib.MainContext.default().iteration(False)
        time.sleep(.002)

window=Gtk.Window();box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
box.get_style_context().add_class('fixture-material');window.add(box)
box.set_size_request(460,300);label=Gtk.Label(label='Live track and controls');box.pack_start(label,True,True,0)
button=Gtk.Button(label='Play');box.pack_end(button,False,False,0)
provider=Gtk.CssProvider();provider.load_from_data(b'''
.fixture-material { padding: 15px; border-radius: 25px; background-image: linear-gradient(135deg,#304237,#1b2b24);
 box-shadow: inset 0 2px rgba(255,220,160,.2), 0 8px 18px rgba(0,0,0,.25); border: 1px solid #735b3e; }
''');box.get_style_context().add_provider(provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+20)
window.show_all();settle(.2)
class Owner:enabled=False;failed=False;suspended=False
owner=Owner()
cache=MaterialCache(box,owner)
def pixels():
    cairo,gtk,pointer=bindings();a=box.get_allocation();scale=box.get_scale_factor()
    width,height=a.width*scale,a.height*scale
    cairo.cairo_surface_set_device_scale.restype=None
    cairo.cairo_surface_set_device_scale.argtypes=[C.c_void_p,C.c_double,C.c_double]
    surface=cairo.cairo_image_surface_create(0,width,height)
    cairo.cairo_surface_set_device_scale(surface,scale,scale);cr=cairo.cairo_create(surface)
    try:
        gtk.gtk_widget_draw(pointer(box.__gpointer__,None),cr);cairo.cairo_surface_flush(surface)
        return np.frombuffer(C.string_at(cairo.cairo_image_surface_get_data(surface),width*height*4),np.uint8).reshape(height,width,4).copy()
    finally:cairo.cairo_destroy(cr);cairo.cairo_surface_destroy(surface)

try:
    original=pixels();owner.enabled=True;cached=pixels()
    diff=np.abs(original.astype(int)-cached.astype(int))
    assert np.percentile(diff,99.9)<=2,('Cached GTK material differs from normal rendering',diff.max(),np.percentile(diff,99.9))
    builds=cache.builds
    for _ in range(10):pixels()
    assert cache.builds==builds,'Movement must reuse the same material surface'
    label.set_text('The next track is still live');settle(.05);changed=pixels()
    assert np.any(changed!=cached),'Children must not be frozen into the material'
    provider.load_from_data(b'.fixture-material { padding: 15px; border-radius: 25px; background: #512d36; border: 1px solid #a97856; }')
    settle(.1);restyled=pixels()
    assert cache.builds>builds and np.any(restyled!=changed),'Style changes must invalidate cached material'
    owner.suspended=True;pixels();assert cache.surface is None
    owner.suspended=False;cache.MAX_PIXELS=1;pixels();assert cache.surface is None,'Oversized cache must fall back to GTK'
    print('PASS GTK-equivalent material pixels, retained cache, live children and suspended cleanup')
finally:cache.close();window.destroy()
