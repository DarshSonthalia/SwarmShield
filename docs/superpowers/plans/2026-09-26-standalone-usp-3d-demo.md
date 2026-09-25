# Standalone USP 3D Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated Matplotlib 3D renderer for an actual recorded uncertainty-aware SwarmShield version-1.0 run.

**Architecture:** `demo/demo_usp_3d.py` is a read-only consumer of the existing comparison export. Pure loading/indexing/selection helpers remain importable without Matplotlib; rendering imports Matplotlib lazily and never calls predictor, allocator, or simulator code.

**Tech Stack:** Python 3 standard library, optional Matplotlib, existing unittest suite and version-1.0 JSON export.

## Global Constraints

- Keep `schema_version: "1.0"` as the only run schema.
- Display recorded beliefs, decisions, assignments, coordinates, and timestamped events without recomputation.
- Never display ground-truth `asset_id` in the normal visualizer.
- Do not commit the generated multi-megabyte `demo/sample_run.json`.
- Preserve all existing `run.py` behavior; `--usp-demo` only chooses `build_hackathon_scenario()`.

---

### Task 1: Read-Only Recording Helpers

**Files:** Create `demo/__init__.py`, `demo/demo_usp_3d.py`, `tests/test_demo_usp_3d.py`.

- [ ] Write failing tests for valid loading, missing file, unsupported/malformed schema, empty trajectories, missing beliefs, requested threat lookup, deterministic auto-selection priority, frame lookup, descending probabilities, and absence of `asset_id` reads.
- [ ] Run `python -m unittest discover -s tests -p test_demo_usp_3d.py -v` and confirm failures are caused by the missing module.
- [ ] Implement `DemoDataError`, `load_recording(path)`, `available_threats(recording)`, `select_focus_threat(recording, requested=None)`, `build_frame_index(run)`, `frame_at(index, time_s)`, `probability_rows(frame, assets)`, and `events_at(run, time_s)` using copied/read-only dictionaries only.
- [ ] Rerun the focused tests and commit.

### Task 2: Recorded Matplotlib Scene

**Files:** Modify `demo/demo_usp_3d.py`, `tests/test_demo_usp_3d.py`.

- [ ] Add a failing test proving Matplotlib is not imported when the helper module is imported.
- [ ] Implement lazy `_load_matplotlib()` with the prescribed friendly installation error.
- [ ] Implement `UspDemo3D` using recorded frames: ground assets, threat/interceptor markers, bounded 20-second trails, current assignment lines, probability-weighted focus-to-asset lines, and a sorted recorded-value information panel.
- [ ] Map frame HOLD to `HOLD / PRESERVE`; use actual `commit`, `retask`, failure, diversion, recovery, and link-loss events for banners and RETASK messaging.
- [ ] Add SPACE, LEFT, RIGHT, and R controls plus `FuncAnimation`; do not interpolate decisions or events.
- [ ] Run focused tests and commit.

### Task 3: CLI and Export Selection

**Files:** Modify `demo/demo_usp_3d.py`, `run.py`, `tests/test_demo_usp_3d.py`.

- [ ] Add failing CLI/parser tests for `--input`, optional `--threat`, friendly validation errors, and `run.py --usp-demo` selection.
- [ ] Add `--usp-demo` to `run.py`; select `build_hackathon_scenario(args.seed)` only when supplied, otherwise preserve `build_scenario(...)` exactly.
- [ ] Add visualizer `main()` returning friendly one-line errors without normal-user tracebacks.
- [ ] Run focused and full tests, then commit.

### Task 4: Documentation and Generated-File Policy

**Files:** Modify `README.md`, `.gitignore`.

- [ ] Ignore `demo/sample_run.json`.
- [ ] Document `pip install matplotlib`, export, launch, controls, renderer-only architecture, and the browser app's continued primary role.
- [ ] Run `git diff --check` and commit.

### Task 5: End-to-End Verification and Integration

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `python run.py --usp-demo --export demo/sample_run.json` and validate the generated version-1.0 recording.
- [ ] Run `python demo/demo_usp_3d.py --input demo/sample_run.json --threat T05` with a non-blocking verification option/environment suitable for automation, while preserving normal interactive launch behavior.
- [ ] Confirm T05's recorded HOLD → COMMIT → failure → RETASK sequence and that the renderer source contains no predictor/scoring/allocation implementation.
- [ ] Remove the generated ignored sample, review the diff, merge locally into `main`, rerun tests, and clean up the worktree.
