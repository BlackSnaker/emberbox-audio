import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EmberClient, initialState } from "./client.js";
import { AudioEngine } from "./audio.js";
import { ListeningRoom } from "./room.js";
import { decodeArtwork, artworkPalette } from "./artwork.js";
import { volumeFromDrag, pageStart, fitLines } from "./interaction.js";
import "./style.css";

const app = document.querySelector("#app");
app.innerHTML = `<div id="hud"><strong>EMBER</strong><span id="status">Комната прослушивания · Quest</span></div><div id="error"></div><div id="controls"><button id="enter" disabled>Проверяю WebXR…</button><button id="sound">Звук Ember с ПК</button><label class="file-label">Открыть аудиофайл<input id="file" type="file" accept="audio/*"></label><button id="theme">Следующая тема</button><button id="home">Вернуть пульт</button></div><div id="hint">Мышь: обзор комнаты, колёсико: расстояние.<br>В шлеме: луч контроллера или щипок рукой.<br>Пульт остаётся на месте при повороте головы.</div><form id="query"><input aria-label="Музыкальное пожелание"><button>Найти</button></form>`;
const $ = (s) => document.querySelector(s),
  client = new EmberClient(),
  audio = new AudioEngine();
let autoSoundStarted = false;
let localActive = false,
  localFiles = [],
  localIndex = 0;
let state = { ...initialState },
  page = "Слушать",
  items = [],
  heading = "Твоя коллекция",
  notice = "",
  busy = false,
  query = "",
  keyboard = false,
  queryKind = "search",
  themeIndex = Math.max(
    0,
    Math.min(3, Number(localStorage.getItem("ember-quest-theme")) || 0),
  ),
  favorite = false,
  listPage = 0,
  browseHistory = [],
  browseNext = null,
  lastBrowse = null,
  story = "",
  storyPage = 0,
  boardDirty = true,
  lastArt = "",
  imageGeneration = 0,
  lastSignature = "",
  quality = "Авто",
  xrSession = null;
const themes = [
  "Тёплая ночь",
  "Зеркальный зал",
  "Тёплое Рождество",
  "Классическая",
];
const scene = new THREE.Scene();
scene.background = new THREE.Color("#101818");
scene.fog = new THREE.FogExp2("#101818", 0.045);
const camera = new THREE.PerspectiveCamera(
  55,
  innerWidth / innerHeight,
  0.05,
  50,
);
camera.position.set(0, 1.7, 1.8);
const renderer = new THREE.WebGLRenderer({
  antialias: true,
  powerPreference: "high-performance",
});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.35));
renderer.xr.enabled = true;
renderer.xr.setReferenceSpaceType("local-floor");
renderer.xr.setFoveation(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;
app.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 1.65, -1.7);
controls.enableDamping = true;
controls.minDistance = 0.9;
controls.maxDistance = 6;
controls.maxPolarAngle = Math.PI * 0.72;
const environment = new RoomEnvironment();
const pmrem = new THREE.PMREMGenerator(renderer);
const env = pmrem.fromScene(environment, 0.06);
scene.environment = env.texture;
scene.environmentIntensity = 0.28;
environment.dispose();
pmrem.dispose();
scene.add(new THREE.HemisphereLight("#e4d6b2", "#0c1717", 0.8));
const key = new THREE.DirectionalLight("#ffe2aa", 1.25);
key.position.set(-3, 5, 2);
scene.add(key);
const rim = new THREE.DirectionalLight("#9dc8df", 0.65);
rim.position.set(4, 2, -4);
scene.add(rim);
const ink = new THREE.MeshStandardMaterial({
  color: "#252c2b",
  roughness: 0.62,
  metalness: 0.18,
  envMapIntensity: 0.25,
});
const brass = new THREE.MeshStandardMaterial({
  color: "#847455",
  roughness: 0.55,
  metalness: 0.55,
});
const glass = new THREE.MeshPhysicalMaterial({
  color: "#bcd4d2",
  metalness: 0.28,
  roughness: 0.18,
  transparent: true,
  opacity: 0.17,
  clearcoat: 1,
  depthWrite: false,
});
const amber = new THREE.MeshStandardMaterial({
  color: "#d1a454",
  metalness: 0.5,
  roughness: 0.25,
  emissive: "#5b2b04",
  emissiveIntensity: 0.18,
});
const timberCanvas = document.createElement("canvas");
timberCanvas.width = 1024;
timberCanvas.height = 1024;
const timber = timberCanvas.getContext("2d");
let grainSeed = 91;
const rand = () => {
  grainSeed = (1664525 * grainSeed + 1013904223) >>> 0;
  return grainSeed / 4294967296;
};
for (let row = 0; row < 12; row++) {
  const y = (row * 1024) / 12,
    h = 1024 / 12;
  for (let col = -1; col < 4; col++) {
    const x = col * 340 + (row % 2) * 170,
      v = Math.floor(rand() * 6);
    timber.fillStyle = `rgb(${34 + v},${36 + v},${36 + v})`;
    timber.fillRect(x, y + 1, 338, h - 2);
    timber.fillStyle = "#090d1060";
    timber.fillRect(x, y, 340, 1);
    timber.fillRect(x, y, 1, h);
    for (let g = 0; g < 55; g++) {
      timber.strokeStyle = g % 2 ? "#a08d6710" : "#05090c24";
      timber.lineWidth = 0.3 + rand();
      timber.beginPath();
      const yy = y + rand() * h;
      timber.moveTo(x, yy);
      timber.bezierCurveTo(
        x + 100,
        yy - 3 + rand() * 6,
        x + 220,
        yy - 2 + rand() * 4,
        x + 338,
        yy,
      );
      timber.stroke();
    }
  }
}
const timberTexture = new THREE.CanvasTexture(timberCanvas);
timberTexture.colorSpace = THREE.SRGBColorSpace;
timberTexture.wrapS = timberTexture.wrapT = THREE.RepeatWrapping;
timberTexture.repeat.set(8, 8);
timberTexture.anisotropy = Math.min(
  4,
  renderer.capabilities.getMaxAnisotropy(),
);
const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(28, 28),
  new THREE.MeshStandardMaterial({
    map: timberTexture,
    color: "#d0c6ae",
    roughness: 0.88,
    metalness: 0,
    envMapIntensity: 0.12,
  }),
);
floor.rotation.x = -Math.PI / 2;
scene.add(floor);
const skirting = new THREE.Mesh(
  new THREE.CylinderGeometry(6.03, 6.03, 0.28, 128, 1, true),
  new THREE.MeshStandardMaterial({
    color: "#1d2427",
    roughness: 0.8,
    side: THREE.BackSide,
  }),
);
skirting.position.y = 0.14;
scene.add(skirting);

