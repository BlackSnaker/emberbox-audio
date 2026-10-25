# Native spatial audio components

Emberbox's own adapter and mixer use the repository's MIT licence.

| Component | Version / source | Licence |
| --- | --- | --- |
| OpenJOC native C ABI and spatial renderer | [0.20.1 release](https://github.com/chyinan/OpenJOC/releases/tag/v0.20.1) | Apache-2.0; the optional setup saves the release's complete `LICENSE` beside the library |
| Chromium public CDM API headers | [Chromium CDM repository](https://chromium.googlesource.com/chromium/cdm/+/main/) | BSD; copyright notices remain in the headers and the complete licence is included in `src/spatial_native/LICENSE.chromium` |
| libmpv / FFmpeg | System-provided libraries and executable | Their respective upstream and distribution licences apply |
| Adam native FairPlay compatibility sources | [Pinned MIT source](https://github.com/silentone12725/apple-music-linux/tree/f2d66c3aa6a0cd78b41def391b2a08ed4af110e7) | MIT; notice in `src/fairplay_native/LICENSE.adam`; optional local build with Ember compatibility patch |

OpenJOC is downloaded only for optional spatial playback, with a pinned archive
checksum. No decoder binary or proprietary Widevine module is bundled in this
repository. Widevine is loaded from the user's compatible existing installation;
its own licence and service restrictions continue to apply.

OpenJOC uses its independent spatial renderer, including its upstream HRTF
implementation and data. See the [upstream project](https://github.com/chyinan/OpenJOC)
for the renderer's provenance and limitations. Emberbox makes no Dolby
certification or equivalence claim. Dolby, Dolby Atmos and Apple Music names
identify their respective formats and services.

[English usage guide](ATMOS_PROTOTYPE.md) · [Руководство на русском](ATMOS_PROTOTYPE.ru.md)

The optional native Lossless setup fetches the pinned Adam source archive, its compatibility loaders and Android runtime dependencies with SHA-256 checks. Those binaries are downloaded locally and are not bundled in this repository. The separate native Apple session is stored in Ember’s private profile.
