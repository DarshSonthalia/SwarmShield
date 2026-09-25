# Uncertainty-Aware Threat Beliefs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace known-destination allocation with deterministic observation-only destination beliefs while retaining the baseline-versus-SwarmShield comparison and operational 3D UI.

**Architecture:** A new pure `belief.py` module converts bounded `TrackObservation` histories into `ThreatBelief` values without accepting `Threat` or `asset_id`. The simulator owns histories and belief cadence, both allocators consume the same observed tracks and belief-derived horizon, and ground truth remains confined to physics and post-decision evaluation.

**Tech Stack:** Python 3.11 standard library/dataclasses/unittest, existing Hungarian allocator and `ThreadingHTTPServer`, ES modules, vendored Three.js r186, HTML/CSS.

## Global Constraints

- Keep exactly two strategies: naive nearest-feasible baseline and uncertainty-aware SwarmShield.
- `Threat.asset_id` is ground truth for trajectory physics, diversion, terminal leakage, and post-decision evaluation only.
- Belief, risk, prioritization, feasibility, allocation, operational snapshots, and normal UI must not read or reveal true destination.
- Beliefs are deterministic geometric estimates; no learned model, randomness, build step, CDN, npm, or runtime internet dependency.
- Risk is `p_hostile * expected_consequence * urgency`; normalized entropy remains separate.
- Uncertainty friction is bounded and diminishes with urgency.
- Feasibility uses the earliest materially plausible arrival, not a weighted mean.
- Both strategies receive identical observations, belief cadence, and feasibility horizon.
- Existing Python tests, 3D playback behavior, API shape, synthetic disclaimer, and backend authority remain intact.
- Implement every behavior test-first and commit each independently reviewable task.

---

### Task 1: Observation and Belief Domain Model

**Files:**
- Modify: `swarmshield/models.py`
- Create: `tests/test_belief.py`

**Interfaces:**
- Produces: `TrackObservation`, `ObservedThreat`, and `ThreatBelief` immutable dataclasses.
- `ObservedThreat` deliberately has no `asset_id`; allocation code will consume it in Task 3.

- [ ] **Step 1: Write failing construction and boundary tests**

```python
from dataclasses import fields
from swarmshield.models import ObservedThreat, ThreatBelief, TrackObservation, Vec2

def test_observed_threat_cannot_carry_ground_truth_destination():
    names = {field.name for field in fields(ObservedThreat)}
    assert "asset_id" not in names
    observed = ObservedThreat("T1", 4.0, Vec2(1, 2), Vec2(3, 4), 0.8, "active", 500)
    assert observed.id == "T1"

def test_belief_serializes_operational_evidence():
    belief = ThreatBelief("T1", 4.0, {"A": .75, "B": .25}, {"A": 10, "B": 30},
                          "A", .75, 70, .51, "medium", .8, 10, 50.4)
    assert belief.to_dict()["top_destination_id"] == "A"
    assert "asset_id" not in belief.to_dict()
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_belief -v`

Expected: import failure because the new dataclasses do not exist.

- [ ] **Step 3: Add the minimal immutable types**

```python
@dataclass(frozen=True)
class TrackObservation:
    time_s: float
    position: Vec2
    velocity: Vec2

@dataclass(frozen=True)
class ObservedThreat:
    id: str
    time_s: float
    position: Vec2
    velocity: Vec2
    p_hostile: float
    state: str
    altitude_m: float

@dataclass(frozen=True)
class ThreatBelief:
    threat_id: str
    time_s: float
    destination_probabilities: dict[str, float]
    approach_times_s: dict[str, float | None]
    top_destination_id: str
    top_probability: float
    expected_consequence: float
    uncertainty: float
    uncertainty_label: str
    urgency: float
    feasible_horizon_s: float
    risk: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 4: Run the focused and model-dependent tests**

Run: `python -m unittest tests.test_belief tests.test_allocator -v`

Expected: all current tests plus the two new tests pass.

- [ ] **Step 5: Commit**

```bash
git add swarmshield/models.py tests/test_belief.py
git commit -m "feat: add observation-only threat belief models"
```

### Task 2: Deterministic Geometric Belief Predictor

**Files:**
- Create: `swarmshield/belief.py`
- Modify: `tests/test_belief.py`

**Interfaces:**
- Consumes: `ObservedThreat`, `TrackObservation`, and `dict[str, Asset]`.
- Produces: `build_threat_belief(observed, history, assets) -> ThreatBelief` and `uncertainty_friction(belief) -> float`.

- [ ] **Step 1: Add failing predictor tests**

```python
def test_probabilities_are_normalized_and_favor_aligned_asset():
    assets = {
        "A": Asset("A", "ahead", Vec2(0, 0), 90, "critical"),
        "B": Asset("B", "side", Vec2(4000, 4000), 20, "low"),
    }
    observed = ObservedThreat("T", 0, Vec2(0, 4000), Vec2(0, -100), .9, "active", 500)
    belief = build_threat_belief(observed, [TrackObservation(0, observed.position, observed.velocity)], assets)
    assert abs(sum(belief.destination_probabilities.values()) - 1) < 1e-9
    assert belief.top_destination_id == "A"
    assert math.isclose(belief.risk, .9 * belief.expected_consequence * belief.urgency)

