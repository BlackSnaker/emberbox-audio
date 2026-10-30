"""Real GTK headphone controls at desktop and small-screen sizes."""
import os,sys,time,tempfile
from pathlib import Path
from unittest.mock import Mock
root=tempfile.TemporaryDirectory(prefix='ember-headphones-')
os.environ['XDG_CONFIG_HOME']=root.name+'/config';os.environ['XDG_CACHE_HOME']=root.name+'/cache'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk
from scene_control import SceneControl
from headphone_profiles import settings


def settle(seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.005)


apple=Mock();scene={'mode':'headphones','preference':'headphones','angle':30,'hrtf':0,'sofa':'',
    'headphones':settings({'profile':'buds4-pro'}),'device':'Samsung Galaxy Buds4 Pro','bluetooth':True,'codec':'aac'}
apple.state={'spatial':{'scene':scene}}
w=Gtk.Window();w.get_style_context().add_class('scene-popover');control=SceneControl(apple);w.add(control);w.show_all();settle(.85)
assert control.headphone_box.get_visible();assert control.tuning.model.get_active_id()=='buds4-pro'
assert not control.tuning.scales['strength'].get_sensitive(),'An unmeasured model exposed fake calibration'
control.tuning.expander.set_expanded(True);settle(.25)
for n in (-1,1,2):control.tuning.scales['bass'].set_value(n)
settle(.2);assert apple.set_scene.call_args.kwargs['headphones']['bass']==2
assert apple.set_scene.call_count==1,'A slider storm was not debounced'
scene['headphones']=settings({'profile':'buds4-pro','bass':2});control.refresh();settle(.2)
control.tuning.compare.clicked();settle(.2);assert apple.set_scene.call_args.kwargs['headphones']['bypass'] is True
scene['headphones']['bypass']=True;control.refresh()
control.tuning.model.set_active_id('airpods-pro-2');settle(.2)
scene['headphones']=settings(apple.set_scene.call_args.kwargs['headphones']);control.refresh()
assert control.tuning.scales['strength'].get_sensitive()
control.ab.clicked();apple.set_scene.assert_called_with('headphones',hrtf=1,sofa='')
scene.update(hrtf=1);control.refresh();settle(.85)
assert w.get_allocated_width()<=460
assert w.get_allocated_height()<=Gdk.Display.get_default().get_monitor(0).get_workarea().height-80
assert control.scroll.get_vadjustment().get_upper()>control.scroll.get_vadjustment().get_page_size(),'Long controls must scroll'
control.scroll.get_vadjustment().set_value(control.scroll.get_vadjustment().get_upper());settle(.1)
control.tuning.reset();assert apple.set_scene.call_args.kwargs['headphones']==settings()
if '--preview' in sys.argv:
    scene['headphones']=settings({'profile':'buds4-pro'});scene.update(hrtf=0);control.pending=None;control.refresh()
    control.tuning.expander.set_expanded(False);control.scroll.get_vadjustment().set_value(0);settle(.9)
    Gdk.pixbuf_get_from_window(w.get_window(),0,0,w.get_allocated_width(),w.get_allocated_height()).savev('/tmp/ember-headphones.png','png',[],[])
w.hide();assert not control.timer and not control.diagram.tick and not control.tuning.timer
w.destroy();assert control.disposed
root.cleanup();print('PASS headphone GTK: honest profiles, debounced controls, matched A/B, HRTF switch, scrolling and cleanup')
