import { describe,it,expect,vi } from 'vitest'
import { render,screen,fireEvent,within } from '@testing-library/react'
import fixture from './fixture.json'
import { frameSchema,scenarioSchema,auditSchema } from '../types'
import { ProbabilityBars,Inspector } from '../components/Inspector'
import { TrackList } from '../components/TrackList'
import { Timeline } from '../components/Timeline'
import { AuditDrawer } from '../components/Audit'
import { DemoPresentation, demoStage } from '../components/DemoPresentation'
import { ModelBoundary } from '../components/ModelBoundary'
import { resourcePresentationPath } from '../components/CityScene'

const frames=fixture.frames.map(f=>frameSchema.parse(f)),scenario=scenarioSchema.parse(fixture.scenario),audit=fixture.audit.map(a=>auditSchema.parse(a))
describe('simulation components',()=>{
  it('derives guided demo stages from real release and reallocation audit entries',()=>{
    expect(demoStage(0,audit)).toBe('opening')
    expect(demoStage(46,audit)).toBe('release')
    expect(demoStage(84,audit)).toBe('reallocate')
    expect(demoStage(110,audit)).toBe('comparison')
  })
  it('renders release evidence from the current frame and configured gates',()=>{
    const f=frames.find(f=>f.time===52)!;render(<DemoPresentation frame={f} scenario={scenario} audit={audit}/>);
    expect(screen.getByRole('heading',{name:'T11'})).toBeInTheDocument()
    const guidance=screen.getByLabelText('Demo guidance')
    expect(guidance).toHaveTextContent('4 / 4')
    expect(guidance).toHaveTextContent('RELEASE I04')
    expect(guidance).toHaveTextContent(`${(f.tracks[10].probabilities.A08*100).toFixed(1)}%`)
  })
  it('keeps demo guidance in a compact strip with real release data',()=>{
    const f=frames.find(f=>f.time===52)!;render(<DemoPresentation frame={f} scenario={scenario} audit={audit}/>);
    expect(screen.getByLabelText('Demo guidance')).toHaveClass('demo-guidance-strip')
    expect(screen.getByText('T11 — RELEASE')).toBeInTheDocument()
    expect(screen.getByText(/4 \/ 4/)).toBeInTheDocument()
  })
  it('builds deterministic shallow resource paths without periodic motion',()=>{
    const start:[number,number,number]=[0,1,0],end:[number,number,number]=[20,5,10]
    expect(resourcePresentationPath('I04',start,end,0)).toEqual(start)
    expect(resourcePresentationPath('I04',start,end,1)).toEqual(end)
    expect(resourcePresentationPath('I04',start,end,.5)).toEqual(resourcePresentationPath('I04',start,end,.5))
    expect(resourcePresentationPath('I04',start,end,.5)).not.toEqual(resourcePresentationPath('I05',start,end,.5))
    const midpoint=resourcePresentationPath('I04',start,end,.5)
    expect(Math.abs(midpoint[1]-(start[1]+end[1])/2)).toBeLessThanOrEqual(1)
  })
  it('states the model boundary without claiming networking or collision avoidance',()=>{
    render(<ModelBoundary onClose={()=>{}}/>);expect(screen.getByRole('heading',{name:'Model boundary'})).toBeInTheDocument()
    expect(screen.getByText('Real peer-to-peer drone networking')).toBeInTheDocument()
    expect(screen.getByText('Real collision avoidance')).toBeInTheDocument()
    expect(screen.getByText('Release hysteresis')).toBeInTheDocument()
  })
  it('renders every probability, including near-zero classes',()=>{
    const track=frames[3].tracks[10];render(<ProbabilityBars track={track} scenario={scenario}/>);
    for(const d of scenario.config.destinations)expect(screen.getByText(d.short_name)).toBeInTheDocument()
    expect(document.querySelectorAll('.probability-row')).toHaveLength(8)
    expect(screen.getByText('Σ 100.0%')).toBeInTheDocument()
  })
  it('probability bar widths match engine values',()=>{
    const track=frames[3].tracks[10];render(<ProbabilityBars track={track} scenario={scenario}/>);
    const row=screen.getByText('Open water').closest('.probability-row')!
    expect(row.querySelector('.probability-track i')).toHaveStyle({width:`${track.probabilities.A08*100}%`})
  })
  it('clicking a registry row selects the correct track',()=>{
    const onSelect=vi.fn();render(<TrackList frame={frames[1]} scenario={scenario} selection={{kind:'track',id:'T01'}} onSelect={onSelect}/>);
    fireEvent.click(screen.getByRole('button',{name:'Inspect T11'}));expect(onSelect).toHaveBeenCalledWith({kind:'track',id:'T11'})
  })
  it('registry assigned filter excludes released track',()=>{
    render(<TrackList frame={frames[3]} scenario={scenario} selection={{kind:'track',id:'T11'}} onSelect={()=>{}}/>);
    fireEvent.change(screen.getByLabelText('Filter tracks'),{target:{value:'assigned'}})
    expect(screen.queryByRole('button',{name:'Inspect T11'})).not.toBeInTheDocument()
    expect(screen.getAllByRole('button',{name:/Inspect T/})).toHaveLength(Object.keys(frames[3].assignments).length)
  })
  it('track search narrows results without changing data',()=>{
    render(<TrackList frame={frames[1]} scenario={scenario} selection={{kind:'track',id:'T01'}} onSelect={()=>{}}/>);
    fireEvent.change(screen.getByLabelText('Search tracks'),{target:{value:'T17'}})
    expect(screen.getAllByRole('button',{name:/Inspect T/})).toHaveLength(1)
  })
  it('inspector assignment agrees with the frame',()=>{
    const f=frames[1],t=f.tracks[10];render(<Inspector selection={{kind:'track',id:'T11'}} frame={f} scenario={scenario} audit={audit.slice(0,f.audit_count)} onSelect={()=>{}}/>);
    expect(screen.getByRole('button',{name:t.assigned_resource!})).toBeInTheDocument()
  })
  it('released inspector cannot show a stale assignment',()=>{
    const f=frames[3];render(<Inspector selection={{kind:'track',id:'T11'}} frame={f} scenario={scenario} audit={audit.slice(0,f.audit_count)} onSelect={()=>{}}/>);
    expect(screen.getByText('RELEASE')).toBeInTheDocument();expect(screen.getByRole('button',{name:'Monitoring only'})).toBeInTheDocument()
  })
  it('resource inspector navigates to its actual track',()=>{
    const f=frames[4],r=f.resources.find(r=>r.assigned_track==='T17')!,select=vi.fn();render(<Inspector selection={{kind:'resource',id:r.id}} frame={f} scenario={scenario} audit={audit.slice(0,f.audit_count)} onSelect={select}/>);
    fireEvent.click(screen.getAllByRole('button',{name:'T17'})[0]);expect(select).toHaveBeenCalledWith({kind:'track',id:'T17'})
  })
  it('audit renders actual release reasoning and excludes future decisions',()=>{
    const entries=audit.filter(a=>a.time<=52);render(<AuditDrawer entries={entries} scenario={scenario} time={52} onClose={()=>{}} onTrack={()=>{}}/>);
    expect(screen.getByText('RELEASE')).toBeInTheDocument();expect(screen.queryByText('REALLOCATE')).not.toBeInTheDocument()
    expect(screen.getByText(/Persistent low-consequence evidence:/)).toBeInTheDocument()
  })
  it('evidence panel exposes every priority factor',()=>{
    const f=frames[3];render(<Inspector selection={{kind:'track',id:'T11'}} frame={f} scenario={scenario} audit={[]} onSelect={()=>{}}/>);fireEvent.click(screen.getByRole('button',{name:'evidence'}));
    for(const label of ['Expected consequence','Confidence','Uncertainty / entropy','Urgency','Escalation','Scarcity pressure','Priority score'])expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByText('4/4 CYCLES')).toBeInTheDocument()
  })
  it('timeline play/pause button follows playback state',()=>{
    const toggle=vi.fn(),props={time:40,duration:120,playing:false,speed:1,onToggle:toggle,onRestart:()=>{},onSeek:()=>{},onSpeed:()=>{},events:scenario.events,audit};
    const {rerender}=render(<Timeline {...props}/>);fireEvent.click(screen.getByLabelText('Play simulation'));expect(toggle).toHaveBeenCalledOnce();rerender(<Timeline {...props} playing/>);expect(screen.getByLabelText('Pause simulation')).toBeInTheDocument()
  })
  it('timeline forwards exact scrub time and speed',()=>{
    const seek=vi.fn(),speed=vi.fn();render(<Timeline time={0} duration={120} playing={false} speed={1} onToggle={()=>{}} onRestart={()=>{}} onSeek={seek} onSpeed={speed} events={scenario.events} audit={audit}/>);
    fireEvent.change(screen.getByLabelText('Simulation timeline'),{target:{value:'51.9'}});expect(seek).toHaveBeenCalledWith(51.9)
    fireEvent.click(screen.getByRole('button',{name:'4×'}));expect(speed).toHaveBeenCalledWith(4)
  })
  it('destination panel computes weighted incoming count from all tracks',()=>{
    const f=frames[3];render(<Inspector selection={{kind:'destination',id:'A08'}} frame={f} scenario={scenario} audit={[]} onSelect={()=>{}}/>);
    const dl=screen.getByText('Probability-weighted count').closest('dl')!;expect(within(dl).getByText(f.tracks.reduce((s,t)=>s+t.probabilities.A08,0).toFixed(2))).toBeInTheDocument()
    expect(screen.getByText('LOW CONSEQUENCE ≠ SAFE')).toBeInTheDocument()
  })
})