def test_stationary_track_falls_back_to_uniform_probabilities():
    observed = ObservedThreat("T", 0, Vec2(0, 0), Vec2(0, 0), .8, "active", 100)
    belief = build_threat_belief(observed, [], two_assets())
    assert set(belief.destination_probabilities.values()) == {.5}

def test_feasible_horizon_uses_earliest_materially_plausible_arrival():
    belief = build_threat_belief(angled_observation(), angled_history(), three_assets())
    plausible = [belief.approach_times_s[key] for key, probability in belief.destination_probabilities.items()
                 if probability >= max(MIN_PLAUSIBLE_PROBABILITY,
                                       belief.top_probability * PLAUSIBLE_RELATIVE_TO_TOP)]
    assert belief.feasible_horizon_s == min(time for time in plausible if time is not None)

def test_uncertainty_friction_is_bounded_and_fades_with_urgency():
    early = replace(example_belief(), uncertainty=1, urgency=.1)
    urgent = replace(example_belief(), uncertainty=1, urgency=.9)
    assert 0 <= uncertainty_friction(early) <= MAX_UNCERTAINTY_FRICTION
    assert uncertainty_friction(urgent) < uncertainty_friction(early)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_belief -v`

Expected: import failure for `swarmshield.belief`.

- [ ] **Step 3: Implement the pure predictor**

```python
HISTORY_LIMIT = 5
SOFTMAX_TEMPERATURE = 0.35
MISS_DISTANCE_SCALE_M = 2400.0
MIN_PLAUSIBLE_PROBABILITY = 0.10
PLAUSIBLE_RELATIVE_TO_TOP = 0.25
MAX_UNCERTAINTY_FRICTION = 18.0

def build_threat_belief(observed, history, assets):
    velocity = _smoothed_velocity(observed.velocity, history[-HISTORY_LIMIT:])
    scores, approach_times = _geometric_scores(observed.position, velocity, assets)
    probabilities = _softmax_or_uniform(scores, SOFTMAX_TEMPERATURE)
    top_id = max(sorted(probabilities), key=probabilities.get)
    expected = sum(probabilities[key] * assets[key].consequence for key in assets)
    urgencies = {key: _urgency(approach_times[key]) for key in assets}
    urgency = sum(probabilities[key] * urgencies[key] for key in assets)
    plausible = [approach_times[key] for key in assets
                 if probabilities[key] >= max(MIN_PLAUSIBLE_PROBABILITY,
                                               probabilities[top_id] * PLAUSIBLE_RELATIVE_TO_TOP)
                 and approach_times[key] is not None]
    horizon = min(plausible, default=float("inf"))
    entropy = _normalized_entropy(probabilities)
    return ThreatBelief(observed.id, observed.time_s, probabilities, approach_times,
                        top_id, probabilities[top_id], expected, entropy,
                        _uncertainty_label(entropy), urgency, horizon,
                        observed.p_hostile * expected * urgency)

def uncertainty_friction(belief):
    return MAX_UNCERTAINTY_FRICTION * belief.uncertainty * (1.0 - belief.urgency)
