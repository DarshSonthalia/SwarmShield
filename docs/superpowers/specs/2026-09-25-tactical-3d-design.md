# SwarmShield Tactical 3D Visualization Design

## Purpose

Replace the active 2D tactical canvas with a simple, interactive 3D operational viewer while preserving the existing SwarmShield simulation, allocator, scenarios, metrics, events, APIs, dashboard, and one-command local workflow.

The viewer explains altitude, pursuit geometry, assignment changes, failures, peer coordination, deconfliction, intercepts, and leakage. It is a synthetic technical visualization, not a cinematic scene or real-world map.

## Scope and constraints

- The Python backend remains the sole source of simulation truth.
- JavaScript renders existing `data.runs[strategy].trajectories`, events, allocations, decisions, and metrics; it does not simulate or infer operational state.
- Position interpolation is visual only. State, assignment, event, outcome, and metric changes occur only at real discrete backend timestamps.
- Preserve `python -m swarmshield.webapp`, the standard-library `ThreadingHTTPServer`, and the existing API contract.
- No build step, npm runtime, CDN, database, framework migration, GIS, landmarks, realistic vehicles, new networking behavior, allocator redesign, or backend simulation redesign.
- Do not change allocator behavior unless a genuine bug is discovered and reported before modification.

## Architecture

### Application controller: `static/app.js`

`app.js` remains responsible for API requests, generated and custom JSON scenarios, playback and slider state, strategy selection, metrics, comparison, event banner, coordination, and live priorities/decision audit. It becomes an ES module and imports the tactical viewer. It selects the active run and authoritative discrete frame, then passes only rendering inputs to the viewer.

### Renderer: `static/tactical3d.js`

`tactical3d.js` owns the Three.js renderer, scene, cameras, lights, controls, raycasting, world geometry, protected assets, entity meshes, lines, trails, picking, resize behavior, camera presets, resource reuse, and disposal.

The public API is a focused object returned by `initTactical3D(container, options)`, with methods equivalent to:

```js
viewer.loadScenario(payload);
viewer.setStrategy(strategy);
viewer.setTime(timeSeconds, discreteTimeSeconds);
viewer.setVisibility({ trails, assignments, peerLinks });
viewer.setCameraPreset('perspective' | 'top' | 'reset');
viewer.resize();
viewer.dispose();
```

## Data flow and correctness boundary

1. The backend returns the existing comparison payload.
2. `app.js` indexes each run's trajectories by timestamp and records ordered available times.
3. For each UI time, `app.js` determines the authoritative nearest discrete timestamp and updates events, coordination, priorities, and dashboard state.
4. `app.js` calls the viewer with the continuous display time and authoritative discrete time.
5. `tactical3d.js` interpolates only `x`, `y`, and `z` between adjacent real samples.
6. Visibility, state, assignments, committed state, failures, intercepts, leaks, and overlays use the authoritative discrete record or actual event log. No state is predicted between snapshots.
7. Strategy changes reuse the same renderer, replace the active run index, clear strategy-derived trails and lines, update cached entity state, and hide stale entities immediately.

## World and coordinate system

- Simulation `x` maps to Three.js `X`.
- Simulation `y` maps to Three.js `Z`.
- Simulation `z` maps to Three.js `Y` after a visual-only scale.
- `VERTICAL_SCALE` is one configurable constant set to `3`.
- Display `VERTICAL SCALE 3×` and `SYNTHETIC SCENARIO · METRE SCALE · NOT GIS DATA`.
- Simulation data remains unchanged.

The ground is a dark matte plane with a subtle metre-scale grid. Bounds derived from assets and trajectories determine ground size, camera target, camera limits, and reset position.

## Scene objects

Every asset receives a ground marker, visual footprint, and visible name label. Critical assets use stronger amber emphasis. Since the payload exposes no asset radius, footprints are decorative and are not described as protection ranges.

Threats use shared low-poly cone/arrowhead geometry. Assigned active threats are red/pink; unassigned active threats are amber; intercepted threats disappear; leaked threats receive brief event-driven feedback before becoming inactive.

Interceptors use shared low-poly geometry distinct from threats. Available, holding, and engaging states are green/cyan; failed interceptors are grey; spent interceptors are hidden. Committed state uses a subtle accent.

