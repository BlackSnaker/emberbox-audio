# Changelog

**English** · [Русский](CHANGELOG.ru.md)

## 0.6.0 — 2026-10-19

- Large original fullscreen covers instead of enlarged thumbnails, preserving aspect ratio with soft rounded corners.
- Automatic original Apple Music motion covers for supported catalog songs: silent loops that pause with music.
- Video decoding outside GTK, cleanup on exit, and static fallback when animation is unavailable. Optional FFmpeg is required.
- Checks for source resolution, unavailable large assets, exact album selection, track changes, and real video decoding.

## 0.5.0 — 2026-10-19

- Fullscreen listening room with large artwork, cover-coloured atmosphere, tactile controls and live gas-discharge tubes.
- Optional LRCLIB synchronized/plain lyrics, smooth active-line follow, click-to-seek, cache and graceful missing/instrumental states.
- Header/settings/F11 entry, Escape return, keyboard controls and original desktop geometry preserved across modes.
- Responsive small-screen layouts, per-source transport/volume and artwork/lyrics delivery that remains responsive during continuous audio animation.
- Original English/Russian previews, setup notes and offline fullscreen/lyrics regression checks.

## 0.4.0 — 2026-10-19

- Experimental Yandex Music source with in-player My Wave, like/dislike, search and loaded collection/queue tracks.
- Yandex ID connection from Accounts, with a separate profile, service and private local bridge.
- Shared playback component setup, independent volume/mute and selected-process spectrum; source switching pauses the previous player.
- English/Russian setup and subscription tester checklist. Real Plus playback is pending tester verification; offline adapter and GTK checks are included.

## 0.3.1 — 2026-10-19

- Move spectrum recorder cleanup off the GTK thread during track and audio-stream changes.
- Give replacement recorders separate PipeWire node names to prevent overlapping stream links.
- Refresh cover/layout painting and recover a stopped frame callback without restarting music.
- Regression checks for Apple Music transitions, slow recorder shutdown and frame recovery.

## 0.3.0 — 2026-10-19

- In-player Spotify and Apple Music account centre with first-launch onboarding and live connection status.
- Official sign-in windows, completion detection, missing-client guidance and Apple setup without a terminal or Node.js.
- Native Apple Music library, catalogue search and playback; a compatible DRM-capable runtime is required.
- YouTube audio search, links, queue and playback without an account.
- Settings and widget restart; desktop players run in independent services.
- Native media card branded **Ember**, with artwork, transport, seeking and volume.
- English/Russian guides and regression checks, plus verified subscription playback and actual PipeWire spectrum.

## 0.2.0 — 2026-10-18

- Spotify / Apple Music web source selector in full and compact views.
- Explicit browser-session binding, capability-aware controls and async MPRIS polling.
- Separate volume/mute profiles and selected-application PipeWire spectrum.
- Source switching pauses previous playback without opening or autoplaying the next source.
- Browser artwork support, English/Russian setup notes and D-Bus regression coverage.
- Apple Music recommendations remain in the browser; shared-tab audio limits are documented.

## 0.1.0 — 2026-10-18

First public source preview of Emberbox Audio.

- Standalone GTK desktop widget with draggable placement and compact mode.
- Grunesphism visual language: warm Gruvbox surfaces, soft relief and tactile controls.
- Real audio-reactive gas-discharge tubes with smooth decay and subtle glass-edge glow.
- Per-user installer, launcher, optional autostart and clean uninstall.
- Original demonstration artwork, English/Russian documentation and automated regression checks.
- Spotify playback, seeking, application volume and experimental personal collections.

Tested desktop: LunaOS / GNOME 50 / Wayland + XWayland. Broader desktop compatibility is still being evaluated.
