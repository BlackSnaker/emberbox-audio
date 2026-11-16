# Ember · Quest

**English** · [Русский](README.ru.md)

An early immersive WebXR port for Meta Quest 3S, running in Quest Browser.
It includes a three-dimensional listening room, physical controls, audio-reactive
tubes, controller rays/hand-pinch input and four room materials. It is **not yet
a standalone Android APK or a complete desktop replacement**.

The optional Linux companion reuses Ember's connected sources, catalogue,
playback, queue, favourites, text DJ and lyrics. Streaming-service sign-in and
processing remain on the PC. Credentials, cookies and DRM keys are not exported.
The headset receives stereo float32 PCM at 48 kHz after an explicit audio action;
this is not a claim of direct Atmos or Hi-Res playback on Quest. Local browser
file playback is available independently of streaming services.

Headset voice capture, the full mashup editor, XR karaoke controls, in-app mixed
reality and standalone streaming-service integrations are still pending. See the
[feature matrix](README.ru.md) for precise boundaries.

## Run

With the installed Ember desktop player running, Node.js/npm and Quest USB
debugging enabled:

```sh
python3 tools/quest.py install-companion
python3 tools/quest.py open
```

The setup preserves a private backup and restarts the desktop interface. Existing
native playback engines remain installed. The companion binds only to loopback;
ADB reverse transports the local connection over USB. Pairing is private to the
OS login session. Do not share the paired URL. Press **Войти в комнату** inside the
headset, then explicitly enable PC audio. No browser security flags are changed.
Disable with `python3 tools/quest.py disable`.

## Checks

```sh
npm --prefix quest ci --ignore-scripts
npm --prefix quest run build
npm --prefix quest test
python3 tests/test_quest_bridge.py
```

`npm --prefix quest run dev` provides an unpaired desktop preview. XR rendering
uses the headset animation loop, instancing and cached text panels. 90 Hz is
requested when the runtime supports it; actual immersive performance and hand
interactions must be checked on device. Windowed FPS is not immersive FPS.

[Meta WebXR](https://developers.meta.com/vr/documentation/web/webxr-overview/)
· [Three.js](https://threejs.org/docs/)

## Installable Quest app

`android/generate.cjs` generates an immersive Android project using Meta Bubblewrap 1.24.1. It needs a hosted HTTPS origin, Digital Asset Links, JDK 17 and Android SDK 32. Keep your signing keystore and passwords outside the repository. The package uses Quest Browser as its runtime, with its own library icon. No independent service authentication or DRM engine is bundled.

The hosted app connects only to the local USB companion. Set `EMBERBOX_QUEST_ORIGIN` to its exact HTTPS origin; pairing remains mandatory. Local-network permission may be requested by the headset browser. Pairing is stored in app storage and can be removed with Forget pairing.

Karaoke controls now support AI/stereo vocal reduction and amount; processing and model installation remain on the PC. Headset voice and the mashup editor still need XR adaptation. Offline startup and the latest APK need a device check. An earlier WebXR build measured 90 FPS / 44 draw calls / 17,628 triangles on Quest 3S; this is not a measurement of the revised room.
