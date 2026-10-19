# Contributing

**English** · [Русский](CONTRIBUTING.ru.md)

Small, focused improvements are welcome. Useful issue reports include the distribution, desktop/compositor, X11 or Wayland, Python version and relevant package versions. For Spotify discovery problems, also include the desktop-client version. Avoid posting account data or private debug logs.

## Check a change

```sh
python3 -m compileall -q src tools tests
python3 -m unittest discover -s tests -p 'test_*.py' -v
node tests/apple_web_test.js
node tests/apple_browser_test.js
node tests/yandex_web_test.js
GDK_BACKEND=x11 dbus-run-session -- xvfb-run -a python3 tests/gui_smoke.py
GDK_BACKEND=x11 dbus-run-session -- xvfb-run -a -s '-screen 0 1920x1080x24' python3 tests/fullscreen_smoke.py
```

The GUI smoke test uses isolated XDG folders, fixture metadata and muted/offline components. It does not control a real Spotify client or desktop playback. Live media checks still need a desktop session and PipeWire.

To regenerate the original-media preview:

```sh
GDK_BACKEND=x11 dbus-run-session -- xvfb-run -a python3 tools/render_preview.py --output /tmp/emberbox-preview
```

Design changes should preserve the [Grunesphism principles](docs/DESIGN.md), readable contrast, separated compact controls and keyboard-accessible actions. Run fullscreen checks against the video’s actual allocation, not only the top-level window size.
