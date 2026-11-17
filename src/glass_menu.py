"""Small retained glass surfaces for desktop menus.

Reflections are static CSS layers. A short frame-clock fade owns opening and
closing; the menu never reads the desktop, blurs live pixels or starts a timer.
Sizing follows the monitor, including when its anchor is a tiny Mini widget.
"""
import os
import weakref
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, GObject, Gtk, Pango

CSS = b'''
.ember-glass-menu {
 font-family: 'Noto Sans'; color: #eee3ca;
 background-color: rgba(29,32,32,.98);
 background-image: linear-gradient(118deg,rgba(255,218,171,.075),rgba(255,247,216,0) 33%,rgba(166,215,233,.025) 76%,rgba(222,187,223,.055)),
  linear-gradient(to bottom,rgba(255,255,242,.10),rgba(255,255,242,.008) 13%,rgba(255,255,242,0) 74%,rgba(212,221,242,.025));
 border: 1px solid rgba(220,230,225,.17); border-top-color: rgba(255,247,223,.34);
 border-left-color: rgba(210,235,236,.25); border-right-color: rgba(243,206,223,.21);
 border-radius: 24px; padding: 0;
 box-shadow: inset 0 1px rgba(255,255,235,.07),inset 0 -1px rgba(215,217,245,.04),0 10px 26px rgba(0,0,0,.24);
}
.ember-glass-menu.nocturne-theme { background-color: rgba(20,24,26,.98); }
.ember-glass-menu.mirrorball-theme { background-color: rgba(25,30,39,.98); }
.ember-glass-menu.christmas-theme { background-color: rgba(23,38,31,.98); }
.ember-glass-menu .menu-body { padding: 16px; }
.ember-glass-menu .menu-brand { color: #cfab70; font-size: 8px; letter-spacing: 2px; font-weight: bold; }
.ember-glass-menu .menu-title { color: #f4e9d0; font-size: 19px; font-weight: bold; letter-spacing: -.35px; }
.ember-glass-menu .menu-subtitle { color: #b4ad9c; font-size: 11px; }
.ember-glass-menu .menu-section-title { color: #eee1c4; font-size: 13px; font-weight: bold; }
.ember-glass-menu .menu-note { color: #b0a995; font-size: 11px; }
.ember-glass-menu .menu-well { padding: 10px; border-radius: 17px;
 background-color: rgba(3,9,10,.17); border: 1px solid rgba(225,231,219,.055);
 box-shadow: inset 0 2px 5px rgba(0,0,0,.17),0 1px rgba(255,241,211,.025); }
.ember-glass-menu button.menu-close, .ember-glass-menu button.menu-action,
.ember-glass-menu button.source-card, .ember-glass-menu button.source-session-row,
.ember-glass-menu button.theme-card, .ember-glass-menu button.menu-tab {
 outline-width: 0; outline-style: none; text-shadow: none;
 transition-property: background-color,border-color,color,box-shadow;
 transition-duration: 220ms; transition-timing-function: ease-out;
}
.ember-glass-menu button.menu-close {
 color: #c9c3b1; padding: 5px; min-width: 20px; min-height: 20px; border-radius: 50%;
 border: 1px solid rgba(233,236,223,.10); background-color: rgba(206,224,223,.025);
 background-image: linear-gradient(145deg,rgba(255,255,236,.055),rgba(255,255,236,0));
 box-shadow: inset 0 1px rgba(255,246,224,.06);
}
.ember-glass-menu button.menu-close:hover { color: #fff0c9; background-color: rgba(228,232,217,.08); }
.ember-glass-menu .menu-nav { padding: 3px; border-radius: 17px;
 background-color: rgba(2,8,10,.22); border: 1px solid rgba(228,235,228,.055);
 box-shadow: inset 0 1px 4px rgba(0,0,0,.16),0 1px rgba(255,246,226,.025); }
.ember-glass-menu button.menu-tab {
 background-color: transparent; background-image: none; border: 1px solid transparent;
 border-radius: 14px; padding: 7px 4px; min-height: 21px; min-width: 0;
 color: #aaa99e; font-size: 11px; box-shadow: none;
}
.ember-glass-menu button.menu-tab:checked {
 color: #fff0cb; background-color: rgba(204,222,215,.065);
 background-image: linear-gradient(125deg,rgba(255,234,199,.07),rgba(255,255,237,0) 42%,rgba(178,219,240,.018) 72%,rgba(232,196,234,.06));
 border-color: rgba(222,231,230,.17); border-top-color: rgba(255,248,224,.31);
 box-shadow: inset 0 1px rgba(255,255,240,.055),0 2px 6px rgba(0,0,0,.14);
}
.ember-glass-menu .glass-flight button.menu-tab {
 background-color: transparent; background-image: none; border-color: transparent; box-shadow: none; transition-duration: 0ms;
}
.ember-glass-menu button.menu-tab:hover { color: #f6e6c3; }
.ember-glass-menu button.menu-action, .ember-glass-menu button.source-session-row {
 background-color: rgba(205,224,214,.025);
 background-image: linear-gradient(145deg,rgba(255,250,221,.055),rgba(206,222,231,.012) 55%,rgba(234,211,233,.025));
 border: 1px solid rgba(228,232,223,.09); border-top-color: rgba(255,243,216,.14);
 color: #ded3ba; border-radius: 14px; min-height: 28px; padding: 8px 10px;
 box-shadow: inset 0 1px rgba(255,249,225,.025),0 3px 5px rgba(0,0,0,.10); font-size: 11px;
}
.ember-glass-menu button.menu-action:hover, .ember-glass-menu button.source-session-row:hover,
.ember-glass-menu button.source-card:hover, .ember-glass-menu button.theme-card:hover {
 background-color: rgba(204,224,222,.075); border-color: rgba(224,235,229,.23); color: #fff0cd;
}
.ember-glass-menu button.menu-action:active, .ember-glass-menu button.source-card:active {
 background-color: rgba(1,6,8,.16); box-shadow: inset 0 2px 5px rgba(0,0,0,.22);
}
.ember-glass-menu button.menu-action.menu-danger { color: #d8aaa0; }
.ember-glass-menu button:disabled { opacity: .5; }
.ember-glass-menu.menu-keyboard button:focus { border-color: rgba(243,209,144,.40); }
.ember-glass-menu .menu-scroll, .ember-glass-menu .menu-scroll viewport { background: transparent; border: none; }
.ember-glass-menu .menu-scroll scrollbar { background: transparent; border: none; }
.ember-glass-menu .menu-scroll scrollbar slider { min-width: 3px; min-height: 22px; border: none; border-radius: 4px; background-color: rgba(218,212,190,.22); }
.ember-glass-menu .menu-divider { background-color: rgba(232,230,210,.08); min-height: 1px; margin: 2px 0; }
.ember-glass-menu button.theme-card {
 border-radius: 16px; padding: 10px; border: 1px solid rgba(230,232,220,.09);
 background-color: rgba(208,223,215,.025); background-image: linear-gradient(145deg,rgba(255,246,210,.04),rgba(255,255,255,0));
 box-shadow: inset 0 1px rgba(255,246,220,.03);
}
.ember-glass-menu button.theme-card.selected { border-color: rgba(231,199,136,.30); background-color: rgba(205,173,105,.065); }
.ember-glass-menu .theme-card-title { color: #e9ddc2; font-size: 12px; font-weight: bold; }
.ember-glass-menu .theme-card-note { color: #aaa793; font-size: 10px; }
.ember-glass-menu .theme-card-light { color: #cbb47d; font-size: 17px; }
.ember-glass-menu .theme-card.selected .theme-card-light { color: #f8d89a; text-shadow: 0 0 6px rgba(255,177,51,.40); }
.ember-glass-menu switch { min-width: 36px; min-height: 20px; border-radius: 14px; background: #111a1a; border: 1px solid rgba(222,226,207,.17); }
.ember-glass-menu switch:checked { background: #847044; border-color: rgba(242,209,147,.45); }
.ember-glass-menu switch slider { min-width: 18px; min-height: 18px; border-radius: 50%; border: none;
 background-image: linear-gradient(145deg,#e3d9bb,#9b9b82); box-shadow: 0 1px 4px rgba(0,0,0,.3),inset 0 1px rgba(255,249,218,.45); }
.ember-glass-menu checkbutton { color: #ddd0b4; font-size: 11px; }
.ember-glass-menu checkbutton check { border-radius: 5px; border: 1px solid rgba(230,226,201,.24); background: rgba(7,13,13,.6); color: #f6d38b; min-width: 15px; min-height: 15px; }
.ember-glass-menu .source-grid { padding: 1px; }
.ember-glass-menu button.source-card {
 border: 1px solid rgba(230,233,222,.10); border-top-color: rgba(246,242,220,.17);
 border-radius: 17px; padding: 11px; min-width: 0;
 color: #e9dec5; background-color: rgba(210,222,211,.025);
 background-image: linear-gradient(145deg,rgba(255,245,214,.06),rgba(255,255,255,0) 65%,rgba(207,216,245,.02));
 box-shadow: inset 0 1px rgba(255,248,226,.035),0 3px 8px rgba(0,0,0,.12);
}
.ember-glass-menu button.source-card.selected { border-color: rgba(239,208,147,.38); background-color: rgba(212,184,118,.07); }
.ember-glass-menu .source-title { color: #f0e3c7; font-size: 12px; font-weight: bold; }
.ember-glass-menu .source-detail { color: #b6af9c; font-size: 10px; }
.ember-glass-menu .source-symbol { color: #c7b68c; }
.ember-glass-menu .source-status { color: #f1cd82; font-size: 9px; }
.ember-glass-menu .source-connections title { padding: 7px 2px; color: #c1bba8; font-size: 11px; }
.ember-glass-menu .source-footer { margin-top: 2px; }
'''

