# Ember · product film

Original 40-second product introduction, Russian and English titles. The GitHub
README embeds the uploaded H.264/AAC edition; repository copies are kept here
for download and reproducible publication.

## What is shown

- Actual GTK 3 desktop UI, captured in isolated Xvfb: source menu, sign-in
  buttons, search, playback, fullscreen artwork/lyrics, and Mini.
- Original **Emberbox Sessions / Afterglow** demonstration artwork and track
  metadata. All account states are fixtures; no credentials, personal libraries
  or paid service recordings are read or exposed.
- The opening still life is promotional concept artwork, not an application
  screenshot. The other screens show the real application with demo data.
- The soundtrack is an original, sample-free synthesis made for this film;
  no commercial song or third-party sample is used. Live tube footage measures
  that soundtrack. The lyric verse is original demonstration text.

The film explains the interface; service access, subscriptions, regions and
experimental integrations retain the conditions documented in each setup guide.
It does not demonstrate verified subscription playback or promise every service
feature for every source. English titles use the Russian demonstration UI.

## Rebuild

Run from the repository root. Capture tools require the normal Linux GUI
runtime, Xvfb and FFmpeg. Music generation also uses NumPy and SciPy; motion
composition uses Pillow and NumPy. Use an isolated X display, not your desktop.

```sh
python3 tools/promo_audio.py --output /tmp/ember-film-audio/ember-original.wav --duration 40
python3 tools/capture_promo.py --help
python3 tools/render_promo.py --help
```

Generate the original 40-second WAV with `promo_audio.py`, then capture with:

```sh
GDK_BACKEND=x11 dbus-run-session -- xvfb-run -a -s '-screen 0 1920x1080x24' \
  python3 tools/capture_promo.py --output /tmp/ember-film-captures \
  --language ru --clip-seconds 3 --pcm /tmp/ember-film-audio/ember-original.wav \
  --pcm-offset 24
mkdir -p /tmp/ember-film-captures/live-frames
ffmpeg -i /tmp/ember-film-captures/fullscreen-live.mp4 -vf fps=30 \
  /tmp/ember-film-captures/live-frames/frame-%04d.png
python3 tools/render_promo.py --captures /tmp/ember-film-captures \
  --audio /tmp/ember-film-audio/ember-original.wav \
  --output /tmp/ember-film-output --language ru
```

Repeat the last command with `--language en`. The renderer requires the
Noto Sans regular and bold fonts; it exports 1920×1080, 60 fps, H.264/yuv420p,
AAC 48 kHz stereo, fast-start MP4. Live GTK footage is captured at 30 fps;
editorial moves and transitions are composed at 60 fps. Upload editions stay
below GitHub's 10 MB free-plan attachment limit.

Original media and scripts follow the repository's MIT license. Music service
names and marks belong to their respective owners; Ember is an independent
project.