```

Implement `_smoothed_velocity`, `_geometric_scores`, `_softmax_or_uniform`, `_normalized_entropy`, `_uncertainty_label`, and `_urgency` as finite, deterministic standard-library math helpers. Approach time is the forward projection time; miss distance contributes continuously to score rather than acting as truth.

- [ ] **Step 4: Run belief tests and full regression suite**

Run: `python -m unittest tests.test_belief -v`

Expected: all belief tests pass.

Run: `python -m unittest discover -s tests -v`

Expected: existing suite remains green.

- [ ] **Step 5: Commit**

```bash
git add swarmshield/belief.py tests/test_belief.py
git commit -m "feat: derive deterministic destination beliefs"
```

### Task 3: Make Both Allocators Observation-Only

**Files:**
- Modify: `swarmshield/allocator.py`
- Rewrite: `tests/test_allocator.py`

**Interfaces:**
- Consumes: `list[ObservedThreat]`, `dict[str, ThreatBelief]`, interceptors.
- Produces: `score_pair(interceptor, observed, belief)`, `allocate_swarmshield(...)`, and `allocate_baseline(...)` without an asset map or `Threat` argument.

- [ ] **Step 1: Replace allocator tests with failing observation-only cases**

```python
def test_pair_feasibility_uses_belief_horizon():
    observed = observed_threat(position=Vec2(0, 0), velocity=Vec2(0, -100))
    score = score_pair(interceptor_behind(), observed, belief(horizon=25, risk=60, urgency=.8))
    assert score.feasible
    assert score.intercept_time_s < 25

def test_uncertainty_can_hold_early_but_not_when_urgent():
    early = allocate_swarmshield([interceptor_behind()], [observed_threat()],
                                 {"T": belief(risk=10, uncertainty=1, urgency=.05)})[0]
    urgent = allocate_swarmshield([interceptor_behind()], [observed_threat()],
                                  {"T": belief(risk=80, uncertainty=1, urgency=.95)})[0]
    assert early == {}
    assert urgent == {"I": "T"}

def test_baseline_and_swarmshield_accept_the_same_observation_inputs():
    observed = [observed_threat()]
    beliefs = {"T": belief(horizon=30)}
    allocate_baseline([interceptor_behind()], observed, beliefs)
    allocate_swarmshield([interceptor_behind()], observed, beliefs)

def test_allocator_source_has_no_asset_id_read():
    source = inspect.getsource(swarmshield.allocator)
    assert ".asset_id" not in source
```

- [ ] **Step 2: Run allocator tests and verify RED**

Run: `python -m unittest tests.test_allocator -v`

Expected: signature/type failures because allocators still require `Threat` and assets.

- [ ] **Step 3: Refactor the allocation boundary**

```python
def score_pair(interceptor: Interceptor, threat: ObservedThreat,
               belief: ThreatBelief) -> PairScore:
    solution = intercept_solution(interceptor, threat)
    # Preserve pursuit/range/battery checks.
    before_impact = intercept_time < belief.feasible_horizon_s - 2.0
    continuity_bonus = 0.65 * belief.risk if interceptor.target_id == threat.id else 0.0
    utility = (belief.risk * probability - time_penalty - resource_penalty
               - energy_penalty - uncertainty_friction(belief) + continuity_bonus)
    return PairScore(...)

def allocate_swarmshield(interceptors, threats, beliefs):
    # Existing Hungarian matrix and zero-utility dummy columns.
    score = score_pair(interceptor, threat, beliefs[threat.id])

def allocate_baseline(interceptors, threats, beliefs):
    # Existing nearest-feasible greedy ordering using the same score feasibility.
    score = score_pair(interceptor, threat, beliefs[threat.id])
```

Generalize `intercept_solution` to the shared observed position/velocity protocol, remove `time_to_asset` and `threat_risk` from the decision module, and preserve Hungarian/dummy/continuity behavior.

- [ ] **Step 4: Run allocator and belief tests**

Run: `python -m unittest tests.test_allocator tests.test_belief -v`

Expected: all pass, including the source-level ground-truth guard.

- [ ] **Step 5: Commit**

```bash
git add swarmshield/allocator.py tests/test_allocator.py
git commit -m "refactor: isolate allocation from destination truth"
```

### Task 4: Integrate Beliefs, Sparse Decisions, and Evaluation

**Files:**
- Modify: `swarmshield/simulator.py`
- Modify: `tests/test_simulator.py`

**Interfaces:**
- Produces operational trajectory rows with `belief`, `decision`, and assignment but no `asset_id`.
- Produces first-commit `prediction_evaluation` metrics and sparse `hold`, `commit`, and `retask` events.

- [ ] **Step 1: Add failing integration and truth-boundary tests**

```python
def test_operational_snapshots_expose_belief_not_truth(self):
    threats = [row for row in self.result["runs"]["swarmshield"]["trajectories"]
               if row["kind"] == "threat"]
    self.assertTrue(all("asset_id" not in row for row in threats))
    self.assertTrue(all("belief" in row and "decision" in row for row in threats))

