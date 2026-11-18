# Yandex Music · direct API

**English** · [Русский](YANDEX_MUSIC.ru.md)

Yandex Music now uses its API and local libmpv playback, without an embedded website, Electron or Widevine. Full tracks and My Wave require Yandex Plus and service availability in your region. This is not a guaranteed public API; Yandex may change it.

## Connect

1. Install `libmpv`, the Python package `python-mpv`, and `secret-tool` (`libsecret-tools` on Debian/Ubuntu and openSUSE; `libsecret` on Arch/Fedora). Your desktop must provide an unlocked Secret Service, such as GNOME Keyring or compatible KWallet.
2. Open **Settings → Player → Accounts and sign-in → Yandex Music → Sign in**. The app displays a one-time code and opens `https://ya.ru/device` in your browser. If it does not open, click the link in the dialog or open the address manually.
3. Enter the code on Yandex's website and approve access. Passwords and confirmation codes are entered only on Yandex. The app receives its token automatically; no manual token copying is needed. Closing the dialog cancels waiting. Reopen sign-in to obtain a new code if it expires.
4. Select Yandex Music as the source, open a playlist, search for a track or start **My Wave**.

The token is validated through `account/status` before saving. It is stored only in the desktop keyring (`application=emberbox`, `service=yandex-music`), not in JSON, process arguments or a browser profile. Connection fails if the keyring is unavailable: there is no plaintext fallback. Reopen the account card to replace the token. Remove it using your keyring manager, and revoke access in Yandex account settings when necessary.

## Features

- Track search, your own playlists and their tracks, and a local queue.
- Direct full-length MP3 streams at the highest available bitrate, pause, seek, covers and metadata. Previews never replace full recordings.
- My Wave through Rotor sessions, batch replenishment, playback/skip events, likes and dislikes.
- Artist pages, popular tracks, albums and album tracks. Guest releases are not exposed by this connection.
- Switching sources pauses Yandex. A slow stream request cannot start audio after you leave the source.

The My Wave panel shows every returned row with scrolling, without a 50-row cutoff; the shared library uses the same API client. The queue is local, not the official application's queue.

## Migrating from the website engine

The old `emberbox-audio-yandex.service` is stopped on startup. Its `yandex-web-profile/` and `yandex-engine.json` are preserved but no longer used. Apple Music and Spotify sessions are unaffected. Website sign-in cannot be converted to an OAuth token: connect a token separately.

## Verification and troubleshooting

Automated checks cover API contracts with fixtures, MP3 signing, credential-free media requests, keyring storage, feedback and inactive-source playback protection. **Live playback with a subscription has not been verified in the development environment.**

With Plus, check reconnection after restarting, search, playlists, My Wave transitions, feedback, seeking, source switching and volume. Report the app version, desktop environment, displayed error and failing action. Do not attach tokens, signed stream URLs or keyring contents. Replace an expired token through the account card.

## Personal playlists and playlist-based Wave

The Yandex panel's **For you** tab shows personal playlists supplied by the API for your account, such as the daily playlist and new-release picks. Titles and availability come from Yandex; unready or missing playlists are not invented. Your own playlists remain in **Playlists**.

Open any playlist and select **Wave from this playlist** to start a recommendation session seeded by that playlist, rather than simply shuffling its tracks. The top **Play My Wave** button starts the general personal wave.

A status under the My Wave button identifies **My Wave**, **Wave from playlist**, or **Wave from track — title**, with Playing/Paused state. The recommendation source stays visible across track changes. **Wave from current track** starts a separate wave seeded by the currently selected recording.

The current song is highlighted in playlist rows. Previous uses the managed playlist queue; after several seconds, its first press restarts the recording. Pressing **Next** at the end of a playlist starts its wave; merely finishing the last recording does not. After updating, reopen the playlist and select a track to attach its playlist context to the queue.
