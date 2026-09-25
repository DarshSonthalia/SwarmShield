import { initTactical3D } from './tactical3d.js';

const slider = document.querySelector('#timeSlider');
const playButton = document.querySelector('#playButton');
const viewer = initTactical3D(document.querySelector('#tacticalScene'), {
  detailsElement: document.querySelector('#entityDetails'),
  statusElement: document.querySelector('#sceneStatus'),
});

let data = null;
let strategy = 'swarmshield';
let time = 0;
let playing = false;
let lastStamp = 0;
let duration = 190;
let frameTimes = { baseline: [], swarmshield: [] };

const fmt = number => Number(number).toLocaleString(undefined, { maximumFractionDigits: 1 });

function nearestAvailableTime(times, value) {
  if (!times.length) return 0;
  let nearest = times[0];
  let distance = Math.abs(value - nearest);
  for (const candidate of times) {
    const nextDistance = Math.abs(value - candidate);
    if (nextDistance < distance) { nearest = candidate; distance = nextDistance; }
    if (candidate > value && nextDistance > distance) break;
  }
  return nearest;
}

function allocationAt(run, discreteTime) {
  let current = run.allocations[0] || null;
  for (const snapshot of run.allocations) {
    if (snapshot.time_s <= discreteTime) current = snapshot; else break;
  }
  return current;
}

function updateEvent(run, discreteTime) {
  const banner = document.querySelector('#eventBanner');
  const visibleTypes = new Set(['threat_diversion', 'interceptor_failure', 'failure_recovery', 'ground_link_loss', 'reassignment', 'collision_avoidance', 'intercept', 'leak']);
  const event = run.events.find(item => item.time_s === discreteTime && visibleTypes.has(item.type));
  if (event) { banner.textContent = event.label.toUpperCase(); banner.classList.add('show'); }
  else banner.classList.remove('show');
}

function updateNetwork(discreteTime) {
  const run = data.runs[strategy];
  const allocation = allocationAt(run, discreteTime);
  const loss = run.events.find(event => event.type === 'ground_link_loss' && event.time_s <= discreteTime);
  const peer = strategy === 'swarmshield' && allocation?.mode === 'peer-to-peer';
  document.querySelector('#networkMode').textContent = peer ? 'P2P ACTIVE' : loss ? 'LINK LOST' : 'GROUND LINK';
  document.querySelector('#networkDetail').textContent = peer
    ? 'Ground cue unavailable. Simulated connected peer groups continue local allocation.'
    : loss ? 'Ground cue unavailable. The static baseline does not reallocate.'
      : 'Central cue available. Decisions remain locally executable.';
  const peers = (allocation?.components?.find(items => items.length) || []).slice(0, 4);
  document.querySelector('#networkPeers').innerHTML = peers.length ? peers.map(id => `<span>${id}</span>`).join('') : '<small>NO ACTIVE PEERS</small>';
}

function renderMetrics() {
  const metrics = data.runs[strategy].metrics;
  const change = data.headline.expected_consequence_reduction_percent;
  document.querySelector('#reductionMetric').textContent = strategy === 'swarmshield' ? fmt(Math.abs(change)) : '0';
  document.querySelector('#reductionLabel').textContent = strategy === 'baseline' ? 'baseline reference' : change > 0 ? 'lower expected consequence of leakage' : change < 0 ? 'higher expected consequence of leakage' : 'same expected consequence of leakage';
  document.querySelector('#criticalMetric').textContent = metrics.critical_leaks;
  document.querySelector('#leakageMetric').textContent = metrics.leakage;
  document.querySelector('#costMetric').textContent = fmt(metrics.defensive_cost);
  document.querySelector('#reassignMetric').textContent = metrics.reassignments;
  const decisions = [...data.runs[strategy].decisions].sort((left, right) => right.risk - left.risk).slice(0, 9);
  document.querySelector('#decisionList').innerHTML = decisions.map(decision => `<div class="decision"><strong>${decision.threat_id}</strong><div><small>RISK ${fmt(decision.risk)}</small><div class="bar"><i style="width:${Math.min(100, decision.risk)}%"></i></div></div><em>${decision.initial_decision === 'intercept' ? decision.interceptor_id : 'UNALLOCATED'}</em></div>`).join('');
}

function renderComparison() {
  const baseline = data.runs.baseline.metrics;
  const shield = data.runs.swarmshield.metrics;
  const rows = [['METRIC', 'NAIVE', 'SWARMSHIELD'], ['Total leakage', baseline.leakage, shield.leakage], ['Critical leaks', baseline.critical_leaks, shield.critical_leaks], ['Expected consequence', baseline.expected_consequence_leaked, shield.expected_consequence_leaked], ['Defensive cost', baseline.defensive_cost, shield.defensive_cost], ['Retasks', baseline.reassignments, shield.reassignments]];
  document.querySelector('#comparisonTable').innerHTML = rows.flatMap((row, rowIndex) => row.map((cell, columnIndex) => `<div class="${rowIndex === 0 ? 'head' : columnIndex === 2 ? 'better' : ''}">${cell}</div>`)).join('');
}

function renderFrame() {
  if (!data) return;
  const discreteTime = nearestAvailableTime(frameTimes[strategy], time);
  viewer.setStrategy(strategy);
  viewer.setTime(time, discreteTime);
  document.querySelector('#timeLabel').textContent = `T+${String(Math.round(time)).padStart(3, '0')} s`;
  updateEvent(data.runs[strategy], discreteTime);
  updateNetwork(discreteTime);
}

