# Spotify inside Ember

**English** · [Русский](SPOTIFY.ru.md)

## Sign in once

1. Open **Settings → Accounts → Sign in to Spotify**.
2. Ember prepares the installed Chromium/Widevine components and opens Spotify's
   official website in its own window. Complete sign-in and any verification there.
3. Choose **Listen**. Spotify's personal shelves, collections and tracks appear
   in Ember. Fullscreen **Collection** also provides catalogue search and the
   shared Ember queue. Artist names and album titles open their pages in Ember.

**The Spotify desktop client is optional.** No Spotify developer application,
client secret or browser extension is needed. Existing Apple/Yandex playback
components can be reused; each service keeps its own signed-in profile.

Playback uses the official web player, including its account, subscription,
region, advertisement and playback restrictions. This integration does not
change those restrictions. The [Spotify web-player guide](https://support.spotify.com/article/web-player/)
explains the website's requirements. Spotify's own **Ember** sign-in window is
available again from Accounts if the service needs attention.

## Playback and privacy

- Play, pause, next, previous and seek use the site's player. The volume dial,
  mute switch and live tubes target only this Ember Spotify session's audio.
- Source changes pause the previous source. Opening Accounts does not autoplay.
- Playback and music browsing run outside GTK; a collection read does not own
  the transport lock. Per-page reads and waits are bounded. Cached track lists
  wait for the requested page instead of silently accepting half-loaded rows.
- Only named music fields leave the site. Passwords, cookies, access tokens and
  complete internal player objects are not read out or exported to GTK.
  Sign-in stays in the official page and its private per-user profile.
- The runtime uses a local Unix socket with user-only permissions, not a public
  browser-debugging port. Another browser's or Spotify client's account files
  are never copied. There is no Ember account server.

This is an experimental website adapter: Spotify UI updates can require fixes.
Artist photographs use the exact artist's public page metadata, with a bounded
lookup and an in-memory cache. Decorative page backgrounds are excluded; this
lookup does not use the signed-in profile or account headers.
The quality badge uses decoder evidence when available; it does not assume
Lossless from an account plan. Native Spotify does not currently support
EmberFlow or beat matching; these controls keep their existing source support.

## Optional desktop-client fallback

If an installed Spotify client is running, select **Spotify · desktop client
(optional)** from the source menu. Basic controls use MPRIS. Native and Flatpak
`com.spotify.Client` installations remain supported.

The older optional personal-picks adapter uses the local desktop client's
Chromium endpoint at `127.0.0.1:43827`. It can restart that client once. This
endpoint grants local debugging access: do not expose or forward it. It is not
used by the new in-player sign-in. Returning to the main **Spotify** source
selects Ember's own web player.
