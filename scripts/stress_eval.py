#!/usr/bin/env python3
"""Evaluate the authored scenario under multiple observation-noise seeds."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

from app.config import load_config
from app.simulation.stress import aggregate_runs
from app.simulation.world import World

def evaluate(seed_count: int) -> dict:
    if seed_count < 1:
        raise ValueError('--seeds must be at least 1')
    runs=[]
    for seed in range(seed_count):
        config=load_config()
        config.seed=seed
        metrics=World(config).frames[-1].metrics
        runs.append({'seed':seed,'swarmshield':metrics.swarm.model_dump(),'baseline':metrics.baseline.model_dump()})
    return {'seed_count':seed_count,'seeds':[run['seed'] for run in runs],'summary':aggregate_runs(runs),'runs':runs}

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,default=30,help='number of observation-noise seeds (default: 30)')
    parser.add_argument('--output',type=Path,help='optional JSON output path')
    args=parser.parse_args()
    result=evaluate(args.seeds)
    text=json.dumps(result,indent=2,sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf-8')
    print(text)

if __name__=='__main__':
    main()
