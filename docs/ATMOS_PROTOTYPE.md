# Apple Music Atmos · native headphone playback

**English** · [Русский](ATMOS_PROTOTYPE.ru.md)

**Emberbox 0.17.0 adds an experimental Apple Music E-AC-3 JOC playback path.**
It requests the enhanced asset within your signed-in session, uses your installed
Widevine CDM and renders spatial audio with OpenJOC. Output is binaural float32
PCM at 48 kHz, two channels for ordinary headphones.

This is OpenJOC's independent renderer, not a Dolby-certified engine or Apple's
app renderer. Atmos bitstream output to an AV receiver and head tracking are not
implemented. Atmos does not mean Lossless.

## Enable it

1. Connect Apple Music through **Settings → Accounts** and play a song available
   in Atmos in your catalogue.
2. Enable **Dolby Atmos · headphones · beta** in player settings. First-use setup
   prepares the optional components in the background.
3. Wait for **Preparing Atmos…** to finish. **Dolby Atmos · 48** appears only after
   the actual decoder confirms JOC.

Prepare components and provision missing system dependencies beforehand with:

```sh
./install.sh --apple-atmos
```

`./install.sh --check --apple-atmos` only inspects and displays a plan. Requirements:
Linux x86_64, glibc ≥ 2.34, a compatible installed Widevine CDM, a C++17 compiler,
NumPy, libmpv/python-mpv, FFmpeg and a PulseAudio protocol server, usually
PipeWire-Pulse. The OpenJOC archive is about 100 MB; allow another 250 MB of free
space for the archive, library and updates. Existing components are reused.
Emberbox does not distribute the proprietary DRM module.

## Spatial EmberFlow

Enable the existing incandescent **EmberFlow** switch and add the next song to
Ember's queue. Atmos uses the same control.

- An authorized decoder and a small buffer prepare the next track ahead of time.
  At most two decoders exist simultaneously.
- Each track receives its own spatial render. Their outputs mix into **one
  float32 stream with a shared output clock**, using sample-based gain curves
  rather than interface volume steps.
- Up to eight seconds of intro reveal, foreground handover and fading ambience.
  Complementary gains preserve peak headroom.
- Queue and artwork promotion follow the audible output clock. The outgoing
  decoder is released after the mix.
- Transitions to ordinary AAC songs use decoding and high-quality conversion to
  the common 48 kHz rate. The badge follows the incoming format; AAC never gains
  an Atmos label.
- **Beat alignment is not available in this path yet.** Tempo and pitch remain
  unchanged. Ordinary Apple Music playback keeps its existing beat alignment.

No additional neural model is required. Preparation and overlap temporarily add
CPU and memory use. Buffers are bounded; unavailable licensing, network or decoder
support returns to ordinary playback rather than looping requests.
[Queue and EmberFlow controls →](FLOW.md)

## Quality evidence and fallback

A catalogue Atmos label cannot change the playing-format badge. Real EC-3 access
units, successful processing by the installed CDM, in-band JOC/OAMD confirmation
and valid PCM are required. Device mixer rate is not substituted for stream data.

Unavailable spatial playback restores ordinary Apple Music playback, with the
attempt's reason in quality details. A failed track is not retried indefinitely.
Disabling the option restores the ordinary engine at the current position. Pause,
seek and source changes control the entire native path.

## Lossless and Hi-Res: a separate source limitation

**Full Apple Music ALAC/Hi-Res playback is not supported yet.** Ordinary tracks
request the highest supported MusicKit HIGH setting (AAC). Catalogue Lossless
and Hi-Res labels are never presented as evidence of the playing stream.

An authorized-session check on 25 October 2026 covered ordinary/enhanced web
profiles and the catalogue `extendedAssetUrls.enhancedHls`. The extended HLS
included ALAC: two checked recordings exposed FairPlay only; a third also had
Widevine declarations. An isolated test decoded the third recording's opening
fragment as 24-bit / 48 kHz ALAC, but Apple's server rejected the continuation
license with `status: -1002`. Checking all declared licenses before playback
confirmed that rejection. This describes the checked recordings/session, not
a guarantee about the entire catalogue.

The isolated decoder also preserved exact 24-bit samples from our own synthetic
ALAC fixtures at 44.1 and 96 kHz. An ALAC decoder therefore does not by itself
provide access to Apple's complete stream. Partial experimental playback is
excluded from the shipped player to avoid stopping a song after a few seconds.

[Apple documents Lossless in its supported applications](https://support.apple.com/en-us/118295)
and [FairPlay as protected playback on Apple platforms](https://developer.apple.com/streaming/fps/).
[Cider also documents the MusicKit.js Lossless limitation](https://cider.sh/learn-more).
Emberbox's native path provides verified JOC playback; a separate FairPlay
backend is not implemented in it yet.

This is a limitation of the current connection, not proof that Linux Lossless
is impossible. [Adam](https://github.com/silentone12725/apple-music-linux) advertises
ALAC up to 192 kHz through Android FairPlay with separate authentication. A source
audit confirmed a different sign-in mechanism and Android library dependencies.
That route needs its own integration, complete-track validation and EmberFlow
checks; support in Ember is not confirmed yet.

## Account, licensing and data

Account tokens and signed media addresses remain inside the signed-in
`music.apple.com` page. Native processes receive opaque licence messages and
encrypted fragments through a private local channel. Your installed CDM performs
licensed decryption through its public API; there is no key export interface.
Audio files and PCM are not written to disk; audio-process core dumps are disabled.
Subscription, device and territory restrictions continue to apply.

## Verification and beta limitations

Development-machine checks include a real licensed Apple JOC stream, pause/resume,
mid-song startup and seeking, song changes and AAC recovery. Six-second Atmos →
Atmos and Atmos → AAC transitions confirmed concurrent decoders, outgoing release
and continued incoming playback. Automated tests cover
multiple encrypted CMAF sample descriptions, byte ranges and IVs, bounded buffers,
continuous mixing and transition cancellation. Real account checks do not run in
public CI.

This is an early implementation for testing on other computers. Apple's private
website interfaces and Widevine requirements can change. This feature does not
add multichannel speaker output, ALAC/Hi-Res support or Dolby certification.

[OpenJOC 0.20.1](https://github.com/chyinan/OpenJOC/releases/tag/v0.20.1) is an
independent experimental Apache-2.0 decoder. Downloads pin SHA-256:

```text
a031c473f3036700f66c81337ed73db8734a86b5086989e219e6bd0e1babe72c
```

Its licence is saved beside the decoder library. Chromium's public CDM API headers
are included with their BSD licence. [Third-party components →](THIRD_PARTY.md)

[Audio quality](AUDIO_QUALITY.md) · [System requirements](REQUIREMENTS.md)
