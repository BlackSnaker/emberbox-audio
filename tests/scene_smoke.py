"""Real GTK/vector preview: finite entrance, reversible morph, controls and cleanup."""
import sys,time
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk
from scene_control import SceneControl
from scene_art import scene_frame


def settle(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.005)


apple=Mock();scene={'mode':'speakers','preference':'speakers','angle':30,'hrtf':0,'device':'Bluetooth speaker pair','bluetooth':True,'codec':'sbc'}
apple.state={'spatial':{'scene':scene}}
w=Gtk.Window();w.get_style_context().add_class('scene-popover');control=SceneControl(apple);w.add(control);w.show_all()
settle(.2);assert 0<control.diagram.opening<1,'Entrance skipped its intermediate frames'
settle(.7);assert not control.diagram.tick
control.buttons['headphones'].clicked();apple.set_scene.assert_called_with('headphones')
assert control.diagram.target==1,'Visual feedback waited for backend polling'
scene.update(mode='headphones',preference='headphones');control.refresh();settle(.25)
assert 0<control.diagram.value<1,'Mode change did not animate'
scene.update(mode='speakers',preference='speakers',angle=40);control.refresh();settle(.85)
assert not control.diagram.tick;assert control.diagram.value==0;assert control.diagram.angle==40
scene.update(mode='headphones',preference='headphones');control.refresh();control.options.set_active_id('1');apple.set_scene.assert_called_with('headphones',hrtf=1)
scene.update(hrtf=1);control.refresh()
scene.update(mode='speakers',preference='speakers');control.refresh();control.options.set_active_id('20');apple.set_scene.assert_called_with('speakers',angle=20)
scene.update(angle=20);control.refresh()
settle(.85)
assert w.get_allocated_width()<=440 and w.get_allocated_height()<=620
assert scene_frame.cache_info().currsize<=16
if '--preview' in sys.argv:
    scene.update(mode='speakers',preference='speakers',angle=30);control.refresh();settle(.85)
    image=Gdk.pixbuf_get_from_window(w.get_window(),0,0,w.get_allocated_width(),w.get_allocated_height())
    image.savev('/tmp/ember-scene-control.png','png',[],[])
w.hide();assert not control.timer and not control.diagram.tick
w.destroy();assert not control.timer
print('PASS scene card: vector entrance, reversible scene/geometry morph, controls, bounded cache and no hidden timers')
