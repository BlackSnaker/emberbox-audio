"""Real small-area refraction, retargeting and idle/reduced-motion cleanup."""
import ctypes as C
import sys,time
from pathlib import Path
from unittest.mock import patch
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import header_glass as glass


def settle(seconds=.04):
    deadline=time.monotonic()+seconds;context=GLib.MainContext.default()
    while time.monotonic()<deadline:
        for _ in range(3):
            if context.pending():context.iteration(False)
        time.sleep(.002)


window=Gtk.Window();window.get_style_context().add_class('ember-stage')
window.set_default_size(700,140)
provider=Gtk.CssProvider();provider.load_from_data(glass.CSS+b'''
window { background-color: #172224; }
.stage-header-glass { margin: 24px; }
.stage-tab { font-size: 13px; color: #ddd2b9; }
''')
Gtk.StyleContext.add_provider_for_screen(window.get_screen(),provider,620)
header=Gtk.Box();header.get_style_context().add_class('stage-header-glass');window.add(header)
nav=Gtk.Box(spacing=2);nav.get_style_context().add_class('stage-top-nav')
buttons=[]
for title in ('Listening','Collection','Queue','DJ','Mashups','Karaoke'):
    button=Gtk.ToggleButton(label=title);button.get_style_context().add_class('stage-tab')
    nav.pack_start(button,False,False,0);buttons.append(button)
lens=glass.GlassNavigation(nav);header.pack_start(lens,False,False,0)
window.show_all();settle(.2)

def select(index):
    for i,button in enumerate(buttons):button.set_active(i==index)
    lens.select(buttons[index])

def wait():
    deadline=time.monotonic()+3
    while lens.active and time.monotonic()<deadline:settle(.02)
    assert not lens.active and not lens.tick
    assert lens.frame is lens.canvas is lens.cr is None
    assert lens.nav.get_opacity()==1. and not lens.layer.get_visible()

try:
    select(0);geometry=window.get_size()
    with patch.object(glass,'snapshot',wraps=glass.snapshot) as capture:
        select(5);assert lens.active
        samples=[];refracted=False;deadline=time.monotonic()+3
        while lens.active and time.monotonic()<deadline:
            settle(.02);samples.append(lens.progress)
            if lens.active and .30<lens.progress<.70:
                w,h=lens.frame_size
                a=np.frombuffer(C.string_at(lens.c.cairo_image_surface_get_data(lens.frame),w*h*4),np.uint8).reshape(h,w,4)
                b=np.frombuffer(C.string_at(lens.c.cairo_image_surface_get_data(lens.canvas),w*h*4),np.uint8).reshape(h,w,4)
                x,y,rw,rh=lens.rect
                left,top=max(0,int(x+12)),max(0,int(y+8))
                right,bottom=min(w,int(x+rw-12)),min(h,int(y+rh-8))
                delta=np.abs(a[top:bottom,left:right,:3].astype(int)-b[top:bottom,left:right,:3].astype(int))
                refracted|=bool(np.count_nonzero(delta.max(axis=2)>18)>12)
        assert any(.1<p<.8 for p in samples) and refracted,'Moving glass must actually refract the cached letters'
        assert capture.call_count==1,'Do not recapture or rerasterise live GTK every frame'
        wait();assert window.get_size()==geometry
        select(0);settle(.16);previous=lens.rect
        select(3);assert lens.active and lens.start==previous,'An interrupted lens must continue from its visible position'
        wait()
        for theme in ('nocturne-theme','mirrorball-theme','christmas-theme'):
            window.get_style_context().add_class(theme);select(1);settle(.08);select(4);wait()
            window.get_style_context().remove_class(theme)
        select(0);settle(.06)
        settings=window.get_settings();settings.set_property('gtk-enable-animations',False)
        assert not lens.active and not lens.tick and lens.frame is None
        before=capture.call_count;select(2);assert capture.call_count==before and not lens.active
        settings.set_property('gtk-enable-animations',True)
        select(5);settle(.06);window.hide();assert not lens.active and lens.canvas is None
        window.show_all();settle(.1);select(0);settle(.06)
        lens.resized(lens,type('Allocation',(),{'width':1,'height':1})())
        assert not lens.active and lens.canvas is None
    print('PASS clear glass: real text refraction, intermediate frames, one cached strip, smooth retargeting, stable geometry, themes, reduced motion, hide/resize and cleanup')
finally:
    lens.close();lens.close();window.destroy()
    Gtk.StyleContext.remove_provider_for_screen(window.get_screen(),provider)
