"""Evaluate a family of synthetic scenarios, including unfavourable cases."""

from __future__ import annotations

import argparse
import json
import statistics

from swarmshield.scenario import build_scenario
from swarmshield.simulator import run_comparison


PROFILES = ("mixed", "concentrated", "dispersed", "uncertain")


def evaluate(
    threats: int, interceptors: int, duration: int, seed_start: int,
    seeds: int, profiles: list[str], events: bool = True,
) -> dict:
    if not 1 <= seeds <= 100:
        raise ValueError("seeds must be between 1 and 100")
    if not 0 <= seed_start <= 1_000_000 or seed_start + seeds - 1 > 1_000_000:
        raise ValueError("seed range must stay between 0 and 1,000,000")
    if not profiles or any(profile not in PROFILES for profile in profiles):
        raise ValueError("profiles must name at least one supported pattern")
    rows = []
    for profile in profiles:
        for seed in range(seed_start, seed_start + seeds):
            result = run_comparison(build_scenario(
                threats, interceptors, seed=seed, duration_s=duration,
                enable_events=events, profile=profile,
            ))
            baseline = result["runs"]["baseline"]["metrics"]
            shield = result["runs"]["swarmshield"]["metrics"]
            rows.append({
                "profile": profile,
                "seed": seed,
                "consequence_change_percent": result["headline"]["expected_consequence_reduction_percent"],
                "baseline_consequence": baseline["expected_consequence_leaked"],
                "swarmshield_consequence": shield["expected_consequence_leaked"],
                "baseline_leaks": baseline["leakage"],
                "swarmshield_leaks": shield["leakage"],
                "peer_claim_conflicts": shield["peer_conflict_snapshots"],
            })
    changes = [row["consequence_change_percent"] for row in rows]
    return {
        "scenario_count": len(rows),
        "threats": threats,
        "interceptors": interceptors,
        "duration_s": duration,
        "better_count": sum(value > 0 for value in changes),
        "equal_count": sum(value == 0 for value in changes),
        "worse_count": sum(value < 0 for value in changes),
        "median_consequence_change_percent": round(statistics.median(changes), 2),
        "worst_consequence_change_percent": min(changes),
        "best_consequence_change_percent": max(changes),
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress-test SwarmShield across seeds and scenario patterns")
    parser.add_argument("--threats", type=int, default=20)
    parser.add_argument("--interceptors", type=int, default=12)
    parser.add_argument("--duration", type=int, default=190)
    parser.add_argument("--seeds", type=int, default=5, help="Number of consecutive seeds (1-100)")
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--no-events", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    result = evaluate(
        args.threats, args.interceptors, args.duration, args.seed_start,
        args.seeds, args.profiles, events=not args.no_events,
    )
    if args.summary_only:
        result.pop("cases")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
