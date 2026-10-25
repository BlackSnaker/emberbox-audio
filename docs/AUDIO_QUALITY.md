# Audio quality

**English** · [Русский](AUDIO_QUALITY.ru.md)

The small **≋** badge beside the album in the desktop widget, and beneath it in fullscreen, describes the current audio stream. Click it for details. Nothing opens on hover; Mini keeps its compact layout.

The material is warm frosted glass, with fine grain and a soft edge highlight. The detail card blurs one in-memory snapshot of its own player window when opened; no capture timer runs. A matte gradient remains available if the window cannot be sampled.

## Prefer the best available stream

Built-in playback prefers maximum supported quality automatically:

- **YouTube:** `bestaudio/best` selects the best available audio stream, without a forced low-bitrate cap or a second lossy encode.
- **Apple Music:** request MusicKit's public **HIGH** setting before playback and on song changes. The current [official MusicKit JS runtime](https://js-cdn.music.apple.com/musickit/v3/musickit.js) defines it as 256 kbps. The optional native path prefers Atmos and, after connecting Apple Lossless, the best available ALAC for ordinary recordings; HIGH alone does not add ALAC or Atmos to the web decoder. A future higher existing setting is not lowered.
- **Yandex Music:** for a recognised Plus account, use the same quality-controller and player-state setters as the official site's **High quality** choice. Yandex selects FLAC or its highest alternative for that recording, including My Wave. A website/adapter change may make automatic selection unavailable; the detail panel reports this. This integration still needs listening verification by testers with Plus.
- **Spotify and external browsers:** choose the highest quality in the source app. These connections currently provide no supported quality-setting operation to Emberbox.

The detail panel distinguishes **maximum requested** from the **format actually decoded**. A subscribed account or requested high-quality setting never establishes a Lossless stream. Yandex applies a changed quality preference to the next song; already buffered audio is not restarted automatically. See [Yandex's quality guide](https://www.yandex.ru/support/music/ru/listening/quality).

- **AAC, Opus, Vorbis, MP3:** the decoder's codec and sample rate, when reported.
- **Lossless:** a confirmed ALAC, FLAC or PCM stream. **Hi‑Res Lossless** appears when that stream's reported sample rate exceeds 48 kHz.
- Details include sample rate, channel count and approximate measured bitrate when the engine provides them. A float32 decoder output does not establish a recording's original bit depth, so Emberbox does not infer one.
- **Available in the catalogue** reads both Apple Music's song `audioVariants` and the website's `audioTraits`, including `atmos` and `surround`. It can include Dolby Atmos, Hi‑Res Lossless and Lossless even when current playback uses AAC. These catalogue labels never become the playing-format badge.

## Source support

| Source | Playing format | Catalogue formats |
| --- | --- | --- |
| Built-in Apple Music | Chromium or confirmed native JOC / ALAC / Hi-Res playback | Song variants supplied by Apple; optional extended-attribute request |
| Built-in Yandex Music | Chromium's active audio decoder, when exposed | Not reported |
| Built-in YouTube | libmpv codec, decoded sample rate/channels and measured packet bitrate | Not reported |
| Spotify / external browsers / Firefox companion | These connections do not currently report the decoded stream format | Not reported |

If data are absent, **Quality → Not reported** explains this; subscription level, quality preferences and device mixer rate are never used as substitutes. Browser playback does not acquire Lossless or Atmos support from a badge. E-AC-3 or multichannel audio alone does not confirm Dolby Atmos; the optional native path verifies in-band JOC/OAMD. [Apple Music Atmos and spatial EmberFlow →](ATMOS_PROTOTYPE.md)

The badge describes the stream **before system audio processing**. Resampling, Bluetooth, spatial processing and output hardware can alter what reaches the listener. It does not certify a bit-perfect output path.

The observer enables only Chromium's local Media diagnostics and keeps a bounded, filtered set of decoder fields. It does not inspect network requests or export media URLs, headers, cookies or DRM material. New-song/prefetch guards prevent a queued track from replacing the active decoder's quality. Unsupported diagnostics leave playback available. Existing native engines update once with their separate account profile retained; Apple restores its song and listening position through the existing upgrade path.

Sources: [Apple song audio variants](https://developer.apple.com/documentation/applemusicapi/songs/attributes-data.dictionary), [Chromium Media diagnostics](https://chromedevtools.github.io/devtools-protocol/tot/Media/), [mpv audio properties](https://mpv.io/manual/stable/#properties).

Native Lossless uses a separate sign-in through **Settings → Connect Apple Lossless…**, saved in a private Ember profile. Its mixer runs at 192 kHz; the badge continues to describe the original source rate. [Native setup and verified formats →](ATMOS_PROTOTYPE.md)
