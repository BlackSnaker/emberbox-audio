"""Offline GTK menus: direct sections, monitor bounds and intact source routing.

Runs with 320px Mini and full-size anchors, independently of account processes,
real playback, network access and audio. The popup must be usable outside the
small widget, rather than getting clipped to its native window.
"""
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixture = tempfile.TemporaryDirectory(prefix='emberbox-menus-')
WAYLAND = os.environ.get('GDK_BACKEND') == 'wayland'
for variable, folder in (('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'),
                         ('XDG_RUNTIME_DIR', 'runtime')):
    # A nested Wayland compositor owns the socket in its private runtime.
    if variable == 'XDG_RUNTIME_DIR' and WAYLAND:
        continue
    directory = Path(fixture.name)/folder
    directory.mkdir(mode=0o700)
    os.environ[variable] = str(directory)
sys.path.insert(0, str(ROOT/'src'))

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk
from seasonal_theme import Appearance
from source_picker import SourcePicker
from sources import Session
from widget_settings import SettingsMenu, settings_button


def settle(seconds=.1):
    until = time.monotonic()+seconds
    context = GLib.MainContext.default()
    while time.monotonic() < until:
        for _ in range(5):
            if context.pending():
                context.iteration(False)
        time.sleep(.002)


def wait(predicate, message, seconds=3):
    until = time.monotonic()+seconds
    while not predicate() and time.monotonic() < until:
        settle(.02)
    assert predicate(), message


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def monitor_bounds(widget):
    monitor = widget.get_display().get_monitor_at_window(widget.get_window())
    area = monitor.get_workarea()
    return area.x, area.y, area.width, area.height


def assert_menu_fits(popup):
    assert popup.get_mapped(), 'The menu failed to open'
    wait(lambda: popup.get_allocated_width() > 200, 'The popup never received its real allocation')
    assert popup.get_window().is_viewable(), 'GTK reported a popup that the native compositor did not map'
    assert popup.get_window().get_window_type() != Gdk.WindowType.CHILD, (
        'The menu is still a child window clipped to the small player')
    x, y, width, height = monitor_bounds(popup)
    origin = popup.get_window().get_origin()
    px, py = origin[-2:]
    allocated = popup.get_allocation()
    # GtkPopover owns its native popup window on X11. Width/height are in the
    # same logical coordinate system as GdkMonitor, including GDK_SCALE=2.
    assert popup.get_allocated_width() <= width-16, (allocated, width, height)
    assert popup.get_allocated_height() <= height-16, (allocated, width, height)
    if WAYLAND:
        # GDK cannot report global toplevel coordinates on Wayland. The
        # compositor applies move_to_rect's flip/slide constraints instead.
        return
    assert px >= x-2 and py >= y-2, (px, py, x, y)
    assert px+allocated.width <= x+width+2, (px, allocated, width)
    assert py+allocated.height <= y+height+2, (py, allocated, height)


def assert_painted(popup):
    if WAYLAND:
        # Wayland does not expose cross-surface pixel readback. The compositor
        # run still covers native surface creation, controls and lifecycle.
        return
    def visible_pixels():
        image = Gdk.pixbuf_get_from_window(popup.get_window(), 0, 0,
            popup.get_allocated_width(), popup.get_allocated_height())
        if image is None:
            return False
        pixels = image.get_pixels()
        # A mapped GtkPopover may report an allocation outside Mini while its
        # entire native child surface is clipped and reads back as pure black.
        # Verify the actual emitted pixels, rather than just GTK allocations.
        return sum(value > 10 for value in pixels[::image.get_n_channels()]) > len(pixels)//image.get_n_channels()*.35
    wait(visible_pixels, 'A mapped menu was not painted outside its Mini anchor')


def key(widget, name):
    event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    event.keyval = Gdk.keyval_from_name(name)
    event.state = Gdk.ModifierType(0)
    return widget.emit('key-press-event', event)


def observe_fade(popup, opening):
    samples = []
    until = time.monotonic()+2
    while time.monotonic() < until:
        samples.append(popup.get_opacity())
        complete = (popup.get_opacity() == 1.) if opening else not popup.get_mapped()
        if complete and not popup._tick:
            break
        settle(.01)
    if popup.get_screen().is_composited() and popup.get_settings().get_property('gtk-enable-animations'):
        assert any(0. < value < 1. for value in samples), ('A fade skipped its intermediate frames', samples)
    assert not popup._tick, 'A finished popup fade retained a frame callback'
    if opening:
        assert popup.get_mapped() and popup.get_opacity() == 1.
    else:
        assert not popup.get_mapped(), 'The closing fade left an invisible modal window'


