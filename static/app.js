const canvas = document.querySelector('#tacticalMap');
const ctx = canvas.getContext('2d');
const slider = document.querySelector('#timeSlider');
const playButton = document.querySelector('#playButton');
let data = null;
let strategy = 'swarmshield';
let time = 0;
let playing = false;
let lastStamp = 0;
let duration = 190;
let frames = { baseline: new Map(), swarmshield: new Map() };
let frameTimes = { baseline: [], swarmshield: [] };

const colors = { threat: '#ff6678', interceptor: '#9df5bf', amber: '#ffbd59', grid: 'rgba(136,184,160,.10)' };
let bounds = { minX: -12000, maxX: 12000, minY: -6500, maxY: 20000 };
let fullBounds = bounds;
let cityBounds = bounds;
let cityFocus = false;
const mapPoint = (x, y) => ({ x: ((x - bounds.minX) / (bounds.maxX - bounds.minX)) * canvas.width, y: canvas.height - ((y - bounds.minY) / (bounds.maxY - bounds.minY)) * canvas.height });
const byTime = (records, t) => records.filter(row => row.t === t);
const fmt = n => Number(n).toLocaleString(undefined, { maximumFractionDigits: 1 });
function consequenceAt(asset, atTime) {
  let value = asset.consequence;
  for (const event of data.scenario.scripted_events) {
    if (event.time_s > atTime) break;
    if (event.type === 'asset_consequence_change' && event.asset_id === asset.id) value = event.new_consequence;
  }
  return value;
}
function latestFrameTime(name, requested) {
  const times = frameTimes[name];
  let low = 0, high = times.length - 1, answer = times[0] || 0;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (times[mid] <= requested) { answer = times[mid]; low = mid + 1; }
    else high = mid - 1;
  }
  return answer;
}

