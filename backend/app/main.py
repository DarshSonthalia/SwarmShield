from contextlib import asynccontextmanager
from threading import RLock
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .config import load_config
from .models import ResetRequest, StepRequest, Frame, Track, Resource, AuditEntry, Metrics, RunResponse, SimulationConfig
from .simulation.world import World
from .simulation.events import EVENTS

lock = RLock()
world: World | None = None

def current() -> World:
    global world
    with lock:
        if world is None:
            world = World(load_config())
        return world

@asynccontextmanager
async def lifespan(app):
    current()
    yield

app = FastAPI(title='SwarmShield',version='1.0.0',description='Fictional allocation and uncertainty simulator. Arbitrary scene units only.',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['GET','POST'],allow_headers=['Content-Type'])
app.add_middleware(GZipMiddleware,minimum_size=1000)

@app.get('/health')
def health():
    return {'status':'ok','simulation':'fictional','seed':current().config.seed}

@app.get('/api/config',response_model=SimulationConfig)
def config():
    return current().config

@app.get('/api/scenario')
def scenario():
    cfg = current().config
    return {'name':'Meridian Bay','description':'Fictional coastal city · Allocation under uncertainty','config':cfg,'events':EVENTS,
            'units':'abstract scene units','baseline':'First come, first served (track ID breaks simultaneous-detection ties)'}

@app.post('/api/reset',response_model=Frame)
def reset(body: ResetRequest):
    global world
    with lock:
        cfg = load_config()
        if body.seed is not None:
            cfg.seed = body.seed
        replacement = World(cfg)
        world = replacement
        return replacement.frame(0)

@app.post('/api/step',response_model=Frame)
def step(body: StepRequest):
    with lock:
        return current().step(body.seconds)

@app.post('/api/run',response_model=RunResponse)
def run():
    return current().run()

@app.get('/api/frame/{time}',response_model=Frame)
def frame(time: float):
    try:
        return current().frame(time)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

def at(time: float | None):
    w = current()
    try:
        return w.frame(w.cursor if time is None else time)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.get('/api/tracks',response_model=list[Track])
def tracks(time: float | None = Query(default=None)):
    return at(time).tracks

@app.get('/api/tracks/{id}',response_model=Track)
def track(id: str,time: float | None = Query(default=None)):
    result = next((t for t in at(time).tracks if t.id==id),None)
    if result is None:
        raise HTTPException(404,'Unknown track')
    return result

@app.get('/api/resources',response_model=list[Resource])
def resources(time: float | None = Query(default=None)):
    return at(time).resources

@app.get('/api/resources/{id}',response_model=Resource)
def resource(id: str,time: float | None = Query(default=None)):
    result = next((r for r in at(time).resources if r.id==id),None)
    if result is None:
        raise HTTPException(404,'Unknown resource')
    return result

@app.get('/api/audit',response_model=list[AuditEntry])
def audit(time: float | None = Query(default=None),track_id: str | None = None):
    w = current()
    try:
        snapshot = w.frame(w.cursor if time is None else time)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    if track_id and track_id not in {t.id for t in snapshot.tracks}:
        raise HTTPException(404,'Unknown track')
    return [a for a in w.audit[:snapshot.audit_count] if not track_id or a.track_id==track_id]

@app.get('/api/metrics',response_model=Metrics)
def metrics(time: float | None = Query(default=None)):
    return at(time).metrics

@app.get('/api/baseline')
def baseline(time: float | None = Query(default=None)):
    f = at(time)
    return {'name':'First come, first served','time':f.time,'assignments':f.baseline_assignments,'metrics':f.metrics.baseline,'swarm':f.metrics.swarm}

# After a production build, the API also serves the complete offline dashboard.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
DIST=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if DIST.is_dir():
    app.mount('/',StaticFiles(directory=DIST,html=True),name='dashboard')