def assert_reachable(widget, popup):
    assert widget.get_mapped(), ('A primary control is hidden', type(widget).__name__)
    point = widget.translate_coordinates(popup, 0, 0)
    assert point is not None
    x, y = point
    area = widget.get_allocation()
    assert x >= 0 and y >= 0, (type(widget).__name__, point)
    assert x+area.width <= popup.get_allocated_width()+2, (type(widget).__name__, point, area)
    assert y+area.height <= popup.get_allocated_height()+2, (type(widget).__name__, point, area)


class FixtureHost:
    def __init__(self):
        self.calls = []
        self.window = Gtk.Window(title='Ember / menu fixtures')
        self.window.set_default_size(320, 180)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.box.set_border_width(12)
        self.window.add(self.box)
        self.row = Gtk.Box(spacing=8)
        self.box.pack_start(self.row, False, False, 0)
        self.source = 'apple-music'
        self.apple_mode = 'native'
        self.apple_web = SimpleNamespace(
            state={'spatial': {'enabled': True, 'scene': {'mode': 'speakers',
                'preference': 'speakers', 'angle': 30, 'hrtf': 0}}},
            set_spatial=lambda value: self.calls.append(('spatial', value)),
            connect_lossless=lambda: self.calls.append(('lossless',)),
            set_scene=lambda *args, **kwargs: self.calls.append(('scene', args, kwargs)))
        self.appearance = Appearance(Path(fixture.name)/'appearance.json')
        self.window.ember_appearance = self.appearance
        self.settings = SettingsMenu(lambda: self.calls.append(('mode',)),
            lambda: self.calls.append(('refresh',)), lambda: self.calls.append(('restart',)),
            accounts=lambda: self.calls.append(('accounts',)), fullscreen=self.open_fullscreen,
            hide=lambda: self.calls.append(('hide',)), quit=lambda: self.calls.append(('quit',)),
            dj=lambda: self.calls.append(('dj',)))
        self.settings.appearance = self.appearance
        self.anchor = settings_button(lambda _button: None)
        self.row.pack_end(self.anchor, False, False, 0)
        self.source_anchor = Gtk.Button(label='Apple Music')
        self.row.pack_start(self.source_anchor, False, False, 0)
        self.box.pack_start(Gtk.Label(label='Original fixture / no playback'), True, True, 0)
        self.picker = SourcePicker(lambda source, session: self.calls.append(('source', source, session)),
                                   lambda: None, lambda: self.calls.append(('accounts',)))

    def open_fullscreen(self):
        self.calls.append(('fullscreen',))


host = FixtureHost()
host.window.show_all()
settle(.2)
preview = os.environ.get('EMBERBOX_MENU_PREVIEW')


def screenshot(name):
    if not preview or WAYLAND:
        return
    settle(.3)
    host.window.get_display().sync()
    folder = Path(preview)
    folder.mkdir(parents=True, exist_ok=True)
    root = host.window.get_screen().get_root_window()
    width, height = root.get_width(), root.get_height()
    Gdk.pixbuf_get_from_window(root, 0, 0, width, height).savev(str(folder/(name+'.png')), 'png', [], [])