const rug = new THREE.Mesh(
  new THREE.RingGeometry(1.3, 3.4, 96),
  new THREE.MeshBasicMaterial({
    color: "#24303c",
    transparent: true,
    opacity: 0.2,
    side: THREE.DoubleSide,
  }),
);
rug.rotation.x = -Math.PI / 2;
rug.position.y = 0.004;
scene.add(rug);
const listeningRoom = new ListeningRoom(scene);
const deck = new THREE.Group();
scene.add(deck);
function box(w, h, d, r, material) {
  return new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, r), material);
}
// A thin glass plate needs a rounded silhouette independent of its depth.
// RoundedBoxGeometry clamps radius to depth/2 and makes shallow UI look square.
function slab(w, h, d, r, material) {
  r = Math.min(r, w / 2, h / 2);
  const shape = new THREE.Shape();
  shape.moveTo(r, 0);
  shape.lineTo(w - r, 0);
  shape.quadraticCurveTo(w, 0, w, r);
  shape.lineTo(w, h - r);
  shape.quadraticCurveTo(w, h, w - r, h);
  shape.lineTo(r, h);
  shape.quadraticCurveTo(0, h, 0, h - r);
  shape.lineTo(0, r);
  shape.quadraticCurveTo(0, 0, r, 0);
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: d,
    bevelEnabled: true,
    bevelSegments: 3,
    steps: 1,
    bevelSize: 0.002,
    bevelThickness: 0.002,
    curveSegments: 12,
  });
  geometry.translate(-w / 2, -h / 2, -d / 2);
  return new THREE.Mesh(geometry, material);
}
const chassis = slab(1.9, 0.3, 0.13, 0.07, ink);
chassis.position.set(0, 0.7, -1.45);
chassis.rotation.x = -0.32;
deck.add(chassis);
const caseRim = new THREE.MeshStandardMaterial({
  color: "#4c504a",
  roughness: 0.58,
  metalness: 0.5,
});
const trim = slab(1.92, 0.32, 0.025, 0.07, caseRim);
trim.position.copy(chassis.position);
trim.position.z += 0.014;
trim.rotation.copy(chassis.rotation);
deck.add(trim);
const face = slab(1.89, 0.29, 0.022, 0.07, glass);
face.material = glass.clone();
face.material.opacity = 0.035;
face.material.clearcoat = 0.35;
face.position.copy(chassis.position);
face.position.z += 0.085;
face.rotation.copy(chassis.rotation);
deck.add(face);
const boardCanvas = document.createElement("canvas");
boardCanvas.width = 1792;
boardCanvas.height = 1024;
let ctx = boardCanvas.getContext("2d");
const boardContext = ctx;
const boardTexture = new THREE.CanvasTexture(boardCanvas);
boardTexture.colorSpace = THREE.SRGBColorSpace;
boardTexture.minFilter = THREE.LinearFilter;
boardTexture.generateMipmaps = false;
const board = new THREE.Mesh(
  new THREE.PlaneGeometry(2.2, 1.257),
  new THREE.MeshBasicMaterial({
    map: boardTexture,
    transparent: true,
    toneMapped: false,
    depthWrite: false,
  }),
);
board.position.set(0, 1.55, -2.4);
board.scale.setScalar(1.08);
deck.add(board);
const artGroup = new THREE.Group();
artGroup.position.set(0, 1.85, -2.6);
artGroup.scale.setScalar(0.8);
deck.add(artGroup);
const mount = slab(1.55, 1.55, 0.075, 0.06, ink);
artGroup.add(mount);
const artEdge = slab(1.58, 1.58, 0.024, 0.06, caseRim);
artEdge.position.z = -0.01;
artGroup.add(artEdge);
const artMaterial = new THREE.MeshBasicMaterial({ toneMapped: false });
const art = new THREE.Mesh(new THREE.PlaneGeometry(1.46, 1.46), artMaterial);
art.position.z = 0.044;
artGroup.add(art);
fetch("/demo-cover.png")
  .then((r) => r.blob())
  .then(decodeArtwork)
  .then((bitmap) => {
    if (imageGeneration) {
      bitmap.close();
      return;
    }
    const texture = new THREE.CanvasTexture(bitmap);
    texture.colorSpace = THREE.SRGBColorSpace;
    artMaterial.map = texture;
    artMaterial.needsUpdate = true;
    applyCoverPalette(bitmap);
  })
  .catch(() => {});

const progressBase = new THREE.Mesh(
  new THREE.PlaneGeometry(1.68, 0.035),
  new THREE.MeshBasicMaterial({
    color: "#53605a",
    transparent: true,
    opacity: 0.4,
  }),
);
progressBase.position.set(0, 0.91, -1.7);
progressBase.userData.seek = true;
deck.add(progressBase);
const progressFill = new THREE.Mesh(
  new THREE.PlaneGeometry(1, 0.009),
  new THREE.MeshBasicMaterial({ color: "#dcb36d", toneMapped: false }),
);
progressFill.position.z = 0.002;
progressBase.add(progressFill);
const interact = [board, progressBase];
let regions = [];
const buttons = [];
function drawKeyIcon(c, label, color) {
  c.clearRect(0, 0, 256, 128);
  c.fillStyle = color;
  const triangle = (x, y, w, h, sign = 1) => {
    c.beginPath();
    c.moveTo(x, y - h / 2);
    c.lineTo(x + sign * w, y);
    c.lineTo(x, y + h / 2);
    c.closePath();
    c.fill();
  };
  if (label === "Ⅱ") {
    c.fillRect(109, 42, 11, 44);
    c.fillRect(137, 42, 11, 44);
  } else if (label === "▶") triangle(113, 64, 40, 44);
  else if (label === "⏮") {
    c.fillRect(100, 46, 7, 36);
    triangle(145, 64, 32, 36, -1);
  } else {
    triangle(109, 64, 32, 36);
    c.fillRect(146, 46, 7, 36);
  }
}
function physical(label, x, action, material = ink) {
  const radius = material === amber ? 0.105 : 0.085;
  const geometry = new THREE.CylinderGeometry(
    radius,
    radius + 0.004,
    0.035,
    64,
  );
  geometry.rotateX(Math.PI / 2);
  const key = new THREE.Mesh(geometry, material);
  key.position.set(x, 0.735, -1.342);
  const seatGeometry = new THREE.CylinderGeometry(
    radius + 0.013,
    radius + 0.016,
    0.02,
    64,
  );
  seatGeometry.rotateX(Math.PI / 2);
  const seat = new THREE.Mesh(seatGeometry, caseRim);
  seat.position.z = -0.021;
  key.add(seat);
  key.rotation.x = -0.34;
  key.userData.action = action;
  key.userData.homeZ = key.position.z;
  deck.add(key);
  interact.push(key);
  buttons.push(key);
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 128;
  const c = canvas.getContext("2d");
  drawKeyIcon(c, label, material === amber ? "#252a22" : "#ead9b8");
  const t = new THREE.CanvasTexture(canvas);
  t.colorSpace = THREE.SRGBColorSpace;
  const letters = new THREE.Mesh(
    new THREE.PlaneGeometry(0.19, 0.095),
    new THREE.MeshBasicMaterial({
      map: t,
      transparent: true,
      toneMapped: false,
      depthWrite: false,
    }),
  );
  letters.position.z = 0.021;
  key.add(letters);
  key.userData.canvas = canvas;
  key.userData.texture = t;
  key.userData.label = label;
  return key;
}
physical("⏮", -0.28, () => action("previous"));
const playKey = physical("▶", 0, () => action("toggle"), amber);
physical("⏭", 0.28, () => action("next"));
const knob = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.095, 0.07, 40), [
  brass,
  ink,
  brass,
]);
knob.rotation.x = Math.PI / 2 - 0.3;
knob.position.set(0.72, 0.735, -1.342);
deck.add(knob);
knob.userData.knob = true;
interact.push(knob);
const indicator = new THREE.Mesh(
  new THREE.BoxGeometry(0.008, 0.004, 0.057),
  new THREE.MeshBasicMaterial({ color: "#ffdd87" }),
);
indicator.position.set(0, 0.038, -0.045);
knob.add(indicator);
const grip = new THREE.InstancedMesh(
  new THREE.BoxGeometry(0.003, 0.052, 0.005),
  brass,
  40,
);
for (let i = 0; i < 40; i++) {
  const a = (i / 40) * Math.PI * 2;
  const transform = new THREE.Object3D();
  transform.position.set(Math.sin(a) * 0.092, 0, Math.cos(a) * 0.092);
  transform.rotation.y = a;
  transform.updateMatrix();
  grip.setMatrixAt(i, transform.matrix);
}
knob.add(grip);
const tubes = new THREE.Group();
tubes.position.set(-0.83, 0.735, -1.342);
tubes.rotation.x = -0.3;
deck.add(tubes);
const glassTubes = new THREE.InstancedMesh(
  new THREE.CapsuleGeometry(0.021, 0.11, 3, 10),
  new THREE.MeshPhysicalMaterial({
    color: "#987346",
    roughness: 0.18,
    metalness: 0.0,
    transparent: true,
    opacity: 0.12,
    clearcoat: 1,
    envMapIntensity: 0.15,
    depthWrite: false,
  }),
  9,
);
tubes.add(glassTubes);
const filamentMaterial = new THREE.MeshBasicMaterial({ color: "#ff9a32" });
const filaments = new THREE.InstancedMesh(
  new THREE.CapsuleGeometry(0.008, 0.1, 2, 8),
  filamentMaterial,
  9,
);
filaments.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
tubes.add(filaments);
const hotCores = new THREE.InstancedMesh(
  new THREE.CapsuleGeometry(0.0022, 0.1, 2, 6),
  new THREE.MeshBasicMaterial({ color: "#ffe2a5", toneMapped: false }),
  9,
);
hotCores.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
tubes.add(hotCores);
const tubeCanvas = document.createElement("canvas");
tubeCanvas.width = 64;
tubeCanvas.height = 128;
const tubeContext = tubeCanvas.getContext("2d");
tubeContext.scale(1, 2);
const glowGradient = tubeContext.createRadialGradient(32, 32, 2, 32, 32, 32);
glowGradient.addColorStop(0, "#ffa12b9c");
glowGradient.addColorStop(0.28, "#ff761d50");
glowGradient.addColorStop(0.7, "#ff640912");
glowGradient.addColorStop(1, "#ff640900");
tubeContext.fillStyle = glowGradient;
tubeContext.fillRect(0, 0, 64, 64);
const tubeTexture = new THREE.CanvasTexture(tubeCanvas);
tubeTexture.colorSpace = THREE.SRGBColorSpace;
const tubeGlow = new THREE.InstancedMesh(
  new THREE.PlaneGeometry(0.088, 0.21),
  new THREE.MeshBasicMaterial({
    map: tubeTexture,
    transparent: true,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
    depthWrite: false,
  }),
  9,
);
tubes.add(tubeGlow);
const tubeColor = new THREE.Color();
const dummy = new THREE.Object3D();
for (let i = 0; i < 9; i++) {
  dummy.position.set(i * 0.052, 0, 0);
  dummy.scale.set(1, 1, 1);
  dummy.updateMatrix();
  glassTubes.setMatrixAt(i, dummy.matrix);
  dummy.position.z = 0.016;
  dummy.updateMatrix();
  tubeGlow.setMatrixAt(i, dummy.matrix);
  tubeGlow.setColorAt(i, tubeColor.setScalar(0));
}
const mirrors = new THREE.InstancedMesh(
  new THREE.BoxGeometry(0.202, 0.202, 0.014),
  new THREE.MeshStandardMaterial({
    color: "#9ba6a9",
    roughness: 0.11,
    metalness: 0.98,
    envMapIntensity: 2.2,
  }),
  3060,
);
const facetColor = new THREE.Color();
for (let i = 0; i < 3060; i++) {
  const col = i % 180,
    row = Math.floor(i / 180),
    a = (col / 180) * Math.PI * 2;
  dummy.position.set(
    Math.sin(a) * 6.15,
    0.105 + row * 0.21,
    -Math.cos(a) * 6.15,
  );
  dummy.rotation.set(0.03 * Math.sin(i * 1.3), -a, 0.04 * Math.sin(i));
  dummy.scale.set(1, 1, 1);
  dummy.updateMatrix();
  mirrors.setMatrixAt(i, dummy.matrix);
  facetColor.setScalar(0.64 + ((i * 17) % 13) / 42);
  mirrors.setColorAt(i, facetColor);
}
scene.add(mirrors);
const mirrorTime = { value: 0 },
  mirrorEnergy = { value: 0 };