function drawBackground() {
  ctx.fillStyle = '#08120f'; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = colors.grid; ctx.lineWidth = 1;
  for (let x = 0; x <= canvas.width; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke(); }
  for (let y = 0; y <= canvas.height; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke(); }
  const urban = data.scenario.assets.filter(asset => asset.kind !== 'low-consequence');
  const sites = urban.length ? urban : data.scenario.assets;
  const city = {
    left: Math.min(...sites.map(a => a.position.x)) - 2400,
    right: Math.max(...sites.map(a => a.position.x)) + 2400,
    bottom: Math.min(...sites.map(a => a.position.y)) - 2500,
    top: Math.max(...sites.map(a => a.position.y)) + 2600,
  };
  const west = mapPoint(city.left, city.top);
  const east = mapPoint(city.right, city.bottom);
  const coast = mapPoint(city.left - 900, 0).x;
  ctx.fillStyle = 'rgba(28,69,86,.32)'; ctx.fillRect(0, 0, Math.max(0, coast), canvas.height);
  ctx.strokeStyle = 'rgba(115,184,255,.46)'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(coast, 0); ctx.lineTo(coast + 8, canvas.height * .35); ctx.lineTo(coast - 8, canvas.height); ctx.stroke();
  ctx.fillStyle = 'rgba(30,55,47,.56)';
  ctx.fillRect(west.x, west.y, east.x - west.x, east.y - west.y);
  ctx.save();
  ctx.beginPath(); ctx.rect(west.x, west.y, east.x - west.x, east.y - west.y); ctx.clip();
  const block = Math.max(1350, (city.right - city.left) / 15, (city.top - city.bottom) / 10);
  for (let x = city.left, i = 0; x < city.right; x += block, i++) {
    for (let y = city.bottom, j = 0; y < city.top; y += block, j++) {
      const a = mapPoint(x + block * .13, y + block * .13);
      const b = mapPoint(x + block * .87, y + block * .87);
      ctx.fillStyle = (i * 7 + j * 11) % 9 === 0 ? 'rgba(48,101,67,.36)' : 'rgba(93,130,111,.17)';
      ctx.fillRect(a.x, b.y, Math.max(1, b.x - a.x), Math.max(1, a.y - b.y));
    }
  }
  ctx.strokeStyle = 'rgba(174,194,181,.22)'; ctx.lineWidth = 3;
  for (let x = city.left; x <= city.right; x += block) {
    const a = mapPoint(x, city.bottom), b = mapPoint(x, city.top);
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }
  for (let y = city.bottom; y <= city.top; y += block) {
    const a = mapPoint(city.left, y), b = mapPoint(city.right, y);
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }
  ctx.restore();
  ctx.fillStyle = '#9ab8aa'; ctx.font = '11px system-ui';
  ctx.fillText('CITY DISTRICTS', west.x + 12, west.y + 19);
  for (const asset of data.scenario.assets) {
    const p = mapPoint(asset.position.x, asset.position.y);
    const edge = mapPoint(asset.position.x + asset.radius_m, asset.position.y);
    const radius = Math.max(5, Math.abs(edge.x - p.x));
    const critical = consequenceAt(asset, time) >= 75;
    ctx.fillStyle = critical ? 'rgba(255,189,89,.13)' : 'rgba(115,184,255,.12)';
    ctx.strokeStyle = critical ? 'rgba(255,189,89,.72)' : 'rgba(115,184,255,.52)';
    ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(p.x, p.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#e8f1ea'; ctx.font = '11px system-ui'; ctx.fillText(asset.name.toUpperCase(), p.x + radius + 5, p.y + 4);
  }
  const scalePx = 5000 / (bounds.maxX - bounds.minX) * canvas.width;
  ctx.strokeStyle = '#c3d3cb'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(canvas.width - 28 - scalePx, canvas.height - 27); ctx.lineTo(canvas.width - 28, canvas.height - 27); ctx.stroke();
  ctx.fillStyle = '#c3d3cb'; ctx.font = '10px ui-monospace'; ctx.fillText('5 km', canvas.width - 28 - scalePx, canvas.height - 34);
  ctx.fillText('N ↑', canvas.width - 46, 34);
}

function draw() {
  if (!data) return;
  drawBackground();
  const run = data.runs[strategy];
  const sampleTime = latestFrameTime(strategy, Math.round(time));
  const rows = frames[strategy].get(sampleTime) || [];
  const assignments = new Map(rows.filter(r => r.kind === 'interceptor' && r.assignment).map(r => [r.assignment, r.id]));
  const threatRows = new Map(rows.filter(r => r.kind === 'threat').map(r => [r.id, r]));
  ctx.setLineDash([6, 8]);
  for (const interceptor of rows.filter(r => r.kind === 'interceptor' && r.assignment)) {
    const target = threatRows.get(interceptor.assignment); if (!target) continue;
    const a = mapPoint(interceptor.x, interceptor.y), b = mapPoint(target.x, target.y);
    ctx.strokeStyle = 'rgba(157,245,191,.28)'; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }
  ctx.setLineDash([]);
  for (const row of rows.filter(r => r.kind === 'threat')) {
    if (row.state === 'intercepted') continue;
    const p = mapPoint(row.x, row.y); const assigned = assignments.has(row.id);
    ctx.fillStyle = assigned ? colors.threat : colors.amber;
    ctx.beginPath(); ctx.moveTo(p.x, p.y + 7); ctx.lineTo(p.x - 5, p.y - 5); ctx.lineTo(p.x + 5, p.y - 5); ctx.closePath(); ctx.fill();
    if (row.risk > 55) { ctx.strokeStyle = 'rgba(255,102,120,.28)'; ctx.beginPath(); ctx.arc(p.x,p.y,11,0,Math.PI*2); ctx.stroke(); }
    ctx.fillStyle = '#d5e1da'; ctx.font = '10px ui-monospace'; ctx.fillText(row.id, p.x + 7, p.y - 7);
  }
  for (const row of rows.filter(r => r.kind === 'interceptor')) {
    if (row.state === 'spent') continue;
    const p = mapPoint(row.x, row.y);
    ctx.fillStyle = row.state === 'failed' ? '#59645f' : colors.interceptor;
    ctx.beginPath(); ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#9fb1a8'; ctx.font = '9px ui-monospace'; ctx.fillText(row.id, p.x + 7, p.y + 3);
  }
  document.querySelector('#timeLabel').textContent = `T+${String(Math.round(time)).padStart(3, '0')} s${sampleTime !== Math.round(time) ? ` · view T+${String(sampleTime).padStart(3, '0')}` : ''}`;
  updateEvent(run);
  updateNetwork(run);
  renderDecisionAudit(rows);
}

function updateEvent(run) {
  const banner = document.querySelector('#eventBanner');
  const event = run.events.find(e => Math.abs(e.time_s - time) < 1.3 && [
    'threat_diversion','confidence_update','asset_consequence_change','interceptor_failure',
    'failure_recovery','ground_link_loss','ground_link_restore','peer_link_degradation',
    'reassignment','peer_conflict','stale_event'
  ].includes(e.type));
  if (event) { banner.textContent = event.label.toUpperCase(); banner.classList.add('show'); } else banner.classList.remove('show');
}

function updateNetwork(run) {
  let ground = true;
  for (const event of data.scenario.scripted_events) {
    if (event.time_s > time) break;
    if (event.type === 'ground_link_loss') ground = false;
    if (event.type === 'ground_link_restore') ground = true;
  }
  const snapshot = [...run.allocations].reverse().find(item => item.time_s <= time);
  const groups = !ground && strategy === 'swarmshield' ? (snapshot?.components || []) : [];
  const conflictsSoFar = run.events.filter(event => event.type === 'peer_conflict' && event.time_s <= time).length;
  document.querySelector('#networkMode').textContent = ground ? 'GROUND CUE · SIM' : strategy === 'swarmshield' ? `PEER MODE · ${groups.length} ${groups.length === 1 ? 'GROUP' : 'GROUPS'}` : 'LINK LOST';
  document.querySelector('#networkDetail').textContent = ground
    ? 'Ground coordination available in the model. No physical link is connected.'
    : strategy === 'swarmshield'
      ? `Local visibility only. ${conflictsSoFar} conflicting claims observed so far; no packet transport is modeled.`
      : 'Static baseline keeps its initial assignments after ground-link loss.';
  const peers = document.querySelector('#networkPeers');
  peers.replaceChildren();
  const labels = groups.length ? groups.slice(0, 4).map((group, index) => `G${index + 1}:${group.length}`) : [ground ? 'GROUND' : 'NO PEERS'];
  for (const label of labels) {
    const chip = document.createElement('span'); chip.textContent = label; peers.appendChild(chip);
  }
}

function renderDecisionAudit(rows) {
  const targets = rows.filter(row => row.kind === 'threat' && row.state === 'active').sort((a, b) => b.risk - a.risk);
  const claims = new Map();
  for (const row of rows.filter(item => item.kind === 'interceptor' && item.assignment)) {
    const list = claims.get(row.assignment) || [];
    list.push(row.id); claims.set(row.assignment, list);
  }
  const assetNames = new Map(data.scenario.assets.map(asset => [asset.id, asset.name]));
  const unassigned = targets.filter(target => !claims.has(target.id)).length;
  document.querySelector('#prioritySubtitle').textContent = `${targets.length} active tracks · ${unassigned} unassigned now · priorities update with new information.`;
  const list = document.querySelector('#decisionList');
  list.replaceChildren();
  for (const target of targets.slice(0, 10)) {
    const item = document.createElement('div'); item.className = 'decision';
    const id = document.createElement('strong'); id.textContent = target.id;
    const middle = document.createElement('div');
    const info = document.createElement('small');
    info.textContent = `${assetNames.get(target.asset_id) || target.asset_id} · priority ${fmt(target.risk)} · confidence ${Math.round(target.confidence * 100)}%`;
    const bar = document.createElement('div'); bar.className = 'bar';
    const fill = document.createElement('i'); fill.style.width = `${Math.min(100, target.risk)}%`;
    bar.appendChild(fill); middle.append(info, bar);
    const decision = document.createElement('em'); decision.textContent = (claims.get(target.id) || []).join(' + ') || 'UNASSIGNED';
    item.append(id, middle, decision); list.appendChild(item);
  }
  if (targets.length > 10) {
    const more = document.createElement('small'); more.textContent = `+ ${targets.length - 10} more active tracks`;
    list.appendChild(more);
  }
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
}

function renderComparison() {
  const b = data.runs.baseline.metrics, s = data.runs.swarmshield.metrics;
  const rows = [['METRIC','NAIVE','SWARMSHIELD'],['Total leakage',b.leakage,s.leakage],['Critical leaks',b.critical_leaks,s.critical_leaks],['Expected consequence',b.expected_consequence_leaked,s.expected_consequence_leaked],['Defensive cost',b.defensive_cost,s.defensive_cost],['Retasks',b.reassignments,s.reassignments],['Peer claim conflicts',b.peer_conflict_snapshots,s.peer_conflict_snapshots]];
  const table = document.querySelector('#comparisonTable'); table.replaceChildren();
  for (const [index, row] of rows.entries()) {
    for (const cell of row) {
      const element = document.createElement('div'); element.textContent = cell;
      if (index === 0) element.className = 'head';
      table.appendChild(element);
    }
  }
}

function animate(stamp) {
  if (!playing) return;
  if (!lastStamp) lastStamp = stamp;
  if (stamp - lastStamp > 100) { time += 1; slider.value = time; lastStamp = stamp; draw(); }
  if (time >= duration) { playing = false; playButton.textContent = '↻ Replay engagement'; } else requestAnimationFrame(animate);
}

playButton.addEventListener('click', () => { if (time >= duration) { time = 0; slider.value = 0; } playing = !playing; playButton.textContent = playing ? '❚❚ Pause' : '▶ Resume'; lastStamp = 0; if (playing) requestAnimationFrame(animate); });
slider.addEventListener('input', event => { time = Number(event.target.value); draw(); });
document.querySelector('#mapViewButton').addEventListener('click', () => {
  cityFocus = !cityFocus;
  bounds = cityFocus ? cityBounds : fullBounds;
  document.querySelector('#mapViewButton').textContent = cityFocus ? 'Full approach' : 'City close-up';
  document.querySelector('#mapCaption').textContent = cityFocus
    ? 'CITY CLOSE-UP · OFFSCREEN TRACKS OMITTED'
    : 'SYNTHETIC CITY · METRE SCALE · NOT GIS DATA';
  draw();
});
document.querySelectorAll('[data-strategy]').forEach(button => button.addEventListener('click', () => { strategy = button.dataset.strategy; document.querySelectorAll('[data-strategy]').forEach(b => b.classList.toggle('active', b === button)); renderMetrics(); draw(); }));

async function loadScenario() {
  playing = false; playButton.textContent = '▶ Run engagement'; time = 0; slider.value = 0;
  const threats = Number(document.querySelector('#threatCount').value);
  const interceptors = Number(document.querySelector('#interceptorCount').value);
  const seed = Number(document.querySelector('#seedValue').value);
  const requestedDuration = Number(document.querySelector('#durationValue').value);
  const profile = document.querySelector('#profileValue').value;
  const events = document.querySelector('#eventsEnabled').checked ? 1 : 0;
  document.querySelector('#systemStatus').textContent = 'GENERATING SCENARIO…';
  const response = await fetch(`/api/run?threats=${threats}&interceptors=${interceptors}&seed=${seed}&duration=${requestedDuration}&events=${events}&profile=${encodeURIComponent(profile)}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Scenario generation failed');
  installPayload(payload);
  document.querySelector('#systemStatus').textContent = `SCENARIO READY / SEED ${seed}`;
}

function installPayload(payload) {
  data = payload; duration = data.scenario.duration_s; slider.max = duration;
  frames = { baseline: new Map(), swarmshield: new Map() };
  frameTimes = { baseline: [], swarmshield: [] };
  for (const name of ['baseline', 'swarmshield']) {
    for (const row of data.runs[name].trajectories) {
      if (!frames[name].has(row.t)) frames[name].set(row.t, []);
      frames[name].get(row.t).push(row);
    }
    frameTimes[name] = [...frames[name].keys()].sort((a, b) => a - b);
  }
  const initialRows = data.runs.swarmshield.trajectories.filter(row => row.t === 0);
  const xs = [...initialRows.map(row => row.x), ...data.scenario.assets.map(asset => asset.position.x)];
  const ys = [...initialRows.map(row => row.y), ...data.scenario.assets.map(asset => asset.position.y)];
  fullBounds = { minX: Math.min(...xs) - 3000, maxX: Math.max(...xs) + 3000, minY: Math.min(...ys) - 3200, maxY: Math.max(...ys) + 1400 };
  const cityAssets = data.scenario.assets.filter(asset => asset.kind !== 'low-consequence');
  const sites = cityAssets.length ? cityAssets : data.scenario.assets;
  cityBounds = {
    minX: Math.min(...sites.map(asset => asset.position.x - asset.radius_m)) - 1800,
    maxX: Math.max(...sites.map(asset => asset.position.x + asset.radius_m)) + 1800,
    minY: Math.min(...sites.map(asset => asset.position.y - asset.radius_m)) - 1800,
    maxY: Math.max(...sites.map(asset => asset.position.y + asset.radius_m)) + 3500,
  };
  cityFocus = false; bounds = fullBounds;
  document.querySelector('#mapViewButton').textContent = 'City close-up';
  document.querySelector('#mapCaption').textContent = 'SYNTHETIC CITY · METRE SCALE · NOT GIS DATA';
  document.querySelector('#scenarioTitle').textContent = data.scenario.name;
  document.querySelector('#threatCount').value = data.scenario.threat_count;
  document.querySelector('#interceptorCount').value = data.scenario.interceptor_count;
  document.querySelector('#durationValue').value = duration;
  if (data.scenario.seed !== null) document.querySelector('#seedValue').value = data.scenario.seed;
  if (['mixed','concentrated','dispersed','uncertain'].includes(data.scenario.profile)) document.querySelector('#profileValue').value = data.scenario.profile;
  document.querySelector('#eventsEnabled').checked = data.scenario.scripted_events.length > 0;
  document.querySelector('#sameRaidLabel').textContent = `SAME RAID. SAME ${data.scenario.interceptor_count} ${data.scenario.interceptor_count === 1 ? 'ROUND' : 'ROUNDS'}.`;
  const sampleStep = data.runs.swarmshield.visual_sample_step_s;
  document.querySelector('#compressionLabel').textContent = `UP TO 10× PLAYBACK${sampleStep > 1 ? ` · ${sampleStep} s VISUAL SAMPLES` : ''}`;
  document.querySelector('#eventBanner').textContent = `${data.scenario.threat_count} ${data.scenario.threat_count === 1 ? 'TRACK' : 'TRACKS'} / ${data.scenario.interceptor_count} ${data.scenario.interceptor_count === 1 ? 'INTERCEPTOR' : 'INTERCEPTORS'}`;
  renderMetrics(); renderComparison(); draw();
  document.querySelector('#customJson').value = JSON.stringify(data.scenario.definition, null, 2);
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
  } catch (error) {
    document.querySelector('#systemStatus').textContent = error.message.toUpperCase();
    console.error(error);
  }
});

loadScenario().catch(err => { document.querySelector('#systemStatus').textContent = 'MODEL LOAD FAILED'; console.error(err); });
