# Grunesphism / Грунесфизм

**English** · [Русский](DESIGN.ru.md)

**Gruvbox warmth. Soft relief. Analogue feel.**

Grunesphism is the name we use for Emberbox’s visual language. It combines a Gruvbox palette, restrained neumorphism and details borrowed from small hi-fi instruments. It is a project design vocabulary, not a claim of a separate established design movement.

## Surfaces and colour

| Token | Colour | Role |
| --- | --- | --- |
| Body | `#2c2c29` | Warm olive-charcoal shell |
| Well | `#292925` | Inset lamp housing |
| Recess | `#20221e` | Progress-track depth |
| Primary text | `#fbf1c7` | Warm cream, never bright white |
| Secondary text | `#bdae93` | Quiet labels |
| Amber | `#fabd2f` | Main playback action |
| Orange | `#fe8019` | Progress and discharge glow |

Relief stays shallow: soft directional gradients, a restrained light edge and darker inset wells. There is no large shadow or frame around the outside of the widget. Contrast comes from the materials inside the body.

Artwork may shift the shell by at most nine RGB levels per channel. A 1.4-second transition keeps the tint subtle and avoids sudden changes between tracks.

## Physical details

- The artist room uses a large, uncropped photograph in a narrow gallery mount. Behind it, two soft-focus layers of the same image retain its colours and light: a broad source-coloured glow, a quiet dark field for the name and a faint matte texture. Monochrome portraits retain their original pixels. The static backdrop is composed off the UI thread and cached.
- The mute switch has a smooth metal collar and a rounded lever, with a 250 ms smootherstep movement.
- The volume dial has a ridged edge, warm scale ticks and an indicator that follows its target smoothly.
- Fullscreen uses a larger volume dial and a passive horizontal glass VU instead of a second volume slider. Its amber discharge follows stereo PCM energy on a −60 to 0 dBFS scale, with a quick rise and a soft decay; pause, mute and stale audio return it to rest.
- Transport buttons have visible breathing room, including in mini mode.
- Glass tubes have no feet or simulated sockets. Small highlights describe the glass; the orange glow softly reaches the edge.

## Light comes from sound

Nine frequency bands cover 55 Hz to 11 kHz. The live meter reads the relevant application stream through PipeWire; it does not use the microphone or animate random bars. FFT measurements drive the indicators, and a critically damped response preserves continuous velocity between samples. Light rises promptly and decays more slowly. The tubes use 384 cached vector-rendered states to keep the animation smooth.

The result is **physically inspired**, rather than an exact simulation of gas-discharge physics. Silence and pause bring the lamps gently back to rest.

## Interaction stays quiet

Fullscreen opens with a centred cover; **Lyrics** explicitly enables text lookup and the split layout. Until then, no lyric lookup, line layout or scrolling runs.

The 900 ms entrance uses a prewarmed hardware GL renderer: a rounded shell and cover move over a gradient, then a single cached image of the room reveals its controls. The GTK scene stays unmapped throughout the movement, avoiding costly opacity-zero Cairo groups and per-frame resizing. Only our own widgets are captured, in memory. The background is cached and prepared off the UI thread. Systems without accelerated GL use a short compositor fade; disabling system animations skips the entrance. Esc cancels immediately.

Lyrics and artwork exchange places over 660 ms: one cover travels between the two layouts while the panel appears with a gentle vertical delay. A ready lyric result is included in the cached destination; later results fade in after the movement. Exiting fullscreen reverses the entrance toward the current desktop widget, including Mini. The normal/Mini switch takes 380 ms and blends two cached card images while resizing, without rebuilding live controls on every frame. Hiding or closing clears transition layers.

No dotted focus rectangles or hover captions. Accessible names remain available for assistive technology. Main actions stay visible; miniature controls remain separated. Compact mode preserves the character of the instrument rather than reducing it to a generic transport bar.

## Original preview media

`assets/demo-cover.svg` and `assets/demo-scene.svg` are original geometric artwork created for this project. Documentation previews show the actual GTK widgets with fixture metadata and measured, generated PCM audio. They do not reveal a user’s Spotify picks or YouTube history.
