import { Sparkles } from 'lucide-react'
import type { AuditEntry, Frame, Scenario } from '../types'
import { clock, leading, pct } from '../state'

export type DemoStage='opening'|'overview'|'release'|'reallocate'|'comparison'

function decision(audit:AuditEntry[],track:string,action:string){return audit.find(a=>a.track_id===track&&a.action===action)}

export function demoStage(time:number,audit:AuditEntry[]):DemoStage{
  const release=decision(audit,'T11','RELEASE')
  const reallocate=decision(audit,'T17','REALLOCATE')
  if(time<3)return 'opening'
  if(release&&time>=Math.max(0,release.time-12)&&time<release.time+8)return 'release'
  if(reallocate&&time>=Math.max(0,reallocate.time-18)&&time<reallocate.time+8)return 'reallocate'
  if(reallocate&&time>=reallocate.time+26)return 'comparison'
  return 'overview'
}

export function DemoPresentation({frame,scenario,audit}:{frame:Frame;scenario:Scenario;audit:AuditEntry[]}){
  const stage=demoStage(frame.time,audit)
  if(stage==='opening'||stage==='overview')return <section className="demo-guidance-strip" aria-label="Demo guidance"><Sparkles size={16}/><div><strong>{frame.time<scenario.config.initial_observation_period?'OBSERVE FIRST — COMMIT WITH EVIDENCE':'HOLD — WAIT FOR SUSTAINED EVIDENCE'}</strong><span>{frame.tracks.length} tracks • {frame.resources.length} resources • first allocation at {clock(scenario.config.initial_observation_period)}</span></div><b>Step 1 / 4</b></section>
  if(stage==='release'){
    const track=frame.tracks.find(t=>t.id==='T11')!,cfg=scenario.config.hysteresis
    const release=decision(audit,'T11','RELEASE')
    const destination=scenario.config.destinations.find(d=>d.id===leading(track))
    const quiet=frame.time-track.last_major_turn>=cfg.turn_quiet_period
    const released=Boolean(release&&frame.time>=release.time)
    return <section className="demo-guidance-strip" aria-label="Demo guidance"><Sparkles size={16}/><div><h2>T11</h2><strong>T11 — {released?'RELEASE':'HOLD'}</strong><span>{destination?.short_name??leading(track)} {(track.probabilities[leading(track)]*100).toFixed(1)}% • consequence {track.expected_consequence.toFixed(3)} • uncertainty {track.entropy.toFixed(3)} • priority {track.priority.toFixed(3)}</span></div><div className="demo-guidance-evidence"><span>{track.probabilities.A08>=cfg.water_probability?'✓':'·'} water ≥ {pct(cfg.water_probability)} · {track.confidence>=cfg.release_confidence?'✓':'·'} confidence ≥ {pct(cfg.release_confidence)} · {quiet?'✓':'·'} quiet {cfg.turn_quiet_period}s</span><strong>Persistence {track.low_consequence_cycles} / {cfg.release_persistence_cycles}{released?` → RELEASE ${release?.resource_id}`:' · HOLD'}</strong></div><b>Step 2 / 4</b></section>
  }
  if(stage==='reallocate'){
    const track=frame.tracks.find(t=>t.id==='T17')!,reallocate=decision(audit,'T17','REALLOCATE')
    const displaced=reallocate?audit.find(a=>a.time===reallocate.time&&a.resource_id===reallocate.resource_id&&a.action==='DISPLACE'):undefined
    const advantage=reallocate&&displaced?reallocate.priority-displaced.priority:null
    const cfg=scenario.config.hysteresis
    const persisted=reallocate&&frame.time>=reallocate.time?cfg.challenger_persistence:Math.min(cfg.challenger_persistence-1,Math.max(1,Math.floor((frame.time-(reallocate?.time??84)+6)/2)))
    return <section className="demo-guidance-strip" aria-label="Demo guidance"><Sparkles size={16}/><div><h2>T17</h2><strong>T17 — REALLOCATE</strong><span>consequence {track.expected_consequence.toFixed(3)} • confidence {track.confidence.toFixed(3)} • priority {track.priority.toFixed(3)} • required advantage +{cfg.improvement_threshold.toFixed(3)}</span></div><div className="demo-guidance-evidence"><span>{advantage===null?'Advantage accumulating':`Recorded advantage +${advantage.toFixed(3)}`}</span><strong>Persistence {persisted} / {cfg.challenger_persistence}{reallocate&&frame.time>=reallocate.time?` → ${reallocate.resource_id}: ${displaced?.track_id??'previous track'} → T17`:' · HOLD'}</strong></div><b>Step 3 / 4</b></section>
  }
  const swarm=frame.metrics.swarm,baseline=frame.metrics.baseline
  return <section className="demo-guidance-strip" aria-label="Demo guidance"><Sparkles size={16}/><div><strong>POLICY COMPARISON</strong><span>Same observations • same {frame.resources.length} resources • static allocation versus release and reallocation</span></div><div className="demo-guidance-evidence"><span>Critical coverage {swarm.critical_tracks_covered}/{swarm.critical_tracks} vs {baseline.critical_tracks_covered}/{baseline.critical_tracks}</span><strong>Cumulative exposure {swarm.cumulative_exposure.toFixed(1)} vs {baseline.cumulative_exposure.toFixed(1)}</strong></div><b>Step 4 / 4</b></section>
}