def test_prediction_metrics_are_first_commit_ground_truth_evaluation(self):
    evaluation = self.result["runs"]["swarmshield"]["metrics"]["prediction_evaluation"]
    self.assertEqual(evaluation["committed_count"] + evaluation["uncommitted_count"], 20)
    self.assertGreaterEqual(evaluation["top_destination_accuracy"], 0)
    self.assertLessEqual(evaluation["brier_score"], 2)

def test_decision_events_are_sparse_transitions(self):
    events = self.result["runs"]["swarmshield"]["events"]
    decision_events = [event for event in events if event["type"] in {"hold", "commit", "retask"}]
    keys = [(event["time_s"], event["type"], event["threat_id"]) for event in decision_events]
    self.assertEqual(len(keys), len(set(keys)))
    self.assertTrue(all("evidence" in event for event in decision_events))

def test_simulator_decision_helpers_do_not_read_destination_truth(self):
    source = inspect.getsource(simulator._update_beliefs) + inspect.getsource(simulator._swarm_assign)
    self.assertNotIn("asset_id", source)
```

- [ ] **Step 2: Run simulator tests and verify RED**

Run: `python -m unittest tests.test_simulator -v`

Expected: failures for missing belief fields, evaluation, and transition events.

- [ ] **Step 3: Add simulator-owned observation histories and belief updates**

```python
def _observe(threat: Threat, time_s: float) -> ObservedThreat:
    return ObservedThreat(threat.id, time_s, threat.position, threat.velocity,
                          threat.p_hostile, threat.state, threat.altitude_m)

def _update_beliefs(time_s, threats, assets, histories):
    observed = {threat.id: _observe(threat, time_s) for threat in threats}
    for item in observed.values():
        histories[item.id].append(TrackObservation(time_s, item.position, item.velocity))
    beliefs = {item.id: build_threat_belief(item, list(histories[item.id]), assets)
               for item in observed.values()}
    return observed, beliefs
```

Use `deque(maxlen=HISTORY_LIMIT)`. Update beliefs before initial allocation and every discrete snapshot. Pass the exact same `observed` and `beliefs` objects to either strategy.

- [ ] **Step 4: Replace operational truth fields and add transition recording**

```python
def _belief_evidence(belief):
    return {"top_destination_id": belief.top_destination_id,
            "top_probability": round(belief.top_probability, 4),
            "expected_consequence": round(belief.expected_consequence, 3),
            "uncertainty": round(belief.uncertainty, 4),
            "uncertainty_label": belief.uncertainty_label,
            "urgency": round(belief.urgency, 4), "risk": round(belief.risk, 3)}

# Threat snapshot fields:
{"belief": _belief_evidence(beliefs[threat.id]),
 "decision": decision_states[threat.id],
 "assignment": threat.assigned_interceptor}
```

Track one state per threat. Emit `hold` only on first observed HOLD, `commit` on HOLD/unseen to assigned, and `retask` when the assigned interceptor changes. Evidence is copied from the actual belief and score; no generated narration per frame.

- [ ] **Step 5: Isolate ground-truth evaluation**

```python
def _prediction_evaluation(commit_records, threats, asset_ids):
    committed = [record for record in commit_records.values()]
    if not committed:
        return {"evaluation_point": "first_commit", "committed_count": 0,
                "uncommitted_count": len(threats), "top_destination_accuracy": None,
                "mean_normalized_entropy": None, "brier_score": None}
    accuracy = mean(record.top_destination_id == asset_ids[tid] for tid, record in commit_records.items())
    brier = mean(sum((record.destination_probabilities[aid] - (aid == asset_ids[tid])) ** 2
                     for aid in record.destination_probabilities)
                  for tid, record in commit_records.items())
    return {"evaluation_point": "first_commit", "committed_count": len(committed),
            "uncommitted_count": len(threats) - len(committed),
            "top_destination_accuracy": round(accuracy, 4),
            "mean_normalized_entropy": round(mean(r.uncertainty for r in committed), 4),
            "brier_score": round(brier, 4)}
```

Build `asset_ids = {threat.id: threat.asset_id ...}` only beside terminal leakage/evaluation code after the simulation loop. Replace projected-leak helpers with a clearly named ground-truth physics helper in the same section; do not call it from allocation.

- [ ] **Step 6: Run simulator tests and the full suite**

Run: `python -m unittest tests.test_simulator -v`

Expected: all simulator tests pass.

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add swarmshield/simulator.py tests/test_simulator.py
git commit -m "feat: run simulation from uncertainty-aware beliefs"
```