const mirrorPalette = [
  new THREE.Color("#32505c"),
  new THREE.Color("#476f79"),
  new THREE.Color("#62536e"),
];
mirrors.material.onBeforeCompile = (shader) => {
  shader.uniforms.emberTime = mirrorTime;
  shader.uniforms.emberEnergy = mirrorEnergy;
  for (let i = 0; i < 3; i++)
    shader.uniforms["emberColour" + i] = { value: mirrorPalette[i] };
  shader.vertexShader =
    "varying vec3 emberFacet;\n" +
    shader.vertexShader.replace(
      "#include <begin_vertex>",
      "#include <begin_vertex>\nemberFacet=(instanceMatrix*vec4(position,1.0)).xyz;",
    );
  shader.fragmentShader =
    "varying vec3 emberFacet;uniform float emberTime;uniform float emberEnergy;uniform vec3 emberColour0;uniform vec3 emberColour1;uniform vec3 emberColour2;\n" +
    shader.fragmentShader.replace(
      "#include <emissivemap_fragment>",
      `#include <emissivemap_fragment>
  float slide=.5+.5*sin(emberFacet.x*.48+emberFacet.z*.35+emberFacet.y*.8-emberTime*.14);
  vec3 light=mix(mix(emberColour0,emberColour1,slide),emberColour2,.25+.25*sin(emberFacet.y+emberTime*.11));
  float glint=pow(.5+.5*sin(emberFacet.x*.9-emberTime*.2+emberFacet.y*.7),8.0);
  totalEmissiveRadiance+=light*(.012+glint*(.08+emberEnergy*.15));`,
    );
};

const garland = new THREE.InstancedMesh(
  new THREE.SphereGeometry(0.026, 7, 5),
  new THREE.MeshBasicMaterial({ color: "#f0ba65" }),
  48,
);
for (let i = 0; i < 48; i++) {
  const a = (i / 48) * Math.PI * 2;
  dummy.position.set(
    Math.sin(a) * 3.8,
    2.8 + Math.sin(a * 8) * 0.12,
    -Math.cos(a) * 3.8,
  );
  dummy.rotation.set(0, 0, 0);
  dummy.updateMatrix();
  garland.setMatrixAt(i, dummy.matrix);
}
scene.add(garland);
function applyTheme() {
  localStorage.setItem("ember-quest-theme", String(themeIndex));
  mirrors.visible = themeIndex === 1;
  garland.visible = themeIndex === 2;
  scene.background.set(
    themeIndex === 2 ? "#10221c" : themeIndex === 3 ? "#1a241d" : "#10171b",
  );
  scene.fog.color.copy(scene.background);
  ink.color.set(
    themeIndex === 2 ? "#182620" : themeIndex === 3 ? "#23251f" : "#151a1f",
  );
  amber.color.set(themeIndex === 2 ? "#a44b40" : "#d1a454");
  boardDirty = true;
}
applyTheme();
const consoleGroup = new THREE.Group();
for (const object of [chassis, trim, face, ...buttons, knob, tubes]) {
  deck.remove(object);
  consoleGroup.add(object);
}
consoleGroup.position.z = -0.35;
deck.add(consoleGroup);
const nameCanvas = document.createElement("canvas");
nameCanvas.width = 512;
nameCanvas.height = 96;
const nameContext = nameCanvas.getContext("2d");
nameContext.fillStyle = "#c9bd9b";
nameContext.font = "500 30px system-ui";
nameContext.textAlign = "center";
nameContext.fillText("E M B E R", 256, 55);
const nameTexture = new THREE.CanvasTexture(nameCanvas);
nameTexture.colorSpace = THREE.SRGBColorSpace;
const namePlate = new THREE.Mesh(
  new THREE.PlaneGeometry(0.3, 0.056),
  new THREE.MeshBasicMaterial({
    map: nameTexture,
    transparent: true,
    toneMapped: false,
    depthWrite: false,
  }),
);
namePlate.position.set(0, 0.603, -1.34);
namePlate.rotation.x = -0.32;
consoleGroup.add(namePlate);

