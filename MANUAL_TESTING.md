# Manual testing checklist

Use this checklist before judging or recording. Expected outcomes are explicit so a second teammate can verify the build without reading the code.

## 1. Start the dashboard

From the project folder, run:

```powershell
python -m swarmshield.webapp
```

On Windows, use `py -m swarmshield.webapp` if `python` is not on PATH.

Open `http://127.0.0.1:8765` in a browser.

Expected:

- Header reads `SCENARIO READY / SEED 42`.
- The full map shows 20 track markers, 12 interceptor markers, a synthetic city, and five protected-zone footprints.
- **City close-up** zooms to the road blocks and protected zones; **Full approach** returns to the entire scenario.
- Open **What do these controls and results mean?** and confirm Seed, Pattern, Dynamic events, and expected consequence are explained.
- SwarmShield is selected by default.
- The mission-effect value matches `demo_output/metrics.json`.

## 2. Test playback and events

Click **Run engagement**.

Expected:

- The time counter advances and all tracks move.
- Assignment lines join interceptors to selected threats.
- Unallocated threats remain amber.
- At T+19 s, I08 loses availability and the system rechecks its assignment.
- At T+25 s, the ground link fails; the badge says **PEER MODE** and shows the current number of groups.
- At T+32 s, T18 changes course toward the Command Centre and rises in **Live priorities**.
- At T+36 s, peer connectivity degrades; by T+42 s multiple groups are visible.
- At T+42 s, T17 confidence drops; at T+51 s, the Industrial Zone's consequence changes.
- At T+72 s, ground coordination is restored.
- The comparison reports peer claim conflicts rather than implying perfect coordination across disconnected groups.
- Intercepted threats and spent interceptors disappear from the active display.

Move the time slider backward and forward. The view must update immediately without restarting the server.

## 3. Test baseline comparison

Select **Naive baseline**.

Expected:

- The same attack geometry and event timing are retained.
- The live priority list updates from the same threat data, but the baseline keeps its static assignments.
- In the default seed, expected consequence is higher for the baseline; critical and total leak counts are equal.
- Raw leakage remains the same in the seeded scenario. SwarmShield changes which threats leak rather than claiming extra ammunition.

Return to **SwarmShield** and confirm the metrics revert.

## 4. Test arbitrary generated scenarios

Try these combinations with **Generate scenario**. Change the seed and switch among Mixed, Concentrated, Dispersed, and Uncertain. Reusing the same seed and controls must reproduce the same results.

| Threats | Interceptors | Duration | What to verify |
|---:|---:|---:|---|
| 1 | 0 | 60 | No crash; zero assignments; leakage is reported. |
| 3 | 10 | 90 | More resources than tracks; initial central assignments are unique. |
| 12 | 30 | 120 | The outcome is computed even when resources are plentiful. |
| 50 | 8 | 120 | Scarcity produces explicit unallocated tracks. |
| 80 | 60 | 90 | Larger runs load and the slider remains responsive. |
| 200 | 120 | 600 | Boundaries load; the playback label discloses downsampled visual frames. |

The optimized strategy can be worse than the baseline for some configurations. The dashboard must show that honestly, including a **higher expected consequence** label when applicable.

## 5. Test a custom scenario

Open **Advanced: edit a complete scenario**. The editor contains the current valid scenario in JSON.

1. Change `name`, an asset `consequence` and `radius_m`, and one threat's `p_hostile`. Click **Run custom scenario**.
2. Confirm the title, trajectory, decision audit, and comparison update.
3. Change a threat's `asset_id` to a nonexistent ID and run it again. The header must show a validation error; the previous valid run should remain visible.
4. Click **Reset to current scenario** to restore a valid template.

Coordinates and protected-zone radii use metres, velocity uses metres per second, and each threat's velocity should intersect its named protected zone if it is expected to reach that zone. Try adding a `confidence_update` or `asset_consequence_change` event. The editor accepts 1-20 assets, 1-200 threats, 0-120 interceptors, and 30-600 seconds.

## 6. Test the API

Open `http://127.0.0.1:8765/api/health`.

Expected response:

```json
{"status":"ok","version":"1.1"}
```

Open `http://127.0.0.1:8765/api/run?threats=7&interceptors=3&seed=9&duration=90&events=0&profile=uncertain` and confirm the response contains `scenario`, `runs.baseline`, `runs.swarmshield`, and `headline`, with the requested counts and profile. Invalid query values return HTTP 400 with a JSON error.

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
- Point to the changing priority list, explicit unassigned decisions, and protected-zone footprints.
- Call peer mode a simulation of proximity groups and local visibility; it is not a working radio network.
- Describe the allocator as a recommendation/coordination layer, not an autonomous lethal system.
