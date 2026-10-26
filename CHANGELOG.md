# Changelog

**English** · [Русский](CHANGELOG.ru.md)

## 0.18.2 — 2026-10-26

- Click the current album title in the widget or fullscreen listening room to open its release page inside Ember. Keep the subdued typography, amber hover and keyboard-accessible controls without tooltips or focus outlines.
- Resolve Apple albums through the captured song relationship, Spotify albums through the exact selected recording, and Yandex albums through source-owned album IDs. Do not silently select a namesake through search. Keep paging tied to the resolved album ID.
- Open the release directly, with artwork, notes, tracks and listening/queue actions. Back returns to the previous room; browsing does not change playback. Preserve source-change and late-response guards. Apple integration 18; Yandex integration 6.
- Stop the DJ dial immediately when leaving its tab, including during the stack crossfade; a late GTK map signal cannot restart hidden animation. Resume the dial when returning.


## 0.18.1 — 2026-10-26

- Keep the native Apple output device and mixer alive on manual track changes and rewind. Consume a prepared next deck with a short, sample-smooth handover; keep the current song playing while an unprepared choice loads. Preserve Atmos / ALAC source quality.
- Warm one upcoming Ember-queue song early, including when automatic EmberFlow mixing is off. Serialize source negotiation, cancel superseded selections and forward only complete PCM frames when a decoder is replaced. Recent manifest descriptors use a four-entry, one-minute memory cache with fresh DRM contexts.
- Fix Previous using an outgoing song's stale position. Repeated Previous can leave a pending rewind; adding music retains up to twenty history entries within the existing 200-entry queue limit. Apple transport no longer waits for catalogue browsing.
- Avoid unnecessary analysis of known-format raw PCM and validate the asynchronous spatial resampler's tail only after draining it. Keep failed manual selections separate from playback-format failures. Engine integration 17.

## 0.18.0 — 2026-10-25

- Optional native Apple ALAC / Hi-Res playback with separate private sign-in, saved sessions and automatic Atmos → ALAC → standard selection. Decoder-confirmed source bit depth/rate.
- One 192 kHz output clock for mixed Lossless / Hi-Res / Atmos EmberFlow; original format badges remain separate from output conversion. Pause, seek and bounded fallback.
- Pinned native-source build, verified library downloads, `--apple-lossless` dependency provisioning and an account window in player settings. Fix the native Linux login symbol collision. Integration 16.
- Verify real 16/44.1 and 24/96 playback, six-second mixed-format overlap, exact synthetic 24-bit ALAC samples up to 192 kHz, and bilingual setup/quality documentation. Native beat alignment remains unavailable.

## 0.17.0 — 2026-10-25

- Experimental playback of real Apple Music E-AC-3 JOC assets through installed Widevine and OpenJOC: spatial float32 headphone output at 48 kHz. The Atmos badge requires decoder confirmation.
- Native EmberFlow uses two prepared decoders, one output clock, sample-based gain envelopes and outgoing-decoder release. Ordinary AAC transitions are supported; spatial-path beat alignment is not available yet.
- Pause, seek, source changes, bounded buffers and ordinary-playback recovery. Account tokens and signed addresses remain on Apple's page; no key export or PCM recording.
- Optional `--apple-atmos` setup, compiler/glibc checks, pinned decoder download with progress and SHA-256. Engine upgrades retain library-track kinds; integration 15.
- Bilingual documentation, requirements and automated checks. This remains a beta independent renderer without Dolby certification.

## 0.16.3 — 2026-10-25

- Read Apple website `audioTraits` alongside catalogue `audioVariants`, including Atmos/surround aliases. Isolate song changes, keep optional lookups asynchronous and upgrade the adapter to integration 14.
- Keep the playing badge tied to decoder evidence; AAC, FLAC or ordinary PCM cannot become Dolby Atmos through a variant label.
- Add an isolated native streaming JOC/binaural developer probe and bilingual engineering notes. Verify the enhanced Apple manifest and clear-fixture decoder separately. Apple Music Atmos playback remains unfinished and is not enabled.

## 0.16.2 — 2026-10-24

- Enlarge EmberFlow's glass lamp from 38×18 to 48×24 with a clearer, rounded filament. Gradually shift its emission from dull red through amber to warm gold, with cooler ends and restrained glass reflections.
- Use a bounded thermal approximation for warm-up and cooling instead of a brightness tween. Quick reversals retain the current temperature; animation still stops when settled or hidden and respects reduced animation.

## 0.16.1 — 2026-10-24

- Recess EmberFlow into the listening console, widget and settings. A glass capsule with a visible incandescent filament warms from amber to soft gold and cools gently when switched off.
- Keep the animation finite, stop it when hidden, and respect the desktop's reduced-animation setting. Verify both interface languages and compact layouts.

## 0.16.0 — 2026-10-24

