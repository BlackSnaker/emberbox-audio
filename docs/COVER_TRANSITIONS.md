# The next wave

**English** · [Русский](COVER_TRANSITIONS.ru.md)

Fullscreen artwork welcomes the next track with a soft water ripple.
Concentric waves gently refract the photograph and catch warm grazing light.
Once playback and the incoming artwork are ready, the new image unfolds from
the wave's centre. Tracks sharing an album cover still receive a transition.

The incoming image unfolds over 1.35 seconds through a broad translucent edge.
Gentle optical movement settles as the warm reflection fades, leaving the
original colours and sharpness. Timing follows presentation frames to avoid
speed jitter from uneven UI event delivery.

The visual starts immediately for queue selections and fullscreen transport
buttons. Automatic changes follow the recording's identity rather than its
image URL. Longer preparation leaves quiet, occasional ripples. Errors,
cancellation and rapid selections dismiss superseded transitions; late artwork
responses cannot restore an older selection.

**Audio never waits for the animation.** The effect adds no playback delay and
does not alter the format, quality, queue or EmberFlow mixing. Native Apple
playback uses the decoder's confirmed state: receiving metadata or artwork
alone does not mean the audio has started.

The GPU processes only the cover area, reusing two textures. No per-frame window
captures, CPU image processing, extra music-service requests or neural models
are used. Frame callbacks stop after settling or hiding; artwork references
are released. Motion artwork pauses during the transition. Systems without
hardware GL use a soft fade; the desktop's reduced-motion setting bypasses
the animation.

Checks cover real GL output, rounded alpha, 1×/2× scaling, delayed Apple readiness,
loading errors, source changes and resource cleanup. Playback checks do not
save audio or account data.
