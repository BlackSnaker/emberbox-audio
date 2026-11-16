// Official Meta immersive PWA packaging. Signing keys never belong in the repo.
const {
  TwaManifest,
  TwaGenerator,
  ConsoleLog,
} = require("@meta-quest/bubblewrap-core");
const fs = require("node:fs/promises");
const path = require("node:path");
async function main() {
  const [origin, output] = process.argv.slice(2);
  if (
    !origin ||
    new URL(origin).protocol !== "https:" ||
    new URL(origin).pathname !== "/" ||
    !output
  )
    throw Error(
      "Usage: npm run generate -- https://your-app-origin.example /absolute/build/folder",
    );
  const target = path.resolve(output);
  const m = new TwaManifest({
    packageId: "io.emberbox.quest",
    host: new URL(origin).hostname,
    name: "Ember Quest",
    launcherName: "Ember Quest",
    startUrl: "/",
    display: "standalone",
    themeColor: "#101818",
    navigationColor: "#101818",
    backgroundColor: "#101818",
    iconUrl: origin + "icon-512.png",
    webManifestUrl: origin + "manifest.webmanifest",
    splashScreenFadeOutDuration: 350,
    appVersion: "0.2.0",
    appVersionCode: 2,
    isMetaQuest: true,
    horizonOSAppMode: "immersive",
    orientation: "landscape",
    enableNotifications: false,
    enableSiteSettingsShortcut: false,
    minSdkVersion: 29,
    shortcuts: [],
    features: {},
    fingerprints: [],
  });
  await fs.mkdir(target, { recursive: true });
  await new TwaGenerator().createTwaProject(
    target,
    m,
    new ConsoleLog("Ember Quest"),
  );
  for (const file of ["build.gradle", "app/build.gradle"]) {
    const p = path.join(target, file);
    const s = await fs.readFile(p, "utf8");
    await fs.writeFile(p, s.replaceAll("jcenter()", "mavenCentral()"));
  }
  const nativeDirectory = path.join(__dirname, "native");
  const javaDirectory = path.join(
    target,
    "app/src/main/java/io/emberbox/quest",
  );
  for (const file of [
    "EmberRuntime.java",
    "PlaybackService.java",
    "HostActivity.java",
  ]) {
    let text = await fs.readFile(path.join(nativeDirectory, file), "utf8");
    text = text.replace(
      'ORIGIN="https://blacksnaker.github.io"',
      "ORIGIN=" + JSON.stringify(origin.replace(/\/$/, "")),
    );
    await fs.writeFile(path.join(javaDirectory, file), text);
  }
  const launcher = path.join(javaDirectory, "LauncherActivity.java");
  let launcherSource = await fs.readFile(launcher, "utf8");
  launcherSource = launcherSource.replace(
    "return uri;",
    `if(uri.getFragment()!=null&&uri.getFragment().contains("bridge=pc"))return uri;
        return Uri.parse(EmberRuntime.ensure(this).roomUrl());`,
  );
  await fs.writeFile(launcher, launcherSource);
  const manifestPath = path.join(target, "app/src/main/AndroidManifest.xml");
  let manifestSource = await fs.readFile(manifestPath, "utf8");
  manifestSource = manifestSource.replace(
    "<application",
    `<uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK"/>
    <application`,
  );
  manifestSource = manifestSource.replace(
    "</application>",
    `<activity android:name=".HostActivity" android:exported="true" android:configChanges="orientation|screenSize" android:theme="@android:style/Theme.Material.NoActionBar">
      <intent-filter><action android:name="android.intent.action.VIEW"/><category android:name="android.intent.category.DEFAULT"/><category android:name="android.intent.category.BROWSABLE"/><data android:scheme="emberquest" android:host="source"/></intent-filter>
    </activity>
    <service android:name=".PlaybackService" android:exported="false" android:foregroundServiceType="mediaPlayback"/>
    </application>`,
  );
  manifestSource = manifestSource.replace(
    'android:allowBackup="true"',
    'android:allowBackup="false"',
  );
  await fs.writeFile(manifestPath, manifestSource);
  const assets = path.join(target, "app/src/main/assets");
  await fs.mkdir(assets, { recursive: true });
  const adapterDirectory = path.resolve(__dirname, "../../src/apple_web_host");
  const favorite = await fs.readFile(
    path.join(adapterDirectory, "favorite_dom.js"),
    "utf8",
  );
  for (const [input, output] of [
    ["page.js", "apple.js"],
    ["spotify.js", "spotify.js"],
    ["yandex.js", "yandex.js"],
  ])
    await fs.writeFile(
      path.join(assets, output),
      favorite +
        "\n" +
        (await fs.readFile(path.join(adapterDirectory, input), "utf8")),
    );
  await fs.copyFile(
    path.join(nativeDirectory, "youtube.js"),
    path.join(assets, "youtube.js"),
  );
  await fs.writeFile(
    path.join(target, "twa-manifest.json"),
    JSON.stringify(m.toJson(), null, 2),
  );
  console.log(
    "Generated immersive Quest Android project. Build with JDK 17 + Android SDK 32.",
  );
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
