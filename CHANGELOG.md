# Changelog

**English** · [Русский](CHANGELOG.ru.md)

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
