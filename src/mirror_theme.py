"""Mirrorball's scoped chrome and bounded, cached optical animation."""
import ctypes as C
import weakref
import math
import time
from gi.repository import Gtk,Gdk,GLib
from source_picker import text
from mirror_art import materials,preview,PHASES,PERIOD

CSS=b'''
.mirrorball-theme .card { padding-top: 35px; background-color: #171d24;
 background-image: linear-gradient(135deg,#30313a,#171c23 40%,#11171e);
 box-shadow: inset 0 1px rgba(228,217,189,.17),inset 0 -1px rgba(118,153,180,.09); }
.mirrorball-theme .card.compact { padding-top: 43px; }
window.ember-stage.mirrorball-theme { background-color: #0c1015; }
window.ember-stage.mirrorball-theme.stage-opening { background-color: transparent; }
.mirrorball-theme .stage-console { background-image: linear-gradient(155deg,rgba(54,56,64,.95),rgba(17,23,30,.97) 45%,rgba(36,41,48,.96));
 border-color: rgba(207,207,199,.16); box-shadow: inset 0 1px rgba(249,232,195,.14),0 8px 24px rgba(0,0,0,.3); }
.mirrorball-theme .stage-art-shell, .mirrorball-theme .cover-surface {
 background-image: linear-gradient(140deg,rgba(196,211,226,.24),rgba(20,27,35,.8) 30%,rgba(9,15,23,.8) 75%,rgba(223,189,133,.16));
 box-shadow: inset 0 1px rgba(240,225,202,.22),0 14px 35px rgba(0,0,0,.4); }
.mirrorball-theme button.stage-tab:checked { background-image: linear-gradient(135deg,#3c3e48,#222c35); color: #eddbb6; }
.mirrorball-theme button.stage-play, .mirrorball-theme button.play, .mirrorball-theme button.stage-accent {
 background-image: linear-gradient(140deg,#f0dfb2,#c7a967 58%,#b48c50); color: #262218;
 box-shadow: inset 0 1px rgba(255,248,222,.55),0 0 17px rgba(221,188,115,.1),0 5px 12px rgba(0,0,0,.3); }
.mirrorball-theme .stage-overline, .mirrorball-theme .stage-library-source { color: #bcb1a3; }
.mirrorball-theme .record-panel { background-color: rgba(10,16,23,.68); border-color: rgba(173,193,212,.10); }
.mirrorball-theme .record-list row.record-row.record-current { background-color: rgba(208,178,121,.095); }
.mirrorball-theme .flow-desk, .mirrorball-theme .dj-hero { background-image: linear-gradient(145deg,#272c34,#131b24); }
.theme-choice.mirror-choice { background-image: linear-gradient(140deg,#252b35,#131b24); border-color: rgba(196,204,210,.19); }
.theme-choice.mirror-choice .theme-choice-title { color: #ecdcba; }
.theme-choice.mirror-choice .theme-choice-note { color: #a8b0ba; }
.theme-choice.mirror-choice switch { background: #111922; border-color: #566171; }
.theme-choice.mirror-choice switch:checked { background: #95805a; border-color: #d5c299; }
.theme-choice.mirror-choice switch slider { background-image: linear-gradient(145deg,#efe2c0,#9b9e9f); }
'''


def prepare(stage):
    light=materials(320,not stage,field=stage)
    if not stage:return light,None
    from mirror_facet_atlas import bake
    return light,bake()


