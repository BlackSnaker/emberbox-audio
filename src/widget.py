#!/usr/bin/python
"""A draggable, directly clickable Gruvbox music desktop widget."""

import os
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
from sources import Monitor, choose_session
from stream_target import Target
from source_picker import SourcePicker, text
from apple_bridge import AppleBridge
from apple_library import AppleLibraryPanel
from apple_web import AppleWeb
from yandex_web import YandexWeb
from yandex_panel import YandexPanel
from accounts import Accounts
from account_panel import AccountPanel
from ember_mpris import EmberMpris
from frame_health import FrameHealth
from fullscreen import FullscreenPlayer
from desktop_launch import launch as launch_desktop
import desktop_window
from kwin_desktop import KWinDesktop
from widget_settings import SettingsMenu, settings_button
import widget_restart
from youtube_audio import YouTubeAudio
from youtube_panel import YouTubePanel


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
button.source-button { font-size: 10px; min-height: 22px; padding: 2px 7px; }
.source-popover button, .source-popover button:focus { outline-style: none; outline-width: 0; }
.source-popover { background-color: #2c2c29; color: #ebdbb2; border-radius: 16px; border-color: #504945; }
button.settings-button { min-width: 18px; min-height: 18px; padding: 3px; border-radius: 12px; color: #bdae93; }
button.settings-button:hover { color: #fabd2f; }
.settings-popover { background-color: #2c2c29; color: #ebdbb2; border-radius: 16px; border: 1px solid #504945; box-shadow: none; }
.settings-popover button, .settings-popover button:focus { outline-style: none; outline-width: 0; }
.settings-popover button.settings-action { min-height: 24px; padding: 7px 12px; border-radius: 11px; }
.settings-popover .drawer-heading { font-size: 14px; }
.account-card { background-color: #30302b; border-radius: 15px; padding: 13px;
  box-shadow: -2px -2px 5px rgba(255,241,206,0.035), 3px 3px 7px rgba(0,0,0,0.24); }
.account-title { color: #fbf1c7; font-size: 15px; font-weight: bold; }
.account-status { color: #b8bb26; font-size: 10px; }
.account-spotify { color: #b8bb26; font-size: 17px; }
.account-apple { color: #d3869b; font-size: 17px; }
.account-yandex { color: #fabd2f; font-size: 17px; }
.account-card button { border-radius: 10px; padding: 6px 10px; }
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

        self.apple = AppleBridge()
        self.apple_web = AppleWeb(self.on_apple_changed)
        self.yandex_web = YandexWeb(self.on_yandex_changed)
        self.apple_was_connected = False
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.mpris = EmberMpris(self.connection,self.system_action,self.seek_to,self.system_volume)
        self.player = None
        self.session = None
        self.sessions = []
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
        self.source = saved.get('source', 'spotify')
        if self.source not in ('spotify', 'apple-music', 'youtube','yandex-music'):
            self.source = 'spotify'
        self.browser_binding = str(saved.get('apple_browser', ''))
        self.apple_mode = 'browser' if saved.get('apple_mode') == 'browser' else 'native'
        self.youtube_binding = str(saved.get('youtube_browser', ''))
        self.youtube_mode = 'browser' if saved.get('youtube_mode') == 'browser' else 'native'
        self.youtube_render_timer = 0
        self.youtube_last_sound = 0.
        self.youtube = YouTubeAudio(self.on_youtube_changed)
        self.monitor = Monitor(self.connection, self.on_sessions)
        self.accounts_visible = False
        self.accounts = Accounts(self.apple_web,self.on_accounts_changed,self.open_spotify_login,
                                 self.connect_for_discovery,self.account_source,self.yandex_web)
        self.source_picker = SourcePicker(self.select_source, self.launch_apple,self.show_accounts)
        self.fullscreen = None
        self.kwin_desktop = None
        self.settings = SettingsMenu(lambda: self.toggle_compact(None), self.reconnect_player, self.restart_widget,self.show_accounts,self.show_fullscreen)
        self.restarting = False
        self.resources_closed = False
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
        self.window.set_resizable(False)
        self.window.set_default_size(WIDTH, HEIGHT)
        self.window.set_size_request(WIDTH, HEIGHT)
        self.desktop_mode = desktop_window.configure(self.window)
        self.window.connect('delete-event', lambda *_args: True)
        self.window.connect('destroy', self.on_destroy)
        self.window.connect('configure-event', self.on_configure)
        self.window.connect('key-press-event',self.on_stage_key)
        self.window.get_screen().connect('monitors-changed', lambda *_args: GLib.idle_add(self.fit_window))
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
        self.source_button = Gtk.Button(label='●  SPOTIFY  ⌄')
        self.source_button.get_style_context().add_class('filter-chip')
        self.source_button.get_style_context().add_class('source-button')
        self.source_button.set_halign(Gtk.Align.START)
        self.source_button.get_accessible().set_name(text('Switch music source', 'Выбрать источник музыки'))
        self.source_button.connect('clicked', self.show_sources)
        header_row.pack_start(self.source_button, True, True, 0)
        neon_caption = Gtk.Label(label='●  LIVE AUDIO')
        neon_caption.get_style_context().add_class('neon-caption')
        self.mini_button = Gtk.Button(label='Mini')
        self.mini_button.get_style_context().add_class('mini-button')
        self.mini_button.get_style_context().add_class('mode-button')
        self.mini_button.get_accessible().set_description('Компактный режим: обложка, кнопки и лампы')
        self.mini_button.connect('clicked', self.toggle_compact)
        header_row.pack_end(self.mini_button, False, False, 0)
        self.settings_button = settings_button(self.show_settings)
        header_row.pack_end(self.settings_button, False, False, 0)
        self.fullscreen_button = Gtk.Button()
        icon=Gtk.Image.new_from_icon_name('view-fullscreen-symbolic',Gtk.IconSize.MENU)
        icon.set_pixel_size(14);self.fullscreen_button.add(icon)
        self.fullscreen_button.get_style_context().add_class('mini-button')
        self.fullscreen_button.get_style_context().add_class('settings-button')
        self.fullscreen_button.get_accessible().set_name(text('Listening room · Fullscreen','Комната прослушивания · На весь экран'))
        self.fullscreen_button.connect('clicked',lambda _b:self.show_fullscreen())
        header_row.pack_end(self.fullscreen_button,False,False,0)
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
        cover_overlay = Gtk.Overlay()
        cover_overlay.add(cover_drag)
        self.compact_source = Gtk.Button(label='S⌄')
        self.compact_source.get_style_context().add_class('filter-chip')
        self.compact_source.get_style_context().add_class('source-button')
        self.compact_source.set_halign(Gtk.Align.START)
        self.compact_source.set_valign(Gtk.Align.START)
        self.compact_source.get_accessible().set_name(text('Switch music source', 'Выбрать источник музыки'))
        self.compact_source.connect('clicked', self.show_sources)
        cover_overlay.add_overlay(self.compact_source)
        self.compact_settings = settings_button(self.show_settings)
        self.compact_settings.set_halign(Gtk.Align.END)
        self.compact_settings.set_valign(Gtk.Align.END)
        self.compact_settings.set_margin_end(2)
        self.compact_settings.set_margin_bottom(2)
        cover_overlay.add_overlay(self.compact_settings)
        body.pack_start(cover_overlay, False, False, 0)

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
        name = self.discovery_name = Gtk.Label(label='✦  For you')
        name.get_style_context().add_class('discovery-name')
        entry.pack_start(name, False, False, 0)
        hint = self.discovery_hint = Gtk.Label(label='Mixes · discoveries · tracks')
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
        self.panel = DiscoveryPanel(self.artwork, self.play_uri, lambda:self.show_accounts('spotify'))
        self.panel.layout_changed = self.reflow
        self.apple_panel = AppleLibraryPanel(self.artwork, self.apple_web if self.apple_mode == 'native' else self.apple, self.play_apple_uri, self.setup_apple_library)
        self.apple_panel.layout_changed = self.reflow
        self.library_stack = Gtk.Stack()
        self.library_stack.set_homogeneous(False)
        self.library_stack.add_named(self.panel, 'spotify')
        self.library_stack.add_named(self.apple_panel, 'apple-music')
        self.yandex_panel = YandexPanel(self.artwork,self.yandex_web,self.start_yandex_wave,
            lambda:self.show_accounts('yandex-music'),self.reflow)
        self.library_stack.add_named(self.yandex_panel,'yandex-music')
        self.account_panel = AccountPanel(self.accounts,self.hide_accounts,lambda:self.window,
                                        lambda:self.reflow() if self.accounts_visible else False)
        self.library_stack.add_named(self.account_panel,'accounts')
        self.youtube_panel = YouTubePanel(self.artwork, self.play_youtube, self.youtube_status, lambda:self.youtube.queue)
        self.youtube_panel.layout_changed = self.reflow
        self.library_stack.add_named(self.youtube_panel, 'youtube')
        self.drawer.add(self.library_stack)
        card.pack_start(self.drawer, False, False, 0)
        self.drawer.connect('notify::child-revealed', lambda *_args: self.reflow())

        self.window.show_all()
        self.panel.show_home()
        self.apple_panel.show_home()
        self.youtube.set_enabled(self.source == 'youtube' and self.youtube_mode == 'native')
        self.apple_web.set_enabled(self.apple_native())
        self.yandex_web.set_enabled(self.source=='yandex-music')
        self.apply_layout()
        self.update_source_ui()
        if self.expanded and not self.compact:
            GLib.idle_add(self.active_panel().open)
        if not saved:
            GLib.idle_add(self.show_accounts)
        GLib.idle_add(self.place_window)
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)
        self.frame_health = FrameHealth(self.window,self.animate)
        if self.desktop_mode == 'normal':
            self.kwin_desktop = KWinDesktop()
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
        self.close_resources()
        Gtk.main_quit()

    def close_resources(self):
        if self.resources_closed:
            return
        self.resources_closed = True
        if self.kwin_desktop:self.kwin_desktop.close()
        self.frame_health.close()
        if self.fullscreen:self.fullscreen.close()
        self.youtube_panel.close()
        self.youtube.close()
        self.accounts.close()
        self.mpris.close()
        self.apple.close()
        self.apple_web.close()
        self.yandex_web.close()
        self.yandex_panel.close()
        self.monitor.close()
        self.meter.stop()
        self.sound.close()
        self.artwork.pool.shutdown(wait=False, cancel_futures=True)

    def show_fullscreen(self):
        if self.fullscreen is None:self.fullscreen=FullscreenPlayer(self)
        self.fullscreen.open()

    def on_stage_key(self,_window,event):
        if Gdk.keyval_name(event.keyval)=='F11':self.show_fullscreen();return True
        return False

    def show_settings(self, button):
        self.drag_offset = None
        self.settings.show(button, self.compact, {'spotify':'Spotify','apple-music':'Apple Music','youtube':'YouTube','yandex-music':text('Yandex Music','Яндекс Музыка')}[self.source])

    def show_accounts(self, service=None):
        if self.compact:
            self.toggle_compact(None)
        self.accounts_visible = True
        self.expanded = True
        self.update_source_ui()
        self.drawer.set_reveal_child(True)
        self.account_panel.open()
        self.reflow()
        return False

    def hide_accounts(self):
        self.accounts_visible = False
        self.update_source_ui()
        self.active_panel().open()
        self.reflow()

    def on_accounts_changed(self):
        if hasattr(self,'account_panel') and not getattr(self,'resources_closed',True):
            self.account_panel.update()

    def account_source(self,source):
        self.select_source(source)
        self.expanded = True
        self.drawer.set_reveal_child(True)
        self.active_panel().open()
        self.reflow()

    def reconnect_player(self):
        self.play_request += 1
        self.meter.stop()
        self.visual_levels = [0.] * 9
        self.visual_velocity = [0.] * 9
        self.equalizer.set_levels(self.visual_levels)
        self.monitor.poll()
        if self.native_web():
            self.native_web().ensure_started()
            self.native_web().poll()
        if self.expanded and not self.compact:
            panel = self.active_panel()
            panel.on_refresh(None)

    def restart_widget(self):
        if self.restarting:
            return
        self.restarting = True
        self.drag_offset = None
        self.save_position()
        self.youtube.save()
        self.sound.flush()
        try:
            if widget_restart.service_restart():
                return
            self.close_resources()
            widget_restart.replace_process(ROOT / 'widget.py')
        except OSError as error:
            self.restarting = False
            print(f'Widget restart failed: {error}', flush=True)

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
        self.compact_source.set_visible(self.compact)
        self.compact_settings.set_visible(self.compact)
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
            self.active_panel().open()
        if self.positioned:
            self.save_position()

    def toggle_discovery(self, _button):
        if self.compact:
            return
        self.expanded = not self.expanded
        self.chevron.set_text('⌃' if self.expanded else '⌄')
        self.drawer.set_reveal_child(self.expanded)
        if self.expanded:
            self.active_panel().open()
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
        monitor = desktop_window.monitor_for(self.window)
        if monitor:
            area = desktop_window.usable_area(monitor)
            target_x, target_y = desktop_window.clamp_position(x, y, width, height, area)
            if (x, y) != (target_x, target_y):
                self.window.move(target_x, target_y)
        return False

    def show_sources(self, button):
        self.monitor.poll()
        self.source_picker.show(button, self.source, self.sessions, self.browser_binding, self.youtube_binding, self.youtube_mode)

    def select_source(self, source, session=None):
        self.accounts_visible = False
        previous = self.session
        if not (self.youtube_native() and source == 'youtube' and session is None):
            self.youtube.set_enabled(False)
        self.source = source
        if source == 'youtube':
            self.youtube_mode = 'browser' if session else 'native'
        if source == 'apple-music':
            self.apple_mode = 'browser' if session else 'native'
        self.apple_web.set_enabled(self.apple_native())
        self.yandex_web.set_enabled(self.source=='yandex-music')
        apple_bridge = self.apple_web if self.apple_mode == 'native' else self.apple
        if self.apple_panel.bridge is not apple_bridge:
            self.apple_panel.pages = {}
            self.apple_panel.selected = None
        self.apple_panel.bridge = apple_bridge
        self.apple_panel.native = self.apple_mode == 'native'
        self.apple_panel.reconnect.set_label(text('Sign in to Apple Music','Войти в Apple Music') if self.apple_panel.native else text('Connect Firefox companion','Подключить Firefox'))
        if session:
            if source == 'youtube':
                self.youtube_binding = session.binding
            else:
                self.browser_binding = session.binding
            self.player = session.name
        else:
            self.player = None
        self.play_request += 1
        # A deliberate change pauses the previous source; it never autoplays
        # the next one. Closing a popover cannot start music or open a window.
        binding = self.youtube_binding if source == 'youtube' else self.browser_binding
        selected = choose_session(self.sessions, self.source, binding, self.player or '') if not (self.youtube_native() or self.native_web()) else None
        if previous and previous.properties.get('PlaybackStatus') == 'Playing':
            if not selected or previous.name != selected.name:
                self.monitor.call(previous, 'Pause')
        self.meter.stop()
        self.visual_levels = [0.] * 9
        self.visual_velocity = [0.] * 9
        self.youtube.set_enabled(self.youtube_native())
        self.update_source_ui()
        self.apply_layout()
        self.apply_sessions()
        if self.expanded and not self.compact:
            self.active_panel().open()
        self.save_position()
        self.monitor.poll()
        if self.youtube_native() and not self.youtube.current:
            self.show_youtube_search()
        if self.apple_native() and not self.apple_web.state.get('title'):
            self.show_apple_library()

    def update_source_ui(self):
        names = {'spotify':'SPOTIFY', 'apple-music':'APPLE MUSIC', 'youtube':'YOUTUBE','yandex-music':text('YANDEX MUSIC','ЯНДЕКС МУЗЫКА')}
        self.source_button.set_label('●  ' + names[self.source] + '  ⌄')
        self.compact_source.set_label({'spotify':'S⌄','apple-music':'A⌄','youtube':'Y⌄','yandex-music':'Я⌄'}[self.source])
        self.open.get_accessible().set_name({'spotify':'Open Spotify','apple-music':'Open Apple Music',
                                            'youtube':'Open YouTube','yandex-music':'Open Yandex Music'}[self.source])
        self.library_stack.set_visible_child_name('accounts' if self.accounts_visible else self.source)
        if self.accounts_visible:
            name,hint = text('◎  Accounts','◎  Аккаунты'),text('Spotify · Apple · Yandex','Spotify · Apple · Яндекс')
        elif self.source == 'spotify':
            name, hint = text('✦  For you', '✦  Для тебя'), text('Mixes · discoveries · tracks','Миксы · открытия · треки')
        elif self.source == 'apple-music':
            name, hint = text('♫  Your library','♫  Медиатека'), text('Playlists · albums · songs','Плейлисты · альбомы · треки')
        elif self.source == 'yandex-music':
            name,hint = text('≈  My Wave','≈  Моя волна'),text('Personal stream · collection','Личный поток · коллекция')
        else:
            name, hint = '♫  YouTube', text('Search · links · queue','Поиск · ссылки · очередь')
        self.discovery_name.set_text(name)
        self.discovery_hint.set_text(hint)
        self.chevron.set_visible(True)

    def active_panel(self):
        if self.accounts_visible:
            return self.account_panel
        return {'spotify':self.panel,'apple-music':self.apple_panel,'youtube':self.youtube_panel,'yandex-music':self.yandex_panel}[self.source]

    def youtube_native(self):
        return self.source == 'youtube' and self.youtube_mode == 'native'

    def apple_native(self):
        return self.source == 'apple-music' and self.apple_mode == 'native'

    def native_web(self):
        if self.source=='yandex-music':return self.yandex_web
        return self.apple_web if self.apple_native() else None

    def show_yandex(self):
        if self.compact:self.toggle_compact(None)
        self.expanded=True
        self.drawer.set_reveal_child(True)
        self.yandex_panel.open()
        self.save_position()

    def start_yandex_wave(self):
        if self.source!='yandex-music':self.select_source('yandex-music')
        self.yandex_panel.request('wave')

    def on_yandex_changed(self):
        if not getattr(self,'resources_closed',True):
            self.accounts.update(self.sessions)
            self.yandex_panel.update()
            if self.source=='yandex-music':self.render_apple()

    def show_apple_library(self):
        if self.compact:
            self.toggle_compact(None)
        self.expanded = True
        self.chevron.set_text('⌃')
        self.drawer.set_reveal_child(True)
        self.apple_panel.open()
        self.save_position()

    def on_apple_changed(self):
        if not getattr(self,'resources_closed',True):
            self.accounts.update(self.sessions)
        if not getattr(self, 'resources_closed', True) and self.apple_native():
            self.render_apple()

    def render_apple(self):
        if not self.native_web() or self.resources_closed:
            return False
        apple = self.native_web()
        state = apple.state
        self.session = None
        self.player = ('yandex-native' if self.source=='yandex-music' else 'apple-native') if apple.connected else None
        target = Target(self.source, apple.pid, '', self.player or '')
        self.sound.refresh(target)
        self.meter.set_target(target)
        self.playing = bool(apple.enabled and state.get('playing'))
        self.meter.start() if self.playing else self.meter.stop()
        self.length = int(max(0, float(state.get('duration') or 0))*1_000_000)
        self.position = int(max(0, float(state.get('position') or 0))*1_000_000)
        self.track_id = None
        authorized = state.get('authorized', False)
        self.title.set_text(state.get('title') or (text('Yandex Music','Яндекс Музыка') if self.source=='yandex-music' else 'Apple Music'))
        self.artist.set_text(state.get('artist') or (text('Your library is inside Emberbox','Медиатека внутри плеера') if authorized else text('Connecting your music…','Подключаю твою музыку…')))
        self.album.set_text(apple.error or state.get('album') or '')
        self.time.set_text(f'{stamp(self.position)}  /  {stamp(self.length)}')
        self.progress.set_fraction(max(0.,min(1.,self.position/self.length)) if self.length else 0.)
        self.progress_event.set_sensitive(bool(authorized and self.length))
        self.previous.set_sensitive(bool(authorized and state.get('canPrevious') and state.get('title')))
        self.next.set_sensitive(bool(authorized and state.get('canNext') and state.get('title')))
        self.play.set_sensitive(True)
        self.play.set_label('Ⅱ' if self.playing else '▶')
        self.set_art(state.get('image') or None)
        return False

    def show_youtube_search(self):
        if self.compact:
            self.toggle_compact(None)
        self.expanded = True
        self.chevron.set_text('⌃')
        self.drawer.set_reveal_child(True)
        self.youtube_panel.open()
        self.youtube_panel.entry.grab_focus()
        self.save_position()

    def play_youtube(self, item, queue, start=0):
        if self.source != 'youtube' or self.youtube_mode != 'native':
            self.select_source('youtube')
        self.youtube.set_enabled(True)
        self.youtube_panel.search.cancel()
        self.youtube.play(item, queue, start)
        self.render_youtube()

    def youtube_status(self, message):
        self.youtube_panel.notice.set_text(message)

    def on_youtube_changed(self):
        if not self.resources_closed and not self.youtube_render_timer:
            self.youtube_render_timer = GLib.timeout_add(80, self.render_youtube)

    def render_youtube(self):
        self.youtube_render_timer = 0
        if not self.youtube_native() or self.resources_closed:
            return False
        audio, item = self.youtube, self.youtube.current
        self.session = None
        self.player = 'youtube-native' if item else None
        target = Target('youtube', os.getpid(), '', self.player or '')
        if time.monotonic() - self.youtube_last_sound >= .8 or getattr(self.sound, 'target', None) != target:
            self.sound.refresh(target)
            self.youtube_last_sound = time.monotonic()
        self.meter.set_target(target)
        self.playing = bool(item and audio.loaded and not audio.paused and not audio.eof)
        self.meter.start() if self.playing else self.meter.stop()
        self.length, self.position = int(audio.duration*1_000_000), int(audio.position*1_000_000)
        self.track_id = None
        self.title.set_text(str(item.get('title') if item else text('Find your next song','Найди свой следующий трек')))
        self.artist.set_text(str(item.get('channel') or 'YouTube') if item else text('Search or paste a YouTube link','Поиск или ссылка YouTube'))
        self.album.set_text(audio.error or (text('Loading audio…','Загружаю музыку…') if audio.loading else 'YouTube · '+text('audio','музыка')))
        self.time.set_text(f'{stamp(self.position)}  /  {stamp(self.length)}' if self.length else 'LIVE' if audio.loaded else '0:00  /  0:00')
        self.progress.set_fraction(max(0.,min(1.,self.position/self.length)) if self.length else 0.)
        self.progress_event.set_sensitive(bool(audio.loaded and self.length))
        self.previous.set_sensitive(bool(item and (audio.index > 0 or audio.position > 3)))
        self.next.set_sensitive(bool(item and audio.index+1 < len(audio.queue)))
        self.play.set_sensitive(True)
        self.play.set_label('Ⅱ' if self.playing else '▶')
        self.set_art(f"https://i.ytimg.com/vi/{item['id']}/hqdefault.jpg" if item else None)
        self.youtube_panel.update_current(item['id'] if item else '')
        if audio.error:
            self.youtube_status(audio.error)
        elif audio.loading:
            self.youtube_status(text('Opening audio…','Открываю музыку…'))
        elif not self.youtube_panel.search.process:
            self.youtube_status('')
        return False

    def setup_apple_library(self):
        if self.apple_native():
            self.show_accounts('apple-music')
            return
        instructions = ROOT / 'browser' / 'apple-music' / 'SETUP.html'
        if not instructions.exists():
            instructions = ROOT.parent / 'browser' / 'apple-music' / 'SETUP.html'
        if instructions.exists():
            launch_desktop(['xdg-open', instructions.as_uri()])
        else:
            self.apple_panel.notice.set_text(text('See docs/APPLE_MUSIC.md to connect Firefox.',
                                                  'Подключение Firefox: см. docs/APPLE_MUSIC.ru.md'))

    def play_apple_uri(self, uri):
        if self.source != 'apple-music' or not uri.startswith('apple:'):
            return
        parts = uri.split(':', 2)
        if len(parts) != 3:
            return
        params = {'kind':parts[1],'id':parts[2]}
        if self.apple_native() and parts[1] in ('library-songs','songs'):
            tracks = (self.apple_panel.track_data or {}).get('tracks',[])
            queue = [item['uri'].split(':',2)[2] for item in tracks if item.get('uri','').startswith('apple:'+parts[1]+':')]
            if len(queue)>1:
                params['queue'] = queue[:100]
        self.apple_panel._request(lambda:self.apple_panel.bridge.request('play',**params),
                                  lambda _result:GLib.timeout_add(200,self.refresh_once))

    def launch_apple(self):
        if self.apple_native():
            self.show_apple_library()
        else:
            launch_desktop(['xdg-open', 'https://music.apple.com/'])

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
        launch_desktop(command)

    def open_spotify_login(self):
        session = self.accounts.spotify_session()
        if session:
            self.monitor.call(session,'Raise',root=True)
        elif self.accounts.spotify:
            launch_desktop(list(self.accounts.spotify))

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
        if self.source != 'spotify':
            return
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
            display = self.window.get_display()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            area = desktop_window.usable_area(monitor)
            x = area.x + area.width - self.layout_width() - 30
            y = area.y + area.height - (164 if self.compact else HEIGHT) - 40
        self.window.move(x, y)
        # The window manager finishes placing a new window asynchronously.
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
                                     'compact': self.compact, 'source': self.source,
                                     'apple_browser': self.browser_binding, 'youtube_mode': self.youtube_mode,
                                     'apple_mode': self.apple_mode,
                                     'youtube_browser': self.youtube_binding}) + '\n')
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
            self.fit_window()
            self.save_position()
            return True
        return False

    def on_seek(self, _box, event):
        if self.native_web():
            if event.button == 1 and self.length:
                fraction = max(0.,min(1.,event.x/max(1,self.progress_event.get_allocated_width())))
                self.native_web().action('seek',position=fraction*self.length/1_000_000)
                return True
            return False
        if self.youtube_native():
            if event.button == 1 and self.youtube.loaded and self.youtube.duration:
                fraction = max(0.,min(1.,event.x/max(1,self.progress_event.get_allocated_width())))
                self.youtube.seek(fraction*self.youtube.duration)
                return True
            return False
        if event.button != 1 or not self.player or not self.length or not self.track_id:
            return False
        width = max(1, self.progress_event.get_allocated_width())
        position = round(max(0, min(1, event.x / width)) * self.length)
        self.call('SetPosition', GLib.Variant('(ox)', (self.track_id, position)))
        GLib.timeout_add(150, self.refresh_once)
        return True

    def on_action(self, _button, action):
        if self.source=='yandex-music':
            if action=='open':self.show_yandex()
            elif action=='toggle' and not self.yandex_web.state.get('title'):self.start_yandex_wave()
            elif action in ('toggle','previous','next'):self.yandex_web.action('transport',action=action)
            return
        if self.apple_native():
            if action == 'open' or (action == 'toggle' and not self.apple_web.state.get('title')):
                self.show_apple_library()
            elif action in ('toggle','previous','next'):
                self.apple_web.action('transport',action=action)
            return
        if self.source == 'youtube':
            if action == 'open':
                url = self.youtube.current['url'] if self.youtube_native() and self.youtube.current else 'https://www.youtube.com/'
                launch_desktop(['xdg-open',url])
                return
            if self.youtube_native():
                if action == 'toggle':
                    self.youtube.toggle() if self.youtube.current else self.show_youtube_search()
                elif action in ('previous','next'):
                    self.youtube.skip(-1 if action == 'previous' else 1)
                return
        if action == 'open':
            if self.source == 'apple-music':
                self.launch_apple()
            elif self.session:
                self.monitor.call(self.session, 'Raise', root=True)
            else:
                self.launch_spotify()
            return
        if not self.session:
            if action == 'toggle':
                if self.source in ('apple-music','youtube'):
                    self.show_sources(self.compact_source if self.compact else self.source_button)
                else:
                    self.launch_spotify()
            return
        method = {'previous': 'Previous', 'toggle': 'PlayPause', 'next': 'Next'}.get(action)
        if method:
            self.call(method)
            GLib.timeout_add(150, self.refresh_once)

    def refresh_once(self):
        self.refresh()
        return False

    def call(self, method, args=None):
        if self.session:
            self.monitor.call(self.session, method, args)

    def set_art(self, url):
        if url == self.art_url:
            return
        self.art_url = url
        self.load_cover()
        if hasattr(self,'frame_health'):
            self.frame_health.request_frame()

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
            if hasattr(self,'frame_health'):
                self.frame_health.request_frame()

    def on_volume_changed(self, sound):
        self.mute_toggle.set_state(sound.volume, sound.muted, sound.available)
        self.volume_knob.set_state(sound.volume, sound.muted, sound.available)

    def system_volume(self,value):
        if self.sound.muted and value>0:
            self.sound.toggle_mute()
        self.sound.set_volume(value)

    def seek_to(self,seconds):
        if self.native_web():
            self.native_web().action('seek',position=seconds)
        elif self.youtube_native():
            self.youtube.seek(seconds)
        elif self.session and self.track_id and self.length>0 and self.session.properties.get('CanSeek',True):
            position=round(max(0,min(self.length/1e6,seconds))*1e6)
            self.call('SetPosition',GLib.Variant('(ox)',(self.track_id,position)))
            GLib.timeout_add(150,self.refresh_once)

    def system_action(self,method,uri=None):
        if method=='OpenUri' and self.apple_native():
            self.play_apple_uri(uri)
            return
        if method=='Play' and self.playing or method in ('Pause','Stop') and not self.playing:
            return
        action = {'Next':'next','Previous':'previous','Play':'toggle','PlayPause':'toggle','Pause':'toggle','Stop':'toggle'}.get(method)
        if action:
            self.on_action(None,action)

    def publish_mpris(self):
        state = {'active':False}
        if self.native_web():
            web=self.native_web()
            item = web.state
            state = {**item,'active':bool(item.get('authorized') and web.connected),'source':self.source,
                     'next':item.get('canNext'),'previous':item.get('canPrevious')}
        elif self.youtube_native() and self.youtube.current:
            item = self.youtube.current
            state = {'active':True,'source':'youtube','id':item['id'],'title':item.get('title',''),
                     'artist':item.get('channel',''),'image':item.get('image',item.get('thumbnail','')),
                     'next':self.youtube.index<len(self.youtube.queue)-1,'previous':self.youtube.index>0}
        state.update(duration=self.length,position=self.position,playing=self.playing)
        if state.get('active'):
            state['image'] = self.artwork.cached_uri(self.cover) or state.get('image','')
        if hasattr(self,'sound'):
            state['volume'] = 0. if self.sound.muted else self.sound.volume
        self.mpris.publish(state)

    def refresh(self):
        self.publish_mpris()
        connected = bool(self.apple_web.state.get('ready') and self.apple_web.state.get('authorized')) if self.apple_native() else self.apple.connected
        if connected and not self.apple_was_connected and self.source == 'apple-music' and self.expanded and not self.compact:
            self.apple_panel.open()
        self.apple_was_connected = connected
        self.monitor.poll()
        return True

    def on_sessions(self, sessions):
        self.sessions = sessions
        self.accounts.update(sessions)
        self.apply_sessions()

    def apply_sessions(self):
        if self.native_web():
            self.render_apple()
            return
        if self.youtube_native():
            self.render_youtube()
            return
        binding = self.youtube_binding if self.source == 'youtube' else self.browser_binding
        session = choose_session(self.sessions, self.source, binding, self.player or '')
        self.session = session
        self.player = session.name if session else None
        target = Target(self.source, session.pid if session else 0,
                        session.family if session else '', self.player or '')
        self.sound.refresh(target)
        self.meter.set_target(target)
        if not session:
            self.playing = False
            self.meter.stop()
            self.length, self.position, self.track_id = 0, 0, None
            self.title.set_text(text('Ready when you are', 'Готов играть'))
            self.artist.set_text(text('Open Spotify to begin', 'Открой Spotify') if self.source == 'spotify'
                                 else text('Start YouTube · choose its browser','Включи YouTube · выбери браузер') if self.source == 'youtube'
                                 else text('Start Apple Music · choose its browser', 'Включи Apple Music · выбери браузер'))
            self.album.set_text('')
            self.time.set_text('0:00  /  0:00')
            self.progress.set_fraction(0)
            self.play.set_sensitive(True)
            self.progress_event.set_sensitive(False)
            self.previous.set_sensitive(False)
            self.next.set_sensitive(False)
            self.play.set_label('▶')
            self.set_art(None)
            return
        props, metadata = session.properties, session.metadata
        self.playing = props.get('PlaybackStatus') == 'Playing'
        if self.playing:
            self.meter.start()
        else:
            self.meter.stop()
        self.length = int(metadata.get('mpris:length') or 0)
        self.track_id = metadata.get('mpris:trackid')
        self.position = int(props.get('Position') or 0)
        self.title.set_text(str(metadata.get('xesam:title') or {'spotify':'Spotify','apple-music':'Apple Music','youtube':'YouTube','yandex-music':text('Yandex Music','Яндекс Музыка')}[self.source]))
        artists = metadata.get('xesam:artist') or []
        self.artist.set_text(', '.join(artists) if artists else text('Music', 'Музыка'))
        self.album.set_text(str(metadata.get('xesam:album') or ''))
        if self.source == 'spotify':
            track_id = str(metadata.get('mpris:trackid') or '').rsplit('/', 1)[-1]
            self.panel.update_current('spotify:track:' + track_id)
        self.time.set_text(f'{stamp(self.position)}  /  {stamp(self.length)}')
        self.progress.set_fraction(max(0, min(1, self.position / self.length)) if self.length else 0)
        self.previous.set_sensitive(bool(props.get('CanGoPrevious', True)))
        self.next.set_sensitive(bool(props.get('CanGoNext', True)))
        self.play.set_sensitive(bool(props.get('CanControl', True)))
        self.progress_event.set_sensitive(bool(props.get('CanSeek', True)))
        self.play.set_label('Ⅱ' if self.playing else '▶')
        self.set_art(metadata.get('mpris:artUrl'))

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
