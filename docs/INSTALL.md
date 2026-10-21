# Install Emberbox Audio

**English** · [Русский](INSTALL.ru.md)

## Get started

Use a recent Linux desktop with PipeWire and **X11 or Wayland with XWayland**. Run the installer as your normal user:

```sh
git clone https://github.com/BlackSnaker/emberbox-audio.git
cd emberbox-audio
./install.sh --autostart
```

Open **Emberbox Audio** from your applications menu. Omit `--autostart` to launch whenever you want. Installation does not start a song.

The installer checks what is already available, shows the missing components and installs them through your distribution's package manager. **`sudo` is used only for missing system packages**, with the package manager's normal confirmation. Review the commands and package list in the terminal; use `--yes` only when you explicitly want to accept those confirmations automatically.

The terminal follows Emberbox's [Grunesphism palette](DESIGN.md): warm amber headings, clear steps and readable status marks. A shortened example:

```text
  E M B E R B O X   A U D I O
  A little warmth. From the first step.
  ────────────────────────────────────────────────
  1/5  Check the system
    ✓  GTK 3
    ↓  FFmpeg
  2/5  Prepare missing components
    $ sudo apt-get install --no-install-recommends ffmpeg
  3/5  Install the player
  4/5  Connect to your desktop
  5/5  Ready for music
    ✓  Installed. Make yourself at home.
```

An absent DRM engine is reported separately; a successful application installation does not mean every streaming service is connected.

## What it prepares

| Component | Purpose |
| --- | --- |
| Python 3.10+, PyGObject, GTK 3, GdkX11 and SVG support | Interface, artwork and desktop integration |
| NumPy, Pillow and websocket-client | Audio analysis, covers and source connections |
| PipeWire tools and `pactl` | Live lamps and application volume |
| XWayland, when using Wayland | Desktop widget and embedded playback |
| libmpv, python-mpv, yt-dlp with matching EJS scripts | Built-in YouTube search and playback |
| Deno ≥ 2.3 or Node ≥ 22 | YouTube JavaScript challenges |
| FFmpeg | Media processing and animated Apple Music covers |

Existing compatible components are reused. Missing Python extras are installed only into an **Emberbox-managed virtual environment with `--system-site-packages`**, so the system GTK bindings remain available. The installer does not run `sudo pip` or modify your system Python packages with pip. If a suitable JavaScript runtime is missing, the managed environment can receive Deno.

The installer does not install Spotify, switch audio servers, enable replacement audio services, change your theme or add third-party system repositories. Install the official Spotify client separately if you want that source: the native `spotify` executable and Flatpak `com.spotify.Client` are detected.

### Distribution support

Automatic missing-package installation supports **Arch and compatible derivatives, Debian/Ubuntu, Fedora, and openSUSE**, using `pacman`, `apt-get`, `dnf` or `zypper` respectively. Package availability still depends on your distribution release and enabled repositories. A missing or broken dependency stops installation with a useful diagnostic.

On unknown or immutable systems, Emberbox does not bypass the distribution's software model. Use its supported package tools or a packaged build to provide the dependencies first, then run `./install.sh --no-deps`. This succeeds only when the checks pass.

## Useful options

| Command | Behaviour |
| --- | --- |
| `./install.sh --check` | Read-only checks and installation plan; installs no packages or app files. Returns a nonzero status if dependencies are missing. |
| `./install.sh --no-deps` | Verify existing dependencies, then install the app; stop if something is missing. |
| `./install.sh --yes` | Explicitly accept package-manager confirmations; `sudo` may still ask for your password. |
| `./install.sh --autostart` | Enable launch at desktop login. |
| `./install.sh --no-autostart` | Disable launch at login. An update without either option keeps the previous setting. |
| `./install.sh --desktop-shortcut` | Add an executable launcher to the configured desktop folder. GNOME needs a desktop-icons extension to display it. |
| `./install.sh --no-desktop-shortcut` | Remove the managed desktop shortcut. Updates otherwise preserve it. |
| `./install.sh --no-systemd` | Use the direct launcher instead of a user service. This fallback is also automatic when a user service manager is unavailable. |
| `./install.sh --lang ru` / `--lang en` | Choose the installer's language; normally selected from the locale. |
| `./install.sh --plain` | Plain, colour-free terminal output; `NO_COLOR=1` also disables colours. |
| `./install.sh --skip-check` | Packaging only: skip dependency installation and validation. This can produce an unusable installation if the package omits requirements. |

