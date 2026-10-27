# Apple Music · native Atmos and Lossless

**English** · [Русский](ATMOS_PROTOTYPE.ru.md)

Emberbox 0.18 adds an optional native **ALAC / Hi-Res Lossless** path alongside
its JOC headphone renderer. With native Lossless connected, automatic selection
prefers **Atmos → highest available ALAC → standard playback**. Availability
still depends on the recording, account and territory.

| Playing format | Evidence and processing |
| --- | --- |
| Dolby Atmos | Licensed E-AC-3, actual JOC/OAMD confirmation by OpenJOC, binaural stereo rendering |
| Lossless | Successfully decoded ALAC, original bit depth and sample rate from its configuration |
| Hi-Res Lossless | Decoded ALAC above 48 kHz, up to 24-bit / 192 kHz |
| AAC fallback | Standard Apple Music playback when the optional path cannot start |

The badge describes the **source being decoded**. Upsampling cannot create an
Atmos or Hi-Res badge. Catalogue variants appear separately in quality details.

## Connect

1. Connect the Apple Music library through **Settings → Accounts**.
2. For native ALAC, choose **Settings → Connect Apple Lossless…**. Setup runs in
   a background process. This native engine needs its own Apple sign-in and,
   when requested, a verification code. Enter them only in that window.
3. Enable **Apple · Atmos / Lossless · beta**. The native sign-in action enables
   it after successful connection. Without native sign-in, the Atmos path and
   standard web playback remain available.
4. Play a song. Open its quality badge to see original bit depth/rate and the
   native output rate. The saved native session survives player restarts.

Pre-install components and provision missing system dependencies:

```sh
./install.sh --apple-atmos     # JOC headphone renderer
./install.sh --apple-lossless  # also prepare the separate ALAC engine
```

`./install.sh --check --apple-lossless` only inspects and shows a plan. Neither
command signs into an account. An Apple Music subscription is required.

## EmberFlow and output

The existing incandescent **EmberFlow** switch and Ember queue control both
native formats. At most two producer processes feed one bounded PCM mixer.
Each input holds up to four seconds plus bounded transport/decoder buffers.
Mixing uses one sample clock, smooth complementary gain envelopes and up to
an eight-second overlap. Artwork and queue handover follow the audible output.

Manual selection keeps that mixer and its output clock running. One upcoming
Ember-queue song is prepared early, even with automatic mixing switched off.
A ready choice uses a short 220 ms envelope; an uncached choice keeps the current
song audible while loading. Network and licence preparation can still take time.
Rapid choices supersede obsolete preparations. Recent manifest descriptors stay
in a four-entry, 60-second memory cache; each selection retains its own authorized source context.
Previous restarts the current song after three seconds; pressing it again while
the rewind is pending selects the previous queue entry. Adding songs keeps up to
twenty recent history entries, reclaiming them if the 200-entry limit needs room.

The original Atmos-only session uses a 48 kHz output clock. When native Lossless
is connected, both decks share **192 kHz**, so a 96/192 kHz source is not forced
through a 48 kHz mixer during overlap. Lower-rate material is converted with a
streaming FFmpeg resampler. This does not increase its original quality.
**Beat alignment is unavailable in the native path**; tempo and pitch stay
unchanged. Ordinary MusicKit playback keeps its existing Beats mode.

OpenJOC is an independent renderer, without Dolby certification or Apple's app
renderer. Output is two-channel PCM for headphones; Atmos bitstream output to
an AV receiver and head tracking are not implemented. The sound server, Bluetooth
or output device may resample or otherwise process audio. The source badge does
not certify an unchanged signal all the way to the headphones.

### Atmos volume on stereo devices

The 7.1.4 layout is a **virtual scene**, rendered into two output channels;
it does not require twelve physical speakers. Version 0.18.5 uses a music
presentation: no cinema dialogue attenuation or broadcast DRC, with the LFE
included equally in both ears. This removes avoidable level/bass loss while
retaining the JOC spatial reconstruction. The gain difference depends on the
track's metadata; different stereo and Atmos masters need not sound equally loud.

After rendering, an Atmos-only stereo-linked limiter detects peaks at 192 kHz
with a −1 dBFS ceiling, 5 ms lookahead and 120 ms release. Both channels share
one gain, preserving the spatial balance. There is no automatic makeup gain
or loudness riding; only peaks above the ceiling are reduced. Delay compensation
retains the complete tail and track timing, including seeks and EmberFlow.
ALAC / Hi-Res does not pass through this limiter. No sound-server volume,
hardware layout, extra model or stored audio recording is involved.

