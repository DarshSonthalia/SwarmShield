import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

export const VERTICAL_SCALE = 3;
export const TRAIL_WINDOW_SECONDS = 20;

const COLORS = {
  threat: 0xff6678,
  unassigned: 0xffbd59,
  interceptor: 0x9df5bf,
  failed: 0x59645f,
  asset: 0x60d394,
  critical: 0xffbd59,
  grid: 0x315b4b,
};

export function simulationToWorld(record, target = new THREE.Vector3()) {
  return target.set(record.x, record.z * VERTICAL_SCALE, record.y);
}

function buildRunIndex(run) {
  const frames = new Map();
  for (const row of run.trajectories) {
    if (!frames.has(row.t)) frames.set(row.t, new Map());
    frames.get(row.t).set(row.id, row);
  }
  return { frames, times: [...frames.keys()].sort((a, b) => a - b) };
}

function bracketTime(times, value) {
  if (!times.length) return [0, 0, 0];
  if (value <= times[0]) return [times[0], times[0], 0];
  const last = times[times.length - 1];
  if (value >= last) return [last, last, 0];
  let low = 0;
  let high = times.length - 1;
  while (low + 1 < high) {
    const mid = Math.floor((low + high) / 2);
    if (times[mid] <= value) low = mid; else high = mid;
  }
  const before = times[low];
  const after = times[high];
  return [before, after, (value - before) / Math.max(after - before, 1e-9)];
}

function material(color, opacity = 1) {
  return new THREE.MeshStandardMaterial({ color, roughness: .64, metalness: .08, transparent: opacity < 1, opacity });
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));
}

