<div align="center">
  <img src="assets/icon.svg" width="72" alt="Emberbox Audio icon">
  <h1>Emberbox Audio</h1>
  <p><strong>Your music, a little warmer.</strong></p>
  <p>Linux · GTK 3 · PipeWire · MIT · Early release</p>
  <p><a href="#get-started">Get started</a> · <a href="docs/DESIGN.md">Grunesphism</a> · <a href="README.ru.md">Русский</a> · <a href="https://github.com/BlackSnaker/emberbox-video">Emberbox Video</a></p>
</div>

![Emberbox Audio: full and compact interfaces in a warm Gruvbox presentation](assets/hero.png)

## Your music, a little warmer.

A warm desktop companion for **Spotify, Apple Music, YouTube and Yandex Music**, with audio-reactive gas-discharge tubes and controls that feel like a small piece of hi-fi equipment.

- **Choose your source.** Spotify, Apple Music, YouTube or Yandex Music, including in mini mode. Apple Music has an in-widget library, song search and playback. [Apple Music setup →](docs/APPLE_MUSIC.md)
- **Music without the window juggling.** Artwork, track details, seeking and transport controls beside your work.
- **Real sound, warm light.** Nine frequency bands from the selected application’s audio stream, with smooth, critically damped motion.
- **Tactile controls.** A metal mute toggle, a fine-adjustable volume dial, and separated playback buttons.
- **Small when you want it.** A draggable mini mode with cover art, controls and glowing tubes.
- **Personal picks, close by.** An optional experimental drawer for your Spotify collections and their tracks.

<div align="center">
  <img src="assets/preview.gif" width="460" alt="Live GTK preview with moving gas-discharge indicators">
  <p><sub>Actual GTK interface. Original demo artwork and generated audio are used for this preview.</sub></p>
</div>

## Step inside the music

![Fullscreen listening room with original demonstration artwork and verse](assets/fullscreen.png)

Open **Listening room · Fullscreen** from settings, press the **⛶** header button or **F11**. Big artwork, a cover-tinted atmosphere, live tubes and line-synchronized lyrics from LRCLIB bring the same Grunesphism materials to a whole screen. Click a timed line to seek; **Esc** brings back your desktop widget exactly where you left it. Plain lyrics and instrumental/missing-text views keep the scene useful when timecodes are unavailable.

Large original covers replace enlarged thumbnails. Supported Apple Music catalog songs can display their authentic animated album cover, looping silently and pausing with the track. Optional FFmpeg enables motion covers; unavailable animations retain static artwork.

[Fullscreen controls, lyrics availability and privacy →](docs/FULLSCREEN.md)

*This capture uses the real GTK interface, original demo artwork and an original demonstration verse.*

## Sign in from the player

![Account centre with original artwork and demo data](assets/accounts.png)

**Settings → Accounts** brings Spotify, Apple Music and Yandex Music together: launch official sign-in, see connection status and return to your music. First launch opens this panel automatically. Apple Music includes background component checks and setup without terminal commands. [Connect your music →](docs/ACCOUNTS.md)

## YouTube, without an account

Select **YouTube · Search & play**, search by title or paste a YouTube/YouTube Music link. Audio plays inside the widget with cover art, a queue, seeking and the same reactive tubes. Existing browser sessions can also be selected. [Setup and details →](docs/YOUTUBE.md)

## My Wave, in the warm light

![Yandex Music interface with original demo artwork and synthetic playback](assets/yandex-music.png)

**Experimental Yandex Music integration:** start **My Wave**, send like/dislike reactions and browse loaded search, collection and queue tracks inside the widget. Connect Yandex ID from **Settings → Accounts**. Full playback requires Yandex Plus. Subscription playback is **awaiting testers**; interface, routing and adapter checks use fixtures. [Setup and tester checklist →](docs/YANDEX_MUSIC.md)

## Get started

**Linux desktop + PipeWire required.** GNOME 50 with Wayland + XWayland is the original tested desktop. KWin 6.7.5 has also been checked in a nested Wayland/XWayland session; full Plasma Shell testing remains on the [KDE tester checklist](docs/KDE.md). Windows and macOS are not supported.

Clone and run the installer as your normal user:

```sh
git clone https://github.com/BlackSnaker/emberbox-audio.git
cd emberbox-audio
./install.sh --autostart
```

The installer checks existing components and prepares the missing ones: GTK and audio tools, YouTube playback with its JavaScript support, and FFmpeg for motion covers. It supports **Arch, Debian/Ubuntu, Fedora and openSUSE**, uses `sudo` only for missing system packages with the package manager's confirmation, and keeps Python extras in an isolated app-managed runtime. Your desktop theme and audio services are kept as configured.

Then open **Emberbox Audio** from your applications menu. Omit `--autostart` to launch only when you choose. The same launcher supports GNOME and KDE; without a user service manager it falls back to direct launch. **`./install.sh --check`** previews checks and commands without changes. `--no-deps` requires dependencies to be present; `--yes` explicitly accepts package confirmations. [Install options, plain output and troubleshooting →](docs/INSTALL.md)

To run from the checkout after dependencies are ready, use `./run.sh`.

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
| Music source | **Spotify / Apple Music / YouTube / Yandex Music ⌄**, or **S⌄ / A⌄ / Y⌄ / Я⌄** on the compact cover |
| Compact mode | **Mini** / expand icon |
| Volume | Wheel over the dial, or drag up/right; **Shift** for finer steps |
| Mute | Metal toggle; the volume setting is retained |
| Seek | Click the progress bar |
| Browse collections | **For you** for Spotify; **Your library** for Apple Music |

## What to expect in v0.7

This is an early source release, built from the working desktop widgets. Apple Music's in-widget integration is experimental and uses Apple's website in a separately configured local engine; compatible runtime binaries are not distributed. Browser MPRIS remains an optional fallback. Spotify personal recommendations use an optional, version-sensitive local desktop-client integration. Website and client updates may require integration fixes; see the setup notes.

- The widget is designed to live on the desktop, underneath ordinary app windows.
- Position, compact mode and audio preferences are kept locally in the standard XDG directories.
- Login stays on Apple's website in an Emberbox-owned profile. Credentials are not exported to the GTK interface; music metadata and thumbnails are cached locally.
- Network work runs outside GTK’s UI thread.

[Install / uninstall](docs/INSTALL.md) · [Contribute & test](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Made to feel at home

Emberbox Audio is one half of a pair. Its companion, [Emberbox Video](https://github.com/BlackSnaker/emberbox-video), shares the tubes, materials and Grunesphism design language.

Built by [BlackSnaker](https://github.com/BlackSnaker). Source and original preview artwork are [MIT licensed](LICENSE). Spotify and Apple Music are third-party services; this is an independent project.
