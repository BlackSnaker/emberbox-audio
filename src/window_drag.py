"""Thresholded window movement through GTK's capture-phase gesture.

A click stays a click. Claiming a real drag cancels a child's pending click;
sliders, text input and scrollbars retain their own pointer gestures.
"""
from gi.repository import Gtk, Gdk


class WindowDrag:
    def __init__(self,window):
        self.window=window;self.start=None
        self.gesture=Gtk.GestureDrag.new(window)
        self.gesture.set_button(1)
        self.gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.gesture.connect('drag-begin',self.begin)
        self.gesture.connect('drag-update',self.update)
        self.gesture.connect('drag-end',lambda *_:self.clear())
        window.connect('unmap',lambda *_:self.clear())

    def clear(self):
        self.start=None

    def begin(self,gesture,_x,_y):
        self.clear()
        event=gesture.get_last_event(gesture.get_last_updated_sequence())
        if event is None:return
        widget=Gtk.get_event_widget(event)
        while widget and widget is not self.window:
            if isinstance(widget,(Gtk.Range,Gtk.Entry,Gtk.TextView)) and not (getattr(event,'state',0) & Gdk.ModifierType.MOD1_MASK):
                gesture.set_state(Gtk.EventSequenceState.DENIED);return
            widget=widget.get_parent()
        self.start=(event.x_root,event.y_root,event.time)

    def update(self,gesture,x,y):
        if self.start is None:return
        threshold=self.window.get_settings().get_property('gtk-dnd-drag-threshold')
        if max(abs(x),abs(y))<max(8,threshold):return
        root_x,root_y,stamp=self.start
        self.clear()
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.window.begin_move_drag(1,round(root_x),round(root_y),stamp)