Examples:

```sh
./install.sh --check --lang en --plain
./install.sh --no-systemd --autostart
```

## KDE Plasma and GNOME

The widget uses X11 window-manager hints, including when running inside a Wayland session through XWayland. **GNOME 50 with Wayland + XWayland** is the original tested desktop. **KWin 6.7.5** has also been tested separately in a nested Wayland session with XWayland; that is not a full Plasma Shell session.

The KWin check covered composited rounded transparency, below-app placement, real pointer and keyboard input, cover dragging, all-desktops placement for the widget, and fullscreen focus with Esc restoration. [Verified scope, placement options and KDE troubleshooting →](KDE.md)

Application-menu launch and XDG autostart use the current desktop session's display environment. This avoids assuming GNOME-specific startup variables on KDE. The launcher can use either a systemd user service or a direct process.

For Plasma testers, please check:

- The menu entry and login autostart both show one widget.
- Dragging, saved position, mini mode and source menus work at your display scale.
- The widget stays below ordinary windows, returns with **Show Desktop**, and behaves sensibly across virtual desktops.
- Fullscreen opens on the intended monitor and **Esc** restores the desktop widget.
- Embedded playback, seeking, application volume and audio-reactive lamps work.
- Sleep/wake, logout/login and monitor changes do not leave an invisible or duplicate widget.

Report your distribution, Plasma/KWin version, X11 or Wayland session, scale and the failing step. Desktop placement and **Show Desktop** behaviour remain compositor-dependent.

## Music accounts and DRM

**Settings → Accounts** connects Spotify, Apple Music and Yandex Music. Account sign-in and paid subscriptions remain necessary where required by the service.

For native Apple Music / Yandex Music playback, Emberbox detects installed compatible playback components. When components are found, initial setup uses a limited, isolated AAC/EME capability check; this checks the engine, not your subscription or the service's acceptance of a complete track. Missing or incompatible DRM components are shown as a limitation with setup instructions. The installer does not silently download an unverified DRM runtime or copy another application's login session.

YouTube playback normally needs no account; availability restrictions and website changes can still affect individual videos. Yandex Music subscription playback remains experimental and awaits tester verification.

[Connect accounts](ACCOUNTS.md) · [Apple Music](APPLE_MUSIC.md) · [Yandex Music](YANDEX_MUSIC.md) · [YouTube](YOUTUBE.md)

## Files, updates and removal

Use the header’s **−** to hide the widget while music continues, and **×** to close it. Mini mode has the same actions in Settings. Click the application icon or desktop shortcut to restore a hidden player; a second copy is not started. The icon’s context menu also offers Show, Hide and Close. Closing exits cleanly, so the user service does not restart it; a later launch opens it again.

Application files use `$XDG_DATA_HOME/emberbox-audio` (default `~/.local/share/emberbox-audio`). Preferences and cache use `$XDG_CONFIG_HOME/emberbox-audio` and `$XDG_CACHE_HOME/emberbox-audio`. The installer refuses to overwrite an unmanaged installation directory. The command launcher is `~/.local/bin/emberbox-audio` by default.

```sh
# Stop when using the user service:
systemctl --user stop emberbox-audio.service
# Update after pulling the checkout:
./install.sh
# Remove the app:
./uninstall.sh
```

Uninstall removes application files and launchers, including the managed Python environment. Personal preferences and cache are kept; system packages installed by the distribution package manager are also kept.

To run directly from the checkout, use `./run.sh` after dependencies are present. `GDK_BACKEND=x11` is intentional; your Wayland desktop session stays enabled.

## Troubleshooting

- **Installation stops:** run `./install.sh --check --plain` and include its output with the error. For an installed copy, also identify which command failed.
- **No window:** launch from the graphical desktop, check XWayland, and try `~/.local/bin/emberbox-audio` in a terminal.
- **Widget behind an app:** the desktop widget intentionally lives below ordinary windows. Return to the desktop.
- **No moving lamps:** check that PipeWire is running and the selected application has audio ports visible to `pw-link -l`.
- **No sound:** check the mute toggle, dial and your desktop's application mixer.
- **User-service diagnostics:** `journalctl --user -u emberbox-audio.service -n 40`.
