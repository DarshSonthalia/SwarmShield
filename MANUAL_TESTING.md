# Manual testing checklist

Use this checklist before judging or recording. Expected outcomes are explicit so a second teammate can verify the build without reading the code.

## Uncertainty-aware acceptance checks

- Confirm only **Naive baseline** and **SwarmShield** are selectable.
- Hover T05 at T+0: the detail card shows likely destination, probability, uncertainty, urgency, risk, HOLD, and no true destination.
- At T+32, confirm T05 changes course and the backend event/tooltip moves to COMMIT.
- At T+33, confirm I09 fails and T05 is recovered/retasked to I11.
- Confirm aggregate first-commit accuracy, entropy, and Brier evidence appears in Decision Audit.
- Repeat generated and custom JSON runs and confirm beliefs remain deterministic.

## 1. Start the dashboard

From the project folder, run:

```powershell
python -m swarmshield.webapp
```

On Windows, use `py -m swarmshield.webapp` if `python` is not on PATH.

Open `http://127.0.0.1:8765` in a browser.

Expected:

- Header reads `SCENARIO READY / SEED 42`.
- The 3D scene shows 20 threat markers, 12 interceptor markers, and five labelled protected assets.
- The caption states `SYNTHETIC SCENARIO · METRE SCALE · NOT GIS DATA · VERTICAL SCALE 3×`.
- Orbit, pan, zoom, Perspective, Top-down, and Reset keep the scene recoverable.
- SwarmShield is selected by default.
- The mission-effect value matches `demo_output/metrics.json`.

## 2. Test playback and events

Click **Run engagement**.

Expected:

- The time counter advances and all tracks move.
- Assignment lines join interceptors to selected threats.
- Unallocated threats remain amber.
- Around T+32 s, the T05 diversion warning appears.
- At T+19 s, I07 fails and T13 is recovered by I09.
- At T+66 s, the network badge changes from `GROUND LINK` to `P2P ACTIVE`.
- Intercepted threats and spent interceptors disappear from the active display.

Move the time slider backward and forward. The view must update immediately without restarting the server.

Toggle **Trails**, **Assignments**, and **Peer links**. Trails remain bounded to
the recent path, assignment lines show only current backend assignments, and
peer links appear only during simulated peer-to-peer coordination.

## 3. Test baseline comparison

Select **Naive baseline**.

Expected:

- The same attack geometry and event timing are retained.
- The decision audit changes to baseline choices.
- The displayed critical leakage and expected consequence are worse than SwarmShield.
- Raw leakage remains the same in the seeded judging scenario. This is intentional: one failed round means both strategies have eleven successful attempts; SwarmShield changes which threats leak rather than claiming extra ammunition.

Return to **SwarmShield** and confirm the metrics revert.

## 4. Test arbitrary generated scenarios

Try these combinations with **Generate scenario**. Change the seed as well.

| Threats | Interceptors | Duration | What to verify |
|---:|---:|---:|---|
| 1 | 0 | 60 | No crash; zero assignments; leakage is reported. |
| 3 | 10 | 90 | More resources than tracks; no duplicate target assignments. |
| 12 | 30 | 120 | The outcome is computed even when resources are plentiful. |
| 50 | 8 | 120 | Scarcity produces explicit unallocated tracks. |
| 80 | 60 | 90 | Larger runs load and the slider remains responsive. |

The optimized strategy can be worse than the baseline for some configurations. The dashboard must show that honestly, including a **higher expected consequence** label when applicable.

## 5. Test a custom scenario

Open **Advanced: edit a complete scenario**. The editor contains the current valid scenario in JSON.

1. Change `name`, an asset `consequence`, and one threat's `p_hostile`. Click **Run custom scenario**.
2. Confirm the title, trajectory, decision audit, and comparison update.
3. Change a threat's `asset_id` to a nonexistent ID and run it again. The header must show a validation error; the previous valid run should remain visible.
4. Click **Reset to current scenario** to restore a valid template.

Coordinates use metres, velocity uses metres per second, and each threat's velocity should point toward its named asset if it is expected to reach that asset. The editor accepts 1-20 assets, 1-200 threats, 0-120 interceptors, and 30-600 seconds.

## 6. Test the API

Open `http://127.0.0.1:8765/api/health`.

Expected response:

```json
{"status":"ok","version":"1.0"}
```

Open `http://127.0.0.1:8765/api/run?threats=7&interceptors=3&seed=9&duration=90&events=0` and confirm the response contains `scenario`, `runs.baseline`, `runs.swarmshield`, and `headline`, with the requested counts. Invalid query values return HTTP 400 with a JSON error.

## 7. Run automated verification

Stop the server with Ctrl+C, then run:

```powershell
python -m unittest discover -s tests -v
python run.py --export demo_output\engagement.json
```

Expected:

- All tests report `ok`.
- The export command prints the baseline and SwarmShield metrics.
- Running the export again produces the same headline metrics.

## 8. Judge-facing sanity checks

- Never say the system intercepts all 20 threats with 12 rounds.
- State that the headline result is scenario-specific and simulated.
- Explain why equal raw leakage can still mean dramatically different defensive outcomes.
- Point to the visible unallocated decisions and the auditable risk components.
- Describe the allocator as a recommendation/coordination layer, not an autonomous lethal system.

## 9. 3D browser and performance checks

- Resize the browser through wide desktop, the 1000 px breakpoint, and a narrow mobile layout. The WebGL canvas, labels, camera aspect, controls, panels, and timeline must remain usable.
- Switch repeatedly between baseline and SwarmShield while paused and playing. No stale meshes, trails, assignment lines, peer links, or event markers may remain.
- Hover moving entities. The compact detail panel must use payload fields only; moving entities must not have permanent DOM labels.
- Generate 200 threats, 120 interceptors, and a 30-second duration. Playback, scrubbing, camera controls, and strategy switching must remain responsive.
- Inspect the browser console and network panel. There must be no JavaScript errors and no runtime CDN/network dependency; Three.js files load from `/vendor/`.
