import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, ArrowUpRight, Box, ChartNoAxesCombined, Check, ChevronDown, CircleHelp, Eye, Layers3, ListFilter, Maximize, Play, Radio, RotateCcw, Shield, Sparkles, WifiOff, X } from 'lucide-react'
import { loadSimulation } from './api'
import type { Layers, Run, Scenario, Selection, Vec3 } from './types'
import { clock,frameAt,pct } from './state'
import { usePlayback } from './hooks/usePlayback'
import { TrackList } from './components/TrackList'
import { Inspector } from './components/Inspector'
import { CityScene } from './components/CityScene'
import { Timeline } from './components/Timeline'
import { AuditDrawer } from './components/Audit'
import { ComparisonPanel } from './components/Comparison'

function Dashboard({run,scenario}:{run:Run;scenario:Scenario}){
  const playback=usePlayback(run.duration)
  const frame=frameAt(run.frames,playback.time),m=frame.metrics
  const [selection,setSelection]=useState<Selection>({kind:'track',id:'T11'})
  const [drawer,setDrawer]=useState<'audit'|'comparison'|null>(null)
  const [layers,setLayers]=useState<Layers>({trails:true,assignments:true,uncertainty:true,labels:true})
  const [showLayers,setShowLayers]=useState(false),[help,setHelp]=useState(false),[demo,setDemo]=useState(false)
  const [cameraReset,setCameraReset]=useState(0),[healthy,setHealthy]=useState(true)
  const lastDemoEvent=useRef(-1)
  const select=useCallback((s:Selection)=>setSelection(s),[])
  const audit=run.audit.slice(0,frame.audit_count)
  const event=[...scenario.events].reverse().find(e=>e.time<=frame.time)??scenario.events[0]
  const eventAge=playback.time-event.time
  const demoTrack=demo&&eventAge<7&&event.track_id?frame.tracks.find(t=>t.id===event.track_id):null
  const demoFocus:Vec3|null=demo?(demoTrack?.position??[0,0,0]):null
  useEffect(()=>{
    if(demo&&lastDemoEvent.current!==event.time){lastDemoEvent.current=event.time;if(event.track_id)setSelection({kind:'track',id:event.track_id});if(event.time>=110)setDrawer('comparison')}
  },[demo,event])
  useEffect(()=>{if(playback.time>=run.duration)setDemo(false)},[playback.time,run.duration])
  useEffect(()=>{
    let alive=true
    const check=()=>fetch('/health',{signal:AbortSignal.timeout(4000)}).then(r=>{if(alive)setHealthy(r.ok)}).catch(()=>{if(alive)setHealthy(false)})
    void check();const id=setInterval(check,15000)
    return()=>{alive=false;clearInterval(id)}
  },[])
  useEffect(()=>{
    const handler=(e:KeyboardEvent)=>{if((e.target as HTMLElement).matches('input,select,textarea,button'))return;if(e.code==='Space'){e.preventDefault();playback.toggle()}if(e.key==='Escape'){setDrawer(null);setHelp(false);setShowLayers(false)}if(e.key==='/'){e.preventDefault();document.querySelector<HTMLInputElement>('[aria-label="Search tracks"]')?.focus()}}
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler)
  },[playback.toggle])
  function startDemo(){lastDemoEvent.current=-1;setDemo(true);setDrawer(null);playback.setTime(0);playback.setSpeed(1);playback.setPlaying(true);setCameraReset(n=>n+1)}
  function seek(t:number){setDemo(false);playback.seek(t)}
  function restart(){setDemo(false);playback.restart();setCameraReset(n=>n+1);setDrawer(null)}
  return <main className="app-shell"><header className="topbar"><div className="brand"><div className="brand-mark"><Shield size={23} strokeWidth={1.5}/><span/></div><div><h1>Swarm<span>Shield</span><sup>SIM</sup></h1><p>INTELLIGENCE UNDER UNCERTAINTY</p></div></div><div className="scenario-switch"><span className="tiny-dot mint"/><div><span>ACTIVE SCENARIO</span><strong>{scenario.name}<ChevronDown size={12}/></strong></div><span className="seed-badge">SEED {run.seed}</span></div><div className="header-actions"><span className={`connection ${healthy?'':'offline'}`}>{healthy?<Radio size={13}/>:<WifiOff size={13}/>}<span>{healthy?'Engine connected':'Cached replay · engine offline'}</span></span><button className="icon-button help-button" onClick={()=>setHelp(true)} aria-label="About this simulation"><CircleHelp size={18}/></button><button className={`demo-button ${demo?'running':''}`} onClick={()=>demo?setDemo(false):startDemo()}><Sparkles size={14}/>{demo?'Exit demo':'Demo mode'}{!demo&&<Play size={11} fill="currentColor"/>}</button></div></header>
    <section className="metrics-strip" aria-label="Simulation metrics"><div className="metric-block"><span>TRACKS OBSERVED <Activity size={12}/></span><div><strong>{m.total_tracks.toString().padStart(2,'0')}</strong><small>{m.active_tracks} active</small></div></div><div className="metric-block"><span>RESOURCE CAPACITY <Box size={12}/></span><div><strong>{m.resources_committed.toString().padStart(2,'0')}<em>/ {frame.resources.length}</em></strong><small className="mint-text">{m.resources_available} available</small></div><div className="capacity-slots">{frame.resources.map(r=><button key={r.id} title={`${r.id} · ${r.assigned_track??'Available'}`} aria-label={`Inspect resource ${r.id}`} onClick={()=>select({kind:'resource',id:r.id})} className={r.assigned_track?'filled':''}/>)}</div></div><div className="metric-block"><span>HIGH CONSEQUENCE</span><div><strong className="warm-text">{m.high_consequence_tracks.toString().padStart(2,'0')}</strong><small>{m.low_consequence_tracks} low consequence</small></div></div><div className="metric-block confidence-metric"><span>ESTIMATE CONFIDENCE</span><div><strong>{pct(m.mean_confidence)}</strong><svg viewBox="0 0 90 24" aria-hidden="true"><path d={run.frames.slice(Math.max(0,frame.time-30),frame.time+1).map((f,i,a)=>`${i?'L':'M'}${i/Math.max(1,a.length-1)*90},${23-f.metrics.mean_confidence*22}`).join(' ')} fill="none" stroke="#6ae3c3" strokeWidth="1.5"/></svg></div><small>Mean uncertainty {pct(m.mean_uncertainty)}</small></div><button className="metric-block metric-compare" onClick={()=>setDrawer(drawer==='comparison'?null:'comparison')}><span>POLICY PERFORMANCE <ArrowUpRight size={14}/></span><div><strong className="mint-text">{m.swarm.critical_tracks_covered}<em>/ {m.high_consequence_tracks}</em></strong><small>critical tracks covered</small></div><small>Baseline {m.baseline.critical_tracks_covered} covered <span>Compare policies →</span></small></button></section>
    <div className="workspace"><TrackList frame={frame} scenario={scenario} selection={selection} onSelect={select}/><section className="city-panel" aria-label="3D coastal city"><div className="city-heading"><div><div className="eyebrow"><span className="tiny-dot mint"/>MERIDIAN BAY / DIGITAL TWIN</div><h2>A wider view. A clearer decision.</h2></div><span className={`phase-pill ${playback.playing?'is-playing':''}`}><span className="tiny-dot"/>{frame.time<scenario.config.initial_observation_period?'OBSERVATION WINDOW':playback.playing?'SIMULATION RUNNING':'SIMULATION PAUSED'}</span></div><div className="map-canvas"><CityScene time={playback.time} run={run} scenario={scenario} selection={selection} onSelect={select} layers={layers} cameraReset={cameraReset} demoFocus={demoFocus}/></div><div className="map-toolbar"><button className={`icon-button ${showLayers?'active':''}`} title="Map layers" aria-label="Map layers" onClick={()=>setShowLayers(x=>!x)}><Layers3 size={16}/></button><button className="icon-button" title="Reset camera" aria-label="Reset camera" onClick={()=>setCameraReset(n=>n+1)}><Maximize size={16}/></button><div className="toolbar-line"/><button className={`icon-button ${drawer==='comparison'?'active':''}`} title="Compare allocation policies" aria-label="Compare allocation policies" onClick={()=>setDrawer(drawer==='comparison'?null:'comparison')}><ChartNoAxesCombined size={16}/></button><button className={`icon-button ${drawer==='audit'?'active':''}`} title="Decision audit" aria-label="Open decision audit" onClick={()=>setDrawer(drawer==='audit'?null:'audit')}><ListFilter size={16}/></button></div>{showLayers&&<div className="layers-popover"><span className="eyebrow">VISIBLE LAYERS</span>{(Object.keys(layers) as (keyof Layers)[]).map(k=><button key={k} onClick={()=>setLayers(l=>({...l,[k]:!l[k]}))} aria-pressed={layers[k]}><span className={`checkbox ${layers[k]?'checked':''}`}>{layers[k]&&<Check size={11}/>}</span>{k}</button>)}<p>Uncertainty rays appear for the selected track.</p></div>}<div className="compass"><span>N</span><svg width="26" height="32" viewBox="0 0 26 32"><path d="m13 3 7 22-7-5-7 5z" fill="#b8c9d0"/><path d="m13 3 0 17-7 5z" fill="#516a76"/></svg><span>SCENE GRID</span></div>
      {demo&&<div className="demo-callout" key={event.time}><span><Sparkles size={13}/>GUIDED DEMO <b>{clock(event.time)}</b></span><h3>{event.title}</h3><p>{event.description}</p></div>}
      {!demo&&frame.time<12&&<div className="observation-callout"><Eye size={17}/><div><strong>Observe first. Commit with evidence.</strong><p>{frame.tracks.length} tracks · {frame.resources.length} resources · first allocation at T+{scenario.config.initial_observation_period}</p></div></div>}
      <div className="map-bottom"><div className="map-legend"><span><i className="warm"/>High consequence</span><span><i className="amber"/>Medium</span><span><i className="teal"/>Low</span><span><i className="blue square"/>Resource</span></div><div className="map-hint">Drag to orbit<span>·</span>Scroll to zoom<span>·</span>Right-drag to pan</div></div><div className="view-status"><span><span className="tiny-dot mint"/>OBSERVATION → INFERENCE → ALLOCATION</span><span>FICTIONAL SCENE · NO REAL-WORLD COORDINATES</span></div>
      {drawer==='audit'&&<AuditDrawer entries={audit} scenario={scenario} time={frame.time} onClose={()=>setDrawer(null)} onTrack={id=>select({kind:'track',id})}/>}{drawer==='comparison'&&<ComparisonPanel frame={frame} run={run} onClose={()=>setDrawer(null)}/>}
    </section><Inspector selection={selection} frame={frame} scenario={scenario} audit={audit} onSelect={select}/></div>
    <div className="decision-strip"><div><span className="tiny-dot mint"/><b>{m.assignment_changes}</b> assignment changes<span className="divider"/><b>{m.released_resources}</b> released<span className="divider"/><b>{m.critical_assets_covered}</b> critical asset classes covered</div><button className="text-button" onClick={()=>setDrawer(drawer==='audit'?null:'audit')}><ListFilter size={13}/>Decision audit<span className="count">{audit.length}</span><ArrowUpRight size={13}/></button></div>
    <Timeline time={playback.time} duration={run.duration} playing={playback.playing} speed={playback.speed} onToggle={playback.toggle} onRestart={restart} onSeek={seek} onSpeed={playback.setSpeed} events={scenario.events} audit={run.audit}/>
    {help&&<div className="modal-backdrop" onClick={()=>setHelp(false)}><section className="help-modal" role="dialog" aria-modal="true" aria-label="About SwarmShield" onClick={e=>e.stopPropagation()}><button className="icon-button modal-close" aria-label="Close help" onClick={()=>setHelp(false)}><X size={18}/></button><Shield size={32} className="mint-text"/><span className="eyebrow">SWARMSHIELD / SIMULATION LAB</span><h2>Decisions you can inspect.</h2><p>SwarmShield is a fictional simulation and decision-support visualization created for a hackathon. It does not implement real-world weapon guidance or operational defence logic.</p><p>Track motion generates noisy observations. An observation-only estimator distributes intent across eight destinations. Consequence, confidence, urgency, uncertainty, and scarcity determine priority. Hysteresis prevents switching on transient evidence.</p><div className="help-shortcuts"><span><kbd>Space</kbd> Play / pause</span><span><kbd>/</kbd> Find track</span><span><kbd>Esc</kbd> Close panels</span></div><p className="muted">Start Demo mode for a guided 120-second story. Click any track, destination, resource, or staging site to inspect it. Scrubbing restores recorded decisions exactly. All distances and speeds are arbitrary scene units.</p><button className="demo-button" onClick={()=>{setHelp(false);startDemo()}}><Sparkles size={14}/>Start guided demo</button></section></div>}
  </main>
}

export default function App(){
  const [data,setData]=useState<{scenario:Scenario;run:Run}|null>(null),[error,setError]=useState<string|null>(null),[attempt,setAttempt]=useState(0)
  useEffect(()=>{const controller=new AbortController();setError(null);loadSimulation(controller.signal).then(setData).catch(e=>{if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Could not load simulation')});return()=>controller.abort()},[attempt])
  if(error)return <div className="boot-screen"><Shield size={38}/><h1>Engine unavailable</h1><p>{error}</p><code>npm run dev</code><button className="demo-button" onClick={()=>setAttempt(a=>a+1)}><RotateCcw size={15}/>Retry connection</button></div>
  if(!data)return <div className="boot-screen"><div className="boot-orbit"><Shield size={36}/></div><h1>SwarmShield</h1><p>Building the observation and decision timeline…</p><span className="eyebrow">DETERMINISTIC SIMULATION / MERIDIAN BAY</span><div className="loading-line"/></div>
  return <Dashboard run={data.run} scenario={data.scenario}/>
}