const colorTarget = new THREE.Color("#b89e65");
const lightColor = new THREE.Color();
let lastPalette = null;
async function artwork(url) {
  const generation = ++imageGeneration;
  try {
    const bitmap = await client.image(url);
    if (!bitmap || generation !== imageGeneration) {
      bitmap?.close();
      return;
    }
    const texture = new THREE.CanvasTexture(bitmap);
    texture.colorSpace = THREE.SRGBColorSpace;
    const previous = artMaterial.map;
    artMaterial.map = texture;
    artMaterial.needsUpdate = true;
    previous?.dispose();
    previous?.image?.close?.();
    applyCoverPalette(bitmap);
    lastPalette = bitmap;
  } catch {}
}
function applyCoverPalette(bitmap) {
  const c = document.createElement("canvas");
  c.width = c.height = 24;
  const cc = c.getContext("2d");
  cc.drawImage(bitmap, 0, 0, 24, 24);
  const rgba = cc.getImageData(0, 0, 24, 24).data;
  const palette = artworkPalette(rgba);
  palette.forEach((rgb, i) =>
    mirrorPalette[i].setRGB(...rgb, THREE.SRGBColorSpace),
  );
  colorTarget.copy(mirrorPalette[0]);
}
function round(x, y, w, h, r = 22, fill = "#24302c") {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}
function text(value, x, y, size = 30, color = "#eee3c8", max = 1600) {
  ctx.font = `${size >= 40 ? "600" : "400"} ${size}px system-ui,sans-serif`;
  ctx.fillStyle = color;
  const words = String(value || "").split(/\s+/);
  let line = "",
    yy = y;
  for (const word of words) {
    if (ctx.measureText(line + word).width > max && line) {
      ctx.fillText(line, x, yy);
      yy += size * 1.27;
      line = "";
    }
    line += word + " ";
  }
  ctx.fillText(line, x, yy);
  return yy;
}
function wrapLines(value, size, width) {
  ctx.font = `${size}px system-ui,sans-serif`;
  const lines = [];
  for (const paragraph of String(value).split("\n")) {
    let line = "";
    for (const word of paragraph.split(/\s+/)) {
      if (ctx.measureText(line + word).width > width && line) {
        lines.push(line);
        line = "";
      }
      line += word + " ";
    }
    lines.push(line);
  }
  return lines;
}
function button(label, x, y, w, h, action, selected = false) {
  round(x, y, w, h, Math.min(22, h / 2), selected ? "#45473c" : "#20292f");
  if (!selected) {
    const sheen = ctx.createLinearGradient(x, y, x, y + h);
    sheen.addColorStop(0, "#e2e8dd10");
    sheen.addColorStop(0.45, "#e2e8dd00");
    sheen.addColorStop(1, "#00000012");
    ctx.fillStyle = sheen;
    ctx.fill();
  }
  ctx.strokeStyle = selected ? "#efd7a0" : "#c1c9bd35";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  text(
    label,
    x + 18,
    y + h * 0.63,
    h < 55 ? 25 : 30,
    selected ? "#f6e2b1" : "#e8ddc4",
    w - 34,
  );
  regions.push({ x, y, w, h, action });
}
const tabs = [
  "Слушать",
  "Коллекция",
  "Очередь",
  "DJ",
  "Караоке",
  "Мешапы",
  "Настройки",
];
function panel(width, height, worldWidth, worldHeight, position) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(worldWidth, worldHeight),
    new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      toneMapped: false,
      depthWrite: false,
    }),
  );
  mesh.position.copy(position);
  deck.add(mesh);
  interact.push(mesh);
  mesh.userData.surface = { canvas, texture, regions: [] };
  return mesh;
}
const navigation = panel(
  1792,
  160,
  2.15,
  0.192,
  new THREE.Vector3(0, 2.63, -2.6),
);
const metadata = panel(
  1792,
  360,
  2.15,
  0.432,
  new THREE.Vector3(0, 0.995, -2.6),
);
const navMount = slab(2.17, 0.209, 0.022, 0.085, ink);
navMount.position.copy(navigation.position);
navMount.position.z -= 0.02;
deck.add(navMount);
const liquidMarker = slab(
  0.275,
  0.106,
  0.016,
  0.052,
  new THREE.MeshPhysicalMaterial({
    color: "#b8c2bb",
    roughness: 0.17,
    metalness: 0.15,
    transparent: true,
    opacity: 0.22,
    clearcoat: 1,
    depthWrite: false,
  }),
);
liquidMarker.position.copy(navigation.position);
liquidMarker.position.z += 0.003;
deck.add(liquidMarker);
navigation.position.z += 0.014;
const heartGroup = new THREE.Group();
heartGroup.position.set(-0.681, 0.825, -2.568);
deck.add(heartGroup);
const heartSeat = new THREE.Mesh(
  new THREE.CylinderGeometry(0.052, 0.055, 0.014, 48).rotateX(Math.PI / 2),
  caseRim,
);
heartGroup.add(heartSeat);
const heartShape = new THREE.Shape();
heartShape.moveTo(0, -0.026);
heartShape.bezierCurveTo(-0.07, 0.015, -0.026, 0.062, 0, 0.027);
heartShape.bezierCurveTo(0.026, 0.062, 0.07, 0.015, 0, -0.026);
const heartLightMaterial = new THREE.MeshBasicMaterial({
  color: "#efbb68",
  transparent: true,
  opacity: 0.14,
  toneMapped: false,
});
const heartLight = new THREE.Mesh(
  new THREE.ShapeGeometry(heartShape, 24),
  heartLightMaterial,
);
heartLight.position.z = 0.01;
heartGroup.add(heartLight);
const heartLens = new THREE.Mesh(
  new THREE.SphereGeometry(0.044, 20, 12),
  new THREE.MeshPhysicalMaterial({
    color: "#e3cda1",
    roughness: 0.12,
    metalness: 0.1,
    transparent: true,
    opacity: 0.11,
    clearcoat: 1,
    depthWrite: false,
  }),
);
heartLens.scale.z = 0.32;
heartLens.position.z = 0.011;
heartGroup.add(heartLens);
heartSeat.userData.action = () => {
  if (localActive) {
    notice = "Избранное доступно для подключённых музыкальных сервисов.";
    boardDirty = true;
    return;
  }
  favorite = !favorite;
  command("favorite", { value: favorite });
  boardDirty = true;
};
interact.push(heartSeat);
let heartHeat = 0;
let markerX = -0.91;
function centerLabel(value, x, y, size, color, width) {
  ctx.font = `${size >= 60 ? 600 : 400} ${size}px system-ui,sans-serif`;
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  for (const [i, line] of fitLines(ctx, value, width, 2).entries())
    ctx.fillText(line, x, y + i * (size * 1.18));
  ctx.textAlign = "left";
}
function paintListeningSurfaces() {
  const savedRegions = regions;
  ctx = navigation.userData.surface.canvas.getContext("2d");
  regions = [];
  ctx.clearRect(0, 0, 1792, 160);
  round(2, 2, 1788, 156, 78, "#1a20253d");
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = "#dce7db35";
  ctx.stroke();
  for (const [i, tab] of tabs.entries()) {
    const x = 22 + i * 250;
    centerLabel(
      tab === "Очередь" && state.queue?.length
        ? `Очередь · ${state.queue.length}`
        : tab,
      x + 120,
      94,
      32,
      page === tab ? "#fff0ce" : "#b8b9af",
      234,
    );
    regions.push({ x, y: 20, w: 240, h: 120, action: () => navigate(tab) });
  }
  navigation.userData.surface.regions = regions;
  navigation.userData.surface.texture.needsUpdate = true;
  ctx = metadata.userData.surface.canvas.getContext("2d");
  regions = [];
  ctx.clearRect(0, 0, 1792, 360);
  centerLabel(state.title, 896, 92, 72, "#f8ebcf", 1650);
  if (notice) {
    ctx.font = "24px system-ui";
    centerLabel(
      fitLines(ctx, notice, 1500, 1)[0] || "",
      896,
      193,
      24,
      "#d8b986",
      1500,
    );
  }
  const chip = (value, x, y, w, action) => {
    ctx.font = "34px system-ui";
    round(x, y, w, 60, 30, "#171e2280");
    ctx.strokeStyle = "#e1deca20";
    ctx.lineWidth = 1;
    ctx.stroke();
    centerLabel(
      fitLines(ctx, value, w - 40, 1)[0] || "",
      x + w / 2,
      y + 41,
      34,
      "#c9c3af",
      w - 40,
    );
    regions.push({ x, y, w, h: 60, action });
  };
  chip(state.artist || "Выбрать музыку", 390, 208, 1012, () =>
    client.online && !localActive
      ? browse("artist", "", state.artistRef)
      : chooseFile(),
  );
  chip(
    state.album || (state.native ? "Войти и открыть медиатеку" : ""),
    470,
    280,
    852,
    () =>
      state.native && !state.authorized
        ? command("login")
        : client.online && !localActive
          ? browse("release", "", state.albumRef)
          : chooseFile(),
  );
  const toggleFavorite = () => {
    if (localActive) {
      notice = "Избранное доступно для подключённых музыкальных сервисов.";
      boardDirty = true;
      return;
    }
    favorite = !favorite;
    command("favorite", { value: favorite });
    boardDirty = true;
  };
  regions.push({ x: 260, y: 264, w: 130, h: 90, action: toggleFavorite });
  if (state.quality?.known)
    centerLabel(state.quality.name, 1505, 322, 24, "#aaa995", 300);
  metadata.userData.surface.regions = regions;
  metadata.userData.surface.texture.needsUpdate = true;
  ctx = boardContext;
  regions = savedRegions;
  board.visible = page !== "Слушать" || keyboard;
  metadata.visible = !board.visible;
  heartGroup.visible = metadata.visible;
  heartSeat.visible = metadata.visible;
}
function paint() {
  boardDirty = false;
  paintListeningSurfaces();
  if (page === "Слушать" && !keyboard) return;
  regions = [];
  ctx.clearRect(0, 0, 1792, 1024);
  round(0, 0, 1792, 1024, 42, "#171e23ed");
  const wash = ctx.createLinearGradient(0, 0, 1792, 1024);
  wash.addColorStop(0, "#d6e3cf0d");
  wash.addColorStop(0.4, "#d6e3cf00");
  wash.addColorStop(1, "#b9914c0c");
  ctx.fillStyle = wash;
  ctx.fill();
  ctx.strokeStyle = "#e9dbb52a";
  ctx.lineWidth = 2;
  ctx.stroke();
  text("E M B E R  /  КОМНАТА ПРОСЛУШИВАНИЯ", 44, 52, 23, "#c9b17e");
  text(
    client.online ? "ПК · " + state.source : "АВТОНОМНО · ЛОКАЛЬНОЕ АУДИО",
    1150,
    52,
    22,
    "#b4bda9",
    600,
  );
  if (keyboard) {
    text(
      queryKind === "dj" ? "Пожелание для Эмбер" : "Поиск музыки",
      48,
      210,
      42,
    );
    round(40, 245, 1712, 100, 22, "#0b1717");
    text(query || "Набери пожелание…", 62, 307, 32, "#f2e4c5", 1660);
    const rows = [
      "ЙЦУКЕНГШЩЗХЪ",
      "ФЫВАПРОЛДЖЭ",
      "ЯЧСМИТЬБЮ",
      "QWERTYUIOP",
      "ASDFGHJKL",
      "ZXCVBNM",
    ];
    let y = 375;
    for (const row of rows) {
      let xx = (1792 - row.length * 120) / 2;
      for (const letter of row) {
        button(letter, xx, y, 106, 60, () => {
          query += letter.toLowerCase();
          boardDirty = true;
        });
        xx += 120;
      }
      y += 75;
    }
    button("Пробел", 80, 850, 450, 65, () => {
      query += " ";
      boardDirty = true;
    });
    button("⌫", 550, 850, 220, 65, () => {
      query = query.slice(0, -1);
      boardDirty = true;
    });
    button("Готово", 790, 850, 440, 65, submit, true);
    button("Отмена", 1250, 850, 460, 65, () => {
      keyboard = false;
      boardDirty = true;
    });
    boardTexture.needsUpdate = true;
    return;
  }
  if (page === "Настройки") {
    text("Твоё пространство", 56, 218, 48);
    let y = 260;
    for (let i = 0; i < themes.length; i++)
      button(
        themes[i],
        60 + i * 420,
        y,
        400,
        72,
        () => {
          themeIndex = i;
          applyTheme();
        },
        themeIndex === i,
      );
    text(
      state.native
        ? "Музыкальные сервисы в шлеме"
        : "Музыкальный источник на подключённом ПК",
      60,
      438,
      32,
    );
    for (const [i, [id, name]] of [
      ["spotify", "Spotify"],
      ["apple-music", "Apple Music"],
      ["youtube", "YouTube"],
      ["yandex-music", "Яндекс Музыка"],
    ].entries())
      button(
        name,
        60 + i * 420,
        488,
        400,
        72,
        () => {
          localActive = false;
          audio.disconnect();
          command("source", { value: id });
        },
        state.source === id,
      );
    button(
      state.native ? "Войти в сервис" : "Звук с ПК",
      60,
      632,
      470,
      72,
      state.native ? () => command("login") : connectSound,
      audio.mode === "pc",
    );
    button("Остановить передачу", 570, 632, 520, 72, () => audio.disconnect());
    button("Вернуть пульт", 1130, 632, 550, 72, recenter);
    button("Забыть сопряжение", 60, 730, 500, 58, () => {
      audio.disconnect();
      client.forget();
      boardDirty = true;
    });
    text(
      "Комната остаётся на месте при повороте головы. Пульт можно вернуть к себе кнопкой выше.",
      60,
      800,
      27,
      "#aaa58f",
      1640,
    );
    text(
      "Atmos, AI-караоке и EmberFlow обрабатываются ПК; передача в шлем — стерео.",
      60,
      858,
      26,
      "#aaa58f",
      1640,
    );
  } else if (page === "Караоке") {
    text("Слова в твоём пространстве", 56, 216, 44);
    const lines = state.lyrics?.lines || [];
    const position = state.position || 0;
    let active = 0;
    for (let i = 0; i < lines.length; i++)
      if (lines[i].time <= position) active = i;
    for (let n = -1; n < 3; n++) {
      const line = lines[active + n];
      if (line)
        text(
          line.text,
          68,
          360 + (n + 1) * 116,
          n === 0 ? 46 : 30,
          n === 0 ? "#f6c978" : "#a4ab9b",
          1640,
        );
    }
    if (!lines.length)
      text(
        client.online ? "Загружаю слова…" : "Для слов подключи Ember на ПК.",
        60,
        390,
        34,
      );
    button("Обновить текст", 60, 866, 420, 64, () => command("lyrics"));
    const k = state.karaoke || {};
    button(
      k.active || k.starting ? "Вокал · тише ON" : "Приглушить вокал",
      520,
      866,
      490,
      64,
      () => command("karaoke", { value: !(k.active || k.starting) }),
      !!k.active,
    );
    button(
      "AI · чище",
      1040,
      866,
      320,
      64,
      () => command("karaoke-engine", { value: "ai" }),
      k.engine === "ai",
    );
    button(
      "Стерео",
      1390,
      866,
      320,
      64,
      () => command("karaoke-engine", { value: "stereo" }),
      k.engine === "stereo",
    );
    for (const [i, v] of [0.5, 0.7, 0.85, 1].entries())
      button(
        `${Math.round(v * 100)}%`,
        520 + i * 300,
        944,
        280,
        52,
        () => command("karaoke-amount", { value: v }),
        Math.abs((k.amount ?? 0.7) - v) < 0.01,
      );
    if (k.starting)
      text("Эмбер готовит инструментал…", 60, 818, 25, "#d9b974", 1600);
    if (k.error) notice = k.error;
  } else if (page === "История") {
    text(heading, 56, 216, 46);
    const lines = wrapLines(story, 32, 1630);
    for (const [i, line] of lines
      .slice(storyPage * 12, (storyPage + 1) * 12)
      .entries())
      text(line, 60, 310 + i * 44, 32, "#d4ccb7", 1630);
    if (storyPage > 0)
      button("←", 1000, 916, 220, 62, () => {
        storyPage--;
        boardDirty = true;
      });
    if ((storyPage + 1) * 12 < lines.length)
      button("→", 1250, 916, 440, 62, () => {
        storyPage++;
        boardDirty = true;
      });
    button("Назад", 60, 916, 400, 62, () => {
      page = "Коллекция";
      boardDirty = true;
    });
  } else if (page === "Мешапы") {
    text("Студия Ember", 56, 218, 48);
    text("Тяжёлая обработка остаётся на ПК", 60, 350, 36);
    text(
      "Звук выбранного источника можно слушать в шлеме. Редактор дорожек и управление студией требуют отдельной XR-адаптации.",
      60,
      452,
      34,
      "#c0b8a3",
      1620,
    );
    button("Подключить звук Ember", 60, 710, 580, 76, connectSound);
    text(
      "Эта функция ещё не перенесена. Здесь нет имитации готовой студии.",
      60,
      920,
      26,
      "#aaa58f",
      1640,
    );
  } else {
    const title =
      page === "DJ"
        ? "Эмбер · На твоей частоте"
        : page === "Очередь"
          ? "Твои следующие песни"
          : heading;
    text(title, 54, 219, 45);
    if (page === "Коллекция") {
      button("Для тебя", 50, 256, 270, 58, () => browse("home"));
      button("Альбомы", 340, 256, 270, 58, () => browse("albums"));
      button("Избранное", 630, 256, 290, 58, () => browse("favorites"));
      button("Поиск", 940, 256, 280, 58, () => openKeyboard("search"));
      button("Назад", 1240, 256, 480, 58, () => goBack());
    }
    if (page === "DJ") {
      button("Пожелание", 50, 256, 400, 58, () => openKeyboard("dj"));
      button("Спокойнее", 470, 256, 380, 58, () =>
        askDJ("Что-нибудь спокойнее"),
      );
      button("Повеселее", 870, 256, 380, 58, () =>
        askDJ("Что-нибудь повеселее"),
      );
      button("Открытия", 1270, 256, 450, 58, () =>
        askDJ("Новые открытия в моём вкусе"),
      );
      if (state.dj?.reply) text(state.dj.reply, 60, 340, 25, "#cab98f", 1630);
    }
    const values =
      page === "Очередь"
        ? state.queue
        : page === "DJ"
          ? state.dj?.items || []
          : items;
    const start = pageStart(listPage, values.length);
    for (let i = 0; i < Math.min(4, values.length - start); i++) {
      const item = values[start + i];
      const y = page === "DJ" ? 400 + i * 111 : 350 + i * 120;
      button("", 52, y, 1440, 104, () => openItem(item, values));
      ctx.font = "500 32px system-ui";
      for (const [lineIndex, line] of fitLines(
        ctx,
        `${String(start + i + 1).padStart(2, "0")}   ${item.title || item.name || "Без названия"}`,
        1370,
        2,
      ).entries())
        text(line, 78, y + 32 + lineIndex * 33, 32, "#eee3c8", 1370);
      ctx.font = "500 24px system-ui";
      text(
        fitLines(ctx, item.artist || item.subtitle || "", 1370, 1)[0] || "",
        78,
        y + 91,
        24,
        "#aeb8a4",
        1370,
      );
      button("+", 1512, y, 205, 104, () => command("queue", { items: [item] }));
    }
    if (start > 0)
      button("← Предыдущие", 52, 880, 410, 64, () => {
        listPage--;
        boardDirty = true;
      });
    if (start + 4 < values.length || browseNext !== null)
      button("Следующие →", 1250, 880, 465, 64, () => nextPage(values));
    if (story && page === "Коллекция")
      button("Прочесть историю", 500, 880, 700, 64, () => {
        page = "История";
        storyPage = 0;
        boardDirty = true;
      });
    if (!values.length && !busy)
      text(
        client.online
          ? "Источник пока не передал записи. Попробуй поиск."
          : "Подключи Ember на ПК для медиатеки и DJ.",
        60,
        440,
        34,
        "#bab19c",
        1640,
      );
  }
  if (notice || busy)
    text(busy ? "Подключаю музыку…" : notice, 55, 990, 24, "#d5b67c", 1660);
  boardTexture.needsUpdate = true;
}
function navigate(target) {
  listPage = 0;
  if (target === "Слушать") lastArt = "";
  page = target;
  keyboard = false;
  notice = "";
  if (target === "Коллекция") browse("home");
  if (target === "Караоке") command("lyrics");
  boardDirty = true;
}
function openKeyboard(kind) {
  queryKind = kind;
  keyboard = true;
  query = "";
  boardDirty = true;
}
function submit() {
  keyboard = false;
  if (queryKind === "dj") askDJ(query);
  else browse("search", query);
  boardDirty = true;
}
async function command(op, details = {}) {
  if (!client.online || localActive) {
    notice = localActive
      ? "Управление сервисом доступно после выбора источника на ПК."
      : "Для этой функции нужно подключение к Ember на ПК.";
    boardDirty = true;
    return;
  }
  try {
    const reply = await client.action(op, details);
    if (
      reply.needsLogin &&
      ["apple-music", "spotify", "yandex-music", "youtube"].includes(
        reply.source,
      )
    ) {
      const open = () =>
        location.assign(
          "intent://source/" +
            reply.source +
            "#Intent;scheme=emberquest;package=io.emberbox.quest;end",
        );
      if (xrSession) xrSession.end().then(open);
      else open();
    }
    notice = "";
  } catch (e) {
    notice = e.message;
  }
  boardDirty = true;
}
async function action(op) {
  try {
    if (client.online && !localActive) {
      const listen = op !== "toggle" || !state.playing;
      await command(op);
      if (listen && audio.mode !== "pc") connectSound();
    } else if (op === "next" || op === "previous") {
      if (localFiles.length)
        await openLocal(
          (localIndex + (op === "next" ? 1 : -1) + localFiles.length) %
            localFiles.length,
        );
    } else if (op === "toggle") {
      await audio.toggle();
      state.playing = !!audio.media && !audio.media.paused;
      boardDirty = true;
    }
  } catch (e) {
    showError(e);
  }
}
let browseGeneration = 0;
async function browse(
  category,
  term = "",
  collection = null,
  offset = 0,
  remember = true,
) {
  if (remember && lastBrowse) browseHistory.push({ ...lastBrowse, listPage });
  lastBrowse = { category, term, collection, offset };
  listPage = 0;
  const id = ++browseGeneration;
  page = "Коллекция";
  busy = true;
  boardDirty = true;
  try {
    if (!client.online)
      throw Error("Открой парную ссылку Ember на подключённом шлеме.");
    const result = await client.browse(category, term, collection, offset);
    if (id !== browseGeneration) return;
    items =
      result.items ||
      result.tracks ||
      result.sections?.flatMap((s) => s.items || []) ||
      [];
    browseNext = result.next ?? null;
    story = result.artist?.bio || result.release?.description || "";
    heading =
      result.artist?.name ||
      result.release?.title ||
      collection?.title ||
      "Твоя коллекция";
    notice = result.note || "";
  } catch (e) {
    notice = e.message;
  } finally {
    if (id === browseGeneration) {
      busy = false;
      boardDirty = true;
    }
  }
}
function goBack() {
  const prior = browseHistory.pop();
  if (prior) {
    browse(prior.category, prior.term, prior.collection, prior.offset, false);
  } else browse("home", "", null, 0, false);
}
function nextPage(values) {
  if ((listPage + 1) * 4 < values.length) {
    listPage++;
    boardDirty = true;
  } else if (browseNext !== null && lastBrowse) {
    browse(
      lastBrowse.category,
      lastBrowse.term,
      lastBrowse.collection,
      browseNext,
    );
  }
}
function openItem(item, context) {
  if (item.kind === "local-file") {
    openLocal(item.index);
    return;
  }
  if (localActive) {
    localActive = false;
    audio.disconnect();
    if (client.state) state = client.state;
  }
  const kind = item.kind || "",
    uri = item.uri || "";
  if (
    /album|playlist|artist/.test(kind) ||
    /:album:|:playlist:|:artist:/.test(uri)
  ) {
    browse(
      kind === "artist"
        ? "artist"
        : /playlist/.test(kind + uri)
          ? "playlist"
          : "release",
      "",
      item,
    );
  } else {
    command("play", { item, context: context.slice(0, 50) });
    if (audio.mode !== "pc") connectSound();
  }
}
async function askDJ(value) {
  page = "DJ";
  query = value;
  await command("dj", { value });
}
function showError(e) {
  notice = e.message || String(e);
  $("#error").textContent = notice;
  boardDirty = true;
}
async function connectSound() {
  try {
    localActive = false;
    if (client.state) state = client.state;
    if (state.audio?.native) {
      audio.mode = "native";
      notice = "";
      boardDirty = true;
      return;
    }
    if (!client.online) throw Error("Сначала подключи музыкальный источник.");
    await audio.stream(client);
    notice = "Музыка в комнате";
    setTimeout(() => {
      if (notice === "Музыка в комнате") {
        notice = "";
        boardDirty = true;
      }
    }, 1800);
    boardDirty = true;
  } catch (e) {
    showError(e);
  }
}
function chooseFile() {
  if (xrSession) {
    xrSession.end().then(() => $("#file").click());
  } else $("#file").click();
}
function nextTheme() {
  themeIndex = (themeIndex + 1) % themes.length;
  applyTheme();
}
function recenter() {
  const head = new THREE.Vector3();
  (xrSession ? renderer.xr.getCamera() : camera).getWorldPosition(head);
  const direction = new THREE.Vector3();
  (xrSession ? renderer.xr.getCamera() : camera).getWorldDirection(direction);
  const angle = Math.atan2(-direction.x, -direction.z);
  deck.position.set(
    head.x,
    Math.max(-0.5, Math.min(0.5, head.y - 1.6)),
    head.z,
  );
  deck.rotation.y = angle;
}
async function openLocal(index) {
  try {
    localActive = true;
    localIndex = index;
    state = await audio.open(localFiles[index]);
    state.queue = localFiles.map((f, i) => ({
      kind: "local-file",
      index: i,
      title: f.name,
      artist: "На устройстве",
    }));
    audio.media.onended = () => {
      if (localIndex + 1 < localFiles.length) openLocal(localIndex + 1);
      else {
        state.playing = false;
        boardDirty = true;
      }
    };
    boardDirty = true;
  } catch (e) {
    showError(e);
  }
}
audio.onchange = () => {
  notice = audio.error || "";
  boardDirty = true;
};
$("#sound").onclick = connectSound;
$("#theme").onclick = nextTheme;
$("#home").onclick = recenter;
$("#file").multiple = true;
$("#file").onchange = async (e) => {
  localFiles = Array.from(e.target.files || []);
  if (localFiles.length) openLocal(0);
};
$("#query").onsubmit = (e) => {
  e.preventDefault();
  query = $("#query input").value;
  $("#query").style.display = "none";
  submit();
};
client.listeners.add((value) => {
  if (value && client.online && !localActive) {
    const draggedVolume = knobDrag ? state.volume : null;
    state = value;
    if (draggedVolume !== null) state.volume = draggedVolume;
    favorite = !!value.favorite;
    const signature = JSON.stringify([
      page,
      value.title,
      value.artist,
      value.album,
      value.playing,
      value.source,
      value.flow,
      value.favorite,
      value.quality?.name,
      value.queue?.map((v) => v.uri),
      value.dj?.phase,
      value.dj?.reply,
      value.lyrics?.status,
    ]);
    if (signature !== lastSignature) {
      lastSignature = signature;
      boardDirty = true;
    }
    if (xrSession && !autoSoundStarted && !localActive) {
      autoSoundStarted = true;
      connectSound();
    }
    if (value.image && value.image !== lastArt) {
      lastArt = value.image;
      artwork(lastArt);
    }
  }
  $("#status").textContent = client.online
    ? (value.native ? "Музыка в шлеме · " : "Подключено к Ember на ПК · ") +
      value.source
    : "Автономный режим · локальные файлы";
});
client.poll();
const raycaster = new THREE.Raycaster(),
  pointer = new THREE.Vector2(),
  rotation = new THREE.Matrix4(),
  rayDirection = new THREE.Vector3();
