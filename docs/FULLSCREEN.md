# Fullscreen listening

**English** · [Русский](FULLSCREEN.ru.md)

Give the music a little more room. Fullscreen listening brings a large cover, a restrained artwork-coloured atmosphere, warm glass tubes and lyrics into the same Grunesphism instrument.

## Open and return

- Press **⛶** in the widget header, choose **Listening room · Fullscreen** in Settings, or press **F11** while the widget is focused. Settings also opens the mode from the compact widget.
- Press **Esc**, **F11**, or the exit button in the upper-right corner to return.
- The desktop widget keeps its position, compact/full layout and library state. Playback continues through the same selected source.

Fullscreen opens on the widget's monitor as a separate, focusable window. It does not turn the desktop widget itself into a fullscreen desktop surface.

## Controls

| Action | Control |
| --- | --- |
| Play / pause | Centre button or **Space** |
| Previous / next track | Transport buttons |
| Seek | Progress bar; **Left / Right** move 10 seconds |
| Volume | Dial; **Up / Down** |
| Mute | Metal toggle |
| Leave fullscreen | **Esc**, **F11**, or upper-right exit button |

The selected source still controls which playback and seek actions are available. Spotify, Apple Music, YouTube and Yandex Music use their existing Emberbox connection; fullscreen does not create a second player. The tubes follow the same measured application audio as the desktop widget.

## Lyrics

While fullscreen is open, Emberbox looks for lyrics matching the current song on [LRCLIB](https://lrclib.net/). Synchronized lyrics highlight the current line and scroll with playback; clicking a timed line seeks to it when the source supports seeking. Plain lyrics remain readable when timestamps are unavailable.

Some songs have no matching text, are instrumental, or only have plain lyrics. A failed lookup leaves the cover and playback controls usable. Lyrics availability depends on the song and the lyrics database; a music-service subscription does not guarantee lyrics.

**Network disclosure:** a lookup sends the song's title, artist, album and duration to LRCLIB. This happens only while fullscreen is shown. Signing in to a music service remains part of that service's existing account connection.

## Visual character

The cover becomes the focal point, with an understated colour wash behind the scene. Cream type, amber light, shallow relief and tactile transport controls carry over from the [Grunesphism design language](DESIGN.md). Lyrics have room to breathe and stay secondary to the currently sung line.