- EmberFlow beat matching for native Apple Music and YouTube: measured tempo and phase, compatible rhythms within ±6%, preserved pitch, then a four-beat return to normal speed after the blend. Add a separate Beats switch in settings; low-confidence material keeps the musical crossfade.
- Apple: silent intro analysis with rewind, Web Audio envelopes against the output clock, bounded waits and integration 13. Avoid MusicKit's stalled paused-seek promise. Authorization and DRM stay with MusicKit.
- YouTube: at most 6.5 seconds of the selected audio stream analyzed by one low-priority FFmpeg thread; prime mpv at the chosen tempo. Reuse the lamp meter's worker for outgoing rhythm. No model, temporary audio device or PCM disk recording.
- Exercise generated drum patterns in the native browser engine and actual mpv output: tempo/phase alignment, unchanged reference tone and speed recovery. Check syncopated patterns, random-signal rejection, real Apple tempo detection and applied rate, fallback blending, pause/cleanup, both interface languages and small screens.

## 0.15.1 — 2026-10-24

- Extend EmberFlow to an eight-second, three-phase blend: introduce the incoming texture, exchange the foreground, then dissolve the outgoing ambience. Smooth phase boundaries and complementary gain retain peak headroom without re-encoding or a new DSP/model process.
- Proportionally shorten mixes for short tracks; reuse fresh lamp-meter measurements to avoid a long entrance after an already quiet outro. Ignore stale measurements and muted playback.
- Synchronize both Apple renderer envelopes; integration 11 bounds the outgoing lease to fourteen seconds including startup. Check cross-engine curve parity, full-length real mpv overlap, cancellation, source-volume isolation and Apple queue handover.

## 0.15.0 — 2026-10-24

- Add EmberFlow: an opt-in amber hardware switch shared by the widget, fullscreen console and mini-mode settings, with a short finite animation and private persisted preference.
- Mix real outgoing and incoming tracks from the Ember queue for up to four seconds. Support native Apple Music and audio-only YouTube; keep source master volume, mute and stream quality separate from the fade.
- Prepare one extra deck near the end, release it after mixing, retain queue ownership without replaying the incoming track, and cancel on pause, seek, source changes or vocal reduction. Compensate mpv cubic gain and isolate MusicKit logical volume from the envelope.
- Upgrade the Apple engine to integration 10, with a bounded authorized tail lease and cleanup on disconnect. Verify real Apple queue transitions and pause, real synthetic-audio overlap, source gating, cancellation, geometry and English/Russian controls.

## 0.14.0 — 2026-10-24

- Route free-form wishes by confidence, not word count or the presence of a single mood keyword. Use a local Qwen3.5 2B model for imagery, scenes and conversational changes; keep fully understood requests immediate.
- Compile a grounded playlist search and localized sound description. Keep context for follow-ups, release it for new wishes, preserve no-vocal requests and exclusions, and ask for a musical detail when interpretation fails. Uncertain sentences never fall back to literal song-title searches.
- Prefer the app-owned pinned 1.28 GB model, with reasoning disabled, two CPU threads, one inference at a time, a small context window, bounded response cache and 30-second idle unloading. Cancellation terminates the private HTTP helper so a new wish need not wait for the previous HTTP timeout.
- Wait for model readiness during concurrent background warm-up. Handle fully covered vocal-only changes immediately, and keep previous genres from leaking into a new scene introduced with conversational filler.
- Enable free-form mode for new preferences; preserve existing choices and expose setup when a model is missing. Verify the full keyboard-to-model-to-playlist-to-queue path in both languages, context isolation, unavailable models, validation and cancellation.

## 0.13.3 — 2026-10-24

- Interpret the reported Russian “что - нибудь погрустнее” as a melancholy mix. Normalize spacing, Unicode dashes and indefinite pronoun forms consistently across mood, artist and theme parsing; strip conversational openings such as “ну, а можно”. Keep the submitted text visible as typed.
- Preserve artist hyphens and explicitly quoted song-title searches. Verify the exact reported phrase through playlist loading, ranking, keyboard input and queue replacement, including recovery from an earlier incorrect lookup.

## 0.13.2 — 2026-10-24

- Understand conversational mood changes: “something happier”, “livelier”, “calmer”, “for work” and “something else”. Generic mood changes release the previous artist; “Beatles, but happier” and “their songs, but happier” keep the named scope. “More” continues it.
- Search Apple Music mood playlists and load real songs; use collections returned by Spotify search. Rank the requested mood ahead of unrelated favourites and cache each musical direction separately. Unfamiliar occasion requests can use playlist search without entering an exact song-title filter.
- Prefer fresh songs when changing a mix; failed searches retain the last successful musical context. Keep common requests local, bounded and asynchronous, with female speech unchanged.
- Verify the keyboard-to-catalogue-to-queue sequence, mood collection loading, exclusions, repeat avoidance and Apple search resource validation.
- Replace the Russian voice with locally synthesized Silero v5.5 Kseniya at 48 kHz, automatic stress and “ё”, pinned package verification, two CPU threads and soft audio edges. Use short mood-aware spoken links; retain full written replies. Prepare/reuse CPU-only PyTorch in the private voice environment; document the model licence and updated storage budget.

