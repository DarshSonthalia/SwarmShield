# SwarmShield

**Scarcity-aware resource allocation and uncertainty visualization for a fictional coastal city.**

> SwarmShield is a fictional simulation and decision-support visualization created for a hackathon.
> It does not implement real-world weapon guidance or operational defence logic.
> All positions, speeds and scores are abstract scene units with no real-world mapping.

SwarmShield shows how a decision layer can spread **12 simulated resources** across **20 uncertain incoming tracks** in *Meridian Bay*, a made-up coastal city:

**observe → estimate intent → quantify uncertainty → rank consequence → allocate scarce resources → continuously reassess**

The focus is the allocation decision under uncertainty, not physical guidance. Every number, assignment line, audit entry and metric in the dashboard comes from the running deterministic simulation.

---

## Quick start

Requirements: **Python 3.10-3.13** and **Node.js 22.12+**.  
Tested with Python 3.13 and Node.js 22.12+.

```bash
npm run setup     # creates backend/.venv, installs Python + frontend dependencies
npm run dev       # backend on :8000 + dashboard on :5173
```

Open **http://localhost:5173**. Press `Ctrl+C` to stop both services.

Shortcuts: `./start.sh` (macOS/Linux) or `./start.ps1` (Windows PowerShell) run `npm run dev`.

### Manual setup

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload      # http://127.0.0.1:8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                        # http://127.0.0.1:5173
```

### All commands

| Command | What it does |
|---|---|
| `npm run setup` | Create the venv, `pip install`, `npm ci` |
| `npm run dev` | Backend + Vite dev server together |
| `npm test` | Backend pytest, then frontend Vitest |
| `npm run test:e2e` | Playwright browser tests against the real engine (needs Google Chrome; set `PLAYWRIGHT_CHANNEL` to use another) |
| `npm run build` | Type-check and build the dashboard into `frontend/dist` |
| `npm start` | Backend only. After `npm run build`, it also serves the dashboard at http://127.0.0.1:8000 |
| `npm run package` | Zip the project to `artifacts/SwarmShield.zip` |
| `backend/.venv/Scripts/python scripts/stress_eval.py --seeds 30 --output evidence/stress_test_30_seeds.json` | Multi-seed observation-noise evaluation (Windows) |
| `backend/.venv/Scripts/python scripts/collect_evidence.py` | Collect backend, frontend, E2E, metric, and stress evidence (Windows) |

---

## Demo walkthrough

1. Open the dashboard and press **Demo mode** (top right). The scenario restarts, the camera resets, and playback runs through the scripted story with short callouts. The camera briefly focuses on each featured track.
2. Or explore by hand:
   - **Timeline** (bottom): play/pause (`Space`), restart, speed 0.5× / 1× / 2× / 4×, scrubbing. Diamonds mark scenario events (click one to jump to it). Ticks mark assignment changes.
   - **3D city**: drag to orbit, scroll to zoom, right-drag to pan. Click a track, resource (blue cube), destination zone or staging site to inspect it.
   - **Track registry** (left): search (`/`) and filter (high priority, assigned, unassigned, high uncertainty, open-water leading, recently changed, critical destination).
   - **Context inspector** (right): full probability distribution, priority breakdown, evidence gates, observation and decision history.
   - **Decision audit** and **Compare policies** open from the map toolbar or the strip above the timeline.

Moments worth showing:

| Time | What happens |
|---|---|
| T+0 – T+12 | Observation window: 20 tracks, 12 staged resources, broad estimates, no commitments |
| T+12 | First allocations. T11 appears headed for the residential district and CBD and is assigned |
| T+32 – T+40 | T11 turns toward open water. The resource is **held**, and the audit logs the open-water trend under review |
| T+50 | T03 briefly deviates. Hysteresis keeps its resource in place |
| T+52 | After 4 qualifying cycles, **T11's resource is released** (open-water probability 97%) |
| T+66 – T+84 | T17 turns toward the airport. Its priority rises and at T+84 a resource is **reallocated** from a weaker track |
| T+76 | T18 and T19 escalate toward power and civic infrastructure |
| T+110 – T+120 | Compare live backend metrics against the static first-come / one-resource-per-track baseline |

The ambiguous track T14 circles with high noise and stays monitored without a commitment.

---

## Architecture

```
backend/                  FastAPI + Pydantic + NumPy
  app/main.py             REST API (see below); serves frontend/dist when built
  app/models.py           Typed public contracts (Track, Resource, Frame, AuditEntry, Metrics, config)
  app/config.json         Every tunable: seed, counts, intervals, weights, uncertainty, hysteresis, map
  app/simulation/
    world.py              Builds the full deterministic timeline, validates invariants per frame
    tracks.py             Hidden ground truth + scripted behaviours (the only module that knows intent)
    observation.py        Noisy position/velocity measurements: the only bridge out of ground truth
    inference.py          Geometric destination inference from observations only
    uncertainty.py        Entropy, circular heading variance, stability
    consequence.py        Probability-weighted consequence
    priority.py           Transparent, decomposed priority score
    allocator.py          Scarcity-aware allocation, reassessment, release, reallocation
    hysteresis.py         Switching and release gates
    resources.py          Resource motion plans (two C2 quintic segments per plan)
    trajectory.py         Quintic Hermite segments matching position/velocity/acceleration
    baseline.py           First-come-first-served comparison allocator
    metrics.py            Coverage, exposure, stability, utilization for both policies
    events.py             Narrative scenario events used by the timeline and demo mode
    audit.py              Immutable decision records with factor snapshots
  tests/                  pytest suite
