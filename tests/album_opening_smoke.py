"""Finite opacity choreography must leave controls/layout alive and clean up."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
from album_opening import AlbumOpening


def settle(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.005)


window=Gtk.Window();body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);window.add(body)
hero=Gtk.Button(label='Album');records=Gtk.Button(label='Recording')
body.pack_start(hero,False,False,0);body.pack_start(records,False,False,0);window.show_all();settle(.1)
settings=Gtk.Settings.get_default();original=settings.get_property('gtk-enable-animations')
opening=AlbumOpening(body)
try:
    settings.set_property('gtk-enable-animations',True)
    geometries=[w.get_allocation() for w in (hero,records)]
    opening.begin(hero,records);settle(.25)
    assert opening.busy and .08<hero.get_opacity()<1 and .08<records.get_opacity()<hero.get_opacity()
    clicks=[];records.connect('clicked',lambda *_:clicks.append(True));records.clicked();assert clicks
    assert [(w.get_allocated_width(),w.get_allocated_height()) for w in (hero,records)]==[(a.width,a.height) for a in geometries]
    settle(.5);assert not opening.busy and hero.get_opacity()==records.get_opacity()==1
    opening.begin(hero,records);settle(.1);window.hide();assert not opening.busy
    assert hero.get_opacity()==records.get_opacity()==1
    window.show_all();settle(.05);settings.set_property('gtk-enable-animations',False)
    opening.begin(hero,records);assert not opening.busy
    assert hero.get_opacity()==records.get_opacity()==1
    settings.set_property('gtk-enable-animations',True)
    opening.begin(hero,records);window.destroy();assert not opening.busy and not opening.widgets
finally:settings.set_property('gtk-enable-animations',original);window.destroy()
print('PASS album opening: finite frame clock, stagger, stable layout, live controls, unmap, reduced motion and disposal')
