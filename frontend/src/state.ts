import type { Frame, Track, Vec3 } from './types'
export type Filter='all'|'priority'|'assigned'|'unassigned'|'uncertain'|'water'|'changed'|'critical'
export const filters: {id:Filter;label:string}[]=[{id:'all',label:'All tracks'},{id:'priority',label:'High priority'},{id:'assigned',label:'Assigned'},{id:'unassigned',label:'Unassigned'},{id:'uncertain',label:'High uncertainty'},{id:'water',label:'Open-water leading'},{id:'changed',label:'Recently changed'},{id:'critical',label:'Critical destination'}]
export function filterTracks(tracks:Track[],filter:Filter,time:number):Track[]{
  return tracks.filter(t=>filter==='all'||filter==='priority'&&t.priority>=.4||filter==='assigned'&&t.assigned_resource!==null||filter==='unassigned'&&t.assigned_resource===null||filter==='uncertain'&&t.entropy>=.6||filter==='water'&&leading(t)==='A08'||filter==='changed'&&time-t.last_major_turn<=10||filter==='critical'&&['A01','A02','A04','A05'].includes(leading(t)))
}
export const leading=(track:Track)=>Object.entries(track.probabilities).sort((a,b)=>b[1]-a[1])[0]?.[0]??'A08'
export const pct=(n:number)=>(n*100).toFixed(0)+'%'
export const clock=(n:number)=>`T+${Math.floor(n).toString().padStart(3,'0')}`
export const trackColor=(track:Track)=>track.entropy>.78?'#a6b2c6':track.expected_consequence>=.72?'#ff9f79':track.expected_consequence>=.3?'#dfc38c':'#69c8c3'
export const frameAt=(frames:Frame[],time:number)=>frames[Math.min(frames.length-1,Math.max(0,Math.floor(time)))]
export const advanceTime=(time:number,delta:number,speed:number,duration:number)=>Math.min(duration,Math.max(0,time+Math.max(0,delta)*speed))

// Quintic Hermite reconstruction between exact backend p/v/a endpoints.
export function smoothPosition(p0:Vec3,v0:Vec3,a0:Vec3,p1:Vec3,v1:Vec3,a1:Vec3,u:number):Vec3{
  return p0.map((p,i)=>{
    const c0=p,c1=v0[i],c2=a0[i]/2
    const d=p1[i]-c0-c1-c2,v=v1[i]-c1-2*c2,a=a1[i]-2*c2
    return c0+c1*u+c2*u*u+(10*d-4*v+a/2)*u**3+(-15*d+7*v-a)*u**4+(6*d-3*v+a/2)*u**5
  }) as Vec3
}
