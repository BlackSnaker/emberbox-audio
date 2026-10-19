# YouTube in Emberbox Audio

**English** · [Русский](YOUTUBE.ru.md)

Choose **YouTube · Search & play** in the source menu. Search by song/artist or paste a link from YouTube or YouTube Music. Select a result to play **audio inside the music widget**. A browser window opens only when you explicitly press the arrow.

- Public videos need no YouTube account or API key. Private, age-restricted, region-unavailable or anti-bot-blocked videos may fail.
- Results form the playback queue. Next advances; previous restarts the current track after three seconds, otherwise goes to the previous result. At the end of a track the next result plays while YouTube is the active source.
- The cover, progress, mute toggle, dial, compact mode and audio-reactive tubes use the same Grunesphism interface.
- Source changes pause playback. The queue and position are stored locally; restarts never autoplay.
- To control an existing browser tab, start YouTube/YouTube Music there, then choose its media session in the source menu. Browser media focus and audio can be shared with other tabs.

Native search/playback uses **libmpv + python-mpv + yt-dlp**. Keep yt-dlp current; modern YouTube extraction also needs its supported JavaScript runtime/EJS setup. Emberbox never imports browser cookies or login tokens. See the [official yt-dlp EJS setup](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

Arch dependencies: `python-mpv mpv yt-dlp deno`. Ubuntu: `python3-mpv mpv`, plus a current yt-dlp and supported JavaScript runtime. These packages are optional if you only use Spotify/Apple Music/browser playback.

Search and loading run outside GTK's UI thread. Native audio is scoped to this widget's process; its spectrum does not follow the separate Emberbox Video player or the system monitor.
