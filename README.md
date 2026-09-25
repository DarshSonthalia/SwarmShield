# SwarmShield

SwarmShield is a deterministic, explainable simulation of scarce interceptor allocation for SDTH 2026 Track 3, Layer 3. The app accepts generated raids with different force sizes and a complete editable JSON scenario.

The prototype treats **no interceptor allocated** as an explicit decision, weighs unavoidable leakage by protected-zone consequence, and retasks before commitment when tracks or assessments change. It models degraded peer coordination after a ground-link loss and compares outcomes against a static nearest-feasible-target baseline. It is an advisory simulation, not a real-world engagement system.

## What is included

- A dependency-free Python simulation and rectangular assignment solver.
- A browser dashboard with a synthetic city map, protected-zone footprints, a city close-up, live priority list, time scrubber, and baseline toggle.
- A reproducible default 20-threat / 12-interceptor scenario at metre scale.
- A generator for 1-200 threats, 0-120 interceptors, reproducible seeds, four scenario patterns, durations, and dynamic events.
- A custom JSON editor for protected zones, positions, velocities, confidence, interceptor capabilities, and events.
- Simulated local peer visibility, network partitioning, and conflicting claims, rather than a fictitious globally shared ledger.
- Automated tests covering balanced, scarce, over-provisioned, tiny, and large scenarios, plus invalid inputs.
- An export command for an engagement dataset when the later visualization phase begins.

## One-command product run

From this folder on Windows:

```powershell
python -m swarmshield.webapp
```

Open `http://127.0.0.1:8765`. The app uses only Python's standard library.

Use **Generate scenario** to vary counts, seed, pattern, duration, or dynamic events. The same seed plus the same settings reproduces the same generated scenario. Open **Advanced: edit a complete scenario** to edit the full scenario as JSON. The editor starts with a valid template; click **Run custom scenario** to simulate it. Invalid references or out-of-range values produce a validation error in the header.

The model supports its documented input bounds. It may score below the baseline in some scenarios; the UI displays that result directly. A finite simulation horizon reports projected leakage for unresolved tracks still headed toward a protected zone. Physics and allocation still run at one-second steps in large scenarios; only browser visualization frames are downsampled. These are simulation results, not performance claims for real systems.

If `python` is not on PATH on Windows, try the Python launcher (`py`) instead.

## Validate and export

```powershell
python -m unittest discover -s tests -v
python run.py --export demo_output\engagement.json
python run.py --profile concentrated --seed 17
python evaluate.py --seeds 5 --summary-only
```

The evaluation command reports better, equal, and worse cases across patterns and seeds. The JSON export is the contract for a later visual demo. The app is the deliverable for this phase; the video remains paused until app testing is complete. See [MODEL_NOTES.md](MODEL_NOTES.md) for the simulation design and the gap to any real deployment.

## Safety and claim discipline

This is a simulation and decision-support prototype. It contains no real targeting interfaces, flight-controller integration, weapons control, classified data, or claim of operational validation. Its novelty claim is the hackathon-level integration of explicit non-engagement, consequence-weighted leakage, pre-commitment retasking, and measured degradation—not the invention of auctions or weapon-target assignment.