### Task 5: Tune the Reproducible T05 Decision Narrative

**Files:**
- Modify: `swarmshield/scenario.py`
- Modify: `tests/test_simulator.py`
- Modify: `tests/test_scenario_matrix.py`

**Interfaces:**
- Preserves generic `build_scenario(...)` and custom JSON.
- `build_hackathon_scenario()` yields a natural T05 HOLD → COMMIT → failure recovery/RETASK sequence.

- [ ] **Step 1: Add the failing demonstration test**

```python
def test_t05_demonstrates_uncertainty_commit_and_recovery(self):
    events = self.result["runs"]["swarmshield"]["events"]
    t05 = [event for event in events if event.get("threat_id") == "T05"]
    sequence = [event["type"] for event in t05]
    self.assertIn("hold", sequence)
    self.assertIn("commit", sequence)
    self.assertTrue(any(kind in sequence for kind in ("retask", "failure_recovery")))
    self.assertLess(sequence.index("hold"), sequence.index("commit"))
```

- [ ] **Step 2: Run the demonstration test and verify RED**

Run: `python -m unittest tests.test_simulator.SimulatorTests.test_t05_demonstrates_uncertainty_commit_and_recovery -v`

Expected: FAIL because the generic scenario does not yet produce the required T05 transition.

- [ ] **Step 3: Tune fixed default geometry and scripted events**

In `build_hackathon_scenario`, start from `build_scenario(...)`, then modify T05's initial position/velocity so two assets have similar early geometric scores. Add a fixed T05 diversion that changes physical heading and ground truth, and target the deterministic initially assigned interceptor with the fixed failure event. Keep all behavior driven by normal predictor/allocation code:

```python
scenario = build_scenario(20, 12, seed=seed, duration_s=190, enable_events=True)
t05 = next(threat for threat in scenario.threats if threat.id == "T05")
t05.position = Vec2(-4900.0, 13600.0)
t05.velocity = Vec2(0.0, -146.0)
scenario.events = [event for event in scenario.events
                   if event["type"] not in {"threat_diversion", "interceptor_failure"}]
scenario.events.extend([
    {"time_s": 32, "type": "threat_diversion", "threat_id": "T05",
     "new_asset_id": "A01", "new_confidence": .94,
     "label": "T05 changes course toward Command Centre"},
    {"time_s": 48, "type": "interceptor_failure", "interceptor_id": "I05",
     "label": "I05 fails after T05 commitment"},
])
scenario.events.sort(key=lambda event: event["time_s"])
return scenario
```

If the RED test proves I05 is not T05's assigned interceptor under the completed ordinary allocator, adjust only the fixed default scenario geometry or the fixed failure event's interceptor ID, rerun the same test, and record the final deterministic values in this plan before committing. Do not branch on T05 anywhere outside scenario construction/tests.

- [ ] **Step 4: Verify the narrative and scenario matrix**

Run: `python -m unittest tests.test_simulator tests.test_scenario_matrix -v`

Expected: T05 sequence passes and all generated/custom scenario invariants remain green.

- [ ] **Step 5: Commit**

```bash
git add swarmshield/scenario.py tests/test_simulator.py tests/test_scenario_matrix.py
git commit -m "feat: demonstrate uncertainty-driven T05 retasking"
```

### Task 6: Expose Belief Evidence in the Operational 3D UI

**Files:**
- Modify: `static/tactical3d.js`
- Modify: `static/app.js`
- Modify: `static/index.html`
- Modify: `static/styles.css`
- Modify: `tests/test_webapp.py`

**Interfaces:**
- Consumes backend `row.belief`, `row.decision`, sparse decision events, and existing assignments.
- Keeps the existing `initTactical3D` controller API and visual-only interpolation boundary.

- [ ] **Step 1: Add failing static-structure and payload tests**

```python
def test_operational_ui_uses_belief_fields_without_truth_label(self):
    renderer = (STATIC_ROOT / "tactical3d.js").read_text(encoding="utf-8")
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    self.assertIn("top_destination_id", renderer)
    self.assertIn("uncertainty_label", renderer)
    self.assertIn("decision", renderer)
    self.assertNotIn("row.asset_id", renderer)
    self.assertIn("prediction_evaluation", app)

def test_payload_keeps_two_strategy_submission(self):
    payload = generate_payload()
    self.assertEqual(set(payload["runs"]), {"baseline", "swarmshield"})
    self.assertNotIn("known_destination", json.dumps(payload))
```

- [ ] **Step 2: Run web tests and verify RED**

