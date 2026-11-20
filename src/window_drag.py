"""Thresholded window movement through GTK's capture-phase gesture.

A click stays a click. Claiming a real drag cancels a child's pending click;
sliders, text input and scrollbars retain their own pointer gestures.
"""
from gi.repository import Gtk, Gdk
from hardware_controls import VolumeKnob


class WindowDrag:
    def __init__(self,window, moved=None):
        self.window=window;self.start=None;self.origin=None;self.moving=False
        self.moved=moved
        self.manual=window.get_display().__gtype__.name.startswith('GdkX11')
        self.gesture=Gtk.GestureDrag.new(window)
        self.gesture.set_button(1)
        self.gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.gesture.connect('drag-begin',self.begin)
        self.gesture.connect('drag-update',self.update)
        self.gesture.connect('drag-end',lambda *_:self.end())
        self.gesture.connect('cancel',lambda *_:self.end())
        window.connect('unmap',lambda *_:self.clear())

    def clear(self):
        self.start=None;self.origin=None;self.moving=False

    def end(self):
        moving=self.moving
        self.clear()
        if moving and self.moved:self.moved()


    def begin(self,gesture,_x,_y):
        self.clear()
        event=gesture.get_last_event(gesture.get_last_updated_sequence())
        if event is None:return
        widget=Gtk.get_event_widget(event)
        while widget and widget is not self.window:
            own_input = isinstance(widget,(Gtk.Range,Gtk.Entry,Gtk.TextView,VolumeKnob)) or (
                isinstance(widget,Gtk.EventBox) and isinstance(widget.get_child(),Gtk.ProgressBar))
            if own_input and not (getattr(event,'state',0) & Gdk.ModifierType.MOD1_MASK):
                gesture.set_state(Gtk.EventSequenceState.DENIED);return
            widget=widget.get_parent()
        self.start=(event.x_root,event.y_root,event.time)
        self.origin=tuple(self.window.get_position())

    def update(self,gesture,x,y):
        if self.start is None:return
        threshold=self.window.get_settings().get_property('gtk-dnd-drag-threshold')
        if not self.moving and max(abs(x),abs(y))<max(8,threshold):return
        root_x,root_y,stamp=self.start
        if not self.moving:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            if not self.manual:
                self.clear()
                self.window.begin_move_drag(1,round(root_x),round(root_y),stamp)
                return
            self.moving=True
        # GNOME ignores WM move requests for a DESKTOP-type surface. On X11
        # use global pointer coordinates instead; window-relative gesture
        # deltas would feed back as the window itself moves.
        event=gesture.get_last_event(gesture.get_last_updated_sequence())
        if event is not None:
            self.window.move(round(self.origin[0]+event.x_root-root_x),
                             round(self.origin[1]+event.y_root-root_y))
