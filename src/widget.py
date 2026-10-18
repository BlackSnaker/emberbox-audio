#!/usr/bin/python
"""A draggable, directly clickable Gruvbox Spotify desktop widget."""

import json
import math
import subprocess
import shutil
import signal
import threading
import time
from pathlib import Path
from paths import CACHE_DIR, CONFIG_DIR

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

import control
from audio_meter import SpotifyAudioMeter
from artwork import Artwork
from cover_tint import CoverTint
from discovery_panel import DiscoveryPanel
from hardware_controls import MuteToggle, VolumeKnob
from nixie_spectrum import NixieSpectrum
from spotify_volume import SpotifyVolume


ROOT = Path(__file__).parent
STATE = CONFIG_DIR / 'window.json'
WIDTH = 460
HEIGHT = 242
COMPACT_WIDTH = 320

CSS = b'''
/* Grunesphism: Gruvbox warmth, shallow relief, inset wells, no outer frame. */
window { background-color: transparent; border: none; box-shadow: none; }
.card {
  font-family: 'Noto Sans';
  background-color: #2c2c29;
  background-image: linear-gradient(to bottom right, #30302c, #282826);
  border: none;
  border-radius: 22px;
  box-shadow: inset 0 1px 0 rgba(255, 241, 206, 0.035);
}
.card button, .card button:focus {
  outline-style: none;
  outline-width: 0;
}
.eyebrow { color: #d79921; font-size: 9px; font-weight: bold; letter-spacing: 2px; }
.title { color: #fbf1c7; font-size: 20px; font-weight: bold; }
.artist { color: #bdae93; font-size: 12px; }
.album { color: #928374; font-size: 10px; }
.time { color: #928374; font-size: 10px; font-weight: bold; }
.hint { color: #a89984; font-size: 10px; }
.cover { border-radius: 11px; }
.cover-surface {
  padding: 5px;
  border-radius: 18px;
  background-color: #252622;
  box-shadow: inset 3px 3px 6px rgba(0, 0, 0, 0.52), inset -2px -2px 5px rgba(255, 239, 197, 0.055);
}
.lamp-well {
  padding: 6px 10px;
  border-radius: 17px;
  background-color: #292925;
  box-shadow: inset 3px 3px 7px rgba(0, 0, 0, 0.36), inset -2px -2px 5px rgba(255, 239, 197, 0.035);
}
button.control {
  background-image: linear-gradient(to bottom right, #35342f, #2a2a26);
  background-color: #302f2b;
  border: none;
  border-radius: 20px;
  color: #ebdbb2;
  box-shadow: -2px -2px 5px rgba(255, 241, 206, 0.055), 3px 3px 7px rgba(0, 0, 0, 0.42);
  min-width: 24px;
  min-height: 28px;
  padding: 3px 9px;
}
button.control:hover { background-image: linear-gradient(to bottom right, #3b3932, #302f29); color: #fabd2f; }
button.control:active { background-image: none; background-color: #292a25; box-shadow: inset 2px 2px 5px rgba(0, 0, 0, 0.5), inset -2px -2px 4px rgba(255, 241, 206, 0.055); }
button.control:disabled { color: #665c54; background-image: none; background-color: #2b2b27; box-shadow: inset 1px 1px 3px rgba(0, 0, 0, 0.25); }
button.play {
  background-color: #fabd2f;
  background-image: linear-gradient(to bottom right, #ffd15b, #e3a527);
  border-color: #fabd2f;
  color: #282828;
  font-weight: bold;
  min-width: 38px;
  min-height: 34px;
  box-shadow: -2px -2px 6px rgba(255, 214, 120, 0.11), 3px 4px 8px rgba(0, 0, 0, 0.48), inset 1px 1px 1px rgba(255, 243, 190, 0.35);
}
button.play:hover { background-image: linear-gradient(to bottom right, #ffdb76, #edb034); color: #282828; }
button.play:active { background-image: linear-gradient(to bottom right, #dea126, #f5bb3d); box-shadow: inset 3px 3px 6px rgba(97, 55, 3, 0.4), inset -1px -1px 3px rgba(255, 236, 168, 0.22); }
button.open { color: #d79921; font-size: 16px; background-color: transparent; background-image: none; box-shadow: none; min-width: 16px; min-height: 20px; padding: 1px 3px; }
button.hardware-toggle, button.hardware-toggle:hover, button.hardware-toggle:active {
  background-color: transparent; background-image: none; border: none;
  padding: 0; margin: 0; min-width: 0; min-height: 0; box-shadow: none;
}
.progress trough { min-height: 5px; border: none; box-shadow: inset 2px 2px 3px rgba(0, 0, 0, 0.6), inset -1px -1px 2px rgba(255, 241, 206, 0.07); border-radius: 5px; background-color: #20221e; }
.progress progress { min-height: 5px; border: none; box-shadow: 0 0 4px rgba(254, 128, 25, 0.18); border-radius: 5px; background-color: #fe8019; background-image: linear-gradient(to bottom, #ffc05a, #e88a29); }
.neon-caption { color: #a87842; font-size: 8px; letter-spacing: 1px; }
button.discovery-toggle { background-image: linear-gradient(to bottom right, #32322d, #2a2b26); background-color: #2d2e28; color: #ebdbb2; border: none; box-shadow: -2px -2px 5px rgba(255, 241, 206, 0.045), 3px 3px 7px rgba(0, 0, 0, 0.35); border-radius: 14px; padding: 9px 13px; }
button.discovery-toggle:hover { background-image: linear-gradient(to bottom right, #38372f, #302f28); color: #fabd2f; }
button.discovery-toggle:active { background-image: none; background-color: #282a24; box-shadow: inset 2px 2px 5px rgba(0, 0, 0, 0.45), inset -2px -2px 4px rgba(255, 241, 206, 0.045); }
.discovery-name { color: #fabd2f; font-size: 12px; font-weight: bold; }
.discovery-hint { color: #a89984; font-size: 10px; }
.drawer-heading { color: #ebdbb2; font-size: 15px; font-weight: bold; }
.caption { color: #928374; font-size: 10px; }
button.mini-button { background-image: linear-gradient(to bottom right, #34332d, #292a25); background-color: #302f2b; color: #bdae93; border: none; border-radius: 14px; box-shadow: -1px -1px 4px rgba(255, 241, 206, 0.045), 2px 2px 5px rgba(0, 0, 0, 0.35); min-width: 21px; min-height: 23px; padding: 2px 5px; font-size: 17px; }
button.mini-button:hover { color: #fabd2f; }
button.mini-button:active { background-image: none; box-shadow: inset 2px 2px 4px rgba(0, 0, 0, 0.45); }
button.filter-chip { background-image: linear-gradient(to bottom right, #32322c, #2a2b25); background-color: #2e2e28; border: none; box-shadow: -1px -1px 3px rgba(255, 241, 206, 0.04), 2px 2px 4px rgba(0, 0, 0, 0.3); color: #a89984; border-radius: 13px; padding: 5px 11px; min-height: 16px; font-size: 11px; }
button.filter-chip:hover { color: #ebdbb2; }
button.filter-chip:checked { background-image: none; background-color: #252721; color: #fabd2f; box-shadow: inset 2px 2px 4px rgba(0, 0, 0, 0.48), inset -1px -1px 3px rgba(255, 241, 206, 0.055); }
button.mix-tile { background-image: linear-gradient(to bottom right, #30302a, #292b25); background-color: #2d2e28; border: none; box-shadow: -1px -1px 4px rgba(255, 241, 206, 0.035), 2px 3px 5px rgba(0, 0, 0, 0.3); border-radius: 13px; padding: 9px; min-height: 65px; }
button.mix-tile:hover { background-image: linear-gradient(to bottom right, #36362e, #2e3028); }
button.mix-tile:active { background-image: none; background-color: #282a23; box-shadow: inset 2px 2px 5px rgba(0, 0, 0, 0.42); }
.mix-title { color: #ebdbb2; font-size: 12px; font-weight: bold; }
.mix-subtitle { color: #a89984; font-size: 10px; }
button.warm-button { background-image: linear-gradient(to bottom right, #ffd15b, #e3a527); background-color: #fabd2f; color: #282828; border: none; border-radius: 15px; box-shadow: -1px -1px 4px rgba(255, 214, 120, 0.08), 2px 3px 6px rgba(0, 0, 0, 0.38); padding: 7px 12px; font-size: 11px; font-weight: bold; }
button.warm-button:hover { background-image: linear-gradient(to bottom right, #ffdb76, #edb034); }
button.warm-button:active { box-shadow: inset 2px 2px 4px rgba(97, 55, 3, 0.35); }
button.track-row { background-image: none; background-color: transparent; border: none; box-shadow: none; border-radius: 9px; padding: 6px 7px; }
button.track-row:hover { background-color: #30312a; }
button.track-row.current-track { background-color: #252821; box-shadow: inset 2px 2px 4px rgba(0, 0, 0, 0.4), inset -1px -1px 3px rgba(255, 241, 206, 0.04); }
button.track-row.current-track .track-title { color: #fabd2f; }
.track-title { color: #ebdbb2; font-size: 12px; }
.track-number, .track-duration { color: #928374; font-size: 10px; }
entry.track-search { background-color: #252721; color: #ebdbb2; border: none; border-radius: 11px; box-shadow: inset 2px 2px 5px rgba(0, 0, 0, 0.48), inset -1px -1px 3px rgba(255, 241, 206, 0.045); min-height: 28px; font-size: 11px; }
.discovery-scroll, .filter-scroll, .discovery-scroll viewport, .filter-scroll viewport { background-color: transparent; border: none; }
.discovery-scroll scrollbar, .filter-scroll scrollbar { background-color: transparent; border: none; }
.discovery-scroll scrollbar slider, .filter-scroll scrollbar slider { background-color: #665c54; border: none; border-radius: 5px; min-width: 3px; min-height: 3px; }
button.mode-button { font-size: 10px; min-width: 30px; min-height: 20px; padding: 3px 7px; }
.card.compact { border-radius: 18px; }
.compact .cover-surface { padding: 4px; border-radius: 14px; }
.compact .lamp-well { padding: 4px 8px; border-radius: 13px; }
.compact button.control { min-width: 18px; min-height: 24px; padding: 3px 4px; }
.compact button.play { min-width: 26px; min-height: 30px; }
.compact button.mini-button { min-width: 18px; min-height: 20px; padding: 2px 4px; }
'''