One cached assignment line per interceptor connects it to its current discrete-snapshot target. Lines hide or retarget immediately on assignment changes. Threat and interceptor trails cover at most the previous 20 seconds and contain actual backend positions only. Trail buffers update only when discrete time changes. Optional peer links appear only when backend coordination reports peer mode and remain labelled as simulated.

## Interaction and labels

- OrbitControls provide rotate, pan, and zoom with bounded distance and target.
- Perspective is the scenario-derived default and frames protected assets and incoming tracks.
- Top-down gives a map-like view; Reset restores the default perspective.
- Asset labels remain visible through lightweight DOM overlays.
- Moving entities have no permanent labels. Raycasting drives a compact hover/click panel containing only payload fields.
- Native HTML controls provide camera presets and visibility toggles; no extra UI library is introduced.

## Event feedback

The existing event banner stays authoritative. The scene adds restrained feedback driven only by real records/events: failed interceptors turn grey; assignment lines switch on actual assignments; peer mode mirrors coordination state; collision-avoidance events briefly highlight the named interceptor with `DECONFLICT`; trajectory changes show diversions; intercept/leak feedback follows actual snapshots and event timestamps.

## Performance and lifecycle

- Cache entity meshes in `Map` objects keyed by ID.
- Share low-poly geometry and base materials where practical.
- Update transforms, visibility, color, and line endpoints in place.
- Never rebuild the scene per playback frame.
- Bound trails to 20 seconds and update them only at discrete-time changes.
- Avoid permanent moving-object DOM labels.
- Use one renderer and scene for both strategies.
- Dispose scenario-owned resources, controls, observers, and overlays during rebuild/disposal.
- Cap device pixel ratio and validate a 200-threat/120-interceptor payload.

## Responsive behavior

A `ResizeObserver` watches the scene container. Resizing updates renderer dimensions, camera aspect, projection matrix, and label positions. Existing responsive dashboard behavior remains intact.

## Dependency strategy

Vendor one fixed official Three.js release and matching `OrbitControls.js` under `static/vendor/`. Record the exact release, upstream URLs, and license in `static/vendor/README.md`. Imports are local, with no runtime network or npm dependency.

## HTML and styling

Replace only the active canvas portion with `#tacticalScene` and operational overlays. Preserve the builder, JSON editor, strategy toggle, playback, event banner, mission effects, coordination, live priorities/decision audit, comparison, and model-boundary disclaimer. Load `app.js` with `type="module"`. Preserve the restrained dark green tactical identity.

## Backend changes

No backend change is planned. Existing payloads contain the required position, altitude, state, assignment, risk, asset, committed, class, scenario, event, allocation, decision, and metric data. If missing data is discovered, stop and report it before changing backend behavior.

## Testing and verification

Add dependency-free static-structure tests for the Three.js module, local vendor imports, scene container, module script, disclaimers, and removal of the active 2D canvas. Test that the Python server serves modules/vendor files with JavaScript MIME types. Preserve and run all unit tests through `python -m unittest discover -s tests -v`.

Manual browser verification covers first load, health API, generated/custom scenarios, validation errors, dynamic events, counts, seed, duration, play/pause/replay, slider scrubbing, strategy switching without stale state, metrics, priorities, comparison, banner, coordination, camera presets, controls, resize, failure/reassignment/recovery/deconfliction/link-loss/intercept/leak visuals, maximum-size responsiveness, console errors, and runtime network requests.

## Safe 2D retirement

Remove the 2D canvas from active HTML only after structural tests exist and fail for the old UI. Replace its renderer behind those tests. Once the 3D path is verified, delete dead 2D functions and variables instead of retaining intertwined rendering systems.

## Acceptance criteria

Running `python -m swarmshield.webapp` and opening `http://127.0.0.1:8765` shows one responsive 3D synthetic operational scene driven entirely by backend trajectories. It displays protected assets, altitude, active entities, assignments, bounded trails, discrete state changes, restrained event feedback, camera presets, and existing dashboard outputs. Generated/custom scenarios, strategy switching, playback, metrics, coordination, priorities, comparison, event banner, and all existing tests continue working.
