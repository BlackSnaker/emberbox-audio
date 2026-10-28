# Connect your music

**English** · [Русский](ACCOUNTS.ru.md)

Open **Settings → Accounts · Spotify / Apple / Yandex**, or **Connect accounts…** in the source selector. New installations open this panel automatically. It is also available from mini mode.

## Spotify

1. Choose **Sign in to Spotify**. Its official website opens in an Ember window.
2. Complete sign-in and any verification on Spotify's page. The account status updates automatically.
3. Choose **Listen** for personal shelves, tracks, catalogue search and the Ember queue. **No separate Spotify client is required.**

The same compatible DRM-capable engine used for Apple/Yandex can be reused, with a separate Spotify profile. Website playback follows your Spotify account's subscription and regional restrictions. An already running desktop client remains an optional source-menu fallback. [Spotify setup](SPOTIFY.md).

## Apple Music

1. Click **Sign in to Apple Music**. Emberbox checks the locally installed playback components in the background.
2. Complete Apple Account sign-in in Apple's own window. The player recognises completion and hides that window.
3. Click **Listen**. Playlists, albums, songs and catalogue search are inside Emberbox.

A compatible DRM-capable engine and installed Widevine are required. The installer reports their availability separately from the core app dependencies; missing DRM does not mean all music sources are ready. If automatic detection cannot find working components, the panel explains what is missing and offers file/folder selectors. No terminal commands or Node.js installation are needed for the in-player setup. See [compatibility and optional manual setup](APPLE_MUSIC.md).

## Yandex Music

Choose **Sign in to Yandex Music**, complete Yandex ID sign-in in the separate Emberbox window, then choose **Listen → My Wave**. Authentication gets its own profile; existing Apple playback components can be reused. Yandex Plus is required. This integration is experimental and subscription playback is awaiting tester verification. [Setup and tester checklist](YANDEX_MUSIC.md).

## Connection behaviour

- Opening the account panel or signing in does not switch or autoplay a music source. **Listen** explicitly chooses that source.
- Spotify and Apple sign-in stay on their official websites in separate Ember-owned profiles.
- Existing Apple sign-in survives widget restarts and engine updates. Credentials are not exported to the GTK interface.
- The desktop's media card for native Spotify, Apple Music, Yandex Music and YouTube playback is named **Ember**, with playback, seeking and volume controls.

[Spotify details](SPOTIFY.md) · [Apple Music details](APPLE_MUSIC.md)
