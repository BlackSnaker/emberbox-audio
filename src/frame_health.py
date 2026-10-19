"""Keep the desktop widget painting after cover/layout changes on XWayland."""
import json
import os
from pathlib import Path
import time
from gi.repository import Gdk,GLib,Gtk
from paths import APP_ID,CACHE_DIR


class FrameHealth:
    def __init__(self,window,animate):
        self.window,self.animate = window,animate
        self.last_frame = time.monotonic()
        self.frames = self.paints = self.recoveries = 0
        self.obscured = False
        self.closed = False
        self.tick = window.add_tick_callback(self._tick)
        window.add_events(Gdk.EventMask.VISIBILITY_NOTIFY_MASK)
        window.connect('visibility-notify-event',self._visibility)
        self.clock = window.get_frame_clock()
        self.paint_handler = self.clock.connect('after-paint',self._paint)
        self.path = Path(os.environ.get('XDG_RUNTIME_DIR',CACHE_DIR))/APP_ID/'ui-health.json'
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.timer = GLib.timeout_add(1000,self.check)

    def _tick(self,window,clock):
        self.last_frame = time.monotonic()
        self.frames += 1
        return self.animate(window,clock)

    def _paint(self,*_args):
        self.paints += 1
        return False

    def _visibility(self,_window,event):
        self.obscured = event.state == Gdk.VisibilityState.FULLY_OBSCURED
        return False

    def request_frame(self):
        if self.closed or not self.window.get_mapped():
            return
        self.window.queue_resize_no_redraw()
        self.window.queue_draw()
        native = self.window.get_window()
        if native:
            native.invalidate_rect(None,True)
        clock = self.window.get_frame_clock()
        if clock:
            clock.request_phase(Gdk.FrameClockPhase.UPDATE|Gdk.FrameClockPhase.LAYOUT|Gdk.FrameClockPhase.PAINT)

    def check(self):
        if self.closed:
            return False
        age = time.monotonic()-self.last_frame
        mapped = self.window.get_mapped()
        if mapped and not self.obscured and age>1.5:
            if self.tick:
                self.window.remove_tick_callback(self.tick)
            self.tick = self.window.add_tick_callback(self._tick)
            self.request_frame()
            self.recoveries += 1
        # Only counters and window health; no titles, account or music data.
        value = {'frames':self.frames,'paints':self.paints,'frameAgeMs':round(age*1000),
                 'mapped':mapped,'obscured':self.obscured,'recoveries':self.recoveries,
                 'inputGrab':Gtk.grab_get_current() is not None}
        try:
            temporary = self.path.with_suffix('.next.json')
            temporary.write_text(json.dumps(value))
            temporary.chmod(0o600)
            temporary.replace(self.path)
        except OSError:pass
        return True

    def close(self):
        if self.closed:
            return
        self.closed = True
        GLib.source_remove(self.timer)
        if self.tick:
            self.window.remove_tick_callback(self.tick)
        if self.clock.handler_is_connected(self.paint_handler):
            self.clock.disconnect(self.paint_handler)