frontend/                 React 19 + TypeScript + Vite + React Three Fiber + Tailwind
  src/api.ts, types.ts    Fetch + zod validation of every backend payload
  src/App.tsx             Dashboard layout, demo mode, metrics strip, help
  src/components/         CityScene (3D + 2D fallback), TrackList, Inspector, Timeline, Audit, Comparison, Boundary
  src/hooks/usePlayback.ts  Client-side playback clock
  src/state.ts            Filters, colours, frame lookup, quintic interpolation between frames
  e2e/                    Playwright tests against the real engine
scripts/                  Cross-platform Node launchers, packaging, fixture export
```

### Simulation pipeline

At startup `World` computes the whole scenario (t = 0…120 s, one frame per second) from the fixed seed `2407`. Each second is processed in a fixed order:

1. **Motion**: hidden tracks advance.
2. **Observation** (every 2 s): noisy position and velocity. Noise shrinks over time; the ambiguous track stays noisy.
3. **Inference**: destination probabilities, entropy, confidence and expected consequence are updated.
4. **Allocation** (every 2 s, from T+12): priority scoring, then the allocator cycle.
5. **Audit**: every transaction is recorded *before* the frame is published.
6. **Frame**: a deep snapshot, checked by `validate_frame` (one resource per track, probabilities sum to 1, states agree with assignments, finite motion).

Because frames are precomputed and immutable, scrubbing to any time always shows the same state. The dashboard downloads the full run once (`POST /api/run`) and plays it back locally, so it keeps working if the engine goes offline afterwards.

### API

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness + seed |
| `GET /api/scenario` · `GET /api/config` | Scenario metadata, events, full config |
| `POST /api/run` | Complete replay bundle (all frames + audit) |
| `GET /api/frame/{time}` | One frame |
| `GET /api/tracks[/{id}]` · `/api/resources[/{id}]` · `/api/metrics` · `/api/baseline` | State at `?time=` (default: server cursor) |
| `GET /api/audit?time=&track_id=` | Decisions up to that frame only (no future leakage) |
| `POST /api/reset` `{seed?}` · `POST /api/step` `{seconds}` | Rebuild with a seed; advance the cursor |

Interactive docs: http://127.0.0.1:8000/docs.

---

## How it works

### Uncertainty and inference

The allocator never sees a track's true destination. For each observation, `inference.py` scores each of the 8 destinations by **heading alignment** (a filtered velocity over the last 3 observations against the direction to the destination) and adds a small **distance** term. The scores are turned into a likelihood with a softmax. How sharp that softmax is depends on **reliability**:

```
reliability = evidence(observation count) × stability(heading variance) × recovery(time since last major turn) × (1 − maneuver uncertainty)
```

The new likelihood is blended with the previous distribution, and some uniform probability is mixed back in when evidence is weak. Early estimates are therefore broad. They sharpen as consistent observations accumulate. A turn larger than 0.25 rad resets the recovery term, so uncertainty rises again. The dashboard shows:

- **confidence**: combines normalised entropy and reliability
- **entropy**: shown as uncertainty
- **stability** and **heading variance**
- **uncertainty visuals**: rays to every destination weighted by probability, and a halo sized by entropy

### Expected consequence and priority

`expected_consequence = Σ P(destination) × weight(destination)`, where the weights in `config.json` are high for airport, CBD, power and emergency; medium for residential, industrial and port; and 0.04 for open water. The priority score is a sum of named terms. The inspector shows each one:

```
priority = 0.70 · consequence · (0.55 + 0.45·urgency) · (0.6 + 0.4·confidence)   # consequence term
         + 0.07 · entropy · consequence                                           # uncertainty watch
         + 0.10 · escalation                                                      # rising consequence / recent change
         + 0.08 · scarcity · consequence²                                         # scarcity pressure
         − 0.035 if unassigned                                                    # switching penalty
