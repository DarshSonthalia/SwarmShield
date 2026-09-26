#!/usr/bin/env python3
"""Collect reproducible test and metric evidence for the technical archive."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'
EVIDENCE=ROOT/'evidence'
PYTHON=BACKEND/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
NPM='npm.cmd' if os.name=='nt' else 'npm'

def capture(name: str, command: list[str], cwd: Path) -> bool:
    result=subprocess.run(command,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (EVIDENCE/name).write_text(result.stdout,encoding='utf-8')
    print(f'{name}: {"PASS" if result.returncode==0 else "FAIL"}')
    return result.returncode==0

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,default=30)
    parser.add_argument('--skip-e2e',action='store_true',help='omit browser evidence when Playwright is unavailable')
    args=parser.parse_args()
    EVIDENCE.mkdir(exist_ok=True)
    ok=[capture('backend_tests.txt',[str(PYTHON),'-m','pytest','-q'],BACKEND)]
    ok.append(capture('frontend_tests.txt',[NPM,'test'],ROOT/'frontend'))
    if not args.skip_e2e:
        ok.append(capture('e2e_tests.txt',[NPM,'run','test:e2e'],ROOT))
    sys.path.insert(0,str(BACKEND))
    from app.config import load_config
    from app.simulation.world import World
    metrics=World(load_config()).frames[-1].metrics.model_dump()
    (EVIDENCE/'default_metrics.json').write_text(json.dumps(metrics,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    stress=EVIDENCE/f'stress_test_{args.seeds}_seeds.json'
    ok.append(capture(stress.name,[str(PYTHON),str(ROOT/'scripts/stress_eval.py'),'--seeds',str(args.seeds),'--output',str(stress)],ROOT))
    if not all(ok):
        raise SystemExit(1)

if __name__=='__main__':
    main()
