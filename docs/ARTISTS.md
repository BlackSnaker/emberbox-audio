# A room for the artist

**English** · [Русский](ARTISTS.ru.md)

In fullscreen, click the **artist's name ›** beneath the song. Collection track
rows and open collections also have an **Artist ›** action; the current artist's
name is clickable in Queue. Browsing stays inside the listening room and does
not start a track.

![Actual artist room with original demonstration media and fictional metadata](../assets/artist.png)

## A warmer portrait

A wide photographic masthead fades into olive charcoal: rounded portrait,
large cream name, available genres and amber playback controls. The artist's
image supplies the restrained background and clearer right edge. Missing photos
retain a quiet fallback. Image preparation runs away from GTK and completed
banners use a small bounded cache.

**Overview**, **Albums**, **Singles & EPs**, **Compilations**, **Appears on** and
**About** stay above the scroll area. Overview brings together featured releases
and popular songs. About shows the selected source's editorial description with
attribution; biographies are not generated. Collaborations and unresolved names
offer artist cards for an explicit choice. Exact recording relationships take
precedence; name searches are never silently assigned to a namesake.

## Open a release

Click a cover for tracks, available release date and track count. **Read the
liner notes** softly unfolds the source's album description when supplied.

![Release with original demonstration liner notes](../assets/artist-release.png)

- Click a song to play from that point and continue through the loaded playable
  songs. Explicit queue additions remain ahead of the new continuation.
- **+** adds a song; **Queue** adds the loaded playable selection without
  interrupting music. **Listen** starts the loaded songs.
- Unavailable recordings remain visible with disabled playback/queue controls.
- **Load more** uses the source's next page, up to 200 loaded entries. Spotify
  exposes up to its first 100 cached album tracks, not a complete catalogue.
- **‹ Artist** restores the artist category; **‹ Back** returns to the preceding
  room page. **Alt+Left** also goes back; **Esc / F11** restores the desktop widget.

Transport, seeking, volume and tubes stay available. Track changes retain the
artist you deliberately opened. A source change opens that source's context;
late replies from another page/source are discarded.

## Source coverage

| Source | Artist room |
| --- | --- |
| Apple Music, in-player connection | Catalogue portrait, supplied editorial notes, popular songs, albums, singles/EPs, compilations, appearances and paged release tracks. Uses the existing account/playback connection. |
| Spotify | Information exposed by the connected desktop client. Categories and biographies depend on its page. The optional adapter remains version dependent; missing categories stay empty. |
| Yandex Music | Artist identity, loaded releases, songs and supplied descriptions from the official site's session. Separate categories depend on the site. Subscription playback still awaits tester verification. |
| YouTube | In-player search for the current name/channel. No verified artist discography or biography is available through this connection; another service's catalogue is not substituted. |

Unavailable text and empty sections do not stop music. Offline adapter checks
do not establish live catalogue coverage for every Spotify/Yandex artist.

## Data and verification

Requests reuse the selected source's connection, sending the selected artist or
recording ID, or the name when resolving it, to that source. No additional
account or third-party biography service is introduced. Artwork uses the normal
local thumbnail cache; catalogue results and browsing state use bounded memory
caches. Passwords, cookies and tokens are not copied into this page.

Apple uses documented [artist views](https://developer.apple.com/documentation/applemusicapi/artists/views-data.dictionary)
and [artist attributes](https://developer.apple.com/documentation/applemusicapi/artists/attributes-data.dictionary).
Editorial markup becomes plain text, not executable content or GTK markup.
Spotify/Yandex browsing uses in-page navigation and reports unavailable navigation
without forcing a page reload that would interrupt playback.

Checks cover exact identity, collaborations, pagination, unavailable songs,
unchanged transport, stale replies, source changes and real GTK at 1024×600,
1280×720 and 1920×1080 in both languages. Previews use original artwork and
fictional artist/release text.

[Player](../README.md) · [Collection and queue](COLLECTION.md) · [Accounts](ACCOUNTS.md)