class MirrorPainter:
    def __init__(self,area,owner,atlas):
        from cover_pause_paint import bindings
        self.owner=weakref.ref(owner);self.c,self.g,pointer=bindings();self.closed=False
        for name in ('push_group','pop_group_to_source'):
            function=getattr(self.c,'cairo_'+name);function.restype=None;function.argtypes=[C.c_void_p]
        self.surfaces=[];self.width,self.height,frames=atlas
        for raw in frames:
            surface=self.c.cairo_image_surface_create(0,self.width,self.height)
            self.c.cairo_surface_flush(surface)
            C.memmove(self.c.cairo_image_surface_get_data(surface),raw,len(raw));self.c.cairo_surface_mark_dirty(surface)
            self.surfaces.append(surface)
        self.pointer=pointer(area.__gpointer__,None)
        self.callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_void_p)(self.draw)
        self.handler=self.g.g_signal_connect_data(self.pointer,b'draw',self.callback,None,None,0)

    def draw(self,_area,cr,_data):
        owner=self.owner()
        if not owner or owner.closed or self.closed or not owner.enabled:return False
        index=owner.phase;first=math.floor(index)%PHASES;mix=index%1
        c=self.c;c.cairo_save(cr)
        # GtkOverlay can supply the parent's broad damage clip. Bound the
        # temporary blend group explicitly to this small optical region.
        c.cairo_rectangle(cr,0,0,owner.area.get_allocated_width(),owner.area.get_allocated_height());c.cairo_clip(cr)
        c.cairo_scale(cr,owner.area.get_allocated_width()/self.width,owner.area.get_allocated_height()/self.height)
        # SOURCE-like interpolation: draw both opaque facets into a group so
        # transparency at the material's edge is not added twice.
        c.cairo_push_group(cr)
        c.cairo_set_source_surface(cr,self.surfaces[first],0,0);c.cairo_paint_with_alpha(cr,1-mix)
        c.cairo_set_operator(cr,12) # CAIRO_OPERATOR_ADD, complementary weights.
        c.cairo_set_source_surface(cr,self.surfaces[(first+1)%PHASES],0,0);c.cairo_paint_with_alpha(cr,mix)
        c.cairo_pop_group_to_source(cr);c.cairo_set_operator(cr,2);c.cairo_paint(cr)
        c.cairo_restore(cr);owner.draws+=1
        return False

    def close(self):
        if self.closed:return
        self.closed=True;self.g.g_signal_handler_disconnect(self.pointer,self.handler)
        for surface in self.surfaces:self.c.cairo_surface_destroy(surface)
        self.surfaces=[]


class MirrorSurface:
    def __init__(self,appearance,window,overlay,stage=False):
        self.appearance,self.window,self.overlay,self.stage=appearance,window,overlay,stage
        self.closed=self.enabled=self.suspended=self.obscured=self.failed=False
        self.materials=[];self.job=None
        self.tick=0;self.phase=4.;self.age=0.;self.last=None;self.painted_at=None;self.painter=None;self.generation=0;self.draws=0
        self.drawn_age=None;self.drawn_gain=None
        self.area=Gtk.DrawingArea();self.area.set_has_window(False);self.area.set_can_focus(False);self.area.set_no_show_all(True)
        self.area.set_halign(Gtk.Align.END if stage else Gtk.Align.FILL);self.area.set_valign(Gtk.Align.START)
        self.area.set_margin_end(70 if stage else 18);self.area.set_margin_start(0 if stage else 18)
        self.area.set_margin_top(120 if stage else 12)
        self.area.set_size_request(480 if stage else -1,170 if stage else 17)
        overlay.add_overlay(self.area);overlay.set_overlay_pass_through(self.area,True)
        if stage:overlay.reorder_overlay(self.area,1)
        self.glints=None;self.facets=None
        from mirror_rhythm import SongRhythm
        self.rhythm=SongRhythm('mirrorball-'+str(id(self)))
        settings=window.get_settings()
        window.add_events(Gdk.EventMask.VISIBILITY_NOTIFY_MASK)
        self.signals=[(window,window.connect('map',lambda *_:self.resume())),
                      (window,window.connect('unmap',lambda *_:self.pause())),
                      (window,window.connect('visibility-notify-event',self.visibility)),
                      (settings,settings.connect('notify::gtk-enable-animations',lambda *_:self.resume()))]

    def set_enabled(self,enabled):
        self.enabled=bool(enabled);self.pause();self.generation+=1
        if self.job:self.job.cancel();self.job=None
        if not enabled:
            self.area.hide()
            if self.glints:self.glints.close();self.glints=None
            if self.facets:self.facets.close();self.facets=None
            if self.painter:self.painter.close();self.painter=None
            for cache in self.materials:cache.close()
            self.materials=[]
            return
        if self.stage and self.facets is None:
            from mirror_facets import FacetLayer
            self.facets=FacetLayer(self);self.facets.area.show();self.facets.advance(self.age)
        if self.stage and self.glints is None:
            from mirror_glints import Glints
            self.glints=Glints(self);self.glints.area.show();self.glints.advance(self.age)
        if not self.materials:
            from winter_surface_cache import MaterialCache
            def visit(widget):
                if isinstance(widget,Gtk.Box) and any(widget.get_style_context().has_class(name) for name in
                        ('card','stage-console','stage-art-shell','cover-surface','lamp-well','stage-nav')):
                    self.materials.append(MaterialCache(widget,self))
                if isinstance(widget,Gtk.Container):
                    for child in widget.get_children():visit(child)
            visit(self.overlay)
        self.area.show()
        if self.painter:self.resume();return
        generation=self.generation
        future=self.job=self.appearance.pool.submit(prepare,self.stage)
        def done(result):
            try:atlas,scales=result.result()
            except Exception:return
            def apply():
                if self.closed or generation!=self.generation or not self.enabled:return False
                self.job=None
                try:
                    self.painter=MirrorPainter(self.area,self,atlas)
                    if scales is not None:self.facets.set_atlas(scales)
                except (OSError,RuntimeError,AttributeError):return False
                self.area.queue_draw();self.resume();return False
            GLib.idle_add(apply)
        future.add_done_callback(done)

    def eligible(self):
        return self.enabled and not self.closed and not self.suspended and not self.obscured and self.window.get_mapped() and self.area.get_mapped() and self.painter

    def resume(self):
        self.pause(release=False)
        if not self.eligible():self.rhythm.release();return
        self.area.queue_draw()
        if self.window.get_settings().get_property('gtk-enable-animations'):
            self.tick=self.area.add_tick_callback(self.advance)
        else:self.rhythm.release()

    def advance(self,_area,clock):
        if not self.eligible():self.tick=0;return False
        now=clock.get_frame_time()/1e6
        if self.last is not None:
            dt=min(.1,max(0,now-self.last))
            # Capture timestamps use monotonic time; GDK's paint timestamp can
            # lag behind the latest audio callback on a busy first frame.
            speed=self.rhythm.advance(self.appearance.audio_host,time.monotonic(),dt)
            self.age+=dt*speed
            self.phase=(self.phase+dt*speed*PHASES/PERIOD)%PHASES
        self.last=now
        if self.painted_at is None or now-self.painted_at>=1/30-.002:
            self.painted_at=now;gain=self.rhythm.timing.gain
            changed=self.drawn_age is None or abs(self.age-self.drawn_age)>.0001 or abs(gain-self.drawn_gain)>.0005
            if changed:
                self.drawn_age,self.drawn_gain=self.age,gain;self.area.queue_draw()
                if self.glints:self.glints.advance(self.age)
                if self.facets:self.facets.advance(self.age)
        return True

    def pause(self,release=True):
        if self.tick:self.area.remove_tick_callback(self.tick);self.tick=0
        self.last=self.painted_at=None
        if release:self.rhythm.release()

    def set_suspended(self,value):
        self.suspended=bool(value);self.resume()

    def visibility(self,_window,event):
        self.obscured=event.state==Gdk.VisibilityState.FULLY_OBSCURED;self.resume();return False

    def close(self):
        if self.closed:return
        self.pause();self.closed=True;self.generation+=1
        if self.job:self.job.cancel();self.job=None
        if self.painter:self.painter.close();self.painter=None
        if self.glints:self.glints.close();self.glints=None
        if self.facets:self.facets.close();self.facets=None
        for cache in self.materials:cache.close()
        self.materials=[]
        for widget,signal in self.signals:
            if widget.handler_is_connected(signal):widget.disconnect(signal)
        self.area.destroy()


