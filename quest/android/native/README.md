# Android playback host (in development)

The immersive PWA remains the renderer. This host owns service sign-in and web
playback on the headset, with private app cookies and a loopback metadata/control
bridge. It must be verified on actual Quest firmware before it can replace the
Linux companion. Do not advertise unverified codec/DRM capability as playback.

No passwords, cookies or DRM material cross the bridge. Source adapters are
copied from Ember's existing website adapters during packaging. The headset's
system WebView and platform CDM perform protected playback.
