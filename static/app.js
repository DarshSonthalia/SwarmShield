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

const colors = { threat: '#ff6678', interceptor: '#9df5bf', amber: '#ffbd59', grid: 'rgba(136,184,160,.10)' };
let bounds = { minX: -12000, maxX: 12000, minY: -6500, maxY: 20000 };
const mapPoint = (x, y) => ({ x: ((x - bounds.minX) / (bounds.maxX - bounds.minX)) * canvas.width, y: canvas.height - ((y - bounds.minY) / (bounds.maxY - bounds.minY)) * canvas.height });
const byTime = (records, t) => records.filter(row => row.t === t);
const fmt = n => Number(n).toLocaleString(undefined, { maximumFractionDigits: 1 });

function drawBackground() {
  ctx.fillStyle = '#08120f'; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = colors.grid; ctx.lineWidth = 1;
  for (let x = 0; x <= canvas.width; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke(); }
  for (let y = 0; y <= canvas.height; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke(); }
  const coast = mapPoint(0, -1000).y;
  ctx.fillStyle = 'rgba(35,82,97,.16)'; ctx.fillRect(0, coast, canvas.width, canvas.height - coast);
  ctx.strokeStyle = 'rgba(115,184,255,.25)'; ctx.beginPath(); ctx.moveTo(0, coast); ctx.lineTo(canvas.width, coast); ctx.stroke();
  for (const asset of data.scenario.assets) {
    const p = mapPoint(asset.position.x, asset.position.y);
    ctx.strokeStyle = asset.kind === 'critical' ? 'rgba(255,189,89,.75)' : 'rgba(157,245,191,.45)';
    ctx.strokeRect(p.x - 7, p.y - 7, 14, 14);
    ctx.fillStyle = '#8da49a'; ctx.font = '11px system-ui'; ctx.fillText(asset.name.toUpperCase(), p.x + 12, p.y + 4);
  }
}

function draw() {
  if (!data) return;
  drawBackground();
  const run = data.runs[strategy];
  const rows = frames[strategy].get(Math.round(time)) || [];
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
  document.querySelector('#timeLabel').textContent = `T+${String(Math.round(time)).padStart(3, '0')} s`;
  updateEvent(run);
  updateNetwork();
}

function updateEvent(run) {
  const banner = document.querySelector('#eventBanner');
  const event = run.events.find(e => Math.abs(e.time_s - time) < 1.3 && ['threat_diversion','interceptor_failure','failure_recovery','ground_link_loss','reassignment','collision_avoidance'].includes(e.type));
  if (event) { banner.textContent = event.label.toUpperCase(); banner.classList.add('show'); } else banner.classList.remove('show');
}

function updateNetwork() {
  const loss = data.scenario.scripted_events.find(event => event.type === 'ground_link_loss');
  const peer = Boolean(loss && time >= loss.time_s);
  document.querySelector('#networkMode').textContent = peer ? (strategy === 'swarmshield' ? 'P2P ACTIVE' : 'LINK LOST') : 'GROUND LINK';
  document.querySelector('#networkDetail').textContent = peer ? (strategy === 'swarmshield' ? 'Ground cue unavailable. Connected peer groups continue local allocation.' : 'The static baseline does not reallocate after link loss.') : 'Ground cue available.';
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
  const decisions = [...data.runs[strategy].decisions].sort((a,b) => b.risk-a.risk).slice(0,9);
  document.querySelector('#decisionList').innerHTML = decisions.map(d => `<div class="decision"><strong>${d.threat_id}</strong><div><small>RISK ${fmt(d.risk)}</small><div class="bar"><i style="width:${Math.min(100,d.risk)}%"></i></div></div><em>${d.initial_decision === 'intercept' ? d.interceptor_id : 'UNALLOCATED'}</em></div>`).join('');
}

function renderComparison() {
  const b = data.runs.baseline.metrics, s = data.runs.swarmshield.metrics;
  const rows = [['METRIC','NAIVE','SWARMSHIELD'],['Total leakage',b.leakage,s.leakage],['Critical leaks',b.critical_leaks,s.critical_leaks],['Expected consequence',b.expected_consequence_leaked,s.expected_consequence_leaked],['Defensive cost',b.defensive_cost,s.defensive_cost],['Retasks',b.reassignments,s.reassignments]];
  document.querySelector('#comparisonTable').innerHTML = rows.flatMap((row,i) => row.map((cell,j) => `<div class="${i===0?'head':(j===2?'better':'')}">${cell}</div>`)).join('');
}

function animate(stamp) {
  if (!playing) return;
  if (!lastStamp) lastStamp = stamp;
  if (stamp - lastStamp > 100) { time += 1; slider.value = time; lastStamp = stamp; draw(); }
  if (time >= duration) { playing = false; playButton.textContent = '↻ Replay engagement'; } else requestAnimationFrame(animate);
}

playButton.addEventListener('click', () => { if (time >= duration) { time = 0; slider.value = 0; } playing = !playing; playButton.textContent = playing ? '❚❚ Pause' : '▶ Resume'; lastStamp = 0; if (playing) requestAnimationFrame(animate); });
slider.addEventListener('input', event => { time = Number(event.target.value); draw(); });
document.querySelectorAll('[data-strategy]').forEach(button => button.addEventListener('click', () => { strategy = button.dataset.strategy; document.querySelectorAll('[data-strategy]').forEach(b => b.classList.toggle('active', b === button)); renderMetrics(); draw(); }));

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
  data = payload; duration = data.scenario.duration_s; slider.max = duration;
  frames = { baseline: new Map(), swarmshield: new Map() };
  for (const name of ['baseline', 'swarmshield']) {
    for (const row of data.runs[name].trajectories) {
      if (!frames[name].has(row.t)) frames[name].set(row.t, []);
      frames[name].get(row.t).push(row);
    }
  }
  const initialRows = data.runs.swarmshield.trajectories.filter(row => row.t === 0);
  const xs = [...initialRows.map(row => row.x), ...data.scenario.assets.map(asset => asset.position.x)];
  const ys = [...initialRows.map(row => row.y), ...data.scenario.assets.map(asset => asset.position.y)];
  bounds = { minX: Math.min(...xs) - 1600, maxX: Math.max(...xs) + 1600, minY: Math.min(...ys) - 1200, maxY: Math.max(...ys) + 1400 };
  document.querySelector('#scenarioTitle').textContent = data.scenario.name;
  document.querySelector('#threatCount').value = data.scenario.threat_count;
  document.querySelector('#interceptorCount').value = data.scenario.interceptor_count;
  document.querySelector('#durationValue').value = duration;
  document.querySelector('#eventsEnabled').checked = data.scenario.scripted_events.length > 0;
  document.querySelector('#sameRaidLabel').textContent = `SAME RAID. SAME ${data.scenario.interceptor_count} ${data.scenario.interceptor_count === 1 ? 'ROUND' : 'ROUNDS'}.`;
  document.querySelector('#compressionLabel').textContent = `SIM / ${(duration / 30).toFixed(1)}× DEMO COMPRESSION`;
  document.querySelector('#eventBanner').textContent = `${data.scenario.threat_count} ${data.scenario.threat_count === 1 ? 'TRACK' : 'TRACKS'} / ${data.scenario.interceptor_count} ${data.scenario.interceptor_count === 1 ? 'INTERCEPTOR' : 'INTERCEPTORS'}`;
  const peers = data.scenario.definition.interceptors.slice(0, 4).map(item => item.id);
  document.querySelector('#networkPeers').innerHTML = peers.length ? peers.map(id => `<span>${id}</span>`).join('') : '<small>NO PEERS</small>';
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