_provider = None


def install_style():
    global _provider
    if _provider is None:
        _provider = Gtk.CssProvider()
        _provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 25)


def label(value, style='menu-note', wrap=True):
    item = Gtk.Label(label=value)
    item.set_xalign(0)
    item.set_line_wrap(wrap)
    item.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    # A width hint allows wrapping inside the allocated menu, not a long
    # translated sentence determining the popover's minimum width.
    item.set_max_width_chars(1 if wrap else 50)
    item.get_style_context().add_class(style)
    return item


class GlassPopover(Gtk.Window):
    """A real native popup, free of the Mini widget's 320px clipping region.

    GDK positions this transient surface in the monitor's logical coordinates.
    GTK and seat grabs keep outside clicks and Escape local to the menu, while
    nested GTK menus (the soundstage comboboxes) can temporarily take the grab.
    """
    __gsignals__ = {'closed': (GObject.SignalFlags.RUN_LAST, None, ())}
    _active = weakref.WeakKeyDictionary()

    def __init__(self, anchor, css_class, width=408):
        super().__init__(type=Gtk.WindowType.POPUP)
        self._anchor = anchor
        self._owner = anchor.get_toplevel()
        self._seat = None
        self._gtk_grab = False
        self._nested_grab = False
        self._tick = 0
        self._regrab = 0
        self._open = False
        self._closing = False
        self._disposed = False
        self._position_key = None
        self._modal = True
        self._anchor_handlers = []
        self._owner_handlers = []
        install_style()
        context = self.get_style_context()
        context.add_class('ember-glass-menu')
        context.add_class(css_class)
        self.set_transient_for(self._owner)
        self.set_attached_to(anchor)
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(True)
        self.set_focus_on_map(True)
        Gtk.Window.set_modal(self, True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.TOUCH_MASK)
        self.connect('button-press-event', self._outside_press)
        self.connect('touch-event', self._outside_touch)
        self.connect('key-press-event', self._key)
        self.connect('grab-broken-event', self._grab_broken)
        self.connect('grab-notify', self._grab_notify)
        self.connect('size-allocate', self._allocated)
        self.connect('hide', self._hidden)
        self.connect('unmap', self._hidden)
        self.connect('destroy', self._destroyed)
        self._anchor_handlers = [anchor.connect('unmap', self._anchor_unmapped),
                                 anchor.connect('destroy', lambda *_: self.destroy())]
        self._owner_handlers = [self._owner.connect('unmap', self._anchor_unmapped),
                                self._owner.connect('destroy', lambda *_: self.destroy()),
                                self._owner.connect('configure-event', self._owner_moved)]
        display = anchor.get_display()
        native = anchor.get_window()
        monitor = display.get_monitor_at_window(native) if native else display.get_primary_monitor()
        monitor = monitor or display.get_monitor(0)
        area = monitor.get_workarea()
        self.menu_width = max(240, min(width, area.width - 36))
        self.content_height = max(170, min(540, area.height - 64))
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.body.get_style_context().add_class('menu-body')
        self.body.set_size_request(self.menu_width - 2, -1)
        self.add(self.body)

    def get_relative_to(self):
        return self._anchor

    def set_modal(self, modal):
        """Allow a native file chooser to suspend the menu's input grab."""
        self._modal = bool(modal)
        Gtk.Window.set_modal(self, self._modal)
        if self._modal and self.get_mapped() and not self._closing:
            self._take_grab()
        elif not self._modal:
            self._release_grab()

    def _place(self):
        if self._disposed or not self.get_realized() or not self._anchor.get_mapped():
            return
        point = self._anchor.translate_coordinates(self._owner, 0, 0)
        if point is None:
            return
        x, y = point
        allocation = self._anchor.get_allocation()
        key = (x, y, allocation.width, allocation.height,
               self.get_allocated_width(), self.get_allocated_height())
        if key == self._position_key:
            return
        self._position_key = key
        rect = Gdk.Rectangle()
        rect.x, rect.y = x, y
        rect.width, rect.height = allocation.width, allocation.height
        self.get_window().move_to_rect(rect, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_EAST,
            Gdk.AnchorHints.FLIP_Y | Gdk.AnchorHints.SLIDE_X | Gdk.AnchorHints.SLIDE_Y, 0, 8)

    def _allocated(self, *_):
        self._place()

    def _owner_moved(self, *_):
        self._position_key = None
        self._place()
        return False

    def _anchor_unmapped(self, *_):
        self._finish_close()

    def _take_grab(self):
        if self._disposed or not self.get_mapped() or not self._modal:
            return False
        if not self._gtk_grab:
            self.grab_add()
            self._gtk_grab = True
        if self._seat is None:
            seat = self.get_display().get_default_seat()
            if seat:
                result = seat.grab(self.get_window(),
                    Gdk.SeatCapabilities.ALL_POINTING | Gdk.SeatCapabilities.KEYBOARD,
                    True, None, Gtk.get_current_event(), None, None)
                if result == Gdk.GrabStatus.SUCCESS:
                    self._seat = seat
        if self._seat is None:
            # A denied native grab must not leave a GTK-only modal surface
            # blocking this application's controls without outside dismissal.
            self._finish_close()
            return False
        return True

    def _release_grab(self):
        # Another menu can have replaced this seat grab before our closing
        # fade finishes. Never ungrab that newer menu or its combobox popup.
        if self._seat is not None:
            if Gtk.grab_get_current() is self:
                self._seat.ungrab()
            self._seat = None
        if self._gtk_grab:
            self._gtk_grab = False
            self.grab_remove()
        self._nested_grab = False

    def _belongs(self, widget):
        if widget is None:
            return False
        if widget is self or widget.get_toplevel() is self:
            return True
        if isinstance(widget, Gtk.Menu):
            return self._belongs(widget.get_attach_widget())
        if isinstance(widget, Gtk.Window):
            return (self._belongs(widget.get_attached_to()) or
                    self._belongs(widget.get_transient_for()))
        return False

    def _queue_regrab(self):
        if self._regrab or self._disposed:
            return
        def check():
            self._regrab = 0
            if self._disposed or not self.get_mapped() or self._closing or not self._modal:
                return False
            current = Gtk.grab_get_current()
            if current is self:
                if self._nested_grab:
                    self._nested_grab = False
                    self._take_grab()
                elif self._seat is None:
                    self._finish_close()
            elif self._belongs(current):
                self._nested_grab = True
            else:
                self._finish_close()
            return False
        self._regrab = GLib.idle_add(check)

    def _grab_broken(self, _widget, event):
        # A nested GtkComboBox menu takes a new native grab and returns it on
        # grab-notify. The old grab has already ended; do not ungrab the new one.
        self._seat = None
        # Never wrap event.grab_window here: GTK may already have destroyed a
        # transient combobox GdkWindow while this queued event is delivered.
        # The live GTK grab stack is inspected once after dispatch instead.
        self._queue_regrab()
        return False

    def _grab_notify(self, _widget, was_grabbed):
        current = Gtk.grab_get_current()
        if not was_grabbed and current is not self and self._belongs(current):
            self._nested_grab = True
        if not was_grabbed and current is not self:
            self._queue_regrab()
        if was_grabbed and self._open and not self._closing:
            self._queue_regrab()

    def _inside(self, event):
        native = self.get_window()
        if not native:
            return False
        origin = native.get_origin()
        x, y = origin[-2:]
        return (x <= event.x_root < x+self.get_allocated_width() and
                y <= event.y_root < y+self.get_allocated_height())

    def _outside_press(self, _widget, event):
        self.get_style_context().remove_class('menu-keyboard')
        if self._closing:
            return True
        if not self._inside(event):
            self.popdown()
            return True
        return False

    def _outside_touch(self, _widget, event):
        if event.type == Gdk.EventType.TOUCH_BEGIN:
            return self._outside_press(_widget, event)
        return False

    def _key(self, _widget, event):
        if self._closing:
            return True
        if event.keyval == Gdk.KEY_Escape:
            self.popdown()
            return True
        if event.keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            self.get_style_context().add_class('menu-keyboard')
            backward = event.keyval == Gdk.KEY_ISO_Left_Tab or bool(event.state & Gdk.ModifierType.SHIFT_MASK)
            direction = Gtk.DirectionType.TAB_BACKWARD if backward else Gtk.DirectionType.TAB_FORWARD
            if not self.child_focus(direction):
                self.set_focus(None)
                self.child_focus(direction)
            return True
        return False

    def _stop_motion(self):
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0

    def _animate(self, target):
        self._stop_motion()
        settings = self.get_settings()
        if not settings.get_property('gtk-enable-animations') or not self.get_screen().is_composited():
            self.set_opacity(target)
            if self._closing:
                self._finish_close()
            return
        start = self.get_opacity()
        began = self.get_frame_clock().get_frame_time()
        duration = 190000 if target else 150000
        def frame(_widget, clock):
            progress = (min(1., max(0., (clock.get_frame_time()-began)/duration))
                        if settings.get_property('gtk-enable-animations') else 1.)
            eased = 1.-(1.-progress)**3
            self.set_opacity(start+(target-start)*eased)
            if progress < 1.:
                return True
            self._tick = 0
            if self._closing:
                self._finish_close()
            return False
        self._tick = self.add_tick_callback(frame)

    def popdown(self):
        if self._disposed or not self.get_visible() or self._closing:
            return
        self._closing = True
        self._release_grab()
        Gtk.Window.set_modal(self, False)
        self._animate(0.)

    def dismiss(self):
        """Unmap before hiding an owner surface (required by Wayland)."""
        self._finish_close()

    def _finish_close(self):
        self._stop_motion()
        self._release_grab()
        if self.get_visible():
            self.hide()

    def _hidden(self, *_):
        self._stop_motion()
        self._release_grab()
        if self._regrab:
            GLib.source_remove(self._regrab)
            self._regrab = 0
        self._closing = False
        self.set_opacity(1.)
        current = self._active.get(self._owner)
        if current and current() is self:
            del self._active[self._owner]
        if self._open:
            self._open = False
            self.emit('closed')

    def _destroyed(self, *_):
        if self._disposed:
            return
        self._disposed = True
        self._hidden()
        for widget, handlers in ((self._anchor, self._anchor_handlers), (self._owner, self._owner_handlers)):
            for handler in handlers:
                if widget.handler_is_connected(handler):
                    widget.disconnect(handler)
        self._anchor_handlers.clear()
        self._owner_handlers.clear()

    def heading(self, title, subtitle=None):
        header = Gtk.Box(spacing=12)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        titles.pack_start(label('E M B E R  /  AUDIO', 'menu-brand', False), False, False, 0)
        titles.pack_start(label(title, 'menu-title'), False, False, 0)
        if subtitle:
            titles.pack_start(label(subtitle, 'menu-subtitle'), False, False, 0)
        header.pack_start(titles, True, True, 0)
        close = Gtk.Button()
        image = Gtk.Image.new_from_icon_name('window-close-symbolic', Gtk.IconSize.MENU)
        image.set_pixel_size(12)
        close.add(image)
        close.set_valign(Gtk.Align.START)
        close.set_has_tooltip(False)
        close.get_style_context().add_class('menu-close')
        ru = os.environ.get('EMBERBOX_LANGUAGE', os.environ.get('LANG', 'en')).startswith('ru')
        close.get_accessible().set_name('Закрыть меню' if ru else 'Close menu')
        close.connect('clicked', lambda *_: self.popdown())
        header.pack_end(close, False, False, 0)
        self.close_button = close
        self.body.pack_start(header, False, False, 0)

    def scroller(self, child, max_height=300):
        scroll = Gtk.ScrolledWindow()
        scroll.get_style_context().add_class('menu-scroll')
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        scroll.set_max_content_height(max(80, min(max_height, self.content_height)))
        scroll.add(child)
        return scroll

    def present(self):
        if self._disposed or not self._anchor.get_mapped():
            return
        previous = self._active.get(self._owner)
        previous = previous() if previous else None
        if previous is not None and previous is not self:
            # Wayland requires the popup's parent to be the topmost surface.
            # Finish a sibling's closing fade before mapping this new surface.
            previous._finish_close()
        self._active[self._owner] = weakref.ref(self)
        self._stop_motion()
        self._closing = False
        self._open = True
        Gtk.Window.set_modal(self, self._modal)
        self.get_style_context().remove_class('menu-keyboard')
        self.body.show_all()
        _minimum, natural = self.get_preferred_size()
        self.set_default_size(natural.width, natural.height)
        self.set_opacity(0.)
        self.realize()
        self._position_key = None
        self._place()
        self.show_all()
        self._place()
        if not self._take_grab():
            return
        self.child_focus(Gtk.DirectionType.TAB_FORWARD)
        self._animate(1.)

    def popup(self):
        self.present()