try:
    with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected menu network')):
        for size in ((320, 180), (460, 320), (980, 540)):
            host.window.resize(*size)
            settle(.1)
            screen_x, screen_y, screen_w, screen_h = monitor_bounds(host.window)
            # A right/bottom docked Mini is the difficult placement case.
            host.window.move(screen_x+screen_w-size[0]-10, screen_y+screen_h-size[1]-10)
            settle(.1)
            original = host.window.get_size()
            host.settings.show(host.anchor, size[0] == 320, 'Apple Music')
            menu = host.settings
            wait(lambda: menu.popover.get_mapped(), 'Settings did not open')
            observe_fade(menu.popover, True)
            assert_menu_fits(menu.popover)
            assert_painted(menu.popover)
            assert set(menu.section_buttons) == {'player', 'audio', 'appearance', 'system'}
            for section, button in menu.section_buttons.items():
                assert_reachable(button, menu.popover)
                assert button.get_can_focus(), 'Section navigation must work with a keyboard'
                assert button.get_ancestor(Gtk.ScrolledWindow) is None, 'Sections must stay outside scrolling content'
                button.clicked()
                settle(.32)
                assert menu.stack.get_visible_child_name() == section
                assert_menu_fits(menu.popover)
                assert host.window.get_size() == original, 'Opening a menu resized the player'
            menu.select_section('audio')
            settle(.3)
            assert_reachable(menu.scene_button, menu.popover)
            menu.select_section('player')
            settle(.3)
            assert_reachable(menu.mode_button, menu.popover)
            assert_reachable(menu.fullscreen_button, menu.popover)
            assert menu.is_open_for(host.window), 'Fullscreen must suppress shortcuts while menus are active'
            menu.section_buttons['audio'].grab_focus()
            assert menu.popover.get_focus() is menu.section_buttons['audio'], 'Section buttons cannot receive keyboard focus'
            key(menu.popover, 'Tab')
            assert menu.popover.get_focus() is not menu.section_buttons['audio'], 'Keyboard traversal did not move through menu controls'
            screenshot('settings-'+str(size[0]))
            menu.dismiss_for(host.window)
            observe_fade(menu.popover, False)
            assert not menu.is_open_for(host.window)
            assert not host.calls, 'Browsing settings changed playback or activated an action'

        # The soundstage is a second native popup with real GTK combobox menus.
        # A nested grab must return to the soundstage, not dismiss it or leave
        # a dead layer that consumes subsequent clicks.
        menu.show(host.anchor, True, 'Apple Music')
        menu.select_section('audio')
        settle(.35)
        menu.scene_button.clicked()
        wait(lambda: menu.scene_popup.get_mapped(), 'The soundstage menu failed to open')
        scene_popup = menu.scene_popup
        assert_menu_fits(scene_popup)
        assert_painted(scene_popup)
        menu.scene_control.options.popup()
        wait(lambda: menu.scene_control.options.get_property('popup-shown'), 'The soundstage combobox did not open')
        assert scene_popup.get_mapped(), 'A nested combobox closed the soundstage'
        menu.scene_control.options.popdown()
        wait(lambda: Gtk.grab_get_current() is scene_popup, 'A nested combobox did not return keyboard and pointer control')
        scene_popup.set_modal(False)
        assert Gtk.grab_get_current() is not scene_popup, 'A native file chooser could not suspend the scene grab'
        scene_popup.set_modal(True)
        assert Gtk.grab_get_current() is scene_popup, 'Closing a native chooser did not restore the scene grab'
        scene_popup.popdown()
        wait(lambda: not scene_popup.get_mapped(), 'The soundstage failed to close')
        assert not menu.scene_control.timer and not menu.scene_control.diagram.tick
        assert not host.calls, 'Opening nested settings changed audio'

        # Rapid changes cannot restore the classic theme or leave two visible
        # sections. Reduced motion must switch directly to the requested page.
        menu.show(host.anchor, False, 'Apple Music')
        menu.select_section('appearance')
        settle(.3)
        for theme in ('classic', 'christmas', 'mirrorball', 'velvet', 'nocturne'):
            assert_reachable(menu.theme_cards[theme], menu.popover)
            menu.theme_cards[theme].clicked()
            assert host.appearance.theme == theme, 'The visible theme card did not apply the actual preference'
        # A failed preference write must leave the controls truthful. The
        # previous menu restored its snow switch on failure; keep that contract.
        menu.theme_cards['christmas'].clicked()
        original_note = menu.appearance_note.get_text()
        with patch.object(host.appearance, 'save_preferences', return_value=False):
            menu.snow_switch.set_active(True)
            assert not menu.snow_switch.get_active() and not host.appearance.snow_enabled
            assert menu.appearance_note.get_text() != original_note
            menu.theme_cards['nocturne'].clicked()
            assert host.appearance.theme == 'christmas'
            assert menu.theme_cards['christmas'].get_style_context().has_class('selected')
        menu.theme_cards['nocturne'].clicked()
        assert not host.calls
        for section in ('appearance', 'audio', 'system', 'player', 'audio', 'appearance'):
            menu.select_section(section)
            settle(.025)
            assert menu.popover.get_style_context().has_class('nocturne-theme')
        wait(lambda: not menu.stack.get_transition_running(), 'A rapid tab switch left a transition alive')
        wait(lambda: not menu.navigation.active and not menu.navigation.tick,
             'A settled settings menu kept animating')
        assert menu.stack.get_visible_child_name() == 'appearance'
        settings = host.window.get_settings()
        animations = settings.get_property('gtk-enable-animations')
        settings.set_property('gtk-enable-animations', False)
        try:
            menu.popover.popdown()
            assert not menu.popover.get_mapped() and not menu.popover._tick
            menu.show(host.anchor, False, 'Apple Music')
            assert menu.popover.get_mapped() and menu.popover.get_opacity() == 1. and not menu.popover._tick
            menu.select_section('system')
            settle(.05)
            assert not menu.stack.get_transition_running()
            assert_reachable(menu.restart_button, menu.popover)
            menu.restart_button.clicked()
            wait(lambda: not menu.popover.get_mapped(), 'An action left its menu open')
            assert host.calls == [('restart',)]
        finally:
            settings.set_property('gtk-enable-animations', animations)
        host.calls.clear()

        # Sources remain one click away even when many browser sessions exist.
        # Each external row must route the EXACT session, never a stale loop
        # variable or a neighbouring source.
        sessions = [Session('org.mpris.MediaPlayer2.firefox.instance'+str(i), 'Firefox '+str(i),
            'firefox-'+str(i), properties={'Metadata': {'xesam:title':
                'Original fixture with a deliberately long title '+str(i),
                'xesam:url': 'https://music.apple.com/us/song/123' if i % 2 else 'https://youtube.com/watch?v=fixture'}})
            for i in range(24)]
        sessions.append(Session('org.mpris.MediaPlayer2.spotify', 'Spotify', 'spotify'))
        host.window.resize(320, 180)
        settle(.1)
        host.picker.show(host.source_anchor, 'apple-music', sessions, 'firefox-23')
        picker = host.picker
        settle(.25)
        assert_menu_fits(picker.popover)
        assert_painted(picker.popover)
        assert set(picker.service_buttons) == {'spotify', 'apple-music', 'youtube', 'yandex-music'}
        for button in picker.service_buttons.values():
            assert_reachable(button, picker.popover)
            assert button.get_can_focus()
        assert not picker.external_expander.get_expanded(), 'External sessions must not overwhelm the main service choices'
        assert_reachable(picker.accounts_button, picker.popover)
        assert not host.calls
        screenshot('sources-mini')
        picker.external_expander.set_expanded(True)
        settle(.4)
        assert_menu_fits(picker.popover)
        adjustment = picker.session_scroll.get_vadjustment()
        assert adjustment.get_upper() > adjustment.get_page_size(), 'Many browser sessions must scroll independently'
        adjustment.set_value(adjustment.get_upper()-adjustment.get_page_size())
        settle(.1)
        picker.session_buttons[-1].clicked()
        wait(lambda: not picker.popover.get_mapped(), 'Selecting a source left its menu open')
        assert host.calls == [('source', 'apple-music', sessions[23])], host.calls
        host.calls.clear()
        for service in picker.service_buttons:
            picker.show(host.source_anchor, 'apple-music', [], '')
            settle(.12)
            picker.service_buttons[service].clicked()
            wait(lambda: not picker.popover.get_mapped(), 'A native service did not dismiss its menu')
            assert host.calls == [('source', service, None)], host.calls
            host.calls.clear()
        picker.show(host.source_anchor, 'spotify', [], '')
        settle(.15)
        picker.accounts_button.clicked()
        wait(lambda: not picker.popover.get_mapped(), 'Connect accounts did not dismiss its menu')
        assert host.calls == [('accounts',)]
        host.calls.clear()
        picker.show(host.source_anchor, 'spotify', [], '')
        settle(.15)
        key(picker.popover, 'Escape')
        wait(lambda: not picker.popover.get_mapped(), 'Escape did not close the source menu')
        assert not host.calls, 'Closing a menu changed music sources'
        # Destroying old popups must unsubscribe theme listeners. Reopening a
        # small menu repeatedly cannot retain every old Appearance callback.
        listeners = len(host.appearance.listeners)
        for _ in range(8):
            menu.show(host.anchor, True, 'Apple Music')
            menu.select_section('player')
            picker.show(host.source_anchor, 'apple-music', [], '')
            picker.popover.popdown()
            menu.popover.popdown()
            settle(.04)
        assert len(host.appearance.listeners) <= listeners+1, 'Reopening menus retained stale theme subscriptions'
        menu.show(host.anchor, True, 'Apple Music')
        settle(.15)
        host.window.hide()
        wait(lambda: not menu.popover.get_mapped(), 'Hiding the player left an orphaned settings window')
        assert not menu.navigation.tick, 'A hidden settings menu kept rendering its navigation'
        print('PASS Liquid Glass menus: Mini/widget/fullscreen anchors, direct sections, bounded external sessions, exact routing, keyboard reachability, rapid theme-safe switching, reduced motion and lifecycle cleanup')
finally:
    for popup in (host.settings.popover, getattr(host.settings, 'scene_popup', None), host.picker.popover):
        if popup:
            popup.destroy()
    host.window.destroy()
    host.appearance.close()
    fixture.cleanup()
