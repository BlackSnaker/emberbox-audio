# Changelog

**English** · [Русский](CHANGELOG.ru.md)

## 0.10.1 — 2026-10-22

- Make the vocal dial directly reduce the vocal-band stereo centre: the previous dominance gate could leave it nearly unchanged under wide accompaniment.
- Retain smooth strength changes, bass protection and unchanged side information; explicitly show when reduction is on.
- Add a regression with centred vocals masked by louder stereo backing, and wait for fresh captured PCM in routing checks.

## 0.10.0 — 2026-10-22

- Fullscreen Karaoke page with large lyrics, soft line transitions, timed entry countdowns and the existing audio-responsive tubes.
- Preserve genuine enhanced-LRC word timing, including Unicode, offsets, repeated lines and explicit vocal rests; privately import timed lyrics for a recording or return to automatic LRCLIB text.
- Opt-in, adjustable stereo vocal reduction in an isolated DSP process. Protect bass and stereo side content; explicitly distinguish the effect from stem separation and source stream quality.
- Temporary per-application audio routing, restoration on exit/failure and recovery after forced helper termination. Never capture a microphone or change the default output.
- Check both pactl/pacat during installation, add bilingual usage/limitations documentation, synthetic DSP tests and actual GTK/audio routing checks.

## 0.9.2 — 2026-10-22

- Continue search results and loaded albums from the clicked song in fullscreen and desktop track lists.
- Replace generated continuations on a new selection while retaining explicitly queued songs, avoiding automatic duplicates and silent loss at the queue limit.
- Keep catalogue-ID matching for Apple Music and advance unknown-duration YouTube items from real EOF; ordinary pause and restored queues never start the next song.
- Add regression checks for search-click completion, manual queue retention, duplicate rows, capacity and real GTK controls.

## 0.9.1 — 2026-10-22

- Clickable audio-quality badge in the desktop widget and fullscreen: decoder codec/rate, channel details and measured YouTube bitrate.
- Prefer the highest supported built-in stream: MusicKit HIGH, Yandex High quality for recognised Plus accounts and YouTube best-audio selection. Report the request separately from actual playback.
- Separate optional Apple catalogue formats from actual playback; never infer Atmos, Lossless or bit depth from subscription, settings or mixer output.
- Bounded Chromium Media observer, active-player and track-change guards, packaged native-engine updates and source-safe unknown states.
- Local-time queue heading and English/Russian quality documentation.

## 0.9.0 — 2026-10-21

- Fullscreen Listening / Collection / Queue pages, with large cover cards, album details and in-player search.
- Add individual songs or loaded collections to a private, source-specific queue; reorder, remove, play from a row and preserve upcoming music across mode changes.
- Keep automatic queue advancement in the widget, including desktop media controls, with guarded source changes, pause handling and no autoplay after restoration.
- Async collection/playback requests, cancellation of superseded results, source capability notes and responsive English/Russian previews down to 1024×600.
- Queue persistence/end-state tests, provider and Spotify DOM contracts, actual fullscreen interaction and desktop transport regressions.

## 0.8.1 — 2026-10-21

- Prepare and cache silent artwork clips before animation, so network requests are outside the playback loop.
- Present a bounded queue on the display clock at 60 fps, with short preroll and gentle interpolation for lower-rate source video. Tolerate small vsync timing jitter and resume after pauses without racing through old frames.
- Update an existing GPU texture without per-frame GTK layout or texture reallocation. Preserve the decoder and its position when artwork changes size; transitions use the current video frame.
- Check cadence, backpressure, cache reuse/cancellation, actual FFmpeg decoding, GPU layout, resize, pause and cleanup.

## 0.8.0 — 2026-10-21

- Open fullscreen with a centred large cover. Lyrics load and render only after pressing **Lyrics**; **Artwork** returns to the cover.
- Replace per-frame GTK layout/opacity work with a prewarmed GPU entrance and one in-memory room texture. Defer lyrics, artwork decoding and motion lookup until the entrance ends.
- Animate Lyrics/Artwork in both directions, with a moving cover and cascading reveal. Fullscreen returns to the desktop widget through a reverse transition; Mini also animates its size and contents.
- Prepare the background off the UI thread using a cached gradient. Use a cheap compositor fade when hardware GL is unavailable, and honour disabled system animations.
- Cover/lyrics layout checks, real shader/offscreen capture checks, cancellation and playback-preservation regressions.

## 0.7.5 — 2026-10-21

- A 720 ms fullscreen entrance: expand the rounded player shell from the desktop widget, move the cover into place, and softly reveal the listening room.
- Use GTK frame-clock timing, honour disabled system animations, and clean up immediately on Esc, hide or close. Preserve playback and the desktop widget's geometry.
- Support an opaque fallback without compositing; no additional graphics dependencies.

## 0.7.4 — 2026-10-21

- A larger tactile volume dial in fullscreen; replace the duplicate volume slider with a passive amber glass VU.
- Measure stereo PCM energy, with smooth attack/decay and a return to rest on pause, mute or stale audio. Preserve the seek timeline and desktop/mini controls.
- Verify fullscreen controls down to 1024×600 and fix the fullscreen preview's artwork fixture.

## 0.7.3 — 2026-10-21

- Refresh Yandex player contexts after sign-in and read context consumers outside the main content.
- Load playlist cards, open their tracks inside the widget, and support tracks whose Play control appears only on hover.
- Reuse Apple’s configured playback components while preserving Yandex’s separate signed-in profile; replace older Yandex adapters once.
- Acknowledge source activation before the first Play and preserve actionable errors instead of clearing them on every status poll.
- Add bounded official-site navigation and sanitized player-capability diagnostics. Real Plus playback remains with subscription testers.

## 0.7.2 — 2026-10-21

- Automatic desktop shortcut on KDE Plasma, with localized XDG desktop folders and a remembered opt-out.
- Application-menu access remains available when the desktop folder is disabled; GNOME desktop icons are not enabled automatically.
- CI verifies the Plasma shortcut file, executable permissions and desktop-entry syntax.

## 0.7.1 — 2026-10-21

- Hide and close controls, with the same actions in compact settings and launcher context menus.
- Clicking the launcher restores an existing hidden widget instead of starting a duplicate.
- Optional desktop shortcut installation, preserved across updates and removed on uninstall.

## 0.7.0 — 2026-10-20

- Dependency-aware installer for Arch, Debian/Ubuntu, Fedora and openSUSE, with a warm terminal interface, read-only checks, and missing-package installation.
- Managed Python runtimes, full YouTube EJS/JavaScript checks, FFmpeg and safe update rollback; no system pip or audio-service replacement.
- Desktop-session launch environment and XDG autostart, including automatic direct-launch fallback when user systemd is unavailable.
- KWin-specific placement, alpha-preserving window type, app-scoped all-workspaces integration, and panel-aware geometry.
- Verified with real isolated KWin 6.7.5/XWayland input, pixel and fullscreen checks; full Plasma Shell and physical multi-monitor testing remain with testers.
- Bilingual setup/KDE documentation and explicit DRM readiness, independently of account/subscription status.

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
