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

- The mute switch has a smooth metal collar and a rounded lever, with a 250 ms smootherstep movement.
- The volume dial has a ridged edge, warm scale ticks and an indicator that follows its target smoothly.
- Transport buttons have visible breathing room, including in mini mode.
- Glass tubes have no feet or simulated sockets. Small highlights describe the glass; the orange glow softly reaches the edge.

## Light comes from sound

Nine frequency bands cover 55 Hz to 11 kHz. The live meter reads the relevant application stream through PipeWire; it does not use the microphone or animate random bars. FFT measurements drive the indicators, and a critically damped response preserves continuous velocity between samples. Light rises promptly and decays more slowly. The tubes use 384 cached vector-rendered states to keep the animation smooth.

The result is **physically inspired**, rather than an exact simulation of gas-discharge physics. Silence and pause bring the lamps gently back to rest.

## Interaction stays quiet

No dotted focus rectangles or hover captions. Accessible names remain available for assistive technology. Main actions stay visible; miniature controls remain separated. Compact mode preserves the character of the instrument rather than reducing it to a generic transport bar.

## Original preview media

`assets/demo-cover.svg` and `assets/demo-scene.svg` are original geometric artwork created for this project. Documentation previews show the actual GTK widgets with fixture metadata and measured, generated PCM audio. They do not reveal a user’s Spotify picks or YouTube history.
