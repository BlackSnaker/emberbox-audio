import * as THREE from "three";

// Fixed architecture and gentle light motion: the room never moves around the
// listener. No camera shake, moving horizon, shadow maps or mirror render passes.
export class ListeningRoom {
  constructor(scene) {
    this.group = new THREE.Group();
    scene.add(this.group);
    this.smoothEnergy = 0;
    this.time = 0;
    this.warm = new THREE.Color("#d3a15f");
    this.current = new THREE.Color("#d3a15f");
    this.dummy = new THREE.Object3D();
    const wood = new THREE.MeshStandardMaterial({
      color: "#17201f",
      roughness: 0.88,
      metalness: 0.08,
    });
    const metal = new THREE.MeshStandardMaterial({
      color: "#635c49",
      roughness: 0.5,
      metalness: 0.65,
    });
    this.luminous = new THREE.MeshBasicMaterial({
      color: "#b58c51",
      transparent: true,
      opacity: 0.26,
      depthWrite: false,
    });
    const pillars = new THREE.InstancedMesh(
      new THREE.BoxGeometry(0.12, 3.7, 0.14),
      wood,
      56,
    );
    const seams = new THREE.InstancedMesh(
      new THREE.BoxGeometry(0.013, 2.95, 0.02),
      this.luminous,
      56,
    );
    for (let i = 0; i < 56; i++) {
      const a = (i / 56) * Math.PI * 2;
      this.dummy.position.set(Math.sin(a) * 6, 1.85, -Math.cos(a) * 6);
      this.dummy.rotation.set(0, -a, 0);
      this.dummy.updateMatrix();
      pillars.setMatrixAt(i, this.dummy.matrix);
      this.dummy.position.set(Math.sin(a) * 5.91, 1.65, -Math.cos(a) * 5.91);
      this.dummy.updateMatrix();
      seams.setMatrixAt(i, this.dummy.matrix);
    }
    this.group.add(pillars, seams);
    for (const y of [0.05, 3.4]) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(5.9, 0.025, 5, 112),
        metal,
      );
      ring.rotation.x = Math.PI / 2;
      ring.position.y = y;
      this.group.add(ring);
    }
    const canopy = new THREE.Mesh(new THREE.RingGeometry(4.1, 6.05, 112), wood);
    canopy.rotation.x = Math.PI / 2;
    canopy.position.y = 3.45;
    canopy.material.side = THREE.DoubleSide;
    this.group.add(canopy);
    const glowCanvas = document.createElement("canvas");
    glowCanvas.width = 128;
    glowCanvas.height = 128;
    const c = glowCanvas.getContext("2d"),
      g = c.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "#fff8dc55");
    g.addColorStop(0.27, "#ffe2a51c");
    g.addColorStop(1, "#ffe2a500");
    c.fillStyle = g;
    c.fillRect(0, 0, 128, 128);
    const texture = new THREE.CanvasTexture(glowCanvas);
    this.haloMaterial = new THREE.MeshBasicMaterial({
      map: texture,
      color: "#bc9d62",
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    this.halos = new THREE.InstancedMesh(
      new THREE.PlaneGeometry(1, 1),
      this.haloMaterial,
      24,
    );
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * Math.PI * 2;
      this.dummy.position.set(
        Math.sin(a) * 5.7,
        0.8 + (i % 3) * 0.8,
        -Math.cos(a) * 5.7,
      );
      this.dummy.rotation.set(0, -a, 0);
      this.dummy.scale.set(2.6, 3.1, 1);
      this.dummy.updateMatrix();
      this.halos.setMatrixAt(i, this.dummy.matrix);
    }
    this.group.add(this.halos);
    // Low diffuse pools anchor the console without brightening the entire floor.
    const pool = new THREE.Mesh(
      new THREE.PlaneGeometry(7, 7),
      this.haloMaterial,
    );
    pool.rotation.x = -Math.PI / 2;
    pool.position.set(0, 0.009, -2);
    this.group.add(pool);
  }
  update(dt, levels, color, playing, comfort = 1) {
    this.time += dt;
    let energy = 0;
    for (let i = 0; i < levels.length; i++)
      energy += levels[i] / Math.max(1, levels.length);
    this.smoothEnergy += (energy - this.smoothEnergy) * (1 - Math.exp(-dt * 3));
    this.current.lerp(color, 1 - Math.exp(-dt * 0.35));
    this.haloMaterial.color.copy(this.current).lerp(this.warm, 0.3);
    this.luminous.color.copy(this.haloMaterial.color);
    const breath = 0.5 + 0.5 * Math.sin(this.time * 0.23);
    this.luminous.opacity =
      (0.12 + this.smoothEnergy * 0.2 + breath * 0.035) * comfort;
    this.haloMaterial.opacity = (0.34 + this.smoothEnergy * 0.32) * comfort;
  }
}