## 0.13.1 — 2026-10-24

- Resolve exact artist requests through the artist catalogue; bypass diversity caps, exclude unrelated title hits and recommendations, and keep artist continuations ahead of the preserved user tail.
- Keep the submitted wish visible in the input and response area. Describe the actual artist, track count and first recording instead of repeating fixed copy.
- Give Ember female RU/EN voices, pinned model hashes and voice identity checks; retain the two-CPU speech budget.

## 0.13.0 — 2026-10-24

- Ember DJ: an integrated personal radio tab with keyboard Enter/button requests, push-to-talk and local neural RU/EN speech. Soft tab transitions, a metal microphone dial, live tubes and responsive music cards.
- Real source tracks, Apple/Spotify personal picks, bounded local taste, feedback and queue continuation preserving manual additions.
- Optional model setup with progress, cancellation and hashes; private preferences, explicit microphone capture, background inference and temporary ducking without changing the dial.
- Check input, cancellation, queues, geometry, privacy and audio gain; exercise real local speech synthesis, recognition and intent inference.

- Lightweight common-wish parsing, single-flight bounded metadata caches, five-second response budget, cancellation, no hidden-tab drawing and optional two-thread language inference. Spotify transport no longer waits for background Home/Search navigation.

## 0.12.7 — 2026-10-23

- Open the artist room with a 1.05-second layered entrance: ambient light first, then a gently approaching portrait, rising typography and music panels, with smooth acceleration and settling.
- Prewarm the GL renderer alongside the listening room; animate fixed in-memory textures inside the catalogue viewport. Keep the transport and navigation live, defer catalogue repaints until handoff, and bound photo preparation. Reject portraits prepared for an older allocation.
- Cancel cleanly on back, resize, source changes and fullscreen exit. Respect reduced motion, handle a lost context and offer a short cached-image fade without accelerated GL. Deliver completed catalogue/artwork jobs even while the frame clock is busy.
- Check real GPU layers, stable textures, portrait dimensions, transport, deferred updates, cancellation, reduced motion, fallback and existing fullscreen transitions; retain bilingual layouts and original fixture media.

## 0.12.6 — 2026-10-23

- Light the artist masthead with two soft-focus layers of the same photograph, a source-coloured glow behind the portrait, subtle reflected light and static matte grain. Retain the character of monochrome photographs.
- Adapt the dark reading area to the reserved text width. Verify cream-text contrast against white photos at three sizes, source colour, monochrome depth, deterministic texture and an untouched clear photograph.
- Prepare and cache the backdrop off GTK; refresh the English/Russian artist previews.

## 0.12.5 — 2026-10-23

- Recompose the artist masthead as a large photographic gallery: a 320px square portrait in a 360px desktop hero, a generous right photo bay and a poster-scale artist name. Adapt the hero to shorter displays.
- Simplify the photo mount to a narrow matte edge and one hairline, with a softer shadow; retain the complete image and its blurred backdrop. Keep the heading and playback actions in their own half.
- Verify actual portrait size, full source edges, wide photos, short/long artist names, visible first-screen music, three GTK sizes and both languages; refresh the previews.

## 0.12.4 — 2026-10-23

- Show the complete artist photograph at its original aspect ratio inside a shallow matte metal frame, over a softly blurred, tinted copy of the same photo.
- Reserve a separate portrait area before allocating the heading and controls; let the masthead grow for wrapped text. Keep artist photo caches separate from square cover thumbnails and retain all source edges.
- Check portrait, landscape, square and panoramic photos, edge preservation, original photo proportions and English/Russian GTK layouts at three screen sizes. Refresh the artist previews.

## 0.12.3 — 2026-10-23

- Keep the fullscreen console and progress bar stationary when a track title wraps to two lines. Reserve title space and size artwork against measured header, metadata and footer heights.
- Check short, long, Russian and ellipsized titles in artwork/lyrics layouts at four screen sizes. Keep every console control visible without sending playback commands.

## 0.12.2 — 2026-10-23

- Load the full Apple artist albums relationship automatically through every next page; retain editions by ID and remove the 200-release artist-list ceiling.
- Add All releases, catalogue-based category filters, loaded/complete/region status and a resumable failed-page action. Keep 48 covers on screen per catalogue page, with source/page cancellation and repeated-continuation protection.
- Preserve the Apple account and wait for authorization before restoring playback during the adapter update. Verify 1,100 releases, duplicate titles, interrupted scans, cancellation, transport responsiveness and English/Russian GTK layouts.

