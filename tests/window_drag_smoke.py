"""Window gesture capture, threshold, click cancellation and input exclusions."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk
from window_drag import WindowDrag
window=Gtk.Window();row=Gtk.Box();window.add(row)
button=Gtk.Button(label='Play');row.add(button)
entry=Gtk.Entry();row.add(entry)
scale=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,100,1);row.add(scale)
window.show_all()
while Gtk.events_pending():Gtk.main_iteration_do(False)
drag=WindowDrag(window)
drag.manual=False
assert drag.gesture.get_propagation_phase()==Gtk.PropagationPhase.CAPTURE
class Gesture:
    def __init__(self):self.states=[]
    def get_last_updated_sequence(self):return None
    def get_last_event(self,_seq):return SimpleNamespace(x_root=10.,y_root=20.,time=123)
    def set_state(self,value):self.states.append(value)
gesture=Gesture()
with patch('window_drag.Gtk.get_event_widget',return_value=button),patch.object(window,'begin_move_drag') as move:
    drag.begin(gesture,0,0);drag.update(gesture,2,2)
    assert not gesture.states and not move.called,'A click must not become a drag'
    drag.update(gesture,32,0)
    move.assert_called_once_with(1,10,20,123)
    assert gesture.states==[Gtk.EventSequenceState.CLAIMED]
    assert drag.start is None
for control in (entry,scale):
    gesture=Gesture()
    with patch('window_drag.Gtk.get_event_widget',return_value=control):drag.begin(gesture,0,0)
    assert drag.start is None and gesture.states==[Gtk.EventSequenceState.DENIED]
gesture=Gesture()
gesture.get_last_event=lambda _seq:SimpleNamespace(x_root=10.,y_root=20.,time=123,state=Gdk.ModifierType.MOD1_MASK)
with patch('window_drag.Gtk.get_event_widget',return_value=scale),patch.object(window,'begin_move_drag') as move:
    drag.begin(gesture,0,0);drag.update(gesture,32,0)
    assert move.called,'Alt-drag must also move from interactive controls'
window.destroy()
print('PASS window drag: capture, click threshold, claimed drag, entry and slider input')
