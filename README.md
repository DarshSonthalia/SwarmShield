# SwarmShield

SwarmShield is a deterministic, explainable simulation of scarce interceptor allocation for SDTH 2026 Track 3, Layer 3. The app accepts generated raids with different force sizes and a complete editable JSON scenario.

The prototype treats **no interceptor allocated** as an explicit decision, estimates destination beliefs from observed geometry, minimizes the expected consequence of unavoidable leakage, retasks before commitment, recovers an orphaned target after a round fails, continues through a simulated ground-link loss using peer components, and compares itself against a static nearest-feasible-target baseline.

## Uncertainty-aware decision model

The submission compares exactly two strategies: a naive nearest-feasible baseline and uncertainty-aware SwarmShield. Both receive the same observed positions, velocities, track history, belief update cadence, and conservative feasible horizon. `Threat.asset_id` is reserved for trajectory physics, scripted diversion, terminal leakage, and post-decision evaluation; it is not available to prediction, risk, prioritization, feasibility, or allocation.

Destination probabilities are deterministic geometric estimates based on smoothed heading alignment and projected miss distance. SwarmShield uses `hostile probability × expected consequence × probability-weighted urgency` as risk. Normalized entropy remains a separate uncertainty measure and contributes only a bounded commitment friction that fades as urgency rises. Prediction accuracy, entropy, and multiclass Brier score are evaluated against ground truth at each threat's first commitment.

The previous SwarmShield version used the known scenario destination directly during allocation. That known-destination behavior is not a selectable strategy in this build. A useful future three-way ablation would compare naive nearest-feasible, known-destination SwarmShield, and uncertainty-aware SwarmShield.

## What is included

- A dependency-free Python simulation and rectangular assignment solver.
- A polished browser dashboard with an interactive 3D tactical viewer, time scrubber, audit trail, event playback, and baseline toggle.
- A reproducible default 20-threat / 12-interceptor scenario at metre scale.
- A generator for 1-200 threats, 0-120 interceptors, seeds, durations, and dynamic events.
- A custom JSON editor for assets, starting positions, velocities, confidence, interceptor capabilities, and events.
- Automated tests covering balanced, scarce, over-provisioned, tiny, and large scenarios, plus invalid inputs.
- An export command for an engagement dataset when the later visualization phase begins.

## One-command product run

From this folder on Windows:

```powershell
python -m swarmshield.webapp
```

Open `http://127.0.0.1:8765`. The app uses only Python's standard library.

The operational view uses locally vendored Three.js r186 and requires no
Internet connection or JavaScript build step. Drag to orbit, right-drag to
pan, and scroll to zoom. **Perspective**, **Top-down**, and **Reset** provide
safe camera presets; trails, current assignments, and simulated peer links can
be toggled independently.

Simulation `(x, y, z)` is rendered as Three.js `(X, Y, Z) = (x, z × 3, y)`.
The 3× vertical exaggeration is visual only. Entity states, assignments,
events, outcomes, and metrics always come from discrete Python trajectory
snapshots. The scene is synthetic metre-scale data, not GIS data.

Use **Generate scenario** to vary counts, seed, duration, or dynamic events. Open **Advanced: edit a complete scenario** to edit the full scenario as JSON. The editor starts with a valid template; click **Run custom scenario** to simulate it. Invalid references or out-of-range values produce a validation error in the header.

The model supports its documented input bounds. It may score below the baseline in some scenarios; the UI displays that result directly. A finite simulation horizon also reports projected leakage for unresolved tracks still headed toward an asset. These are simulation results, not performance claims for real systems.

If `python` is not on PATH on Windows, try the Python launcher (`py`) instead.

## Validate and export

```powershell
python -m unittest discover -s tests -v
python run.py --export demo_output\engagement.json
```

The JSON is the contract for a later visual demo. The app is the deliverable for this phase; the video will be built after app testing.

## Safety and claim discipline

This is a simulation and decision-support prototype. It contains no real targeting interfaces, flight-controller integration, weapons control, classified data, or claim of operational validation. Its novelty claim is the hackathon-level integration of explicit non-engagement, consequence-weighted leakage, pre-commitment retasking, and measured degradation—not the invention of auctions or weapon-target assignment.
