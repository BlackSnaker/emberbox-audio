# KDE Plasma / KWin

**English** · [Русский](KDE.ru.md)

Emberbox keeps its [Grunesphism materials](DESIGN.md) on KDE: transparent rounded corners, soft relief, readable controls and warm light. Use the normal [installer](INSTALL.md); a separate KDE build or theme is not required. A Wayland session needs XWayland.

## What has been verified

The integration test ran against **KWin 6.7.5 in a nested Wayland session with XWayland**, hosted by Xvfb and using QPainter compositing. This exercises a real compositor and pointer/keyboard events. It is a controlled test environment, not a full Plasma Shell desktop.

| Check | Result in that session |
| --- | --- |
| Rounded transparency | Composited pixels at a rounded corner showed the synthetic desktop background; the card itself remained opaque. |
| Desktop layer | The widget used a normal window kept below ordinary apps, with a stable window identity and no taskbar/pager entry. |
| Startup focus | Opening the widget did not steal keyboard focus. |
| Pointer and keyboard | A pointer click opened settings; the search field accepted keyboard input. |
| Dragging | Dragging the cover moved the window through KWin. |
| Virtual desktops | A narrowly scoped, temporary KWin script placed only the desktop widget on all virtual desktops. |
| Fullscreen | The listening room gained focus and a higher layer. It was not below apps or on all desktops. Esc restored the widget's position, size and compact state. |

These results do **not** cover a full Plasma Shell session, native KWin X11, KDE 6.8, hardware graphics drivers or physical multi-monitor layouts. Panel and multi-monitor work-area calculations also have synthetic geometry tests; actual panel layouts need tester confirmation. Streaming-account access is separate from window-manager testing.

## How desktop placement works

Emberbox detects KDE/Plasma from the desktop environment or KWin window-manager identity. On KDE it selects an ordinary window kept below apps, preserving transparency and interactive controls. Other desktops retain the original desktop-window mode. The fullscreen listening room remains a separate ordinary fullscreen window.

For virtual-desktop placement on KWin/XWayland, Emberbox uses a temporary script restricted to **resource name `emberbox-audio` and window role `desktop-widget`**. It does not change global KWin settings or install persistent window rules. If scripting is unavailable, the widget still runs; it may stay on the current virtual desktop.

KWin's window types and window properties are documented in the [X11 window implementation](https://github.com/KDE/kwin/blob/master/src/x11window.cpp), [shared window implementation](https://github.com/KDE/kwin/blob/master/src/window.cpp) and [scripting API](https://develop.kde.org/docs/plasma/kwin/api/). KDE also describes its [Wayland architecture](https://community.kde.org/KWin/Wayland).

## Troubleshooting placement

### Try an explicit mode

`EMBERBOX_DESKTOP_MODE` overrides automatic detection:

| Value | Behaviour |
| --- | --- |
| `normal` | Normal window kept below apps; the default on KDE. |
| `desktop` | Desktop-window mode; the original default on other desktops. |

Stop an existing copy before testing. From the source checkout:

```sh
# If the installed copy uses a user service:
systemctl --user stop emberbox-audio.service
# Try one mode:
EMBERBOX_DESKTOP_MODE=normal ./run.sh
```

Replace `normal` with `desktop` to compare. To persist an override for the installed systemd service, run `systemctl --user edit emberbox-audio.service` and add:

```ini
[Service]
Environment=EMBERBOX_DESKTOP_MODE=normal
```

Then restart that service. This override affects Emberbox only.

### If all-desktops scripting is unavailable

You can keep the widget on the current desktop or create a **user window rule** in **System Settings → Window Management → Window Rules**. Match both the Emberbox window class (`emberbox-audio` / `EmberboxAudio`, as reported by Detect Window Properties) and the exact window role **`desktop-widget`**. Set its virtual-desktop placement to **All Desktops**; the exact property label varies by Plasma version.

Restricting the role keeps the listening room and sign-in windows outside this rule. If your rules editor cannot match the role, leave the widget on its current desktop rather than applying an app-wide all-desktops rule. No global KWin settings need changing.

## Checklist for Plasma testers

Please test your actual desktop session:

- Launch from the application menu and at login; check that only one widget appears.
- Try mini mode, menus, searching, dragging and saved placement at your display scale.
- Check below-app placement, **Show Desktop**, virtual desktops and Activities.
- Open fullscreen on each monitor, exit with Esc, and check restoration.
- Check panels, fractional scaling, monitor reconnection and sleep/wake.
- Play audio from your chosen source; test volume, seeking and the live lamps.

Include distribution, Plasma and KWin versions, X11/Wayland, scaling, monitor/panel layout and the failing step in your report. For installation failures, attach `./install.sh --check --plain` output. For the installed user service, relevant logs are available with `journalctl --user -u emberbox-audio.service -n 40`.
