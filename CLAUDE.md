# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SwarmShield: a hackathon project. It is a fictional simulation and visualization of allocating scarce resources when you are unsure of intent. A deterministic Python engine (FastAPI) simulates 20 tracks moving toward 8 destinations in a made-up coastal city ("Meridian Bay"). A React + three.js dashboard replays the run. All coordinates are abstract scene units. Keep it that way: the code states that it contains no real-world guidance, interception or defence logic.

## Commands

The root `package.json` drives everything through Node scripts in `scripts/`. Those scripts call the backend venv interpreter at `backend/.venv/bin/python` directly, so no venv needs to be activated. Node >= 22.12 is required.

```bash
npm run setup      # create backend/.venv, pip install, npm ci in frontend/
npm run dev        # uvicorn on 127.0.0.1:8000 + Vite on 127.0.0.1:5173 (./start.sh does the same)
npm test           # backend pytest, then frontend vitest
npm run build      # tsc -b && vite build -> frontend/dist
npm start          # backend only; serves frontend/dist at / if it has been built
npm run test:e2e   # Playwright (starts backend + Vite itself; uses Chrome channel, override with PLAYWRIGHT_CHANNEL)
npm run package    # zip the project to artifacts/SwarmShield.zip
```

Single tests:

```bash
cd backend && .venv/bin/python -m pytest tests/test_allocator.py::test_name -q
cd frontend && npx vitest run src/test/state.test.ts -t "test name"
```

There is no linter configured. Type checking for the frontend runs as part of `npm run build` (`tsc -b`).

## Architecture

### Backend: precomputed deterministic world (`backend/app/`)

- `World.__init__` (`simulation/world.py`) builds the **whole run up front** from `config.seed`. It loops t = 0..duration and stores a deep-copied `Frame` for every second. It also appends to one shared `audit` list; each frame records `audit_count`, the length of that list at that moment. API endpoints never simulate. They index into `frames` (`/api/frame/{t}`, `?time=` query params) or return everything at once (`/api/run`). `/api/reset` rebuilds the world, optionally with a new seed. `/api/step` only moves `world.cursor`.
- Per-tick pipeline order matters: hidden motion → noisy observation → inference → (every `allocation_interval`) priority scoring + allocator cycle → resource motion → FCFS baseline → metrics → `validate_frame` (assertions on assignment/probability invariants).
- **Observation boundary**: only `simulation/tracks.py` knows the true intent (`HiddenTrack.true_destination`, `behavior`). `observation.py` is the only bridge out of it, and it passes on noisy position and velocity only. `inference.py`, `priority.py` and `allocator.py` must operate only on the public `Track` model. Don't leak hidden fields past this boundary.
- The scenario is authored. Track specs and scripted behaviors (`water_reveal`, `late_airport`, `power_escalation`, `brief_turn`, `ambiguous`, …) in `tracks.py` line up with the narrative `EVENTS` in `simulation/events.py` (T11 at t=32, T03 at t=50, T17 at t=66, and so on). The frontend's demo mode steps through those events. Changing seed, specs or tuning can break the story and tests.
- The allocator (`allocator.py`) is gated by hysteresis (`hysteresis.py`): minimum assignment duration, cooldown, challenger persistence across cycles, and multi-gate "release" to open water (A08). Every state change goes through `audit.record`, which snapshots factors and the full assignment map.
- All tuning lives in `app/config.json`, validated by `SimulationConfig` in `models.py` (`extra='forbid'`). Validators require destinations A01–A08, exactly 8 sites, and `allocation_interval` to be a multiple of `observation_interval`.
- `models.py` holds the public API contracts. The frontend mirrors them with zod schemas in `frontend/src/types.ts`. Keep the two in sync.

### Frontend (`frontend/src/`)

- On load, `api.ts` fetches `/api/scenario` and `/api/run` once and parses them with zod. From then on, playback is **fully client-side**: `usePlayback` advances a float `time` with requestAnimationFrame, and `frameAt(frames, time)` picks the frame. Because of this the dashboard keeps working when the backend goes down (the header's health check just shows "engine offline").
- `CityScene.tsx` (react-three-fiber) interpolates between integer frames. `smoothPosition` in `state.ts` does quintic Hermite interpolation between the backend's position/velocity/acceleration values. The backend's resource paths are C2 quintic segments (`simulation/trajectory.py`, `resources.py`).
- The Vite dev server proxies `/api` and `/health` to :8000. In production, FastAPI mounts `frontend/dist` as static files.
- `frontend/patches/` holds a `patch-package` patch (applied on `postinstall`) to drei's `Html`. drei gives every `<Html>` its own React root and unmounts it synchronously, which React 19 logs as a console error. The patch defers the unmount and is StrictMode-safe. The e2e tests fail on any console error, so keep the patch when upgrading drei.

### Test fixtures

`frontend/src/test/fixture.json` is generated from the real engine. Regenerate it after changing backend output or contracts:

```bash
backend/.venv/bin/python scripts/export_fixture.py
```
