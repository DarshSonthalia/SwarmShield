# Uncertainty-Aware Threat Beliefs

## Purpose

Replace the previous known-destination SwarmShield decision model with a deterministic, uncertainty-aware model while preserving the existing two-way comparison:

1. Naive nearest-feasible baseline
2. Uncertainty-aware SwarmShield

The Python simulation remains the sole source of truth. The allocator receives observations and beliefs, never a threat's true destination. No third strategy is added in this iteration.

## Non-goals

- No simulation-physics redesign, probabilistic trajectory physics, GIS data, new networking, or allocator-family replacement.
- No learned predictor or stochastic output.
- No known-destination strategy in the submission UI or API.
- No JavaScript-derived simulation state.

## Truth boundary

`Threat.asset_id` is private ground truth. Its permitted uses are limited to:

- initial trajectory generation and scripted diversions;
- physical impact/leak resolution;
- final evaluation of belief predictions and leakage outcomes;
- scenario validation and serialization needed to define ground truth.

It must not be read by belief prediction, risk scoring, threat prioritization, feasibility, allocation, operational snapshots, or the normal UI. A regression test will enforce the decision-path boundary.

The simulator will construct an observation-only input containing threat ID, timestamp, position, velocity, status, hostile probability, and recent track history. The belief and allocator APIs will accept this observation type rather than `Threat`, making accidental destination access structurally difficult.

## Belief model

Add a separate `ThreatBelief` model keyed by threat ID. It contains:

- destination probability for every protected asset;
- per-asset estimated approach time;
- top predicted destination and probability;
- expected consequence;
- normalized entropy and a human-readable uncertainty label;
- probability-weighted urgency;
- conservative feasible horizon;
- decision risk;
- observation timestamp.

Recent observed positions and velocities are retained in a short bounded history. Prediction is deterministic:

1. Smooth the recent velocity/heading.
2. For each asset, calculate forward heading alignment and projected miss distance.
3. Convert those geometric scores to probabilities with a fixed-temperature softmax.
4. Fall back to a uniform distribution if the track is stationary or scores are non-finite.

No true destination is an input to these calculations.

### Derived quantities

For asset `a` with destination probability `p(a)`:

```text
expected_consequence = sum(p(a) * consequence(a))
urgency              = sum(p(a) * urgency(approach_time(a)))
risk                 = hostile_probability * expected_consequence * urgency
uncertainty          = entropy(p) / log(asset_count)
```

Risk and uncertainty remain separate. Uncertainty influences commitment utility through a bounded friction that fades as urgency rises:

```text
uncertainty_friction = MAX_FRICTION * uncertainty * (1 - urgency)
```

This prevents uncertainty from inflating consequence risk while still allowing early HOLD decisions. High urgency cannot be suppressed indefinitely by uncertainty.

The feasibility horizon is the earliest approach time among materially plausible destinations, not a probability-weighted mean. A destination is materially plausible when its probability is at least a fixed absolute floor or a fixed fraction of the top probability. Constants live together in `belief.py` and are documented and tested.

## Allocation behavior

Both strategies receive the same observations, belief update cadence, and conservative feasible horizon.

### Naive baseline

Assign the nearest feasible interceptor to each threat. Feasibility uses observed motion, interceptor range/battery, the physical intercept solution, and the belief-derived conservative horizon. It does not read consequence-weighted risk or true destination.

### Uncertainty-aware SwarmShield

Reuse the existing Hungarian assignment, dummy assignments, and continuity bonus. Pair utility combines:

- belief-derived risk and urgency;
- physical intercept feasibility and cost;
- the bounded uncertainty friction;
- existing continuity preference.

The allocator may HOLD when early evidence is too ambiguous, COMMIT when evidence/urgency crosses the utility threshold, and RETASK after failures or materially changed evidence. Additional hysteresis is introduced only if focused tests demonstrate unstable assignments.

Assignment explanations are deterministic and structured from the actual score components. Events are emitted only for meaningful transitions: first HOLD, HOLD-to-COMMIT, assignment/retask, interceptor failure, intercept, and leak. Per-frame narration is excluded.

## Simulation integration

The simulator owns:

- bounded observation histories;
- the current `ThreatBelief` map;
- belief updates before allocation at every discrete simulation step;
- sparse decision-transition state;
- ground-truth-only terminal evaluation.

Snapshots expose belief evidence instead of `asset_id`: probabilities, top likely destination, expected consequence, uncertainty/label, urgency, risk, decision, and assignment. Existing entity positions, statuses, events, metrics, and assignments still come from discrete backend snapshots. The 3D viewer may interpolate positions visually but never invent state transitions.

Strategy switching reuses the same scenario and renderer but reloads the selected backend result, clearing stale trails, assignments, and decision overlays.

## Evaluation

Prediction quality is evaluated against ground truth only after the decision path has completed. For each threat, the evaluation point is its first COMMIT snapshot; threats never committed are excluded from commitment-accuracy metrics and counted separately.

Report:

- top-destination accuracy at first commitment;
- mean normalized entropy at first commitment;
- multiclass Brier score at first commitment;
- committed and uncommitted sample counts.

Leakage and protected-value metrics continue to use physical outcomes and true destinations. Evaluation code must not feed results back into beliefs or allocation.

## Operational UI

Keep the current dark tactical 3D interface and synthetic-scenario disclaimer. Normal operational views must not show true destinations.

- Moving-entity hover/click details show likely destination, probability, uncertainty, urgency, risk, decision, and assigned interceptor.
- The decision/audit panel shows sparse HOLD, COMMIT, and RETASK evidence.
- Asset labels remain visible; no permanent labels are added for all moving entities.
- Existing playback, scrubbing, camera presets, resize behavior, comparison table, and two strategy controls remain intact.

The prior known-destination behavior is documented in the README/technical notes as the previous SwarmShield model. A future three-way ablation may compare naive nearest-feasible, known-destination SwarmShield, and uncertainty-aware SwarmShield.

## Demonstration scenario

Tune the deterministic default scenario so T05 initially has ambiguous geometry, naturally produces HOLD, changes course and produces COMMIT, then undergoes an interceptor failure followed by recovery/retask. These outcomes must arise from the predictor, utility, and fixed scenario geometry/events; IDs or UI output must not be special-cased.

## Verification

Automated coverage will include:

- probability normalization, deterministic prediction, entropy, urgency, and conservative horizon;
- no `asset_id` access in prediction/allocation inputs and no truth field in operational snapshots;
- identical observation information and horizon for both strategies;
- HOLD-to-COMMIT and failure-to-RETASK behavior in the deterministic demo;
- sparse event emission and structured evidence;
- first-commit accuracy, entropy, and Brier calculations;
- existing allocator, simulator, server, and static-structure tests.

Manual browser verification will cover first load, generated/custom scenarios, play/pause, scrubbing, strategy switching, belief details, camera presets, resizing, failure/reassignment, ground-link loss, and console errors.

## Expected files

- Create `belief.py` for observation-only prediction and derived belief quantities.
- Modify `models.py`, `allocator.py`, `simulator.py`, and `scenario.py` for belief state, clean allocation interfaces, evaluation, and the deterministic demo.
- Modify `server.py` only as needed to serialize the extended result without changing networking behavior.
- Modify `static/app.js`, `static/tactical3d.js`, `static/index.html`, and `static/styles.css` for minimal operational belief evidence.
- Extend focused Python/static tests and update `README.md` plus technical notes.
