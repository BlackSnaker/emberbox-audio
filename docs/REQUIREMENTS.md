# System requirements

**English** · [Русский](REQUIREMENTS.ru.md)

Emberbox Audio is a Linux desktop application. Ordinary playback, fullscreen
artwork and optional local AI karaoke have different resource needs.

## Hardware at a glance

**These are provisional sizing recommendations, not benchmarked hardware
minima.** The lowest usable CPU and RAM configuration has not yet been tested.
RAM means total system memory, including the desktop and music source.

| Resource | Playback, tubes and fullscreen | Local AI vocal reduction |
| --- | --- | --- |
| CPU starting point | 2 modern CPU cores | 4 modern cores / 8 threads; the startup benchmark must keep up with the audio |
| RAM starting point | 4 GB | 8 GB or more; the development reference has 16 GB |
| Free-space planning budget | Reserve 1 GB | Reserve 2 GB total, including the player |
| Graphics | Integrated graphics; hardware OpenGL 3.2 recommended for animated covers and transitions | Same display requirements; AI runs on CPU, without CUDA or a discrete GPU |
| Display | Smallest tested fullscreen layout: 1024×600 logical pixels | Same; larger displays give lyrics more room |

CPU generation, power limits, other applications and the selected playback
engine affect responsiveness. A core count alone cannot guarantee real-time AI.
The space figures are planning budgets, not fixed installation sizes: additional
distribution packages, Spotify/browser installations, account profiles and
growing caches can require more. At display scaling above 100%, allow enough
physical pixels to retain the tested logical workspace.

## Required software

| Component | Requirement |
| --- | --- |
| Platform | Linux; **x86_64 is the currently tested target**. The built-in Apple/Yandex DRM path expects Linux x64 Widevine. ARM has not been validated. Windows and macOS are unsupported. |
| Desktop session | X11, or Wayland **with XWayland**; GTK uses its X11 backend in both cases |
| Audio | Running PipeWire, its `pw-record`, `pw-play`, `pw-link` and `pw-dump` tools, plus `pactl` and `pacat`. Karaoke additionally needs a compatible PulseAudio protocol server, normally PipeWire-Pulse, with null-sink support. |
| Python and UI | Python ≥ 3.10, PyGObject, GTK 3, GdkX11 and an SVG image loader |
| Python libraries | NumPy ≥ 1.24, Pillow ≥ 10 and websocket-client ≥ 1.6 |
| YouTube | libmpv, python-mpv, yt-dlp with matching EJS scripts, and Deno ≥ 2.3 or Node ≥ 22 |
| Animated artwork | FFmpeg; the standard installer checks for it. Static covers remain usable without animation. |
| Network | Internet access for installation/downloads, streaming, online artwork and automatic lyrics; preparing AI also downloads its model and runtime |

Git is needed for the documented `git clone` installation. A systemd user
manager is optional: the launcher can run the app directly.

The installer checks existing components and prepares missing dependencies on
**Arch and compatible derivatives, Debian/Ubuntu, Fedora and openSUSE**. Package
availability depends on the distribution release and configured repositories.
Unknown or immutable distributions need dependencies supplied through their own
supported packaging tools. [Installation and distribution details →](INSTALL.md)

## Music sources

| Source | Additional requirement |
| --- | --- |
| Spotify | Separately installed Spotify desktop client, native or Flatpak, and an account. Personal recommendations use a separate experimental connection. |
| Apple Music | Apple Music subscription and a compatible installed Electron/Chromium runtime with working AAC/EME and Linux x64 Widevine. Setup checks capabilities; sign-in remains on Apple's site. |
| YouTube | The YouTube dependencies above. Publicly playable media normally needs no account. |
| Yandex Music | Yandex ID, Yandex Plus and a compatible playback/DRM runtime. Subscription playback remains experimental and awaits tester verification. |

Emberbox does not bundle proprietary DRM binaries or install Spotify. Installing
the GTK player does not establish a subscription or connect every source.
[Account setup →](ACCOUNTS.md)