let hovered = null,
  knobDrag = null;
const pickable = [];
function hit(ray) {
  raycaster.ray.copy(ray);
  pickable.length = 0;
  for (const object of interact) if (object.visible) pickable.push(object);
  const hits = raycaster.intersectObjects(pickable, false);
  return hits[0] || null;
}
function clickHit(result, inputOwner = "mouse") {
  if (!result) return;
  if (result.object.userData.surface) {
    const surface = result.object.userData.surface;
    const x = result.uv.x * surface.canvas.width,
      y = (1 - result.uv.y) * surface.canvas.height;
    surface.regions
      .find((v) => x >= v.x && x <= v.x + v.w && y >= v.y && y <= v.y + v.h)
      ?.action();
  } else if (result.object === board) {
    const x = result.uv.x * 1792,
      y = (1 - result.uv.y) * 1024;
    const region = regions.find(
      (v) => x >= v.x && x <= v.x + v.w && y >= v.y && y <= v.y + v.h,
    );
    region?.action();
  } else if (result.object.userData.seek) {
    const position = result.uv.x * (state.duration || 0);
    if (client.online && !localActive) command("seek", { value: position });
    else if (audio.media) audio.media.currentTime = position;
  } else if (result.object.userData.knob) {
    const normal = new THREE.Vector3(0, 0, 1).applyQuaternion(
      consoleGroup.getWorldQuaternion(new THREE.Quaternion()),
    );
    knobDrag = {
      start: state.volume ?? 0.65,
      x: consoleGroup.worldToLocal(result.point.clone()).x,
      plane: new THREE.Plane().setFromNormalAndCoplanarPoint(
        normal,
        result.point,
      ),
      owner: inputOwner,
    };
    controls.enabled = false;
  } else {
    result.object.userData.action?.();
    if (buttons.includes(result.object))
      result.object.userData.pressUntil = performance.now() + 90;
  }
}
renderer.domElement.addEventListener("pointerdown", (e) => {
  pointer.set(
    (e.clientX / innerWidth) * 2 - 1,
    (-e.clientY / innerHeight) * 2 + 1,
  );
  raycaster.setFromCamera(pointer, camera);
  clickHit(hit(raycaster.ray));
});
const dragPoint = new THREE.Vector3();
let pendingVolume = null,
  volumeBusy = false;
