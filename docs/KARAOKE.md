# Karaoke

**English** · [Русский](KARAOKE.ru.md)

Open fullscreen with **⛶ / F11**, then select **Karaoke**. Large cream type,
amber word lighting, gentle line transitions and the familiar tubes give your
voice room. Transport, the volume dial and the listening queue keep working.
Leaving fullscreen returns to the desktop widget.

![Actual GTK karaoke scene with original demonstration lyrics](../assets/karaoke.png)

## Words and timing

- Automatic lyrics come from LRCLIB, using the same recording matching as the
  ordinary lyrics panel. Only opening Lyrics or Karaoke starts a lookup.
- Ordinary LRC highlights **lines**. The footer explicitly says when word
  timestamps are unavailable. Words are never assigned invented equal timings.
- **Load LRC** accepts a UTF-8 enhanced LRC file for the current recording,
  with real `<mm:ss.xxx>` word tags. Supplied word segments warm to amber on
  their timestamp. Sub-word tags also work when the file supplies them.
- A countdown appears in the last five seconds before a timed entry. Empty
  timed lines and explicit final word ends allow instrumental rests. Pause,
  backward/forward seeks and song changes update the stage without restarting
  playback. Plain text is readable but has no timed highlighting.
- Imported text stays in a private per-user configuration file, associated with
  that title, artist, album and duration. It is not uploaded. **Automatic**
  removes that override and looks up lyrics again. Files are limited to 120 KB.

The common automatic source usually supplies line timing. Importing an LRC
does not align a different recording, live performance or remix automatically.
This release supports enhanced LRC, not Apple's TTML catalogue or a connection
to Apple Music Sing. Song lyrics are not bundled with Emberbox.

**Network disclosure:** an automatic lookup sends title, artist, album and
duration to [LRCLIB](https://lrclib.net/). Lyrics remain optional; unavailable
text does not stop the music.

## Vocal reduction

The metal switch enables an **experimental stereo centre filter** for the
selected player's output. Its separate small dial controls reduction strength;
the large console dial continues to control overall volume. At 0% the routed
signal passes through, with the filter's buffering delay.

This is a real-time spectral mid/side effect, not AI stem separation. A voice
mixed in the centre can be attenuated substantially; stereo backing vocals,
reverb and off-centre voices can remain. Centred instruments can also become
quieter. Bass below the vocal band and stereo side information are protected.
The dial reduces the entire vocal-band mid signal, including when wide
accompaniment overlaps it. It does not gate reduction on centre dominance.
Try a moderate setting first. Mono and multichannel streams are not processed.

The effect runs in a separate Python/NumPy process with overlap-add and smoothed
gain, outside GTK. Its algorithmic delay is 32 ms, plus audio-server
buffering. It resamples to stereo float PCM at 48 kHz; an active filter is not
a bit-perfect or lossless output path, regardless of the source-quality badge.
It requires `pactl` and `pacat` (the installer checks both), and a compatible
PipeWire-Pulse or PulseAudio server with null-sink support. It does not depend
on GNOME or KDE desktop APIs.

Only the selected application is routed to a temporary sink. Other applications
and the system mix are not captured. For an external browser, that application's
shared audio output can include other tabs in the same browser session; use the
isolated built-in Apple/Yandex engine when you need separation. No microphone
is opened and audio is neither saved nor uploaded.

The effect is off initially. It switches off on leaving Karaoke/fullscreen or
changing source. New streams from that same player are picked up while active.
On failure, the helper restores original stream destinations; disconnected
outputs fall back to the server's available default. It respects streams the
user has manually moved elsewhere and never changes the default device.
Closing Emberbox or killing its GUI closes the helper's control pipe and restores
audio. If the helper itself is forcibly killed, the next Emberbox start recovers
its abandoned route from a private journal. A brief interruption can occur when
moving streams or losing an output device.

## Verification

`tests/karaoke_smoke.py` checks actual GTK controls down to 1024×600, genuine
word timing, pauses, seeks and filter lifecycle with offline fixtures.
`test_karaoke_audio.py` checks synthetic DSP and restoration invariants.

An opt-in `EMBERBOX_AUDIO_ROUTE_TEST=1 python3 tests/karaoke_route_smoke.py`
creates original tones and private inaudible null sinks to verify real routing,
suppression, preserved bass/sides, EOF/SIGTERM cleanup and forced-kill recovery.
It does not move existing application streams or change the default output.
Live song separation quality still depends on each recording; synthetic checks
cannot establish it for an entire music catalogue.