## EmberFlow and beat matching

No additional model is needed. One extra deck is prepared around the transition;
Apple adds a MusicKit renderer and a small Web Audio graph. YouTube uses FFmpeg,
already checked by the installer: one low-priority thread analyzes at most 6.5
seconds. Observations stay in memory and playback uses its original engine. The
outgoing YouTube detector shares the lamp worker, estimating BPM at most once a
second. Turning Beats off stops this analysis and intro decoding.

## Optional Apple Music Atmos

Spatial playback requires **Linux x86_64, glibc ≥ 2.34**, compatible Widevine and
a C++17 compiler. `./install.sh --apple-atmos` checks components and prepares the
decoder: about 100 MB download; allow another 250 MB of free space. Output is
48 kHz for headphones. EmberFlow temporarily adds a second decoder; mixer input
buffers are bounded to four seconds each plus transport buffers. No additional
neural model is needed. The minimum CPU for this mode has not been established;
ordinary installation checks cannot guarantee real-time spatial rendering.
[Beta capabilities and limitations →](ATMOS_PROTOTYPE.md)

## AI karaoke: additional resources

- First use downloads a SHA256-verified **30 MB UVR model** and prepares a
  private ONNX Runtime / ONNX / SciPy environment. Runtime packages add roughly
  **100–250 MB**, depending on reused dependencies; setup/update needs temporary
  space as well. These files are additional to the source engine and its cache.
- Processing is local, on CPU, with **up to four inference threads**. No GPU,
  CUDA, API key or additional account is required.
- A startup benchmark chooses the processing block size. If processing cannot
  keep up or buffering exceeds its bound, the effect stops and original audio
  returns. The dependency check alone does not establish AI performance.
- **Fast · stereo** is a lighter, explicitly selectable alternative without
  model downloads. Lyrics-only karaoke also works without AI preparation.

[Buffering, routing and vocal-reduction details →](KARAOKE.md)

## What has actually been checked

The v0.11.3 development reference is an **AMD Custom APU 0405, 4 cores / 8
threads, 16 GB RAM and integrated AMD graphics**, running Linux x86_64. Local
UVR with denoising on this machine needs roughly **2–3 seconds of buffering**;
the player displays its measured delay. This is a reference result, not a
minimum specification or a latency promise for other computers.

- **GNOME 50, Wayland + XWayland:** the original working desktop environment.
- **KWin 6.7.5, nested Wayland + XWayland:** window placement, input, rounded
  transparency and fullscreen restoration checked. A full Plasma Shell session
  still needs [KDE tester coverage](KDE.md).
- **1024×600, 1280×720 and 1920×1080:** fullscreen layout checks, including
  karaoke controls. These layout checks do not establish frame rates on every GPU.

From the checkout, preview the software checks without installing anything:

```sh
./install.sh --check --lang en --plain
```

This checks software dependencies, not available RAM, disk headroom, account
entitlements or real-time AI speed. For a hardware report, include CPU model,
RAM, distribution, desktop/session, display scale, source and the affected mode.

[Back to the player](../README.md) · [Install](INSTALL.md) · [Karaoke](KARAOKE.md)

## Local Ember DJ

Optional: plan for 4 modern cores, 8 GB total RAM and 3 GB additional storage
for local models/runtime. Text-based mood matching works without models;
voice and language AI are prepared in the DJ tab.
[Setup, checked components and limitations →](DJ.md)

## Optional Apple Lossless / Hi-Res

`./install.sh --apple-lossless` also prepares the native ALAC adapter and checks GCC/G++, make, git, OpenSSL and libcurl linking dependencies. The extra download is about 75 MB beyond OpenJOC. Allow about 500 MB total free disk space for preparation/updates and 512 MB additional RAM headroom for the native path and overlap. These are resource allowances, not measured minimum hardware. No Android VM or new AI model runs. A separate Apple sign-in is available from player settings. Lossless sessions use a common 192 kHz mixer for mixed-format EmberFlow. [Details →](ATMOS_PROTOTYPE.md)
