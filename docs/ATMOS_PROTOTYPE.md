# Apple Music Atmos: engineering prototype

**English** · [Русский](ATMOS_PROTOTYPE.ru.md)

**Status, 2026-10-25: Apple Music Atmos playback is not enabled in Emberbox.**
The stages below were tested independently. The protected playback path remains
unfinished; version 0.16.3 fixes catalogue availability reporting.

## Verified stages

| Stage | Observation on the development machine |
| --- | --- |
| Song and album catalogue | Both supply `audioTraits: atmos`; the adapter now recognizes this |
| Normal MusicKit playback | The decoder reports AAC, 44.1 kHz, two channels |
| Authorized enhanced HLS asset lookup | The master playlist advertises `ec-3` with `CHANNELS="16/JOC"`, alongside AAC alternatives, in a Widevine playback session |
| Current Chromium 155 runtime | E-AC-3, AC-3 and AC-4 fail MSE and Media Capabilities checks; AAC succeeds |
| Independent native decoder | OpenJOC 0.20.1 parses JOC/OAMD and renders a clear upstream fixture to binaural float32 PCM at 48 kHz |

The playlist was inspected inside the authorized Apple page. Only allowlisted
format labels were returned; media URLs, account tokens, keys, licences and
audio segments were not exported. A manifest declaration does not establish
successful protected playback or JOC decoding of that Apple recording.

## Reproduce native streaming

The developer-only [probe](../tools/probe_spatial.py) feeds a local raw fixture
through OpenJOC's streaming C ABI in small chunks, consumes PCM immediately and
drains the renderer tail. It writes no PCM files, opens no audio device and
makes no network requests. The installed player does not load it.

Use the trusted library from the [OpenJOC 0.20.1 release](https://github.com/chyinan/OpenJOC/releases/tag/v0.20.1).
The tested archive is `openjoc-0.20.1-x86_64-unknown-linux-gnu.tar.gz`.
Its SHA-256 was checked against the release checksum file:

```text
a031c473f3036700f66c81337ed73db8734a86b5086989e219e6bd0e1babe72c
```

The clear upstream fixture is
[`joc.lifecycle.ec3`](https://github.com/chyinan/OpenJOC/blob/v0.20.1/crates/openjoc-wasm/testdata/joc.lifecycle.ec3).
Supply local paths after obtaining those files:

```bash
python3 tools/probe_spatial.py \
  --library /absolute/path/to/libopenjoc_capi.so \
  --input /absolute/path/to/joc.lifecycle.ec3
```

Repeat with `--chunk-size 997` to check fragmented input. The PCM hash and sample
count should remain identical. The probe rejects unconfirmed/non-JOC input,
non-finite output and unexpected formats, and limits fixture size/duration.

One local run rendered 196,863 output frames including the filter tail in
0.74 seconds for 4.10 seconds of output. All samples were finite, peak 0.00331;
maximum staged compressed input was 4,096 bytes. This short synthetic fixture
is not a performance guarantee for commercial albums or other JOC profiles.
The JSON explicitly reports `appleMusicPlaybackVerified: false`.

OpenJOC is an experimental independent Apache-2.0 decoder. Its binaural output
does not claim parity with Apple's/Dolby's renderer or Dolby certification.
See the [upstream scope](https://github.com/chyinan/OpenJOC).

## Remaining engine work

The current Electron runtime links codecs internally. Placing FFmpeg or an
OpenJOC shared library beside it does not add E-AC-3 to MSE or connect that
library to encrypted MusicKit playback.

A complete implementation needs a maintained Chromium/Electron build with
E-AC-3 demuxing/decoding, authorized EME/CDM handling and JOC/OAMD rendering in
that same media pipeline. The clear-file prototype cannot consume encrypted
HLS segments. Then the enhanced asset selector, seek, pause, track changes,
latency, EmberFlow, karaoke and AAC fallback need end-to-end checks before
enabling playback or a playing Dolby Atmos badge.

Chromium gates codec handling with
[`enable_platform_ac3_eac3_audio`](https://chromium.googlesource.com/chromium/src/+/main/media/media_options.gni).
That flag alone does not supply JOC rendering. Dolby also distinguishes
[stream selection, decoding and the full spatial pipeline](https://professionalsupport.dolby.com/s/article/Dolby-Audio-and-Dolby-Atmos-in-web-apps?language=en_US).