function sendVolume(value) {
  pendingVolume = value;
  if (volumeBusy) return;
  volumeBusy = true;
  (async () => {
    while (pendingVolume !== null) {
      const v = pendingVolume;
      pendingVolume = null;
      await command("volume", { value: v });
    }
    volumeBusy = false;
  })();
}
function dragKnob(ray, owner, now = performance.now()) {
  if (
    !knobDrag ||
    knobDrag.owner !== owner ||
    !ray.intersectPlane(knobDrag.plane, dragPoint)
  )
    return;
  const x = consoleGroup.worldToLocal(dragPoint).x;
  const v = volumeFromDrag(knobDrag.start, x - knobDrag.x);
  state.volume = v;
  if (client.online && !localActive) {
    if (now - lastVolumeSend > 80) {
      lastVolumeSend = now;
      sendVolume(v);
    }
  } else audio.setVolume(v);
}
function releaseKnob(owner) {
  if (knobDrag?.owner !== owner) return;
  if (client.online && !localActive) sendVolume(state.volume);
  knobDrag = null;
  controls.enabled = !xrSession;
}
renderer.domElement.addEventListener("pointermove", (e) => {
  if (!knobDrag || xrSession) return;
  pointer.set(
    (e.clientX / innerWidth) * 2 - 1,
    (-e.clientY / innerHeight) * 2 + 1,
  );
  raycaster.setFromCamera(pointer, camera);
  dragKnob(raycaster.ray, "mouse");
});
window.addEventListener("pointerup", () => releaseKnob("mouse"));
window.addEventListener("pointercancel", () => releaseKnob("mouse"));
window.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  if (keyboard) {
    if (e.key === "Enter") submit();
    else if (e.key === "Backspace") {
      query = query.slice(0, -1);
      boardDirty = true;
    } else if (e.key.length === 1) {
      query += e.key;
      boardDirty = true;
    }
  } else if (e.code === "Space") {
    e.preventDefault();
    action("toggle");
  }
});
const controllers = [];
const rayLine = new THREE.BufferGeometry().setFromPoints([
  new THREE.Vector3(),
  new THREE.Vector3(0, 0, -1),
]);
for (let i = 0; i < 2; i++) {
  const controller = renderer.xr.getController(i);
  controller.addEventListener("selectstart", () =>
    clickHit(controller.userData.hit, controller),
  );
  controller.addEventListener("selectend", () => releaseKnob(controller));
  controller.addEventListener("disconnected", () => releaseKnob(controller));
  const line = new THREE.Line(
    rayLine,
    new THREE.LineBasicMaterial({
      color: "#d9c28a",
      transparent: true,
      opacity: 0.55,
    }),
  );
  line.scale.z = 4;
  controller.add(line);
  scene.add(controller);
  controllers.push(controller);
  const hand = renderer.xr.getHand(i);
  scene.add(hand);
  const joints = new THREE.InstancedMesh(
    new THREE.SphereGeometry(0.006, 5, 4),
    new THREE.MeshBasicMaterial({
      color: "#d7c69e",
      transparent: true,
      opacity: 0.3,
    }),
    1,
  );
  joints.frustumCulled = false;
  joints.visible = false;
  scene.add(joints);
  hand.userData.mesh = joints;
}
const dot = new THREE.Mesh(
  new THREE.SphereGeometry(0.006, 8, 6),
  new THREE.MeshBasicMaterial({ color: "#ffe0a0" }),
);
dot.visible = false;
scene.add(dot);
async function enter() {
  try {
    if (client.bridgeMode !== "quest") await audio.ready();
    const session = await navigator.xr.requestSession("immersive-vr", {
      optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking"],
    });
    xrSession = session;
    await renderer.xr.setSession(session);
    document.body.classList.add("xr-active");
    session.addEventListener("end", () => {
      xrSession = null;
      document.body.classList.remove("xr-active");
      controls.enabled = true;
    });
    controls.enabled = false;
    const supported = session.supportedFrameRates;
    if (supported?.length) {
      const target = [90, 72].find((v) => Array.from(supported).includes(v));
      if (target) await session.updateTargetFrameRate(target);
    }
    needsRecenter = true;
    if (client.online && !localActive) {
      autoSoundStarted = true;
      connectSound();
    }
  } catch (e) {
    showError(e);
  }
}
$("#enter").onclick = enter;
if (navigator.xr) {
  navigator.xr
    .isSessionSupported("immersive-vr")
    .then((supported) => {
      $("#enter").disabled = !supported;
      $("#enter").textContent = supported
        ? "Войти в комнату"
        : "VR недоступен в этом браузере";
    })
    .catch((e) => {
      $("#enter").textContent = "WebXR недоступен";
      showError(e);
    });
} else $("#enter").textContent = "Предпросмотр · без шлема";
const artScale = new THREE.Vector3();
let needsRecenter = false,
  lastVolumeSend = 0,
  last = 0,
  lastLyric = -1,
  frames = 0,
  frameSum = 0;