function animate(stamp) {
  if (!playing) return;
  if (!lastStamp) lastStamp = stamp;
  const elapsed = Math.min((stamp - lastStamp) / 1000, .25);
  lastStamp = stamp;
  time = Math.min(duration, time + elapsed * (duration / 30));
  slider.value = time;
  renderFrame();
  if (time >= duration) { playing = false; playButton.textContent = '↻ Replay engagement'; }
  else requestAnimationFrame(animate);
}

playButton.addEventListener('click', () => {
  if (time >= duration) { time = 0; slider.value = 0; }
  playing = !playing;
  playButton.textContent = playing ? '❚❚ Pause' : '▶ Resume';
  lastStamp = 0;
  if (playing) requestAnimationFrame(animate);
});

slider.addEventListener('input', event => {
  playing = false;
  playButton.textContent = '▶ Resume';
  time = Number(event.target.value);
  renderFrame();
});

document.querySelectorAll('[data-strategy]').forEach(button => button.addEventListener('click', () => {
  strategy = button.dataset.strategy;
  document.querySelectorAll('[data-strategy]').forEach(item => item.classList.toggle('active', item === button));
  viewer.setStrategy(strategy);
  renderMetrics();
  renderFrame();
}));

document.querySelectorAll('[data-camera]').forEach(button => button.addEventListener('click', () => viewer.setCameraPreset(button.dataset.camera)));

function updateVisibility() {
  viewer.setVisibility({
    trails: document.querySelector('#showTrails').checked,
    assignments: document.querySelector('#showAssignments').checked,
    peerLinks: document.querySelector('#showPeerLinks').checked,
  });
}

for (const id of ['showTrails', 'showAssignments', 'showPeerLinks']) document.querySelector(`#${id}`).addEventListener('change', updateVisibility);

async function loadScenario() {
  playing = false; playButton.textContent = '▶ Run engagement'; time = 0; slider.value = 0;
  const threats = Number(document.querySelector('#threatCount').value);
  const interceptors = Number(document.querySelector('#interceptorCount').value);
  const seed = Number(document.querySelector('#seedValue').value);
  const requestedDuration = Number(document.querySelector('#durationValue').value);
  const events = document.querySelector('#eventsEnabled').checked ? 1 : 0;
  document.querySelector('#systemStatus').textContent = 'GENERATING SCENARIO…';
  const response = await fetch(`/api/run?threats=${threats}&interceptors=${interceptors}&seed=${seed}&duration=${requestedDuration}&events=${events}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Scenario generation failed');
  installPayload(payload);
  document.querySelector('#systemStatus').textContent = `SCENARIO READY / SEED ${seed}`;
}

function installPayload(payload) {
  data = payload; duration = data.scenario.duration_s; slider.max = duration; slider.step = .1;
  frameTimes = { baseline: [], swarmshield: [] };
  for (const name of ['baseline', 'swarmshield']) frameTimes[name] = [...new Set(data.runs[name].trajectories.map(row => row.t))].sort((left, right) => left - right);
  viewer.loadScenario(payload);
  viewer.setStrategy(strategy);
  document.querySelector('#scenarioTitle').textContent = data.scenario.name;
  document.querySelector('#threatCount').value = data.scenario.threat_count;
  document.querySelector('#interceptorCount').value = data.scenario.interceptor_count;
  document.querySelector('#durationValue').value = duration;
  document.querySelector('#eventsEnabled').checked = data.scenario.scripted_events.length > 0;
  document.querySelector('#sameRaidLabel').textContent = `SAME RAID. SAME ${data.scenario.interceptor_count} ${data.scenario.interceptor_count === 1 ? 'ROUND' : 'ROUNDS'}.`;
  document.querySelector('#compressionLabel').textContent = `SIM / ${(duration / 30).toFixed(1)}× DEMO COMPRESSION`;
  document.querySelector('#eventBanner').textContent = `${data.scenario.threat_count} TRACKS / ${data.scenario.interceptor_count} INTERCEPTORS`;
  document.querySelector('#customJson').value = JSON.stringify(data.scenario.definition, null, 2);
  renderMetrics(); renderComparison(); updateVisibility(); renderFrame();
}

document.querySelector('#scenarioForm').addEventListener('submit', event => {
  event.preventDefault();
  loadScenario().catch(error => { document.querySelector('#systemStatus').textContent = error.message.toUpperCase(); console.error(error); });
});

document.querySelector('#loadTemplate').addEventListener('click', () => {
  if (data) document.querySelector('#customJson').value = JSON.stringify(data.scenario.definition, null, 2);
});

document.querySelector('#runCustom').addEventListener('click', async () => {
  playing = false; playButton.textContent = '▶ Run engagement'; time = 0; slider.value = 0;
  document.querySelector('#systemStatus').textContent = 'RUNNING CUSTOM SCENARIO…';
  try {
    const scenario = JSON.parse(document.querySelector('#customJson').value);
    const response = await fetch('/api/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(scenario) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Custom scenario failed');
    installPayload(payload);
    document.querySelector('#systemStatus').textContent = 'CUSTOM SCENARIO READY';
  } catch (error) { document.querySelector('#systemStatus').textContent = error.message.toUpperCase(); console.error(error); }
});

window.addEventListener('beforeunload', () => viewer.dispose());
loadScenario().catch(error => { document.querySelector('#systemStatus').textContent = 'MODEL LOAD FAILED'; console.error(error); });
