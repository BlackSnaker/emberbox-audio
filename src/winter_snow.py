"""Frequent sparse, input-transparent snow; stopped when hidden or disabled."""
import random
import math
from itertools import zip_longest
import gi
gi.require_version('Gtk','3.0')
gi.require_version('Gdk','3.0')
from gi.repository import Gdk,Gtk,GLib
from winter_snow_model import SnowShower


class WinterSnow:
    def __init__(self,window,overlay,stage=False):
        self.window,self.overlay,self.stage=window,overlay,stage
        self.closed=self.enabled=self.failed=self.obscured=False
        self.painter=None;self.timer=self.tick=0;self.start_time=None;self.active=False
        self.model=SnowShower();self.random=random.Random();self.dots=[];self.targets=lambda:[]
        self.shelves=[];self.geometry_at=0.;self.geometry_size=None;self.damage_pixels=0
        self.area=Gtk.DrawingArea();self.area.set_has_window(False);self.area.set_app_paintable(True)
        self.area.set_no_show_all(True);self.area.set_halign(Gtk.Align.FILL);self.area.set_valign(Gtk.Align.FILL)
        self.area.set_can_focus(False)
        overlay.add_overlay(self.area);overlay.set_overlay_pass_through(self.area,True)
        self.signals=[(overlay,overlay.connect('map',lambda *_:self.schedule(first=True))),
                      (overlay,overlay.connect('unmap',lambda *_:self.pause()))]
        window.add_events(Gdk.EventMask.VISIBILITY_NOTIFY_MASK)
        self.signals.append((window,window.connect('visibility-notify-event',self.visibility)))
        settings=window.get_settings()
        self.signals.append((settings,settings.connect('notify::gtk-enable-animations',self.animations_changed)))

    def set_targets(self,getter):self.targets=getter;self.geometry_at=0.

    def eligible(self):
        return bool(not self.closed and self.enabled and not self.failed and not self.obscured
                    and self.overlay.get_mapped() and self.window.get_mapped()
                    and self.window.get_settings().get_property('gtk-enable-animations'))

    def set_enabled(self,enabled):
        self.enabled=bool(enabled);self.pause()
        if self.enabled:self.schedule(first=True)

    def schedule(self,first=False):
        if not self.eligible() or self.timer or self.active:return
        delay=self.random.uniform(2.,3.5) if first else self.random.uniform(2.5,5.)
        self.timer=GLib.timeout_add(round(delay*1000),self.begin)

    def animations_changed(self,*_):
        self.pause();self.schedule(first=True)

    def visibility(self,_window,event):
        hidden=event.state==Gdk.VisibilityState.FULLY_OBSCURED
        if hidden!=self.obscured:
            self.obscured=hidden
            if hidden:self.pause()
            else:self.schedule(first=True)
        return False

    def warmup(self):
        if self.painter or self.failed or self.closed:return
        try:
            from winter_snow_paint import SnowPainter
            self.painter=SnowPainter(self.area,self)
        except (OSError,RuntimeError,AttributeError):self.failed=True

    def begin(self):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
        if not self.eligible():return False
        self.area.show();self.warmup()
        if not self.painter:self.area.hide();return False
        w,h=self.overlay.get_allocated_width(),self.overlay.get_allocated_height()
        self.model.start(max(1,w),max(1,h),frequent=True);self.start_time=None;self.active=True
        self.geometry_at=0.;self.geometry_size=None;self.dots=[]
        if not self.tick:self.tick=self.area.add_tick_callback(self.advance)
        return False

    def geometry(self,now):
        size=self.overlay.get_allocated_width(),self.overlay.get_allocated_height()
        if self.geometry_size is not None and size!=self.geometry_size:
            self.pause();self.schedule(first=True);return False
        if now-self.geometry_at<.35 and size==self.geometry_size:return True
        self.geometry_at=now;self.geometry_size=size
        shelves=[]
        for index,widget in enumerate(self.targets()[:12]):
            if not widget or not widget.get_mapped():continue
            point=widget.translate_coordinates(self.overlay,0,0)
            if point is None:continue
            x,y=point;area=widget.get_allocation()
            inset=min(14,area.width*.15)
            left=max(8.,x+inset);right=min(size[0]-8.,x+area.width-inset)
            if right-left>18 and 25<y<size[1]-6:
                shelves.append((str(index),left,right,float(y)))
        self.shelves=shelves;return True

    def advance(self,_area,clock):
        if not self.eligible():self.pause();return False
        now=clock.get_frame_time()/1e6
        if self.start_time is None:self.start_time=now
        if not self.geometry(now):return False
        previous=self.dots
        self.dots=self.model.advance(now-self.start_time,self.shelves)
        if self.model.finished or now-self.start_time>self.model.duration+32.:
            self.tick=0;self.active=False;self.dots=[];self.model.clear();self.area.hide()
            self.schedule();return False
        self.invalidate(previous,self.dots);return True

    def invalidate(self,previous,current):
        # GTK/GDK keeps these as a damage region: never invalidate the complete
        # window for a few moving flakes. Repaint old footprints as well.
        width,height=self.area.get_allocated_width(),self.area.get_allocated_height()
        self.damage_pixels=0
        dirty=[]
        for before,after in zip_longest(previous,current):
            if before==after:continue
            if before is not None:dirty.append(before)
            if after is not None:dirty.append(after)
        for x,y,radius,_alpha,h in dirty:
            left=max(0,math.floor(x-abs(radius)-2));top=max(0,math.floor(y-h-2))
            right=min(width,math.ceil(x+abs(radius)+2));bottom=min(height,math.ceil(y+h+2))
            if right>left and bottom>top:
                self.area.queue_draw_area(left,top,right-left,bottom-top)
                self.damage_pixels+=(right-left)*(bottom-top)

    def pause(self):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
        if self.tick:self.area.remove_tick_callback(self.tick);self.tick=0
        self.active=False;self.start_time=None;self.dots=[];self.model.clear();self.area.hide()

    def close(self):
        if self.closed:return
        self.closed=True;self.pause()
        for obj,signal in self.signals:
            if obj.handler_is_connected(signal):obj.disconnect(signal)
        self.signals=[]
        if self.painter:self.painter.close();self.painter=None
        self.area.destroy()