const smooth = new Float32Array(9);
const pose = new THREE.Vector3();
renderer.setAnimationLoop((now, xrFrame) => {
  if (xrFrame && needsRecenter) {
    recenter();
    needsRecenter = false;
  }
  const dt = Math.min(0.05, last ? (now - last) / 1000 : 1 / 90);
  last = now;
  if (!xrSession) controls.update();
  const levels =
    audio.mode === "pc" || !client.online ? audio.sample() : state.levels || [];
  for (let i = 0; i < 9; i++) {
    smooth[i] +=
      (Math.max(0.01, levels[i] || 0) - smooth[i]) *
      (1 - Math.exp(-dt * (levels[i] > smooth[i] ? 18 : 8)));
    dummy.position.set(i * 0.052, -0.062 + smooth[i] * 0.063, 0);
    dummy.rotation.set(0, 0, 0);
    dummy.scale.set(1, Math.max(0.02, smooth[i] * 1.3), 1);
    dummy.updateMatrix();
    filaments.setMatrixAt(i, dummy.matrix);
    hotCores.setMatrixAt(i, dummy.matrix);
    tubeGlow.setColorAt(i, tubeColor.setScalar(smooth[i] * 1.6));
  }
  filaments.instanceMatrix.needsUpdate = true;
  hotCores.instanceMatrix.needsUpdate = true;
  tubeGlow.instanceColor.needsUpdate = true;
  const label = state.playing ? "Ⅱ" : "▶";
  if (playKey.userData.label !== label) {
    playKey.userData.label = label;
    const c = playKey.userData.canvas.getContext("2d");
    drawKeyIcon(c, label, "#252a22");
    playKey.userData.texture.needsUpdate = true;
  }
  const progress = THREE.MathUtils.clamp(
    (state.position || 0) / Math.max(1, state.duration || 0),
    0,
    1,
  );
  progressFill.scale.x = Math.max(0.0001, 1.68 * progress);
  progressFill.position.x = -0.84 + 0.84 * progress;
  for (const key of buttons) {
    const target = now < (key.userData.pressUntil || 0) ? -0.006 : 0;
    key.userData.pressSpeed =
      (key.userData.pressSpeed || 0) +
      ((target - (key.position.z - key.userData.homeZ)) * 220 -
        (key.userData.pressSpeed || 0) * 28) *
        dt;
    key.position.z += key.userData.pressSpeed * dt;
  }
  const volume = knobDrag
    ? state.volume
    : client.state && !localActive
      ? client.state.volume
      : audio.volume;
  knob.rotation.y = (0.5 - volume) * Math.PI * 1.5;
  if (xrSession) {
    dot.visible = false;
    for (const controller of controllers) {
      controller.updateWorldMatrix(true, false);
      rotation.identity().extractRotation(controller.matrixWorld);
      raycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
      rayDirection.set(0, 0, -1).applyMatrix4(rotation);
      raycaster.ray.direction.copy(rayDirection);
      controller.userData.hit = hit(raycaster.ray);
      if (controller.userData.hit) {
        dot.position.copy(controller.userData.hit.point);
        dot.visible = true;
      }
      dragKnob(raycaster.ray, controller, now);
      const hand = renderer.xr.getHand(controllers.indexOf(controller)),
        mesh = hand.userData.mesh;
      let count = 0;
      const joint = hand.joints?.["index-finger-tip"];
      if (joint?.visible) {
        joint.getWorldPosition(pose);
        dummy.position.copy(pose);
        dummy.scale.setScalar(0.6);
        dummy.rotation.set(0, 0, 0);
        dummy.updateMatrix();
        mesh.setMatrixAt(count++, dummy.matrix);
      }
      mesh.count = count;
      mesh.visible = count > 0;
      mesh.instanceMatrix.needsUpdate = true;
    }
  }
  if (audio.media && audio.mode === "local") {
    state.position = audio.media.currentTime;
    state.duration = audio.media.duration || 0;
    state.playing = !audio.media.paused;
  }
  if (page === "Караоке") {
    const lines = state.lyrics?.lines || [];
    let n = 0;
    for (let i = 0; i < lines.length; i++)
      if (lines[i].time <= state.position) n = i;
    if (n !== lastLyric) {
      lastLyric = n;
      boardDirty = true;
    }
  }
  if (boardDirty) paint();
  heartHeat += ((favorite ? 1 : 0) - heartHeat) * (1 - Math.exp(-dt * 2.8));
  heartLightMaterial.opacity = 0.16 + heartHeat * 0.84;
  const tabIndex = Math.max(0, tabs.indexOf(page));
  const markerTarget = ((22 + tabIndex * 250 + 120) / 1792) * 2.15 - 1.075;
  markerX += (markerTarget - markerX) * (1 - Math.exp(-dt * 12));
  liquidMarker.position.x = markerX;
  liquidMarker.scale.x =
    1 + Math.min(0.35, Math.abs(markerTarget - markerX) * 3);
  liquidMarker.scale.y = 1 / Math.sqrt(liquidMarker.scale.x);
  mirrorTime.value += dt;
  mirrorEnergy.value +=
    (smooth.reduce((a, b) => a + b, 0) / 9 - mirrorEnergy.value) *
    (1 - Math.exp(-dt * 3));
  listeningRoom.update(dt, smooth, colorTarget, state.playing);
  lightColor.copy(colorTarget).multiplyScalar(0.42);

  rim.color.lerp(colorTarget, 1 - Math.exp(-dt * 0.4));
  art.position.z +=
    ((state.playing ? 0.049 : 0.043) - art.position.z) *
    (1 - Math.exp(-dt * 5));
  const coverScale = state.playing ? 1 : 0.985;
  art.scale.x += (coverScale - art.scale.x) * (1 - Math.exp(-dt * 5));
  art.scale.y = art.scale.x;
  const listening = page === "Слушать" && !keyboard;
  const artX = listening ? 0 : -2.25;
  artGroup.position.x += (artX - artGroup.position.x) * (1 - Math.exp(-dt * 5));
  artGroup.scale.lerp(
    artScale.setScalar(listening ? 0.8 : 0.5),
    1 - Math.exp(-dt * 5),
  );
  renderer.render(scene, camera);
  frames++;
  frameSum += dt;
  if (frameSum > 2) {
    window.emberMetrics = {
      fps: Math.round(frames / frameSum),
      drawCalls: renderer.info.render.calls,
      triangles: renderer.info.render.triangles,
      mode: xrSession ? "xr" : "desktop",
      audio: {
        mode: audio.mode,
        context: audio.context?.state,
        level: Math.max(...audio.levels),
        pcm: audio.pcmStats,
      },
    };
    if (client.online)
      client
        .request("/api/metrics", {
          method: "POST",
          body: JSON.stringify(window.emberMetrics),
        })
        .catch(() => {});
    frames = frameSum = 0;
  }
});
window.addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
window.addEventListener("pagehide", () => {
  client.stopped = true;
  audio.disconnect();
});
window.emberQuest = {
  get state() {
    return state;
  },
  get page() {
    return page;
  },
  get client() {
    return client;
  },
  navigate,
  action,
};

if ("serviceWorker" in navigator)
  navigator.serviceWorker.register("/sw.js").catch(() => {});
// In a signed immersive PWA the library launch is the user activation. Ordinary
// browser tabs retain their explicit Enter button and normal XR permissions.
if (
  window.getDigitalGoodsService !== undefined &&
  navigator.xr?.isSessionSupported
)
  navigator.xr.isSessionSupported("immersive-vr").then((supported) => {
    if (supported) enter();
  });
