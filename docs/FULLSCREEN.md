# Fullscreen listening

**English** · [Русский](FULLSCREEN.ru.md)

Give the music a little more room. Fullscreen listening brings a large cover, a restrained artwork-coloured atmosphere, warm glass tubes and lyrics into the same Grunesphism instrument.

## Open and return

- Press **⛶** in the widget header, choose **Listening room · Fullscreen** in Settings, or press **F11** while the widget is focused. Settings also opens the mode from the compact widget.
- Press **Esc**, **F11**, or the exit button in the upper-right corner to return.
- The desktop widget keeps its position, compact/full layout and library state. Playback continues through the same selected source.

Fullscreen opens on the widget's monitor as a separate, focusable window. It does not turn the desktop widget itself into a fullscreen desktop surface.

Returning animates the cover back toward the desktop widget. Both normal/Mini transitions are animated too; the saved mode and position stay intact.

## Controls

| Action | Control |
| --- | --- |
| Play / pause | Centre button or **Space** |
| Previous / next track | Transport buttons |
| Seek | Progress bar; **Left / Right** move 10 seconds |
| Volume | Dial; **Up / Down** |
| Mute | Metal toggle |
| Lyrics / artwork | Header button |
| Leave fullscreen | **Esc**, **F11**, or upper-right exit button |

The selected source still controls which playback and seek actions are available. Spotify, Apple Music, YouTube and Yandex Music use their existing Emberbox connection; fullscreen does not create a second player. The tubes follow the same measured application audio as the desktop widget.

Collection, albums, search and the separate queue page are described in [Collection and listening queue](COLLECTION.md).

## Lyrics

Fullscreen opens with a large centred cover. Press **Lyrics** in the header to show the text panel; **Artwork** returns to the cover. No lyric lookup, line rendering or scrolling runs before you ask for text.

While the text panel is open, Emberbox looks for lyrics matching the current song on [LRCLIB](https://lrclib.net/). Synchronized lyrics highlight the current line and scroll with playback; clicking a timed line seeks to it when the source supports seeking. Plain lyrics remain readable when timestamps are unavailable.

Some songs have no matching text, are instrumental, or only have plain lyrics. A failed lookup leaves the cover and playback controls usable. Lyrics availability depends on the song and the lyrics database; a music-service subscription does not guarantee lyrics.

**Network disclosure:** a lookup sends the song's title, artist, album and duration to LRCLIB. This happens only while fullscreen and its text panel are shown. Signing in to a music service remains part of that service's existing account connection.

## Visual character

The cover becomes the focal point, with an understated colour wash behind the scene. Cream type, amber light, shallow relief and tactile transport controls carry over from the [Grunesphism design language](DESIGN.md). Lyrics have room to breathe and stay secondary to the currently sung line.

## Original-size covers

Fullscreen requests a separate large source: Apple Music at 1200×1200, Spotify's available large variant, Yandex Music at 1000×1000, and YouTube maxres where available. If the CDN does not supply the larger asset, the available source is retained. Artwork keeps its aspect ratio instead of cropping its edges to fill the square.

### Authentic Apple Music motion artwork

When the current catalog song has a public animated album cover, fullscreen automatically loops it silently. This is the album's original animation, not a motion effect applied to a still image. Pausing music freezes the cover; leaving fullscreen stops its decoder. Loading errors, missing video art, or unsupported catalog IDs retain the static cover.

The clip is prepared locally before its first animated frame. A short, memory-bounded queue feeds display-clock presentation at 60 fps, with gentle frame blending for lower-rate video and scene-cut detection. Hardware GL updates a fixed-size texture; the image fallback uses the same clock. Changing the cover size keeps the same running loop. Pausing or temporarily obscuring the window resumes at its position, without fast-forwarding to wall time. Source quality and display/GPU performance still limit the result.

Completed silent clips are cached for up to seven days, with a 48 MiB per-clip limit and a 160 MiB limit for completed cache entries. A failed or oversized download keeps the still cover. No account credentials or audio are stored in this cache.

Animation needs optional **FFmpeg**: `sudo pacman -S ffmpeg` on Arch or `sudo apt install ffmpeg` on Ubuntu/Debian. Static covers and the player work without it. Support currently covers public Apple Music motion artwork, not Spotify Canvas or every service's animations.

**Network requests:** only while fullscreen is open, the player fetches the public page of the exact Apple Music song and its linked album, then streams cover video from Apple's CDN. It does not search for similarly named releases. No account passwords, cookies, or tokens are sent. Known cover CDNs receive a request for the larger image size.
