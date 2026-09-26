import { useCallback, useEffect, useState } from 'react'
import { advanceTime } from '../state'
export function usePlayback(duration:number){
  const [time,setTime]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1)
  useEffect(()=>{
    if(!playing)return
    let raf=0,last:number|undefined
    const tick=(now:number)=>{
      // Capture the delta now: React may run the updater after `last` has moved on.
      if(last!==undefined){const delta=Math.min((now-last)/1000,.25);setTime(t=>advanceTime(t,delta,speed,duration))}
      last=now;raf=requestAnimationFrame(tick)
    }
    raf=requestAnimationFrame(tick)
    return ()=>cancelAnimationFrame(raf)
  },[playing,speed,duration])
  useEffect(()=>{if(time>=duration)setPlaying(false)},[time,duration])
  const seek=useCallback((next:number)=>{setTime(Math.min(duration,Math.max(0,next)));setPlaying(false)},[duration])
  const toggle=useCallback(()=>{if(time>=duration)setTime(0);setPlaying(p=>!p)},[time,duration])
  const restart=useCallback(()=>{setTime(0);setPlaying(false)},[])
  return {time,playing,speed,setSpeed,setPlaying,setTime,seek,toggle,restart}
}
