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
    appVersion: "0.1.0",
    appVersionCode: 1,
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
