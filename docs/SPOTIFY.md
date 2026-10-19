# Spotify connection

**English** · [Русский](SPOTIFY.ru.md)

## Sign in from Emberbox

Open **Settings → Accounts → Sign in to Spotify**, complete sign-in in the official client and play a song. Connection status updates automatically. If the client is missing, the install button opens the official download page. [Account connection guide](ACCOUNTS.md).

## Basic playback

Open the Spotify desktop client. Emberbox uses its MPRIS interface for track metadata, playback and seeking. The volume dial and mute switch act on Spotify’s PipeWire/PulseAudio stream, not the global system volume.

Both the native `spotify` executable and Flatpak `com.spotify.Client` can be launched. Flatpak audio must be visible in the host PipeWire session.

## Optional personal picks

The **For you** drawer can display personal Spotify collections and their tracks. Open **Settings → Accounts → Connect personal picks** to enable the local desktop integration. This may restart Spotify and interrupt playback once.

This early integration connects to the local Spotify desktop client’s Chromium debugging endpoint at **127.0.0.1:43827**. It reads music metadata from the client UI and invokes its local player interface. It is not the Spotify Web API and does not ask for a developer key or OAuth login. Client updates may change the internal interface and require a fix.

The endpoint gives other software on your local machine debugging access to that client. Emberbox starts it on loopback; do not expose or forward the port. If you do not want this optional connection, use the basic playback controls without connecting the drawer.

No cookies, passwords or session tokens are read by Emberbox. Collection metadata and thumbnails are cached in its per-user XDG cache directory. There is no remote Emberbox service.

The integration’s home navigation can change which page is selected inside Spotify. Clicking a track in the widget is intended to play in the background, without raising Spotify’s window.
