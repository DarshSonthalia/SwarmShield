from __future__ import annotations

import argparse
import json
from pathlib import Path

from swarmshield.scenario import build_scenario
from swarmshield.simulator import run_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="SwarmShield simulator")
    parser.add_argument("--export", type=Path, help="Write complete simulation JSON")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threats", type=int, default=20)
    parser.add_argument("--interceptors", type=int, default=12)
    parser.add_argument("--duration", type=int, default=190)
    parser.add_argument("--profile", choices=["mixed", "concentrated", "dispersed", "uncertain"], default="mixed")
    parser.add_argument("--no-events", action="store_true")
    args = parser.parse_args()
    result = run_comparison(
        build_scenario(
            threat_count=args.threats,
            interceptor_count=args.interceptors,
            seed=args.seed,
            duration_s=args.duration,
            enable_events=not args.no_events,
            profile=args.profile,
        )
    )
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(json.dumps(result, indent=2), encoding="utf-8")
        metrics_path = args.export.parent / "metrics.json"
        metrics_path.write_text(
            json.dumps(
                {
                    "headline": result["headline"],
                    "baseline": result["runs"]["baseline"]["metrics"],
                    "swarmshield": result["runs"]["swarmshield"]["metrics"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Exported {args.export}")
        print(f"Exported {metrics_path}")
    print(json.dumps({"headline": result["headline"], "metrics": {k: v["metrics"] for k, v in result["runs"].items()}}, indent=2))


if __name__ == "__main__":
    main()