```

### Allocation and hysteresis

Every allocation cycle:

1. Track states are re-evaluated. Assigned tracks are **COMMIT**, or **REASSESS** after a recent turn. Unassigned tracks are **HOLD**, **RELEASE** or **REASSESS**.
2. **Release** requires *all* gates, persisting for **4 consecutive cycles**: open-water probability ≥ 0.76, expected consequence ≤ 0.30, confidence ≥ 0.65, no major turn in the last 10 s. The resource must also have been held for at least 12 s and not changed in the last 12 s. **Open water is low consequence, not safe**: released tracks stay monitored, and any failed gate resets the count.
3. Free resources go to the highest-priority candidates that pass minimum priority and confidence.
4. **Reallocation**: a waiting challenger can take the weakest eligible resource only if it beats that track's priority by ≥ 0.07 for **3 consecutive cycles**, after the minimum assignment time and the cooldown. A track that looks like it is heading for open water cannot be displaced this way; only the release gates can free its resource.
5. Every change is written to the audit log with the leading destination, probability, the full factor snapshot, the priority, a reason, and the resulting assignment map.

All thresholds are in the `hysteresis` block of `config.json`.

### Resource motion

Resources stay at their 8 staging sites (2 central, 6 on the perimeter) until T+14. Each motion plan is two **quintic Hermite segments** that match position, velocity and acceleration at every join (C2 continuity), arcing above the city toward a region trailing the assigned track. On retarget, a new plan starts from the resource's current position, velocity and acceleration, so it never teleports or turns instantly. The dashboard uses the same quintic form to interpolate between one-second frames.

### Baseline comparison

**First come, first served**: at T+12 the 12 lowest track IDs get the 12 resources and are never revisited. Both policies receive the same observations. The comparison panel shows coverage of critical tracks, exposure (sum of expected consequence of uncovered tracks, live and cumulative), low-consequence commitments, reassignments, utilization and stability.

### Demo mode

Demo mode resets playback to T+0 at 1× and plays the events from `simulation/events.py`. When an event starts, it selects the featured track, shows a callout, and eases the camera toward the track for a few seconds before returning to the overview. At T+110 it opens the policy comparison.

---

## Testing

```bash
npm test                 # 92 backend + 30 frontend tests
npm run test:e2e         # 3 Playwright scenarios in Chrome (also fails on any browser console error)

# single tests
cd backend && .venv/bin/python -m pytest tests/test_allocator.py -q -k cooldown
cd frontend && npx vitest run src/test/state.test.ts
```

Backend coverage includes probability normalisation, inference, entropy, consequence, priority decomposition, scarcity ranking, hysteresis, release persistence, cooldown, event ordering and frame consistency, determinism, scrubbing isolation, C2 trajectory continuity, metrics, the baseline, audit reconstruction, invariants and API contracts. Frontend tests cover timeline/playback state, filters, track selection, assignment display, audit rendering and probability rendering. They run against `frontend/src/test/fixture.json`, which is exported from the real engine. After changing backend output, regenerate it:

```bash
backend/.venv/bin/python scripts/export_fixture.py
```

---

## Limitations

- **Fictional by design.** Motion, observation noise and inference are simple geometric heuristics tuned to tell a readable story. There is no real-world physics, sensor or guidance model, and there is no engagement or interception outcome: "allocation" means coverage only.
- **Authored scenario.** The 20 track behaviours are scripted and designed around the default seed. Other seeds (`POST /api/reset {"seed": n}`) change the noise but may not reproduce every narrative beat. The dashboard always loads the default scenario.
- **Precomputed timeline.** The run is computed once at startup. There is no live parameter editing in the UI; change `backend/app/config.json` and restart.
- **Single-user engine.** The API keeps one in-memory world with a shared cursor.
- **Heuristic release.** Releasing a track is a persistence heuristic, not a proof that it can no longer reach a target.
- **Local patch.** The frontend applies a small `patch-package` patch to `@react-three/drei` (`frontend/patches/`). It defers `Html` root unmounting to avoid a React 19 console error. The patch is applied automatically on `npm install` / `npm ci`.
- **Needs WebGL.** 3D rendering requires WebGL. Without it the dashboard falls back to a 2D tactical map.