export function initTactical3D(container, options = {}) {
  const details = options.detailsElement || document.querySelector('#entityDetails');
  const status = options.statusElement || document.querySelector('#sceneStatus');
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07110f);
  scene.fog = new THREE.FogExp2(0x07110f, 0.000018);

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x07110f, 1);
  container.appendChild(renderer.domElement);

  const camera = new THREE.PerspectiveCamera(42, 1, 10, 200000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = .07;
  controls.minDistance = 1800;
  controls.maxDistance = 90000;
  controls.maxPolarAngle = Math.PI * .495;
  controls.screenSpacePanning = false;

  scene.add(new THREE.HemisphereLight(0xaed9c5, 0x07110f, 1.7));
  const keyLight = new THREE.DirectionalLight(0xe8fff3, 1.25);
  keyLight.position.set(-12000, 22000, 16000);
  scene.add(keyLight);

  const scenarioGroup = new THREE.Group();
  const trailGroup = new THREE.Group();
  const assignmentGroup = new THREE.Group();
  const peerGroup = new THREE.Group();
  scene.add(scenarioGroup, trailGroup, assignmentGroup, peerGroup);

  const shared = {
    threatGeometry: new THREE.ConeGeometry(115, 330, 5),
    interceptorGeometry: new THREE.OctahedronGeometry(145, 0),
    threat: material(COLORS.threat),
    unassigned: material(COLORS.unassigned),
    interceptor: material(COLORS.interceptor),
    failed: material(COLORS.failed),
  };
  shared.threatGeometry.rotateX(Math.PI / 2);
  shared.interceptorGeometry.rotateX(Math.PI / 4);

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const threatMeshes = new Map();
  const interceptorMeshes = new Map();
  const assignmentLines = new Map();
  const trails = new Map();
  const assetLabels = [];
  let peerLines = [];
  let payload = null;
  let strategy = 'swarmshield';
  let indexes = {};
  let currentContinuousTime = 0;
  let currentDiscreteTime = 0;
  let lastTrailTime = null;
  let defaultCamera = { position: new THREE.Vector3(0, 26000, 34000), target: new THREE.Vector3() };
  let visibility = { trails: true, assignments: true, peerLinks: false };
  let animationFrame = 0;
  let disposed = false;

  function disposeObject(object) {
    object.traverse(child => {
      if (child.userData.shared) return;
      child.geometry?.dispose?.();
      if (Array.isArray(child.material)) child.material.forEach(item => item.dispose?.());
      else child.material?.dispose?.();
    });
  }

  function clearGroup(group) {
    while (group.children.length) {
      const child = group.children.pop();
      disposeObject(child);
    }
  }

  function clearScenario() {
    clearGroup(scenarioGroup);
    clearGroup(trailGroup);
    clearGroup(assignmentGroup);
    clearPeerLines();
    threatMeshes.clear();
    interceptorMeshes.clear();
    assignmentLines.clear();
    trails.clear();
    for (const label of assetLabels.splice(0)) label.element.remove();
    if (details) details.hidden = true;
  }

  function makeGround(bounds) {
    const spanX = bounds.maxX - bounds.minX;
    const spanZ = bounds.maxZ - bounds.minZ;
    const size = Math.max(spanX, spanZ, 18000) * 1.12;
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerZ = (bounds.minZ + bounds.maxZ) / 2;
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(size, size),
      new THREE.MeshStandardMaterial({ color: 0x091713, roughness: 1, metalness: 0 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(centerX, -5, centerZ);
    scenarioGroup.add(ground);
    const grid = new THREE.GridHelper(size, Math.max(20, Math.round(size / 1000)), COLORS.grid, COLORS.grid);
    grid.position.set(centerX, 0, centerZ);
    grid.material.transparent = true;
    grid.material.opacity = .28;
    scenarioGroup.add(grid);
    return { size, centerX, centerZ };
  }

  function addAsset(asset) {
    const critical = asset.kind === 'critical';
    const color = critical ? COLORS.critical : COLORS.asset;
    const marker = new THREE.Mesh(
      new THREE.CylinderGeometry(critical ? 250 : 190, critical ? 250 : 190, critical ? 90 : 60, 12),
      material(color, .86),
    );
    marker.position.set(asset.position.x, critical ? 45 : 30, asset.position.y);
    scenarioGroup.add(marker);
    const ringGeometry = new THREE.RingGeometry(critical ? 360 : 280, critical ? 400 : 315, 32);
    ringGeometry.rotateX(-Math.PI / 2);
    const ring = new THREE.Mesh(ringGeometry, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: critical ? .65 : .35, side: THREE.DoubleSide }));
    ring.position.set(asset.position.x, 5, asset.position.y);
    scenarioGroup.add(ring);
    const element = document.createElement('div');
    element.className = `asset-label ${critical ? 'critical' : ''}`;
    element.textContent = asset.name.toUpperCase();
    container.appendChild(element);
    assetLabels.push({ element, world: new THREE.Vector3(asset.position.x, 240, asset.position.y) });
  }

  function addEntities() {
    const initial = indexes.swarmshield.frames.get(indexes.swarmshield.times[0]) || new Map();
    for (const row of initial.values()) {
      const isThreat = row.kind === 'threat';
      const mesh = new THREE.Mesh(
        isThreat ? shared.threatGeometry : shared.interceptorGeometry,
        isThreat ? shared.unassigned : shared.interceptor,
      );
      mesh.userData = { id: row.id, kind: row.kind, record: row, shared: true };
      mesh.renderOrder = 2;
      scenarioGroup.add(mesh);
      (isThreat ? threatMeshes : interceptorMeshes).set(row.id, mesh);
    }
  }

  function scenarioBounds() {
    const xs = payload.scenario.assets.map(asset => asset.position.x);
    const zs = payload.scenario.assets.map(asset => asset.position.y);
    for (const runName of ['baseline', 'swarmshield']) {
      for (const row of payload.runs[runName].trajectories) {
        xs.push(row.x); zs.push(row.y);
      }
    }
    return {
      minX: Math.min(...xs) - 1800,
      maxX: Math.max(...xs) + 1800,
      minZ: Math.min(...zs) - 1800,
      maxZ: Math.max(...zs) + 1800,
    };
  }

  function loadScenario(nextPayload) {
    payload = nextPayload;
    indexes = {
      baseline: buildRunIndex(payload.runs.baseline),
      swarmshield: buildRunIndex(payload.runs.swarmshield),
    };
    clearScenario();
    const ground = makeGround(scenarioBounds());
    payload.scenario.assets.forEach(addAsset);
    addEntities();
    const target = new THREE.Vector3(ground.centerX, 0, ground.centerZ);
    defaultCamera = {
      target,
      position: new THREE.Vector3(
        ground.centerX + ground.size * .58,
        ground.size * .62,
        ground.centerZ + ground.size * .72,
      ),
    };
    controls.minDistance = Math.max(1800, ground.size * .05);
    controls.maxDistance = ground.size * 2.6;
    camera.far = Math.max(200000, ground.size * 5);
    camera.updateProjectionMatrix();
    setCameraPreset('reset');
    lastTrailTime = null;
    setTime(0, 0);
  }

  function setStrategy(nextStrategy) {
    if (!['baseline', 'swarmshield'].includes(nextStrategy)) return;
    if (strategy !== nextStrategy) {
      strategy = nextStrategy;
      lastTrailTime = null;
      for (const line of assignmentLines.values()) line.visible = false;
      for (const trail of trails.values()) trail.visible = false;
      clearPeerLines();
    }
  }

  function positionFor(id, continuousTime) {
    const index = indexes[strategy];
    const [beforeTime, afterTime, alpha] = bracketTime(index.times, continuousTime);
    const before = index.frames.get(beforeTime)?.get(id);
    const after = index.frames.get(afterTime)?.get(id);
    if (!before && !after) return null;
    const start = simulationToWorld(before || after);
    if (!after || beforeTime === afterTime) return start;
    return start.lerp(simulationToWorld(after), alpha);
  }

  function authoritativeFrame(discreteTime) {
    return indexes[strategy]?.frames.get(discreteTime) || new Map();
  }

  function updateEntity(mesh, row, continuousTime) {
    const world = positionFor(row.id, continuousTime);
    if (world) mesh.position.copy(world);
    mesh.userData.record = row;
    if (row.kind === 'threat') {
      mesh.visible = !['intercepted', 'leaked'].includes(row.state);
      mesh.material = row.assignment ? shared.threat : shared.unassigned;
      mesh.scale.setScalar(row.risk > 55 ? 1.22 : 1);
    } else {
      mesh.visible = row.state !== 'spent';
      mesh.material = row.state === 'failed' ? shared.failed : shared.interceptor;
      mesh.scale.setScalar(row.committed ? 1.18 : 1);
    }
  }

  function getAssignmentLine(id) {
    if (assignmentLines.has(id)) return assignmentLines.get(id);
    const geometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
    const line = new THREE.Line(geometry, new THREE.LineDashedMaterial({ color: COLORS.interceptor, transparent: true, opacity: .3, dashSize: 260, gapSize: 170 }));
    line.visible = false;
    assignmentGroup.add(line);
    assignmentLines.set(id, line);
    return line;
  }

  function updateAssignments(frame) {
    for (const [id, mesh] of interceptorMeshes) {
      const line = getAssignmentLine(id);
      const record = frame.get(id);
      const targetMesh = record?.assignment ? threatMeshes.get(record.assignment) : null;
      line.visible = Boolean(visibility.assignments && mesh.visible && targetMesh?.visible);
      if (!line.visible) continue;
      const positions = line.geometry.attributes.position;
      positions.setXYZ(0, mesh.position.x, mesh.position.y, mesh.position.z);
      positions.setXYZ(1, targetMesh.position.x, targetMesh.position.y, targetMesh.position.z);
      positions.needsUpdate = true;
      line.computeLineDistances();
    }
  }

  function getTrail(id, kind) {
    if (trails.has(id)) return trails.get(id);
    const line = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: kind === 'threat' ? COLORS.threat : COLORS.interceptor, transparent: true, opacity: .32 }),
    );
    trailGroup.add(line);
    trails.set(id, line);
    return line;
  }

  function updateTrails(discreteTime, frame) {
    if (lastTrailTime === discreteTime) return;
    lastTrailTime = discreteTime;
    const index = indexes[strategy];
    const historyTimes = index.times.filter(value => value >= discreteTime - TRAIL_WINDOW_SECONDS && value <= discreteTime);
    for (const [id, row] of frame) {
      const line = getTrail(id, row.kind);
      const points = historyTimes.map(value => index.frames.get(value)?.get(id)).filter(Boolean).map(record => simulationToWorld(record));
      line.geometry.dispose();
      line.geometry = new THREE.BufferGeometry().setFromPoints(points);
      line.visible = visibility.trails && points.length > 1 && !['intercepted', 'leaked', 'spent'].includes(row.state);
    }
  }

  function latestAllocation(discreteTime) {
    const allocations = payload?.runs[strategy]?.allocations || [];
    let latest = null;
    for (const allocation of allocations) {
      if (allocation.time_s <= discreteTime) latest = allocation; else break;
    }
    return latest;
  }

  function clearPeerLines() {
    for (const line of peerLines) {
      peerGroup.remove(line);
      disposeObject(line);
    }
    peerLines = [];
  }

  function updatePeerLinks(discreteTime) {
    clearPeerLines();
    if (!visibility.peerLinks || strategy !== 'swarmshield') return;
    const allocation = latestAllocation(discreteTime);
    if (allocation?.mode !== 'peer-to-peer') return;
    const linkMaterial = new THREE.LineBasicMaterial({ color: 0x73b8ff, transparent: true, opacity: .13 });
    for (const component of allocation.components || []) {
      for (let index = 1; index < component.length; index += 1) {
        const left = interceptorMeshes.get(component[index - 1]);
        const right = interceptorMeshes.get(component[index]);
        if (!left?.visible || !right?.visible) continue;
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([left.position, right.position]), linkMaterial.clone());
        peerGroup.add(line); peerLines.push(line);
      }
    }
  }

  function updateEventFeedback(discreteTime) {
    if (!status || !payload) return;
    const event = payload.runs[strategy].events.find(item => item.time_s === discreteTime && item.type === 'collision_avoidance');
    status.hidden = !event;
    status.textContent = event ? `DECONFLICT · ${event.interceptor_id}` : '';
    for (const mesh of interceptorMeshes.values()) mesh.userData.highlight = false;
    if (event) interceptorMeshes.get(event.interceptor_id)?.scale.multiplyScalar(1.45);
  }

  function setTime(continuousTime, discreteTime = Math.round(continuousTime)) {
    if (!payload || !indexes[strategy]) return;
    currentContinuousTime = continuousTime;
    currentDiscreteTime = discreteTime;
    const frame = authoritativeFrame(discreteTime);
    for (const [id, mesh] of threatMeshes) {
      const row = frame.get(id);
      mesh.visible = Boolean(row);
      if (row) updateEntity(mesh, row, continuousTime);
    }
    for (const [id, mesh] of interceptorMeshes) {
      const row = frame.get(id);
      mesh.visible = Boolean(row);
      if (row) updateEntity(mesh, row, continuousTime);
    }
    updateAssignments(frame);
    updateTrails(discreteTime, frame);
    updatePeerLinks(discreteTime);
    updateEventFeedback(discreteTime);
  }

  function setVisibility(next) {
    visibility = { ...visibility, ...next };
    trailGroup.visible = visibility.trails;
    assignmentGroup.visible = visibility.assignments;
    peerGroup.visible = visibility.peerLinks;
    setTime(currentContinuousTime, currentDiscreteTime);
  }

  function setCameraPreset(name) {
    if (!defaultCamera) return;
    controls.target.copy(defaultCamera.target);
    if (name === 'top') {
      camera.position.copy(defaultCamera.target).add(new THREE.Vector3(0, defaultCamera.position.y * 1.18, .01));
      camera.up.set(0, 0, -1);
    } else {
      camera.up.set(0, 1, 0);
      camera.position.copy(defaultCamera.position);
    }
    camera.lookAt(controls.target);
    controls.update();
  }

  function resize() {
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function updateLabels() {
    const width = container.clientWidth;
    const height = container.clientHeight;
    for (const label of assetLabels) {
      const projected = label.world.clone().project(camera);
      const visible = projected.z > -1 && projected.z < 1;
      label.element.hidden = !visible;
      if (visible) {
        label.element.style.transform = `translate(-50%, -50%) translate(${(projected.x * .5 + .5) * width}px, ${(-projected.y * .5 + .5) * height}px)`;
      }
    }
  }

  function renderLoop() {
    if (disposed) return;
    controls.update();
    updateLabels();
    renderer.render(scene, camera);
    animationFrame = requestAnimationFrame(renderLoop);
  }

  function showDetails(event) {
    if (!details) return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const meshes = [...threatMeshes.values(), ...interceptorMeshes.values()].filter(mesh => mesh.visible);
    const hit = raycaster.intersectObjects(meshes, false)[0];
    if (!hit) { details.hidden = true; return; }
    const row = hit.object.userData.record;
    const belief = row.belief || {};
    const fields = row.kind === 'threat'
      ? [['Track', row.id], ['State', row.state], ['Decision', row.decision || 'HOLD'],
        ['Likely destination', `${belief.top_destination_id || 'UNKNOWN'} ${Math.round((belief.top_probability || 0) * 100)}%`],
        ['Uncertainty', `${belief.uncertainty_label || 'unknown'} ${Math.round((belief.uncertainty || 0) * 100)}%`],
        ['Urgency', belief.urgency ?? '--'], ['Risk', belief.risk ?? row.risk],
        ['Assigned', row.assignment || 'Unallocated']]
      : [['Interceptor', row.id], ['State', row.state], ['Class', row.class], ['Assignment', row.assignment || 'None'], ['Committed', row.committed ? 'Yes' : 'No']];
    details.innerHTML = fields.map(([key, value]) => `<span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong>`).join('');
    details.style.left = `${event.clientX - rect.left + 14}px`;
    details.style.top = `${event.clientY - rect.top + 14}px`;
    details.hidden = false;
  }

  const observer = new ResizeObserver(resize);
  observer.observe(container);
  renderer.domElement.addEventListener('pointermove', showDetails);
  renderer.domElement.addEventListener('pointerleave', () => { if (details) details.hidden = true; });

  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(animationFrame);
    observer.disconnect();
    renderer.domElement.removeEventListener('pointermove', showDetails);
    controls.dispose();
    clearScenario();
    Object.values(shared).forEach(resource => resource.dispose?.());
    renderer.dispose();
    renderer.domElement.remove();
  }

  resize();
  renderLoop();
  return { loadScenario, setStrategy, setTime, setVisibility, setCameraPreset, resize, dispose };
}