def stamp(microseconds):
    seconds = max(0, int(microseconds / 1_000_000))
    return f'{seconds // 60}:{seconds % 60:02d}'


class Widget:
    def __init__(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.player = None
        self.playing = False
        self.length = 0
        self.position = 0
        self.track_id = None
        self.play_request = 0
        self.art_url = None
        self.tint_art_url = None
        self.meter = SpotifyAudioMeter()
        self.artwork = Artwork()
        try:
            saved = json.loads(STATE.read_text())
        except (OSError, ValueError):
            saved = {}
        self.expanded = bool(saved.get('expanded', False))
        self.compact = bool(saved.get('compact', False))
        self.visual_levels = [0.0] * 9
        self.visual_velocity = [0.0] * 9
        self.visual_frame_time = None
        self.save_timer = 0
        self.positioned = False
        self.drag_offset = None
        self.last_size = None

        self.window = Gtk.Window(title='Emberbox Audio')
        self.window.set_name('emberbox-audio')
        self.window.set_decorated(False)
        self.window.set_deletable(False)
        self.window.set_focus_on_map(False)
        self.window.set_resizable(False)
        self.window.set_default_size(WIDTH, HEIGHT)
        self.window.set_size_request(WIDTH, HEIGHT)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_keep_below(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.window.stick()
        self.window.connect('delete-event', lambda *_args: True)
        self.window.connect('destroy', self.on_destroy)
        self.window.connect('configure-event', self.on_configure)
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)

        outside = Gtk.Box()
        outside.set_margin_top(0)
        outside.set_margin_bottom(0)
        outside.set_margin_start(0)
        outside.set_margin_end(0)
        self.window.add(outside)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.card = card
        card.get_style_context().add_class('card')
        self.cover_tint = CoverTint(card)
        card.set_margin_top(0)
        card.set_margin_bottom(0)
        card.set_margin_start(0)
        card.set_margin_end(0)
        outside.pack_start(card, True, True, 0)

        header = Gtk.EventBox()
        self.header = header
        header.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                          Gdk.EventMask.BUTTON_RELEASE_MASK |
                          Gdk.EventMask.POINTER_MOTION_MASK)
        header.connect('button-press-event', self.on_drag)
        header.connect('motion-notify-event', self.on_drag_motion)
        header.connect('button-release-event', self.on_drag_end)
        header.set_margin_top(11)
        header.set_margin_start(15)
        header.set_margin_end(15)
        card.pack_start(header, False, False, 0)
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add(header_row)
        eyebrow = Gtk.Label(label='●  EMBERBOX   /   AUDIO')
        eyebrow.get_style_context().add_class('eyebrow')
        eyebrow.set_halign(Gtk.Align.START)
        header_row.pack_start(eyebrow, True, True, 0)
        neon_caption = Gtk.Label(label='●  LIVE AUDIO')
        neon_caption.get_style_context().add_class('neon-caption')
        self.mini_button = Gtk.Button(label='Mini')
        self.mini_button.get_style_context().add_class('mini-button')
        self.mini_button.get_style_context().add_class('mode-button')
        self.mini_button.get_accessible().set_description('Компактный режим: обложка, кнопки и лампы')
        self.mini_button.connect('clicked', self.toggle_compact)
        header_row.pack_end(self.mini_button, False, False, 0)
        header_row.pack_end(neon_caption, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=13)
        self.body = body
        body.set_margin_start(15)
        body.set_margin_end(15)
        body.set_margin_bottom(0)
        body.set_size_request(-1, 135)
        card.pack_start(body, False, False, 0)

        self.cover = Gtk.Image()
        self.load_cover()
        self.cover.get_style_context().add_class('cover')
        cover_surface = Gtk.Box()
        cover_surface.get_style_context().add_class('cover-surface')
        cover_surface.set_valign(Gtk.Align.CENTER)
        cover_surface.pack_start(self.cover, False, False, 0)
        cover_drag = Gtk.EventBox()
        cover_drag.set_visible_window(False)
        cover_drag.get_accessible().set_description('Перетащи за обложку, чтобы переместить плеер')
        cover_drag.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                              Gdk.EventMask.BUTTON_RELEASE_MASK |
                              Gdk.EventMask.POINTER_MOTION_MASK)
        cover_drag.connect('button-press-event', self.on_drag)
        cover_drag.connect('motion-notify-event', self.on_drag_motion)
        cover_drag.connect('button-release-event', self.on_drag_end)
        cover_drag.add(cover_surface)
        body.pack_start(cover_drag, False, False, 0)

        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.details = details
        body.pack_start(details, True, True, 0)
        self.title = Gtk.Label(label='Ready when you are')
        self.title.set_xalign(0)
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.title.set_max_width_chars(24)
        self.title.get_style_context().add_class('title')
        details.pack_start(self.title, False, False, 0)
        self.artist = Gtk.Label(label='Open Spotify to begin')
        self.artist.set_xalign(0)
        self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist.get_style_context().add_class('artist')
        details.pack_start(self.artist, False, False, 0)
        self.album = Gtk.Label()
        self.album.set_xalign(0)
        self.album.set_ellipsize(Pango.EllipsizeMode.END)
        self.album.set_max_width_chars(40)
        self.album.get_style_context().add_class('album')
        details.pack_start(self.album, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.get_style_context().add_class('progress')
        self.progress.set_margin_top(8)
        self.progress_event = Gtk.EventBox()
        self.progress_event.add(self.progress)
        self.progress_event.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.progress_event.connect('button-press-event', self.on_seek)
        details.pack_start(self.progress_event, False, False, 0)

        self.time = Gtk.Label(label='0:00  /  0:00')
        self.time.set_xalign(0)
        self.time.get_style_context().add_class('time')
        details.pack_start(self.time, False, False, 0)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.controls = controls
        details.pack_end(controls, False, False, 0)
        self.sound = SpotifyVolume(self.on_volume_changed)
        self.mute_toggle = MuteToggle(self.sound.toggle_mute)
        self.volume_knob = VolumeKnob(self.sound.set_volume)
        controls.pack_start(self.mute_toggle, False, False, 0)
        self.transport = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.transport.set_halign(Gtk.Align.CENTER)
        self.transport.set_valign(Gtk.Align.CENTER)
        controls.pack_start(self.transport, True, True, 0)
        controls.pack_end(self.volume_knob, False, False, 0)
        self.previous = self.button('⏮', 'previous', 'Предыдущий трек')
        self.play = self.button('▶', 'toggle', 'Воспроизвести или приостановить', 'play')
        self.next = self.button('⏭', 'next', 'Следующий трек')
        self.open = self.button('↗', 'open', 'Открыть Spotify', 'open')
        for button in (self.previous, self.play, self.next):
            self.transport.pack_start(button, False, False, 0)
        header_row.pack_end(self.open, False, False, 0)
        self.restore_button = Gtk.Button()
        self.restore_button.set_image(Gtk.Image.new_from_icon_name('view-fullscreen-symbolic', Gtk.IconSize.MENU))
        self.restore_button.get_style_context().add_class('mini-button')
        self.restore_button.set_valign(Gtk.Align.CENTER)
        self.restore_button.get_accessible().set_name('Развернуть плеер')
        self.restore_button.connect('clicked', self.toggle_compact)
        controls.pack_end(self.restore_button, False, False, 0)
        self.on_volume_changed(self.sound)

        self.equalizer = NixieSpectrum()
        self.equalizer.get_style_context().add_class('lamp-well')
        card.pack_start(self.equalizer, False, False, 0)

        self.discovery_button = Gtk.Button()
        self.discovery_button.get_style_context().add_class('discovery-toggle')
        self.discovery_button.set_margin_start(18)
        self.discovery_button.set_margin_end(18)
        self.discovery_button.set_margin_bottom(10)
        entry = Gtk.Box(spacing=10)
        name = Gtk.Label(label='✦  For you')
        name.get_style_context().add_class('discovery-name')
        entry.pack_start(name, False, False, 0)
        hint = Gtk.Label(label='Mixes · discoveries · tracks')
        hint.get_style_context().add_class('discovery-hint')
        entry.pack_start(hint, True, True, 0)
        self.chevron = Gtk.Label(label='⌃' if self.expanded else '⌄')
        entry.pack_end(self.chevron, False, False, 0)
        self.discovery_button.add(entry)
        self.discovery_button.connect('clicked', self.toggle_discovery)
        card.pack_start(self.discovery_button, False, False, 0)
        self.drawer = Gtk.Revealer()
        self.drawer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.drawer.set_transition_duration(240)
        self.panel = DiscoveryPanel(self.artwork, self.play_uri, self.connect_for_discovery)
        self.panel.layout_changed = self.reflow
        self.drawer.add(self.panel)
        card.pack_start(self.drawer, False, False, 0)
        self.drawer.connect('notify::child-revealed', lambda *_args: self.reflow())

        self.window.show_all()
        self.panel.show_home()
        self.apply_layout()
        if self.expanded and not self.compact:
            GLib.idle_add(self.panel.open)
        GLib.idle_add(self.place_window)
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)
        self.window.add_tick_callback(self.animate)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)

    def button(self, label, action, tooltip, css_class=None):
        button = Gtk.Button(label=label)
        button.get_style_context().add_class('control')
        if css_class:
            button.get_style_context().add_class(css_class)
        button.get_accessible().set_name(tooltip)
        button.connect('clicked', self.on_action, action)
        return button

    def quit(self):
        self.save_position()
        self.window.destroy()
        return False

    def on_destroy(self, _window):
        self.meter.stop()
        self.sound.close()
        self.artwork.pool.shutdown(wait=False, cancel_futures=True)
        Gtk.main_quit()

    def layout_width(self):
        return COMPACT_WIDTH if self.compact else WIDTH

    def apply_layout(self):
        style = self.card.get_style_context()
        if self.compact:
            style.add_class('compact')
        else:
            style.remove_class('compact')
        self.card.set_spacing(8 if self.compact else 10)
        self.card.set_margin_top(10 if self.compact else 0)
        self.card.set_margin_bottom(10 if self.compact else 0)
        self.body.set_size_request(-1, 78 if self.compact else 135)
        self.body.set_margin_start(12 if self.compact else 15)
        self.body.set_margin_end(12 if self.compact else 15)
        self.details.set_valign(Gtk.Align.CENTER if self.compact else Gtk.Align.FILL)
        self.controls.set_halign(Gtk.Align.CENTER if self.compact else Gtk.Align.FILL)
        self.controls.set_spacing(5 if self.compact else 7)
        self.transport.set_spacing(8 if self.compact else 7)
        self.mute_toggle.set_compact(self.compact)
        self.volume_knob.set_compact(self.compact)
        for child in (self.header, self.title, self.artist, self.album,
                      self.progress_event, self.time, self.open, self.discovery_button):
            child.set_visible(not self.compact)
        self.restore_button.set_visible(self.compact)
        self.equalizer.set_compact(self.compact)
        if self.compact:
            self.drawer.set_reveal_child(False)
            self.drawer.hide()
        else:
            self.drawer.show()
            self.drawer.set_reveal_child(self.expanded)
        self.load_cover(preserve=True)
        self.window.set_size_request(self.layout_width(), 1 if self.compact else HEIGHT)
        self.reflow()

    def toggle_compact(self, _button):
        self.compact = not self.compact
        self.apply_layout()
        if not self.compact and self.expanded:
            self.panel.open()
        if self.positioned:
            self.save_position()

    def toggle_discovery(self, _button):
        if self.compact:
            return
        self.expanded = not self.expanded
        self.chevron.set_text('⌃' if self.expanded else '⌄')
        self.drawer.set_reveal_child(self.expanded)
        if self.expanded:
            self.panel.open()
        self.save_position()

    def reflow(self):
        self.window.resize(self.layout_width(), 1)
        GLib.timeout_add(100, self.fit_window)
        return False

    def fit_window(self):
        if not self.positioned:
            return False
        width, height = self.window.get_size()
        x, y = self.window.get_position()
        monitor = self.window.get_display().get_monitor_at_point(x + width // 2, y + 40)
        if monitor:
            area = monitor.get_geometry()
            target_x = max(area.x, min(x, area.x + area.width - width))
            target_y = max(area.y + 34, min(y, area.y + area.height - height - 10))
            if (x, y) != (target_x, target_y):
                self.window.move(target_x, target_y)
        return False

    def launch_spotify(self, uri=None):
        flags = ['--remote-debugging-port=43827', '--remote-debugging-address=127.0.0.1']
        if shutil.which('spotify'):
            command = [shutil.which('spotify'), *flags]
        elif shutil.which('flatpak'):
            command = ['flatpak', 'run', '--command=spotify', 'com.spotify.Client', *flags]
        else:
            self.panel.notice.set_text('Install the Spotify desktop client first.')
            return
        if uri:
            command.append(uri)
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def connect_for_discovery(self):
        def work():
            try:
                from discovery import LocalSpotify
                with LocalSpotify():
                    return
            except Exception:
                pass
            connection = control.bus()
            name = control.player_name(connection)
            if name:
                try:
                    connection.call_sync(name, control.PATH, 'org.mpris.MediaPlayer2', 'Quit',
                                         None, None, Gio.DBusCallFlags.NONE, 1000, None)
                    for _ in range(25):
                        if not control.player_name(connection):
                            break
                        time.sleep(0.2)
                except GLib.Error:
                    pass
            self.launch_spotify()
        threading.Thread(target=work, daemon=True).start()

    def play_uri(self, uri):
        if not uri.startswith(('spotify:track:', 'spotify:playlist:', 'spotify:album:')):
            return
        from discovery import ConnectionUnavailable, LocalSpotify

        self.play_request += 1
        request = self.play_request
        self.panel.notice.set_text('Starting playback…')
        self.panel.reconnect.hide()

        def work():
            error = None
            try:
                with LocalSpotify() as spotify:
                    if request != self.play_request:
                        return
                    spotify.play(uri)
            except Exception as exc:
                error = exc
            GLib.idle_add(done, error)

        def done(error):
            if request != self.play_request:
                return False
            if error:
                self.panel.notice.set_text(str(error) or 'Could not play this track.')
                if isinstance(error, ConnectionUnavailable):
                    self.panel.reconnect.show()
            else:
                self.panel.notice.set_text('')
                self.refresh_once()
                GLib.timeout_add(450, self.refresh_once)
            self.reflow()
            return False

        threading.Thread(target=work, name='spotify-playback', daemon=True).start()

    def place_window(self):
        try:
            data = json.loads(STATE.read_text())
            x, y = int(data['x']), int(data['y'])
        except (OSError, ValueError, KeyError, TypeError):
            screen = self.window.get_screen()
            index = screen.get_primary_monitor()
            if index < 0:
                index = 0
            area = screen.get_monitor_geometry(index)
            x = area.x + area.width - self.layout_width() - 30
            y = area.y + area.height - (164 if self.compact else HEIGHT) - 40
        self.window.move(x, y)
        # Mutter finishes placing a newly mapped window asynchronously.
        # Wait for the drawer's first layout before enabling position updates.
        GLib.timeout_add(500, self.finish_initial_position, x, y)
        return False

    def finish_initial_position(self, x, y):
        self.window.move(x, y)
        GLib.timeout_add(250, self.enable_position_tracking)
        return False

    def enable_position_tracking(self):
        self.positioned = True
        self.fit_window()
        self.save_position()
        return False

    def on_configure(self, _window, _event):
        size = (_event.width, _event.height)
        if size != self.last_size:
            self.last_size = size
            if self.positioned and self.drag_offset is None:
                GLib.idle_add(self.fit_window)
        if self.positioned:
            if self.save_timer:
                GLib.source_remove(self.save_timer)
            self.save_timer = GLib.timeout_add(400, self.save_position)
        return False

    def save_position(self):
        self.save_timer = 0
        x, y = self.window.get_position()
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({'x': x, 'y': y, 'expanded': self.expanded,
                                     'compact': self.compact}) + '\n')
        return False

    def on_drag(self, _box, event):
        if event.button == 1:
            x, y = self.window.get_position()
            self.drag_offset = (event.x_root - x, event.y_root - y)
            return True
        return False

    def on_drag_motion(self, _box, event):
        if self.drag_offset is not None:
            x = round(event.x_root - self.drag_offset[0])
            y = round(event.y_root - self.drag_offset[1])
            self.window.move(x, y)
            return True
        return False

    def on_drag_end(self, _box, event):
        if event.button == 1 and self.drag_offset is not None:
            self.drag_offset = None
            self.save_position()
            return True
        return False

    def on_seek(self, _box, event):
        if event.button != 1 or not self.player or not self.length or not self.track_id:
            return False
        width = max(1, self.progress_event.get_allocated_width())
        position = round(max(0, min(1, event.x / width)) * self.length)
        self.call('SetPosition', GLib.Variant('(ox)', (self.track_id, position)))
        GLib.timeout_add(150, self.refresh_once)
        return True

    def on_action(self, _button, action):
        print(f'clicked {action}', flush=True)
        if action == 'open' or (action == 'toggle' and not self.player):
            if self.player:
                try:
                    self.connection.call_sync(self.player, control.PATH, 'org.mpris.MediaPlayer2',
                                              'Raise', None, None, Gio.DBusCallFlags.NONE, 1000, None)
                except GLib.Error:
                    self.launch_spotify()
            else:
                self.launch_spotify()
            return
        method = {'previous': 'Previous', 'toggle': 'PlayPause', 'next': 'Next'}.get(action)
        if method and self.player:
            self.call(method)
            GLib.timeout_add(150, self.refresh_once)

    def refresh_once(self):
        self.refresh()
        return False

    def call(self, method, args=None):
        try:
            self.connection.call_sync(self.player, control.PATH, control.PLAYER, method,
                                      args, None, Gio.DBusCallFlags.NONE, 1200, None)
        except GLib.Error as error:
            print(f'Spotify {method}: {error.message}', flush=True)

    def set_art(self, url):
        if url == self.art_url:
            return
        self.art_url = url
        self.load_cover()

    def load_cover(self, preserve=False):
        if not self.art_url:
            self.cover_tint.set_cover(None)
            self.tint_art_url = None
        self.artwork.load(self.cover, self.art_url or '', 64 if self.compact else 112,
                          10 if self.compact else 13, preserve=preserve,
                          on_loaded=self.on_cover_loaded)

    def on_cover_loaded(self, pixbuf):
        if self.art_url and self.tint_art_url != self.art_url:
            self.cover_tint.set_cover(pixbuf)
            self.tint_art_url = self.art_url

    def on_volume_changed(self, sound):
        self.mute_toggle.set_state(sound.volume, sound.muted, sound.available)
        self.volume_knob.set_state(sound.volume, sound.muted, sound.available)

    def refresh(self):
        try:
            name = control.player_name(self.connection)
            if not name:
                self.player = None
                self.sound.refresh(None)
                self.playing = False
                self.meter.stop()
                self.length = 0
                self.track_id = None
                self.title.set_text('Ready when you are')
                self.artist.set_text('Open Spotify to begin')
                self.album.set_text('')
                self.time.set_text('0:00  /  0:00')
                self.progress.set_fraction(0)
                self.previous.set_sensitive(False)
                self.next.set_sensitive(False)
                self.play.set_label('▶')
                self.set_art(None)
                return True

            self.player = name
            self.sound.refresh(name)
            metadata = control.property_value(self.connection, name, 'Metadata')
            status = control.property_value(self.connection, name, 'PlaybackStatus')
            self.playing = status == 'Playing'
            if self.playing:
                self.meter.start()
            else:
                self.meter.stop()
            self.length = int(metadata.get('mpris:length', 0))
            self.track_id = metadata.get('mpris:trackid')
            try:
                self.position = int(control.property_value(self.connection, name, 'Position'))
            except GLib.Error:
                self.position = 0
            self.title.set_text(str(metadata.get('xesam:title') or 'Spotify'))
            artists = metadata.get('xesam:artist') or []
            self.artist.set_text(', '.join(artists) if artists else 'Музыка')
            self.album.set_text(str(metadata.get('xesam:album') or ''))
            track_id = str(metadata.get('mpris:trackid') or '').rsplit('/', 1)[-1]
            self.panel.update_current('spotify:track:' + track_id)
            self.time.set_text(f'{stamp(self.position)}  /  {stamp(self.length)}')
            self.progress.set_fraction(max(0, min(1, self.position / self.length)) if self.length else 0)
            self.previous.set_sensitive(True)
            self.next.set_sensitive(True)
            self.play.set_label('Ⅱ' if self.playing else '▶')
            self.set_art(metadata.get('mpris:artUrl'))
        except (GLib.Error, ValueError, TypeError) as error:
            print(f'Spotify refresh: {error}', flush=True)
        return True

    def animate(self, _window, frame_clock):
        frame_time = frame_clock.get_frame_time()
        elapsed = ((frame_time - self.visual_frame_time) / 1_000_000
                   if self.visual_frame_time is not None else 1 / 60)
        self.visual_frame_time = frame_time
        if elapsed <= 0:
            return True
        # Resume gently after a hidden window or a stalled compositor.
        elapsed = min(elapsed, 0.05)
        if self.playing and time.monotonic() - self.meter.last_sample < 0.35:
            targets = self.meter.levels
        else:
            targets = (0.0,) * 9
        for index in range(len(self.visual_levels)):
            old = self.visual_levels[index]
            target = targets[index]
            velocity = self.visual_velocity[index]
            # Analytic critical damping keeps velocity continuous between samples.
            # The discharge rises quickly; residual light settles more slowly.
            rate = 24.0 if target > old else 11.0
            offset = old - target
            momentum = velocity + rate * offset
            decay = math.exp(-rate * elapsed)
            level = target + (offset + momentum * elapsed) * decay
            velocity = (velocity - rate * momentum * elapsed) * decay
            if level < 0 or level > 1:
                level = max(0.0, min(1.0, level))
                velocity = 0.0
            elif abs(level - target) < 0.0001 and abs(velocity) < 0.003:
                level, velocity = target, 0.0
            self.visual_levels[index] = level
            self.visual_velocity[index] = velocity
        self.equalizer.set_levels(self.visual_levels)
        return True


if __name__ == '__main__':
    from paths import instance_lock
    _instance = instance_lock()
    Widget()
    Gtk.main()