def mirror_choice(appearance):
    tile=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);tile.get_style_context().add_class('theme-choice');tile.get_style_context().add_class('mirror-choice')
    tile.pack_start(Gtk.Image.new_from_pixbuf(preview()),False,False,0)
    row=Gtk.Box(spacing=10);tile.pack_start(row,False,False,0)
    label=Gtk.Label(label=text('Mirrorball','Зеркальный зал'));label.set_xalign(0);label.get_style_context().add_class('theme-choice-title');row.pack_start(label,True,True,0)
    switch=Gtk.Switch();switch.set_active(appearance.mirrorball);switch.set_has_tooltip(False);switch.set_valign(Gtk.Align.CENTER)
    switch.get_accessible().set_name(label.get_text());row.pack_end(switch,False,False,0)
    note=Gtk.Label(label=text('Mirror glass · in rhythm with your music','Зеркальные грани · в ритме музыки'));note.set_xalign(0);note.set_line_wrap(True);note.set_max_width_chars(32);note.get_style_context().add_class('theme-choice-note');tile.pack_start(note,False,False,0)
    def changed(*_):
        if switch.get_active()==appearance.mirrorball:return
        if not appearance.set_theme('mirrorball' if switch.get_active() else 'classic'):
            switch.set_active(appearance.mirrorball);note.set_text(text('Could not save the theme','Не удалось сохранить тему'))
    switch.connect('notify::active',changed)
    unsubscribe=appearance.subscribe(lambda:switch.set_active(appearance.mirrorball));tile.connect('destroy',lambda *_:unsubscribe())
    return tile,switch
