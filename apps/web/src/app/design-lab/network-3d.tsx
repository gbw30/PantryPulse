"use client";

import { useEffect, useRef, useState } from "react";
import { Focus, Rotate3D } from "lucide-react";
import type * as THREE from "three";

type SceneSite = {
  id: string;
  name: string;
  x: number;
  y: number;
  status: "hub" | "needs" | "covered";
};

type Props = {
  sites: SceneSite[];
  selectedId: string;
  filter: "all" | "needs" | "covered";
  theme: "dark" | "light";
  animate: boolean;
  onSelect: (id: string) => void;
  onFallback: () => void;
};

type SceneMarker = {
  site: SceneSite;
  group: THREE.Group;
  ring: THREE.Mesh<THREE.TorusGeometry, THREE.MeshBasicMaterial>;
  label: HTMLDivElement;
  materials: THREE.Material[];
};

function positionFor(site: SceneSite, Vector3: typeof THREE.Vector3) {
  return new Vector3((site.x - 500) / 80, 0, (site.y - 330) / 80);
}

export function Network3D({ sites, selectedId, filter, theme, animate, onSelect, onFallback }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const resetViewRef = useRef<(() => void) | null>(null);
  const currentRef = useRef({ selectedId, filter, animate, onSelect });
  const [error, setError] = useState(false);

  useEffect(() => {
    currentRef.current = { selectedId, filter, animate, onSelect };
  }, [selectedId, filter, animate, onSelect]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    let canceled = false;
    let dispose = () => {};

    async function initialize() {
      try {
        const [three, { OrbitControls }, { CSS2DObject, CSS2DRenderer }] = await Promise.all([
          import("three"),
          import("three/addons/controls/OrbitControls.js"),
          import("three/addons/renderers/CSS2DRenderer.js"),
        ]);
        if (canceled || !mount) return;

        const dark = theme === "dark";
        const colors = {
          floor: dark ? 0x0a2531 : 0xe1eee5,
          grid: dark ? 0x275869 : 0x8bad9f,
          node: dark ? 0x133847 : 0xe4f0e9,
          metal: dark ? 0x1a5060 : 0x82b9a4,
          ink: dark ? 0xd8fff2 : 0x173d33,
          accent: dark ? 0x78e7ce : 0x217e64,
          need: dark ? 0xf1b46f : 0xc66d4d,
          covered: dark ? 0x69c5ba : 0x4b9c88,
          line: dark ? 0x3e7682 : 0x89a99b,
        };
        const scene = new three.Scene();
        scene.fog = new three.FogExp2(colors.floor, 0.026);
        const camera = new three.PerspectiveCamera(48, 1, 0.1, 100);
        camera.position.set(0, 7.1, 9.4);
        camera.lookAt(0, 0, 0);

        const renderer = new three.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
        renderer.outputColorSpace = three.SRGBColorSpace;
        renderer.toneMapping = three.ACESFilmicToneMapping;
        renderer.toneMappingExposure = dark ? 1.45 : 1.65;
        renderer.domElement.className = "lab-3d-canvas";
        mount.appendChild(renderer.domElement);

        const labelRenderer = new CSS2DRenderer();
        labelRenderer.domElement.className = "lab-3d-label-layer";
        labelRenderer.domElement.style.pointerEvents = "none";
        mount.appendChild(labelRenderer.domElement);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.075;
        controls.minDistance = 5;
        controls.maxDistance = 24;
        controls.minPolarAngle = 0.28;
        controls.maxPolarAngle = 1.42;
        controls.target.set(0, 0, 0);
        controls.update();
        resetViewRef.current = () => {
          camera.position.set(0, 7.1, 9.4);
          controls.target.set(0, 0, 0);
          controls.update();
        };

        scene.add(new three.AmbientLight(0xffffff, dark ? 1.45 : 1.8));
        const keyLight = new three.DirectionalLight(0xffffff, dark ? 2.3 : 2.7);
        keyLight.position.set(-4, 9, 5);
        scene.add(keyLight);
        const rimLight = new three.PointLight(colors.accent, dark ? 45 : 28, 14);
        rimLight.position.set(0, 3.5, 0);
        scene.add(rimLight);

        const floor = new three.Mesh(
          new three.PlaneGeometry(15.8, 11.5),
          new three.MeshStandardMaterial({ color: colors.floor, roughness: 0.95, metalness: 0.06 }),
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -0.14;
        scene.add(floor);
        const grid = new three.GridHelper(15, 24, colors.grid, colors.grid);
        grid.position.y = -0.128;
        const gridMaterials = Array.isArray(grid.material) ? grid.material : [grid.material];
        gridMaterials.forEach((material) => { material.transparent = true; material.opacity = dark ? 0.23 : 0.16; });
        scene.add(grid);

        for (const radius of [1.9, 3.6, 5.2]) {
          const points: THREE.Vector3[] = [];
          for (let step = 0; step <= 120; step++) {
            const angle = (step / 120) * Math.PI * 2;
            points.push(new three.Vector3(Math.cos(angle) * radius, -0.116, Math.sin(angle) * radius * 0.68));
          }
          const contour = new three.Line(
            new three.BufferGeometry().setFromPoints(points),
            new three.LineBasicMaterial({ color: colors.grid, transparent: true, opacity: dark ? 0.2 : 0.14 }),
          );
          scene.add(contour);
        }

        const markers: SceneMarker[] = [];
        const pickTargets: THREE.Object3D[] = [];
        for (const site of sites) {
          const isHub = site.status === "hub";
          const statusColor = site.status === "needs" ? colors.need : isHub ? colors.accent : colors.covered;
          const group = new three.Group();
          group.position.copy(positionFor(site, three.Vector3));
          group.userData.siteId = site.id;
          scene.add(group);

          const pedestalMaterial = new three.MeshStandardMaterial({ color: colors.node, metalness: 0.48, roughness: 0.42, transparent: true });
          const base = new three.Mesh(new three.CylinderGeometry(isHub ? 0.53 : 0.42, isHub ? 0.6 : 0.47, 0.17, 48), pedestalMaterial);
          base.position.y = 0.02;
          base.userData.siteId = site.id;
          group.add(base);
          pickTargets.push(base);

          const ringMaterial = new three.MeshBasicMaterial({ color: statusColor, transparent: true, opacity: 0.9 });
          const ring = new three.Mesh(new three.TorusGeometry(isHub ? 0.49 : 0.38, 0.017, 10, 72), ringMaterial);
          ring.rotation.x = Math.PI / 2;
          ring.position.y = 0.12;
          group.add(ring);

          const symbolMaterial = new three.MeshStandardMaterial({
            color: statusColor, metalness: 0.25, roughness: 0.26,
            emissive: statusColor, emissiveIntensity: dark ? 0.27 : 0.09, transparent: true,
          });
          const symbol = new three.Mesh(isHub ? new three.OctahedronGeometry(0.27, 1) : new three.CylinderGeometry(0.2, 0.2, 0.27, 6), symbolMaterial);
          symbol.position.y = isHub ? 0.37 : 0.32;
          symbol.userData.siteId = site.id;
          group.add(symbol);
          pickTargets.push(symbol);

          const stemMaterial = new three.MeshBasicMaterial({ color: statusColor, transparent: true, opacity: 0.45 });
          const stem = new three.Mesh(new three.CylinderGeometry(0.008, 0.008, 0.3, 8), stemMaterial);
          stem.position.y = 0.64;
          group.add(stem);
          const beacon = new three.Mesh(new three.SphereGeometry(isHub ? 0.09 : 0.07, 14, 10), symbolMaterial);
          beacon.position.y = 0.84;
          group.add(beacon);

          const label = document.createElement("div");
          label.className = `lab-3d-label lab-3d-label-${site.status}`;
          const name = document.createElement("strong");
          name.textContent = site.name;
          const status = document.createElement("span");
          status.textContent = isHub ? "CENTRAL HUB" : site.status === "needs" ? "NEEDS SUPPORT" : "COVERED";
          label.append(name, status);
          const labelObject = new CSS2DObject(label);
          labelObject.position.set(0, 1.27, 0);
          group.add(labelObject);
          markers.push({ site, group, ring, label, materials: [pedestalMaterial, ringMaterial, symbolMaterial, stemMaterial] });
        }

        const hub = sites.find((site) => site.id === "hub");
        if (!hub) throw new Error("The demo network needs a hub.");
        const hubPoint = positionFor(hub, three.Vector3);
        const routes: { siteId: string; curve: THREE.QuadraticBezierCurve3; material: THREE.MeshBasicMaterial; pulse: THREE.Mesh }[] = [];
        for (const site of sites.filter((item) => item.id !== "hub")) {
          const end = positionFor(site, three.Vector3);
          const start = hubPoint.clone().setY(0.18);
          end.y = 0.18;
          const midpoint = start.clone().add(end).multiplyScalar(0.5);
          midpoint.y = 0.95;
          const curve = new three.QuadraticBezierCurve3(start, midpoint, end);
          const material = new three.MeshBasicMaterial({ color: colors.line, transparent: true, opacity: 0.3 });
          const tube = new three.Mesh(new three.TubeGeometry(curve, 52, 0.035, 8, false), material);
          scene.add(tube);
          const pulse = new three.Mesh(
            new three.SphereGeometry(0.1, 14, 10),
            new three.MeshBasicMaterial({ color: colors.accent, transparent: true, opacity: 0.95 }),
          );
          pulse.visible = false;
          scene.add(pulse);
          routes.push({ siteId: site.id, curve, material, pulse });
        }

        const raycaster = new three.Raycaster();
        const pointer = new three.Vector2();
        let pointerStart = { x: 0, y: 0 };
        const onDown = (event: PointerEvent) => { pointerStart = { x: event.clientX, y: event.clientY }; };
        const onClick = (event: MouseEvent) => {
          if (Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 7) return;
          const rect = renderer.domElement.getBoundingClientRect();
          pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
          raycaster.setFromCamera(pointer, camera);
          const hit = raycaster.intersectObjects(pickTargets, false)[0];
          if (hit?.object.userData.siteId) currentRef.current.onSelect(String(hit.object.userData.siteId));
        };
        renderer.domElement.addEventListener("pointerdown", onDown);
        renderer.domElement.addEventListener("click", onClick);

        const resize = () => {
          if (!mount) return;
          const width = Math.max(mount.clientWidth, 1);
          const height = Math.max(mount.clientHeight, 1);
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
          renderer.setSize(width, height);
          labelRenderer.setSize(width, height);
        };
        const observer = new ResizeObserver(resize);
        observer.observe(mount);
        resize();

        const clock = new three.Clock();
        const render = () => {
          const elapsed = clock.getElapsedTime();
          const state = currentRef.current;
          for (const marker of markers) {
            const selected = marker.site.id === state.selectedId;
            const dimmed = marker.site.status !== "hub" && state.filter !== "all" && marker.site.status !== state.filter;
            marker.materials.forEach((material) => {
              if ("opacity" in material && typeof material.opacity === "number") material.opacity = dimmed ? 0.15 : 1;
            });
            marker.ring.material.opacity = dimmed ? 0.14 : selected ? 1 : 0.72;
            marker.ring.scale.setScalar(selected && state.animate ? 1 + Math.sin(elapsed * 2.3) * 0.06 : 1);
            marker.label.classList.toggle("is-selected", selected);
            marker.label.style.opacity = dimmed ? "0.18" : "1";
          }
          for (const route of routes) {
            const site = sites.find((item) => item.id === route.siteId);
            const dimmed = site && state.filter !== "all" && site.status !== state.filter;
            const selected = route.siteId === state.selectedId;
            route.material.color.setHex(selected ? colors.accent : colors.line);
            route.material.opacity = dimmed ? 0.05 : selected ? 0.9 : 0.25;
            route.pulse.visible = Boolean(selected && state.animate && !dimmed);
            if (route.pulse.visible) route.pulse.position.copy(route.curve.getPointAt((elapsed * 0.17) % 1));
          }
          controls.update();
          renderer.render(scene, camera);
          labelRenderer.render(scene, camera);
        };
        renderer.setAnimationLoop(render);
        setError(false);

        dispose = () => {
          renderer.setAnimationLoop(null);
          observer.disconnect();
          renderer.domElement.removeEventListener("pointerdown", onDown);
          renderer.domElement.removeEventListener("click", onClick);
          controls.dispose();
          scene.traverse((object) => {
            if (!(object instanceof three.Mesh || object instanceof three.Line || object instanceof three.GridHelper)) return;
            object.geometry.dispose();
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            materials.forEach((material) => material.dispose());
          });
          renderer.dispose();
          renderer.domElement.remove();
          labelRenderer.domElement.remove();
          resetViewRef.current = null;
        };
      } catch (reason) {
        console.error("Unable to initialize 3D network preview", reason);
        if (!canceled) setError(true);
      }
    }

    void initialize();
    return () => { canceled = true; dispose(); };
  }, [sites, theme]);

  return (
    <div className="lab-map lab-3d-map">
      <div ref={mountRef} className="lab-3d-mount" aria-hidden="true" />
      {error ? <div className="lab-3d-error"><strong>3D view is unavailable in this browser.</strong><button onClick={onFallback}>Return to 2D</button></div> : null}
      <div className="lab-3d-topline"><span><Rotate3D size={15} /> Drag to orbit · Scroll to zoom · Right drag to pan</span><label>Location <select value={selectedId} onChange={(event) => onSelect(event.target.value)}>{sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label></div>
      <button className="lab-3d-reset" onClick={() => resetViewRef.current?.()} aria-label="Reset 3D view"><Focus size={17} /> Reset view</button>
    </div>
  );
}
