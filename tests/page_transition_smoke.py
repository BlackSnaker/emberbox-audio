"""Retained page pixels, presentation-clock motion, interruption and cleanup."""
import ctypes as C
import sys,time
from pathlib import Path
from unittest.mock import patch
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import page_transition as page


def settle(seconds=.04):
    deadline=time.monotonic()+seconds;context=GLib.MainContext.default()
    while time.monotonic()<deadline:
        for _ in range(3):
            if context.pending():context.iteration(False)
        time.sleep(.002)


window=Gtk.Window();window.set_default_size(720,360)
stack=Gtk.Stack();stack.set_transition_type(Gtk.StackTransitionType.NONE)
for name in ('old','new'):
    label=Gtk.Label(label=name);label.set_name(name);stack.add_named(label,name)
provider=Gtk.CssProvider();provider.load_from_data(b'#old { background: #203040; } #new { background: #80a0c0; }')
Gtk.StyleContext.add_provider_for_screen(window.get_screen(),provider,620)
fade=page.PageTransition(stack);window.add(fade);window.show_all();settle(.15)
try:
    with patch.object(page,'snapshot',wraps=page.snapshot) as capture:
        fade.prepare();stack.set_visible_child_name('new');fade.begin()
        assert fade.active and stack.get_opacity()==0. and stack.get_mapped()
        if fade.tick:fade.remove_tick_callback(fade.tick);fade.tick=0
        fade.progress=.5;fade.layer.queue_draw();settle()
        w,h=fade.size;c=fade.c;c.cairo_surface_flush(fade.canvas)
        pixels=np.frombuffer(C.string_at(c.cairo_image_surface_get_data(fade.canvas),w*h*4),np.uint8).reshape(h,w,4)
        assert np.max(np.abs(pixels[12,12,:3].astype(int)-np.array((128,104,80))))<=2,'Premultiplied frames must actually mix at the midpoint'
        assert capture.call_count==2,'Capture each page once, never on animation frames'
        prior=fade.canvas
        fade.prepare();assert fade.before and not fade.active and stack.get_opacity()==1.
        stack.set_visible_child_name('old');fade.begin()
        deadline=time.monotonic()+2;frames=[]
        while fade.active and time.monotonic()<deadline:
            settle(.01);frames.append(fade.progress)
        assert any(.1<p<.9 for p in frames) and not fade.active and not fade.tick
        assert fade.before is fade.after is fade.canvas is fade.cr is None and stack.get_opacity()==1.
        assert capture.call_count==4,'Rapid retargeting must capture only its visible composite and destination'
        fade.prepare();stack.set_visible_child_name('new');fade.begin()
        settings=window.get_settings();settings.set_property('gtk-enable-animations',False)
        assert not fade.active and fade.before is None and stack.get_opacity()==1.
        before=capture.call_count;fade.prepare();fade.begin();assert capture.call_count==before
        settings.set_property('gtk-enable-animations',True)
        fade.prepare();stack.set_visible_child_name('old');fade.begin();window.hide()
        assert not fade.active and fade.canvas is None and stack.get_opacity()==1.
        window.show_all();settle();fade.prepare();stack.set_visible_child_name('new');fade.begin()
        fade.resized(fade,type('Area',(),{'width':1,'height':1})())
        assert not fade.active and fade.canvas is None and stack.get_opacity()==1.
    print('PASS retained page transitions: mixed pixels, bounded captures, intermediate frames, rapid retarget, stable live mapping, reduced motion, hide/resize and released surfaces')
finally:
    fade.close();fade.close();window.destroy()
    Gtk.StyleContext.remove_provider_for_screen(window.get_screen(),provider)