The policies use the pinned [OpenJOC C API](https://github.com/chyinan/OpenJOC/blob/v0.20.1/crates/openjoc-capi/include/openjoc.h)
and its [unity dialogue-gain mode](https://github.com/chyinan/OpenJOC/blob/v0.20.1/crates/openjoc-eac3/src/dialnorm.rs).

Pause, seek, source changes and cancellation control the entire native path.
Startup errors such as expired authentication or unavailable licences restore
ordinary playback. Native seek recovery preserves quality as described below.

### Manual track changes

At most two isolated hosts stay available for native Apple playback. An unused
FairPlay host can initialize while the current song plays; released hosts can
serve another song without repeating the saved sign-in startup. Every selection
still checks subscription/source authorization. Native opaque handles stay in the
worker, with a maximum of 16 contexts; idle hosts are recycled after eight loads
or earlier when capacity is low. A stale authorization gets one fresh native
host retry while the previous song remains audible. No extra model or audio recording is introduced.

The encrypted intro is prefetched in the source while authorization runs. Manual
selection needs 160 ms of buffered PCM; automatic EmberFlow keeps its larger
preroll. Current audio continues until the selected decoder is ready, then the
short smooth handover follows the output clock. Catalogue requests can be
superseded without waiting for an older lookup. The library shows Starting until
the selected audio is confirmed. Network authorization may still take time;
no AAC preview or lower-quality asset is used to conceal that delay.

### Seeking without a quality change

Seeking within the current track retains its source context, CDM/licensed handles
and output device. Only the codec pass and bounded PCM queue are replaced. Rapid
requests cancel stale passes and the last position wins; seeking while paused
stays paused. The slider responds immediately while the output confirms the move.
No lower-bitrate rendition or AAC conversion is used to make seeking faster.

For deep Atmos seeks, declared 48 kHz media timestamps allow unused access units
to be skipped before a half-second JOC/HRTF preroll. The audible section still
uses the same Atmos decoder and asset. Unknown timing retains the complete
preroll. A native seek failure gets one native retry; if that fails, playback
stops rather than silently switching the seek to web AAC. Other startup failures
retain the ordinary-playback recovery described below.

## Components and resources

Linux x86_64, glibc ≥ 2.34, NumPy, FFmpeg, libmpv/python-mpv and a PulseAudio
protocol server, normally PipeWire-Pulse, are required. Atmos also uses a compatible
installed Widevine module and a C++17 compiler. Lossless setup checks GCC/G++,
make, git, OpenSSL and libcurl linking dependencies.

Optional downloads are approximately **100 MB for OpenJOC + 75 MB for native
Lossless dependencies**. Allow about **500 MB free disk space** for preparation
and updates, and **512 MB extra RAM headroom** for native decoding and overlap.
These are resource allowances, not measured minimum hardware requirements.
No Android VM or new neural model runs. Existing verified downloads are reused.
The minimum CPU for real-time rendering still needs testing on other machines.

The Lossless adapter builds locally from the MIT-licensed
[Adam source](https://github.com/silentone12725/apple-music-linux/tree/f2d66c3aa6a0cd78b41def391b2a08ed4af110e7)
at a pinned revision, with Ember's compatibility patch. The patch fixes the Linux
`login` symbol collision, forwards Apple dialogs to the user and bounds native
subscription-state access. Loader and Android library downloads are SHA-256
verified. Proprietary DRM libraries are fetched locally and are not bundled here.

## Account and data

Signed media URLs and browser tokens stay inside the authorized Apple page.
The optional native engine keeps its **separate account session in a private
Ember profile**, with access restricted to the current user. Password and
verification-code input travels through private process pipes and is not logged
or saved by the sign-in UI. Apple dialogs require the person's selection.

Native code handles opaque licensed contexts; Ember provides no content-key
export protocol. Encrypted fragments and decoded audio pass through memory and
pipes. Audio/PCM files are not written to disk; native audio workers disable core
dumps. Subscription, device and territory restrictions continue to apply.

## Verification and beta status

Checks include a full 16-bit / 44.1 kHz ALAC recording, real 24-bit / 48 kHz and
24-bit / 96 kHz source sections, native seeking, and mixed-format output-clock
handover. Synthetic ALAC fixtures preserve exact 24-bit samples at 44.1, 96 and
192 kHz. Automated checks cover source selection, rotated licences, encrypted
sample bounds, quality evidence, mixer cancellation and ordinary-playback recovery.
Real account checks do not run in public CI.

This remains an experimental integration: private Apple interfaces and native
library compatibility can change. [OpenJOC 0.20.1](https://github.com/chyinan/OpenJOC/releases/tag/v0.20.1)
is downloaded with pinned SHA-256
`a031c473f3036700f66c81337ed73db8734a86b5086989e219e6bd0e1babe72c`.
Its full Apache-2.0 licence and Adam's MIT notice are saved beside their runtimes.

[Audio quality](AUDIO_QUALITY.md) · [Requirements](REQUIREMENTS.md) · [Third-party components](THIRD_PARTY.md)
