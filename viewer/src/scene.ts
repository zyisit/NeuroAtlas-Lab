import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { Index } from "./data";

export interface Edge { from: string; to: string; weight: number } // weight in [0, 1], 1 = strongest edge of the selected region

export interface SceneHandle {
  setSelection: (regionIds: string[]) => void;
  /** Draw tubes from the selected region to its connected regions. Pass [] to clear. */
  setConnections: (edges: Edge[]) => void;
  focus: (regionId: string) => void;
  dispose: () => void;
}

export interface SceneCallbacks {
  onPick: (regionId: string | null) => void;
  onHover: (regionId: string | null, x: number, y: number) => void;
  onReady: (meshCount: number) => void;
}

const DIM_OPACITY = 0.18;
const CONNECTED_OPACITY = 0.6;
const FULL_OPACITY = 0.95;
const TUBE_MIN_R = 0.45, TUBE_MAX_R = 1.8; // mm; MNI brain is ~150 mm across

/** Mounts a three.js scene into `container`. Geometry is in MNI RAS mm; the
 *  world group is rotated so superior (+z MNI) becomes +y in three.js. */
export function createScene(container: HTMLElement, index: Index, cb: SceneCallbacks): SceneHandle {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, container.clientWidth / container.clientHeight, 1, 2000);
  camera.position.set(170, 110, -260);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 10, 0);

  scene.add(new THREE.HemisphereLight(0xdfe7ee, 0x1a2430, 0.9));
  const key = new THREE.DirectionalLight(0xffffff, 1.4);
  key.position.set(200, 300, -150);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x9fb4c6, 0.5);
  fill.position.set(-200, -50, 200);
  scene.add(fill);

  const world = new THREE.Group();
  world.rotation.x = -Math.PI / 2; // MNI z-up -> three y-up
  scene.add(world);

  const meshes = new Map<string, THREE.Mesh>();
  const base = import.meta.env.BASE_URL;
  // GLTFLoader strips ':' and '.' from node names; map sanitized names back to record ids.
  const idBySanitized = new Map<string, string>();
  for (const rid of index.regions.keys()) idBySanitized.set(THREE.PropertyBinding.sanitizeNodeName(rid), rid);
  const loader = new GLTFLoader();

  loader.load(`${base}assets/julich-3.1/hull.glb`, (g) => {
    g.scene.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        const m = o as THREE.Mesh;
        m.material = new THREE.MeshStandardMaterial({ color: 0xc9d3dc, transparent: true, opacity: 0.07, depthWrite: false, roughness: 0.9, side: THREE.DoubleSide });
        m.renderOrder = -1;
      }
    });
    world.add(g.scene);
  });

  loader.load(`${base}assets/julich-3.1/regions.glb`, (g) => {
    g.scene.traverse((o) => {
      if (!(o as THREE.Mesh).isMesh) return;
      const m = o as THREE.Mesh;
      const rid = idBySanitized.get(m.name) ?? m.name;
      const color = index.colorOf(rid) ?? "#8a9aa8";
      m.material = new THREE.MeshStandardMaterial({ color, transparent: true, opacity: FULL_OPACITY, roughness: 0.75, metalness: 0.0 });
      m.userData.regionId = rid;
      meshes.set(rid, m);
    });
    world.add(g.scene);
    cb.onReady(meshes.size);
  });

  // picking
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let hovered: string | null = null;
  let downAt = 0;
  const pick = (ev: PointerEvent): string | null => {
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObjects([...meshes.values()].filter((m) => (m.material as THREE.MeshStandardMaterial).opacity > 0.5), false);
    return hits[0]?.object.userData.regionId ?? null;
  };
  const onMove = (ev: PointerEvent) => {
    const id = pick(ev);
    if (id !== hovered) { hovered = id; cb.onHover(id, ev.clientX, ev.clientY); }
    else if (id) cb.onHover(id, ev.clientX, ev.clientY);
  };
  const onDown = () => { downAt = performance.now(); };
  const onUp = (ev: PointerEvent) => { if (performance.now() - downAt < 250) cb.onPick(pick(ev)); };
  renderer.domElement.addEventListener("pointermove", onMove);
  renderer.domElement.addEventListener("pointerdown", onDown);
  renderer.domElement.addEventListener("pointerup", onUp);

  // selection
  let selected = new Set<string>();
  let connected = new Set<string>();
  const applySelection = () => {
    const any = selected.size > 0;
    for (const [rid, m] of meshes) {
      const mat = m.material as THREE.MeshStandardMaterial;
      const on = selected.has(rid);
      const near = !on && connected.has(rid);
      mat.opacity = !any ? FULL_OPACITY : on ? 1 : near ? CONNECTED_OPACITY : DIM_OPACITY;
      mat.emissive.set(on ? mat.color : 0x000000);
      mat.emissiveIntensity = on ? 0.35 : 0;
      mat.depthWrite = !any || on || near;
      m.renderOrder = on ? 2 : near ? 1 : 0;
    }
  };

  // connections: one tube per edge, bowed outward so bundles don't all run through the centre of the brain
  const tubes = new THREE.Group();
  world.add(tubes);
  // Tube endpoints in `world` (MNI) coordinates: mesh bounding-sphere centre, else the record centroid.
  const centreOf = (rid: string): THREE.Vector3 | undefined => {
    const m = meshes.get(rid);
    if (m) {
      m.geometry.computeBoundingSphere();
      return world.worldToLocal(m.geometry.boundingSphere!.center.clone().applyMatrix4(m.matrixWorld));
    }
    const c = index.centroidOf(rid);
    return c ? new THREE.Vector3(c[0], c[1], c[2]) : undefined;
  };
  const clearTubes = () => {
    for (const t of tubes.children) { (t as THREE.Mesh).geometry.dispose(); ((t as THREE.Mesh).material as THREE.Material).dispose(); }
    tubes.clear();
  };
  const setConnections = (edges: Edge[]) => {
    clearTubes();
    world.updateMatrixWorld();
    connected = new Set(edges.map((e) => e.to));
    for (const e of edges) {
      const a = centreOf(e.from), b = centreOf(e.to);
      if (!a || !b) continue;
      const mid = a.clone().add(b).multiplyScalar(0.5);
      const bow = mid.clone().normalize().multiplyScalar(a.distanceTo(b) * 0.25); // push the control point away from the origin
      const curve = new THREE.QuadraticBezierCurve3(a, mid.add(bow), b);
      const r = TUBE_MIN_R + (TUBE_MAX_R - TUBE_MIN_R) * Math.sqrt(e.weight);
      const geom = new THREE.TubeGeometry(curve, 16, r, 6, false);
      const color = new THREE.Color(index.colorOf(e.to) ?? "#e8c26a");
      // depthTest off: the tubes are an overlay and must stay visible where they pass inside a surface.
      const mat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.7, roughness: 0.6, transparent: true, opacity: 0.55 + 0.45 * e.weight, depthWrite: false, depthTest: false });
      const t = new THREE.Mesh(geom, mat);
      t.renderOrder = 3;
      tubes.add(t);
    }
    applySelection();
  };

  const resize = () => {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(container);

  let raf = 0;
  const tick = () => { controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(tick); };
  tick();

  return {
    setSelection(ids) { selected = new Set(ids); applySelection(); },
    setConnections,
    focus(rid) {
      // Centre of the loaded meshes for this region (and its descendants); fall back to record centroids.
      world.updateMatrixWorld();
      const ids = [rid, ...index.descendants(rid)];
      const p = new THREE.Vector3();
      let n = 0;
      for (const id of ids) {
        const m = meshes.get(id);
        if (!m) continue;
        m.geometry.computeBoundingSphere();
        p.add(m.geometry.boundingSphere!.center.clone().applyMatrix4(m.matrixWorld));
        n++;
      }
      if (n === 0) {
        const c = index.centroidOf(rid);
        if (!c) return;
        p.set(c[0], c[1], c[2]).applyMatrix4(world.matrixWorld);
      } else {
        p.divideScalar(n);
      }
      // Swing the camera to the side of the brain the region is on, keeping the current distance.
      const centre = new THREE.Vector3(0, 10, 0);
      const dist = camera.position.distanceTo(controls.target);
      const dir = p.clone().sub(centre);
      if (dir.lengthSq() < 1) dir.set(1, 0.4, -1);
      dir.normalize().add(new THREE.Vector3(0, 0.25, 0)).normalize();
      controls.target.copy(p);
      camera.position.copy(p.clone().add(dir.multiplyScalar(dist)));
    },
    dispose() {
      cancelAnimationFrame(raf); ro.disconnect(); clearTubes();
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      controls.dispose(); renderer.dispose(); container.removeChild(renderer.domElement);
    },
  };
}