Run: `python -m unittest tests.test_webapp -v`

Expected: belief-field assertions fail and `row.asset_id` is still present.

- [ ] **Step 3: Update moving-entity details and decision panel**

Replace the threat tooltip rows in `tactical3d.js`:

```javascript
const belief = row.belief || {};
return [
  ['Track', row.id], ['State', row.state], ['Decision', row.decision || 'HOLD'],
  ['Likely destination', `${belief.top_destination_id || 'UNKNOWN'} ${fmtPercent(belief.top_probability)}`],
  ['Uncertainty', `${belief.uncertainty_label || 'unknown'} ${fmtPercent(belief.uncertainty)}`],
  ['Urgency', fmt(belief.urgency)], ['Risk', fmt(belief.risk)],
  ['Assigned', row.assignment || 'Unallocated'],
];
```

Render sparse HOLD/COMMIT/RETASK entries from backend events in the existing decision/live-priority area. Add compact CSS only for the extra evidence rows; retain permanent asset labels and avoid moving-entity DOM labels.

- [ ] **Step 4: Surface prediction evaluation without revealing truth**

Use aggregate `prediction_evaluation` values in `app.js` and add a compact block in `index.html` for accuracy, entropy, Brier, and committed count. Do not show per-threat ground truth.

- [ ] **Step 5: Run web and full tests**

Run: `python -m unittest tests.test_webapp -v`

Expected: all web/static tests pass.

Run: `python -m unittest discover -s tests -v`

Expected: full suite passes.

- [ ] **Step 6: Commit**

```bash
git add static/tactical3d.js static/app.js static/index.html static/styles.css tests/test_webapp.py
git commit -m "feat: show uncertainty evidence in tactical viewer"
```

### Task 7: Documentation, Boundary Audit, and End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `MANUAL_TESTING.md`
- Modify: `demo_output/metrics.json`
- Modify: `tests/test_simulator.py`

**Interfaces:**
- Documents the previous known-destination version and future three-way ablation without exposing it as a current strategy.

- [ ] **Step 1: Add a final source-boundary regression test**

```python
def test_asset_id_reads_are_confined_to_ground_truth_boundaries(self):
    forbidden = [Path("swarmshield/belief.py"), Path("swarmshield/allocator.py")]
    for path in forbidden:
        self.assertNotIn("asset_id", path.read_text(encoding="utf-8"), str(path))
    renderer = Path("static/tactical3d.js").read_text(encoding="utf-8")
    self.assertNotIn("row.asset_id", renderer)
```

- [ ] **Step 2: Run the boundary test before documentation changes**

Run: `python -m unittest tests.test_simulator.SimulatorTests.test_asset_id_reads_are_confined_to_ground_truth_boundaries -v`

Expected: PASS if Tasks 3-6 maintained the boundary; otherwise fail and repair the violating decision path before continuing.

- [ ] **Step 3: Update README and manual verification notes**

Document:

```text
Current comparison: naive nearest-feasible baseline versus uncertainty-aware SwarmShield.
Previous version: known-destination SwarmShield used the scenario's destination directly in risk/allocation.
Future ablation: baseline vs known-destination SwarmShield vs uncertainty-aware SwarmShield.
Ground truth is now reserved for physics and post-decision evaluation.
```

Add the predictor formula, entropy/friction explanation, first-commit evaluation definition, local launch command, and a manual checklist covering load, generated/custom JSON, play/pause, scrub, strategy switch, presets, resize, T05 HOLD/COMMIT/RETASK, link loss, and zero console errors.

- [ ] **Step 4: Regenerate the checked-in demo metrics**

Run: `python run.py --json demo_output/metrics.json`

Expected: deterministic two-run JSON containing belief evaluation fields and no operational trajectory `asset_id`.

- [ ] **Step 5: Run automated verification**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass with zero failures/errors.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 6: Run browser verification through the existing server**

Run: `python run.py --serve --port 8080`

Open `http://127.0.0.1:8080`, execute every `MANUAL_TESTING.md` item, and confirm the console has no errors. Stop the server after verification.

- [ ] **Step 7: Commit**

```bash
git add README.md MANUAL_TESTING.md demo_output/metrics.json tests/test_simulator.py
git commit -m "docs: explain uncertainty-aware SwarmShield"
```

- [ ] **Step 8: Request final code review and integrate locally**

Use the requesting-code-review workflow, resolve any correctness findings test-first, rerun the full suite, then use the finishing-a-development-branch workflow to merge the feature branch into local `main` as requested.
