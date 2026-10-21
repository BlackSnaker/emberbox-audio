# Yandex Music · My Wave

**English** · [Русский](YANDEX_MUSIC.ru.md)

> Experimental integration for subscription testers. The official website loads in the native engine and the anonymous connection has been checked. My Wave subscription playback has **not yet been verified with a real Yandex Plus account**. Automated checks use fixtures.

## Connect inside Emberbox

1. Open **Settings → Accounts → Yandex Music → Sign in**.
2. Sign in with Yandex ID in the **Emberbox Audio · Yandex Music** window. Passwords and confirmation codes stay on Yandex's website.
3. Return to Emberbox, choose **Yandex Music** in the source menu and open **My Wave**.
4. Press **Play My Wave**. **Like / Less like this** send reactions through the website's player controls, so Yandex can adapt its recommendations.

A Yandex Plus subscription and service availability in your region are required. See [Yandex's sign-in and subscription guide](https://yandex.ru/support/music/ru/registration-and-login).

## What is integrated

- A fourth source in full and compact modes, with separate application volume/mute and selected-process PipeWire spectrum.
- An in-widget My Wave start button and reactions, metadata/artwork, seeking, previous/next and standard **Ember** desktop media controls.
- Search, playlist cards with in-widget track drill-down, and currently loaded queue tracks. Lists are limited to 50 loaded rows; paginated/virtualized content is not a complete library export.
- An independent background engine, session profile and private local socket. Changing sources pauses the previous source and does not start the new one automatically.

## Playback components

The account panel can discover and check an installed compatible Electron/Chromium engine and a public Widevine module. If Apple Music is already configured, Emberbox reuses its current runtime/module paths while preserving Yandex’s **separate** existing profile. Apple credentials and sessions are not copied. Runtime binaries are not bundled or downloaded by Emberbox.

If detection fails, use the engine and Widevine chooser in the Yandex account card. The required capabilities and installed-runtime limitations are the same as [Apple Music](APPLE_MUSIC.md).

Configuration: `$XDG_CONFIG_HOME/emberbox-audio/yandex-engine.json` (normally `~/.config/emberbox-audio/`). Profile: `yandex-web-profile/`. The background service is `emberbox-audio-yandex.service`.

## Updating to 0.7.3

Update the checkout and run `./install.sh`. An older background Yandex adapter is replaced separately, retaining its signed-in profile. The Apple Music playback process is not restarted.

Select Yandex Music: playlists load when opening its panel. Click a playlist to see its tracks, and use **All playlists** to return. Plus and service availability are still required for playback. Account sign-in is now shown separately from player readiness.

If sign-in succeeds but music or lists are still missing, open the official window through its account card and test the same track there. Report your Emberbox version, the widget error and, if present, `$XDG_RUNTIME_DIR/emberbox-yandex-web/electron-status.json`. That file contains engine versions, readiness flags and error categories; it does not record cookies, tokens or track titles. Do not share the browser profile itself.

## Test checklist

With an active Plus account, verify:

- Sign-in completes and survives a widget restart.
- My Wave starts, advances automatically and updates the cover, progress and tubes.
- Like, dislike and skips affect the official wave; a track change keeps the interface responsive.
- Search, collection, queue selection, pause/resume and seeking work with the current website.
- Switching between Spotify, Apple Music, YouTube and Yandex pauses the previous source and keeps their volumes separate.
- Desktop media controls show **Ember**, and compact mode keeps the source accessible.

Report the desktop, runtime version and failed action in a GitHub issue. Do not attach cookies, tokens or private browser/profile files.

This adapter uses the official site's current player objects and UI, rather than a guaranteed public Yandex Music API. Website updates may require adapter changes. An unavailable control produces a message in the widget; the account card can reopen the official window.