## 0.12.1 — 2026-10-23

- Redesign the artist overview around a panoramic portrait, larger name and genre badges. Merge category navigation into the toolbar to bring more music onto the first screen.
- Pair a horizontal featured release with compact popular songs, then show album/single/compilation shelves. Deduplicate releases across the overview; a genuinely sparse catalogue uses its supplied artist story beside the release.
- Fetch missing Apple artist views by exact ID, independently and in parallel. Bound the optional phase to 2.2 seconds and the artist command to 6.5 seconds; keep successful sections when another view fails.
- Verify the original one-latest-release regression, useful content in both wide columns, sparse data without invented cards, queue controls, source changes and three GTK layouts in English/Russian. Refresh the previews.

## 0.12.0 — 2026-10-23

- Open the artist from the fullscreen song, collection or queue, with a photographic Grunesphism masthead, portrait, genre details and persistent category navigation.
- Browse albums, singles/EPs, compilations and appearances; open a release for its tracks and supplied liner notes, play its continuation or add songs to the existing queue.
- Use Apple Music catalogue relationships and paged views through the signed-in engine. Offer explicit collaborator/namesake choices; retain source-provided biographies and recording availability.
- Add version-dependent Spotify/Yandex artist readers and an explicit YouTube in-player search fallback. Keep missing categories honest and avoid playback-stopping page reloads while browsing.
- Prepare/cache masthead images off GTK, reject stale page/source replies and synchronize source changes before creating a new browse request. Update the independent engine adapters while retaining profiles.
- Check actual GTK navigation, loading responsiveness, queue continuation, three display sizes and both languages; add offline source contracts, bilingual guides and original-media previews.

## 0.11.3 — 2026-10-22

- Welcome AI karaoke with warm breathing embers, an indeterminate amber light bar and clear preparation/buffering captions. Crossfade back to timed lyrics when the processed-audio helper actually reports readiness.
- Keep cancellation and error states immediate. Drive the small indicator from the existing frame clock, stop it on exit and honour reduced-motion settings. Retain a compact layout at 1024×600.
- Increase the metal toggle sprites by about 20–25% in normal and compact layouts, preserving their smooth travel and existing controls.
- Check real GTK startup phases, reduced motion, cancellation/reopening, geometry and unchanged source transport; refresh English/Russian screenshots and guidance.

## 0.11.2 — 2026-10-22

- Group karaoke controls in a centered 740 px Grunesphism card: switch/status together, mode and strength in a shared inset, stable status height and responsive setup controls. Refresh real GTK screenshots in both languages.
- Add UVR's polarity denoising to neural karaoke: average positive and reversed-polarity predictions to cancel sign-independent model artifacts, without lowering the requested vocal reduction or low-pass filtering the mix.
- Warm inference kernels before speed calibration and use a bounded CPU pool of up to four threads. Calibrate for both passes, retain past/future model context and keep the existing overload/queue safety gates. Buffering can be longer.
- Replace hard clipping of the residual with stereo-linked anticipatory peak protection. Use existing future audio, a smooth attack and carried release; no extra inference or audio delay from the limiter. Preserve exact initial 0% bypass.
- Add regressions for polarity noise cancellation, 100% overload, stereo balance, gain recovery and sample-identical limiter block boundaries.

## 0.11.1 — 2026-10-22

- Keep karaoke frame updates out of GTK layout when titles, timing notes, counters and transport metadata have not changed; prepare lyric neighbours once and allocate word colours only during actual fades.
- Let the delayed karaoke timeline own its progress and footer. Periodic source polling no longer overwrites them with raw undelayed values between animation frames.
- Ship all 201 VU glass frames in a small lossless atlas, generated from the original SVG. No SVG blur/rasterisation runs inside animation ticks; artwork and level resolution are unchanged.
- Retain the UVR model, inference framing, precision and audio mixing settings. Add regressions for idle layout, timed words, delayed track transitions and exact atlas pixels.

## 0.11.0 — 2026-10-22

- Default karaoke to local UVR neural vocal separation, with a separate explicit fast stereo mode. Estimate vocals and blend them out without removing the entire stereo centre.
- One-click optional setup: verified 30 MB model, private inference runtime, progress and repair; source audio is never saved or uploaded.
- CPU calibration, short sliding context, overlap blending, smooth strength changes and bounded capture/inference/playback queues. Stop safely if the machine cannot keep up.
- Delay-aware song/lyric/artwork/progress display and tubes metering the isolated processed return stream. Keep return audio excluded from source volume and routing; apply mute to it separately.
- Wait for the return client before source movement to avoid a startup policy race; retain EOF/signal/forced-kill restoration.
- Neural framing/mixing, model-integrity, delayed pause/seek/track-transition tests, real-model routing checks and bilingual usage/credits.

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
