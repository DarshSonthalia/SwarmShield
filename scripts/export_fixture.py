"""Regenerate frontend contract fixtures from the real deterministic engine."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import load_config
from app.simulation.world import World
from app.simulation.events import EVENTS

w=World(load_config())
scenario={'name':'Meridian Bay','description':'Fictional coastal city','config':w.config.model_dump(),'events':[e.model_dump() for e in EVENTS], 'units':'abstract scene units','baseline':'First come, first served'}
out=ROOT/'frontend/src/test/fixture.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'scenario':scenario,'frames':[w.frame(t).model_dump() for t in [0,12,40,52,84,120]],'audit':[a.model_dump() for a in w.audit]},indent=2)+'\n')
print(f'Generated {out.relative_to(ROOT)} from seed {w.config.seed}')
