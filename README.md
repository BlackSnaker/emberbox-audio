<div align="center">
  <img src="assets/icon.svg" width="72" alt="Emberbox Audio icon">
  <h1>Emberbox Audio</h1>
  <p><strong>Your music, a little warmer.</strong></p>
  <p>Linux · GTK 3 · PipeWire · MIT · Early release</p>
  <p><a href="#get-started">Get started</a> · <a href="docs/DESIGN.md">Grunesphism</a> · <a href="README.ru.md">Русский</a> · <a href="https://github.com/BlackSnaker/emberbox-video">Emberbox Video</a></p>
</div>

![Emberbox Audio: full and compact interfaces in a warm Gruvbox presentation](assets/hero.png)

## Your music, a little warmer.

A warm desktop companion for **Spotify, Apple Music and YouTube**, with audio-reactive gas-discharge tubes and controls that feel like a small piece of hi-fi equipment.

- **Choose your source.** Spotify, Apple Music or YouTube, including in mini mode. Apple Music has an in-widget library, song search and playback. [Apple Music setup →](docs/APPLE_MUSIC.md)
- **Music without the window juggling.** Artwork, track details, seeking and transport controls beside your work.
- **Real sound, warm light.** Nine frequency bands from the selected application’s audio stream, with smooth, critically damped motion.
- **Tactile controls.** A metal mute toggle, a fine-adjustable volume dial, and separated playback buttons.
- **Small when you want it.** A draggable mini mode with cover art, controls and glowing tubes.
- **Personal picks, close by.** An optional experimental drawer for your Spotify collections and their tracks.

<div align="center">
  <img src="assets/preview.gif" width="460" alt="Live GTK preview with moving gas-discharge indicators">
  <p><sub>Actual GTK interface. Original demo artwork and generated audio are used for this preview.</sub></p>
</div>

## Sign in from the player

![Account centre with original artwork and demo data](assets/accounts.png)

**Settings → Accounts** brings Spotify and Apple Music together: launch official sign-in, see connection status and return to your music. First launch opens this panel automatically. Apple Music includes background component checks and setup without terminal commands. [Connect your music →](docs/ACCOUNTS.md)

## YouTube, without an account

Select **YouTube · Search & play**, search by title or paste a YouTube/YouTube Music link. Audio plays inside the widget with cover art, a queue, seeking and the same reactive tubes. Existing browser sessions can also be selected. [Setup and details →](docs/YOUTUBE.md)

## Get started

**Linux desktop + PipeWire required.** Tested on LunaOS (Arch based), GNOME 50, Wayland with XWayland. Other desktop environments are currently best effort; Windows and macOS are not supported.

1. Install the [system dependencies](docs/INSTALL.md).
2. Clone and install for your user:

```sh
git clone https://github.com/BlackSnaker/emberbox-audio.git
cd emberbox-audio
./install.sh --autostart
```

Then open **Emberbox Audio** from your applications menu. Installation uses no `sudo`, downloads no code, and does not change your desktop theme. Omit `--autostart` to launch only when you choose. To try the source without installing, use `./run.sh`.

Select a source in the header. Apple Music plays through a background web engine, with playlists, albums, songs and catalogue search inside Emberbox. It requires a compatible installed DRM-capable runtime and an Apple Music subscription. [One-time setup →](docs/APPLE_MUSIC.md)

Open Spotify to listen to Spotify. Basic playback uses MPRIS; the personal-picks drawer has a separate local connection. [Spotify setup →](docs/SPOTIFY.md)

## Grunesphism / Грунесфизм

Our name for the visual language of Emberbox: **Gruvbox warmth + soft neumorphic relief + tactile analogue details.**

Dark olive-charcoal surfaces, warm cream type, amber light behind glass, a smooth metal switch and a small ridged dial. The light responds to real audio; the motion is physically inspired. Cover colour only gently tints the body. No large outside frame, focus rectangles or hover-tooltip clutter.

[Palette, materials and motion →](docs/DESIGN.md)

## Controls

| Action | Control |
| --- | --- |
| Move the widget | Drag its header or cover |
| Music source | **Spotify / Apple Music / YouTube ⌄**, or **S⌄ / A⌄ / Y⌄** on the compact cover |
| Compact mode | **Mini** / expand icon |
| Volume | Wheel over the dial, or drag up/right; **Shift** for finer steps |
| Mute | Metal toggle; the volume setting is retained |
| Seek | Click the progress bar |
| Browse collections | **For you** for Spotify; **Your library** for Apple Music |

## What to expect in v0.3

This is an early source release, built from the working desktop widgets. Apple Music's in-widget integration is experimental and uses Apple's website in a separately configured local engine; compatible runtime binaries are not distributed. Browser MPRIS remains an optional fallback. Spotify personal recommendations use an optional, version-sensitive local desktop-client integration. Website and client updates may require integration fixes; see the setup notes.

- The widget is designed to live on the desktop, underneath ordinary app windows.
- Position, compact mode and audio preferences are kept locally in the standard XDG directories.
- Login stays on Apple's website in an Emberbox-owned profile. Credentials are not exported to the GTK interface; music metadata and thumbnails are cached locally.
- Network work runs outside GTK’s UI thread.

[Install / uninstall](docs/INSTALL.md) · [Contribute & test](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Made to feel at home

Emberbox Audio is one half of a pair. Its companion, [Emberbox Video](https://github.com/BlackSnaker/emberbox-video), shares the tubes, materials and Grunesphism design language.

Built by [BlackSnaker](https://github.com/BlackSnaker). Source and original preview artwork are [MIT licensed](LICENSE). Spotify and Apple Music are third-party services; this is an independent project.
