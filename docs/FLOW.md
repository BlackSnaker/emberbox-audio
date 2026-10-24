# EmberFlow — one song flows into the next

**English** · [Русский](FLOW.ru.md)

Turn on **EmberFlow** beside the widget's timeline, under the fullscreen tubes,
or in player settings in mini mode. The tactile amber switch is shared across
these views. Its preference is saved; it is off on first installation.

![EmberFlow in the listening console, with original demonstration media](../assets/emberflow.png)

## Listen as one continuous set

Add songs to Ember's **Queue**, play an album/search result list or start an
Ember DJ set. The next queued track is prepared near the end of the current one.
Its opening overlaps the outgoing tail for up to **four seconds**, with gently
eased, complementary volume curves. The curves sum to unity, retaining peak
headroom. Source format and quality settings are retained.

| Source | EmberFlow |
| --- | --- |
| In-player Apple Music | Yes, with the updated native playback engine and an authorized subscription. |
| In-player YouTube | Yes, for the Ember listening queue. |
| Spotify, Yandex Music, browser companion sessions | Not supported in this release. The switch describes source availability. |

The transition follows the next item in the Ember queue. It does not choose a
different song. A restored queue can be adopted when its current song is already
playing; restoring the preference alone never starts playback. Pausing, seeking,
manually changing tracks, switching source or disabling Flow clears staged audio.
Vocal reduction temporarily uses ordinary transitions.

This is a musical crossfade. There is no BPM analysis or beat matching. Late
network startup may shorten the overlap; an unready next track falls back to the
normal queue. With no next item there is nothing to mix.

## Lightweight by design

- No neural model, audio recording or re-encoding. No PCM is saved to disk.
- At most one extra deck is staged, beginning within the last 28 seconds.
  It is paused while preparing, and the outgoing deck is released after mixing.
- Apple uses two authorized MusicKit pages inside Ember's existing engine.
  The hidden staged page is throttled until playback. This temporarily adds a
  renderer and decoder, so memory and startup CPU rise during preparation.
- YouTube uses a second audio-only mpv deck, with a 16 MiB forward demux cache
  per deck and no video rendering. Percentage gain is compensated for mpv's
  cubic volume law; the source's master volume and mute remain separate.
- The GTK switch animates only while changing state. No continuous switch timer
  or extra audio process runs while Flow is off.

Apple support depends on MusicKit's current playback implementation. The engine
keeps a short, already authorized outgoing media element alive during handover;
an eight-second watchdog bounds that lease. Logical source volume is isolated
from the fade, and user transport commands cancel the handover. Authentication
and EME/CDM checks remain with the service. No media URLs or keys are extracted.

## Verification

The live Apple check exercised queue-driven overlap, independently audible
outgoing/incoming pages, queue adoption without restarting the new song, pause,
cleanup and absence of delayed resume. A private PulseAudio sink check used
generated 220/440 Hz tones to measure actual mpv overlap and verify that the
mixed peak did not exceed its input peak. These are reference-machine checks,
not performance guarantees for every source or computer.

Developer checks: `tests/test_ember_flow.py`, `node tests/flow_engine_checks.cjs`,
`python tests/flow_audio_smoke.py` and `tests/flow_ui_smoke.py`.
