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

Pause, seek, source changes and cancellation control the entire native path.
Expired authentication, unavailable licences, network or decoder errors restore
ordinary playback instead of repeatedly retrying the same song.

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
