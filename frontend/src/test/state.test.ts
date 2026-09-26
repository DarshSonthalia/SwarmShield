import { describe,it,expect } from 'vitest'
import fixture from './fixture.json'
import { frameSchema,scenarioSchema } from '../types'
import { advanceTime,frameAt,filterTracks,smoothPosition } from '../state'

const frames=fixture.frames.map(f=>frameSchema.parse(f))
describe('deterministic timeline and selection',()=>{
  it('never advances past the duration',()=>expect(advanceTime(119.8,1,4,120)).toBe(120))
  it('playback speed changes elapsed simulation time',()=>expect(advanceTime(20,.5,4,120)).toBe(22))
  it('backwards wall clock movement cannot reverse simulation',()=>expect(advanceTime(20,-1,1,120)).toBe(20))
  it('chooses the preceding decision frame at fractional times',()=>{const f=Array.from({length:13},(_,time)=>({...frames[time<12?0:1],time}));expect(frameAt(f,11.999).assignments).toEqual({});expect(Object.keys(frameAt(f,12).assignments).length).toBeGreaterThan(0)})
  it('clamps seeks at both ends',()=>{expect(frameAt(frames,-3)).toBe(frames[0]);expect(frameAt(frames,999)).toBe(frames.at(-1))})
  it('assigned filter agrees with the recorded mapping',()=>{const f=frames[3];expect(filterTracks(f.tracks,'assigned',52).map(t=>t.id).sort()).toEqual(Object.values(f.assignments).sort())})
  it('released water track stays visible in monitoring filters',()=>{const f=frames[3];expect(filterTracks(f.tracks,'water',52).some(t=>t.id==='T11')).toBe(true);expect(filterTracks(f.tracks,'unassigned',52).some(t=>t.id==='T11')).toBe(true)})
  it('recently changed filter excludes stale maneuvers',()=>{const f=frames[4];expect(filterTracks(f.tracks,'changed',f.time).every(t=>f.time-t.last_major_turn<=10)).toBe(true)})
  it('quintic reconstruction preserves both endpoints',()=>{const a=frames[1].resources[0],b=frames[2].resources[0];expect(smoothPosition(a.position,a.velocity,a.acceleration,b.position,b.velocity,b.acceleration,0)).toEqual(a.position);const p=smoothPosition(a.position,a.velocity,a.acceleration,b.position,b.velocity,b.acceleration,1);p.forEach((n,i)=>expect(n).toBeCloseTo(b.position[i],8))})
  it('rejects malformed probabilities before render',()=>{const f=structuredClone(fixture.frames[0]);f.tracks[0].probabilities.A01=-1;expect(()=>frameSchema.parse(f)).toThrow()})
  it('rejects contradictory assignment data',()=>{const f=structuredClone(fixture.frames[1]);f.assignments.I01='T99';expect(()=>frameSchema.parse(f)).toThrow()})
  it('loads all fictional destinations and staging sites',()=>{const s=scenarioSchema.parse(fixture.scenario);expect(s.config.destinations).toHaveLength(8);expect(s.config.sites).toHaveLength(8)})
})
