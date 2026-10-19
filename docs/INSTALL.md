# Install Emberbox Audio

**English** · [Русский](INSTALL.ru.md)

## Runtime

- Linux desktop, X11 or Wayland with **XWayland** enabled.
- Python 3.10+, GTK 3 and PyGObject.
- PipeWire and its command-line tools (`pw-record`, `pw-link`, `pw-dump`).
- Spotify desktop client, MPRIS and `pactl` for per-app volume; numpy, Pillow, websocket-client.

The tested desktop is **LunaOS (Arch based), GNOME 50, Wayland + XWayland**. Desktop placement hints depend on the compositor. The recipes below provide dependencies; they are not a claim that every desktop has been tested.

### Arch / Arch based

```sh
sudo pacman -S --needed python python-gobject gtk3 python-numpy python-pillow pipewire-audio libpulse python-websocket-client
```

### Ubuntu / Debian family

Package names below follow Ubuntu 24.04; a recent distribution is recommended.

```sh
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-numpy python3-pil pipewire-bin pulseaudio-utils python3-websocket

```

Install Spotify separately, either as a native `spotify` executable or Flatpak `com.spotify.Client`. Emberbox does not install or modify the Spotify application.

Check your environment:

```sh
python3 tools/check_dependencies.py
```

Use a system Python that can import `gi`. A virtual environment must be created with `--system-site-packages` if you choose to use one. Native GTK and audio dependencies are not installed by `requirements.txt`.

Optional animated Apple Music covers need `ffmpeg`: install it with `sudo pacman -S ffmpeg` or `sudo apt install ffmpeg`. Static original-size covers work without it. [Motion cover details](FULLSCREEN.md).

## Per-user installation

```sh
./install.sh                 # menu entry; launch when needed
./install.sh --autostart     # also enable start at login
```

No root permission and no downloads are used by this installer. A systemd user service, an application-menu entry and a small launcher are created. Click the menu entry or run `~/.local/bin/emberbox-audio`. The installer does not start a media item.

Installed application files use `$XDG_DATA_HOME/emberbox-audio` (default `~/.local/share/emberbox-audio`). Configuration and cache use `$XDG_CONFIG_HOME/emberbox-audio` and `$XDG_CACHE_HOME/emberbox-audio`. It refuses to overwrite an unmanaged directory.

For a desktop without systemd user services:

```sh
./install.sh --no-systemd
# or use --no-systemd --autostart for an XDG autostart entry
```

## Run from the checkout

```sh
./run.sh
```

`GDK_BACKEND=x11` is selected deliberately: the desktop-widget hints and embedded video integration use X11. The normal Wayland desktop remains enabled.

## Stop, update or remove

```sh
systemctl --user stop emberbox-audio.service
# after updating your checkout:
./install.sh
# remove the application:
./uninstall.sh
```

Uninstall removes installed application files and launchers and leaves personal preferences and caches in place. You can remove those XDG folders manually if you want a complete reset. No desktop theme, Spotify installation or browser profile is changed.

## Troubleshooting

- **No window:** run `./run.sh` from a terminal and check dependency output and XWayland availability.
- **Window disappears behind an app:** the widget intentionally lives below ordinary windows. Return to the desktop.
- **No moving lamps:** check `pw-link -l` and that the intended application is actually producing audio. Spotify output ports must be available to the host PipeWire session.
- **No sound:** check the widget’s mute toggle, its dial and the system’s application mixer.
- **Service diagnostics:** `journalctl --user -u emberbox-audio.service -n 40`.

## Apple Music

A Linux browser with MPRIS support can replace the Spotify client as a source. See [browser setup and limits](APPLE_MUSIC.md).
