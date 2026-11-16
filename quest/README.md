# Ember · Quest

**English** · [Русский](README.ru.md)

An early immersive WebXR port for Meta Quest 3S, running in Quest Browser.
It includes a three-dimensional listening room, physical controls, audio-reactive
tubes, controller rays/hand-pinch input and four room materials. It also has a signed, installable **immersive PWA APK** using the official Meta runtime. It is **not a standalone streaming client or a complete desktop replacement**.

The optional Linux companion reuses Ember's connected sources, catalogue,
playback, queue, favourites, text DJ and lyrics. Streaming-service sign-in and
processing remain on the PC. Credentials, cookies and DRM keys are not exported.
The headset receives stereo float32 PCM at 48 kHz after an explicit audio action;
this is not a claim of direct Atmos or Hi-Res playback on Quest. Local browser
file playback is available independently of streaming services.

Headset voice capture, the full mashup editor and in-app mixed reality remain pending. Karaoke controls use PC processing; native service playback is experimental and still under account testing. See the
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

## Experimental native service host

The Android package now contains a system WebView playback host, a private loopback metadata/control bridge, and a foreground media session. It reuses the existing website adapters. A genuine Apple Music sign-in window and platform Widevine support have been verified on Quest 3S; full subscription playback is still awaiting the user sign-in check. CDM availability alone is not proof of playback. Cookies and DRM state stay in the provider WebView. No service session is copied from the PC.

`tools/quest.py open-app` opens the native route; `open-companion-app` explicitly uses the Linux companion. Native DJ, neural karaoke, mashups, EmberFlow and direct Atmos/Hi-Res are not ported yet. YouTube background playback restrictions are not bypassed. There is no test oscillator in the product: Play without a playable source remains silent.
