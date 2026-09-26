import { memo, useLayoutEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Html, Line, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import type { Frame, Layers, Run, Scenario, Selection, Vec3 } from '../types'
import { frameAt, smoothPosition, trackColor } from '../state'
import { Boundary } from './Boundary'

const coast:Vec3[]=[[-45,0,-31],[-26,0,-37],[-10,0,-38],[6,0,-35],[31,0,-33],[40,0,-22],[42,0,-7],[38,0,10],[35,0,21],[28,0,28],[12,0,30],[0,0,27],[-18,0,33],[-33,0,29],[-43,0,20],[-47,0,4],[-45,0,-15],[-45,0,-31]]
function noise(n:number){return (Math.sin(n*127.1+311.7)*43758.5453)%1*.5+.5}
const City=memo(function City({scenario}:{scenario:Scenario}){
  const buildings=useRef<THREE.InstancedMesh>(null)
  const shape=useMemo(()=>{const s=new THREE.Shape();coast.forEach(([x,,z],i)=>i?s.lineTo(x,-z):s.moveTo(x,-z));return s},[])
  const blocks=useMemo(()=>{
    const result:{p:Vec3;s:Vec3;color:THREE.Color}[]=[]
    let k=0
    for(const d of scenario.config.destinations.filter(d=>!['A01','A08'].includes(d.id))){
      const n=d.id==='A02'?7:5
      for(let i=0;i<n;i++)for(let j=0;j<n;j++){
        k++;if(noise(k)<.13)continue
        const x=d.position[0]+(i-(n-1)/2)*2.4,z=d.position[2]+(j-(n-1)/2)*2.4
        const h=d.id==='A02'?2+noise(k+17)*10:d.id==='A04'?1.8+noise(k+7)*3:d.id==='A06'?.8+noise(k+3)*2:1+noise(k+5)*3
        result.push({p:[x,h/2+.12,z],s:[1.2+noise(k)*.7,h,1.4+noise(k+2)*.5],color:new THREE.Color(d.id==='A02'?'#477281':d.id==='A06'?'#304d55':d.id==='A04'?'#4a646c':'#345665')})
      }
    }
    // Low-density peripheral neighborhoods make the city read as a continuous place.
    for(let x=-35;x<30;x+=4)for(let z=-28;z<25;z+=4){k++;if(scenario.config.destinations.some(d=>Math.hypot(d.position[0]-x,d.position[2]-z)<d.radius+1)||noise(k)<.35)continue;const h=.6+noise(k+1)*1.1;result.push({p:[x,h/2,z],s:[1.5,h,1.6],color:new THREE.Color('#243e46')})}
    return result
  },[scenario])
  useLayoutEffect(()=>{if(!buildings.current)return;const matrix=new THREE.Matrix4();blocks.forEach((b,i)=>{matrix.compose(new THREE.Vector3(...b.p),new THREE.Quaternion(),new THREE.Vector3(...b.s));buildings.current!.setMatrixAt(i,matrix);buildings.current!.setColorAt(i,b.color)});buildings.current.instanceMatrix.needsUpdate=true;if(buildings.current.instanceColor)buildings.current.instanceColor.needsUpdate=true},[blocks])
  return <group><mesh rotation={[-Math.PI/2,0,0]} position={[0,-.7,0]}><planeGeometry args={[240,240]}/><meshStandardMaterial color="#091d2b" roughness={.6} metalness={.25}/></mesh><gridHelper args={[220,44,'#244352','#18313f']} position={[0,-.65,0]}/><mesh rotation={[-Math.PI/2,0,0]} position={[0,-.35,0]}><extrudeGeometry args={[shape,{depth:.65,bevelEnabled:false}]}/><meshStandardMaterial color="#16343a" roughness={.95}/></mesh><Line points={coast.map(([x,,z])=>[x,.08,z])} color="#487f81" lineWidth={1.2} transparent opacity={.6}/><instancedMesh ref={buildings} args={[undefined,undefined,blocks.length]}><boxGeometry/><meshStandardMaterial roughness={.75} metalness={.22}/></instancedMesh>
    {[-32,-18,-4,10,24].map(x=><Line key={`x${x}`} points={[[x,.12,-30],[x,.12,23]]} color="#507175" lineWidth={.6} transparent opacity={.35}/>)}{[-26,-12,2,16].map(z=><Line key={`z${z}`} points={[[-40,.12,z],[33,.12,z]]} color="#507175" lineWidth={.6} transparent opacity={.35}/>)}
    {/* Airport: parallel runways, apron, terminal. No operational placement data. */}
    {[-31,-26].map(x=><group key={x}><mesh position={[x,.16,-24]}><boxGeometry args={[1.9,.2,16]}/><meshStandardMaterial color="#48646b"/></mesh>{[-30,-27,-24,-21,-18].map(z=><mesh key={z} position={[x,.28,z]}><boxGeometry args={[.15,.05,1.4]}/><meshBasicMaterial color="#a7babb"/></mesh>)}</group>)}<mesh position={[-22,1,-24]}><boxGeometry args={[3,2,7]}/><meshStandardMaterial color="#49616b"/></mesh>
    {/* Port fingers and containers. */}{[23,28,33].map((x,i)=><group key={x}><mesh position={[x,.05,25]}><boxGeometry args={[3,.5,11]}/><meshStandardMaterial color="#2c4a57"/></mesh>{[22,25,28].map((z,j)=><mesh key={z} position={[x,.65,z]}><boxGeometry args={[1.7,.8,1.8]}/><meshStandardMaterial color={(i+j)%2?'#416777':'#65858b'}/></mesh>)}</group>)}
    {/* Power cylinders and civic mast provide recognizable district silhouettes. */}{[-29,-25,-21].map(x=><mesh key={x} position={[x,2.5,18]}><cylinderGeometry args={[1,1.7,5,10]}/><meshStandardMaterial color="#547983"/></mesh>)}<mesh position={[4,4,-22]}><cylinderGeometry args={[.15,.6,8,8]}/><meshStandardMaterial color="#7e9b9f" emissive="#214346"/></mesh>
    <Html position={[-55,0,34]} center><span className="map-water-label">MERIDIAN STRAIT</span></Html><Html position={[51,0,-47]} center><span className="map-coordinate">NORTH SECTOR<br/>FICTIONAL GRID 04</span></Html>
  </group>
})

function CameraRig({focus,reset}:{focus:Vec3|null;reset:number}){
  const controls=useRef<OrbitControlsImpl>(null),lastReset=useRef(reset)
  const desired=useRef(new THREE.Vector3(0,0,0))
  useFrame(({camera},delta)=>{
    if(lastReset.current!==reset){camera.position.set(88,100,112);lastReset.current=reset;desired.current.set(0,0,0);controls.current?.target.set(0,0,0);controls.current?.update()}
    if(focus&&controls.current){desired.current.set(focus[0]*.55,0,focus[2]*.55);controls.current.target.lerp(desired.current,1-Math.exp(-delta*1.8));controls.current.update()}
  })
  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.08} minDistance={65} maxDistance={310} maxPolarAngle={Math.PI/2.2} minPolarAngle={.2}/>
}

function ZoneMarkers({scenario,selection,onSelect,labels}:{scenario:Scenario;selection:Selection;onSelect:(s:Selection)=>void;labels:boolean}){
  return <group>{scenario.config.destinations.map(d=>{
    const selected=selection.kind==='destination'&&selection.id===d.id
    return <group key={d.id} position={d.position} onClick={e=>{e.stopPropagation();onSelect({kind:'destination',id:d.id})}}><mesh rotation={[-Math.PI/2,0,0]} position={[0,.18,0]}><ringGeometry args={[d.radius-.12,d.radius,64]}/><meshBasicMaterial color={selected?'#8bffdb':'#71a7a8'} transparent opacity={selected?.65:.17} side={THREE.DoubleSide}/></mesh><mesh rotation={[-Math.PI/2,0,0]} position={[0,.16,0]}><circleGeometry args={[d.radius,40]}/><meshBasicMaterial color="#69baa9" transparent opacity={selected?.1:.015} depthWrite={false}/></mesh>{labels&&<Html position={[0,d.id==='A02'?14:6,0]} center zIndexRange={[30,0]}><button className={`zone-label ${selected?'selected':''}`} onClick={()=>onSelect({kind:'destination',id:d.id})}><small>{d.id}</small>{d.short_name}</button></Html>}</group>
  })}{scenario.config.sites.map(s=><group key={s.id} position={s.position} onClick={e=>{e.stopPropagation();onSelect({kind:'site',id:s.id})}}><mesh rotation={[0,Math.PI/4,0]}><boxGeometry args={[1.3,.4,1.3]}/><meshStandardMaterial color="#819fda" emissive="#446594" emissiveIntensity={.5}/></mesh><mesh rotation={[-Math.PI/2,0,0]}><ringGeometry args={[1.5,1.65,6]}/><meshBasicMaterial color="#7e9fcd" transparent opacity={.45}/></mesh>{labels&&<Html position={[0,1.4,0]} center zIndexRange={[20,0]}><button className="site-label" onClick={()=>onSelect({kind:'site',id:s.id})}>{s.id}</button></Html>}</group>)}</group>
}

function DynamicObjects({frame,next,alpha,time,run,scenario,selection,onSelect,layers}:{frame:Frame;next:Frame;alpha:number;time:number;run:Run;scenario:Scenario;selection:Selection;onSelect:(s:Selection)=>void;layers:Layers}){
  const trailFrames=useMemo(()=>run.frames.slice(Math.max(0,frame.time-18),frame.time+1),[run,frame.time])
  const selectedTrack=selection.kind==='track'?frame.tracks.find(t=>t.id===selection.id):undefined
  const positions=frame.tracks.map((t,i)=>smoothPosition(t.position,t.animation_velocity,t.animation_acceleration,next.tracks[i].position,next.tracks[i].animation_velocity,next.tracks[i].animation_acceleration,alpha))
  const resourcePositions=frame.resources.map((r,i)=>smoothPosition(r.position,r.velocity,r.acceleration,next.resources[i].position,next.resources[i].velocity,next.resources[i].acceleration,alpha))
  return <group>{frame.tracks.map((t,i)=>{
    const p=positions[i],selected=selection.kind==='track'&&selection.id===t.id,color=trackColor(t)
    const trail=trailFrames.map(f=>f.tracks[i].position).concat([p])
    return <group key={t.id}>{layers.trails&&trail.length>2&&<Line points={trail} color={color} lineWidth={selected?1.8:1} transparent opacity={selected?.75:.3}/>}<group position={p} onClick={e=>{e.stopPropagation();onSelect({kind:'track',id:t.id})}}><mesh><octahedronGeometry args={[selected?.9:.64,0]}/><meshStandardMaterial color={color} emissive={color} emissiveIntensity={.65}/></mesh><mesh><sphereGeometry args={[2,8,8]}/><meshBasicMaterial transparent opacity={0} depthWrite={false}/></mesh>{selected&&<mesh rotation={[-Math.PI/2,0,0]}><ringGeometry args={[1.8,1.95,48]}/><meshBasicMaterial color={color} transparent opacity={.8}/></mesh>}{layers.labels&&(selected||t.expected_consequence>=.72||frame.time<12)&&<Html position={[0,2.5,0]} center zIndexRange={[45,0]}><button className={`track-map-label ${selected?'selected':''}`} style={{color}} onClick={()=>onSelect({kind:'track',id:t.id})}>{t.id}{selected&&<span> {t.assigned_resource??'OBS'}</span>}</button></Html>}</group><Line points={[p,[p[0],.4,p[2]]]} color={color} transparent opacity={selected?.25:.07} lineWidth={.7}/>{selected&&layers.uncertainty&&<mesh position={p} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[2.5,2.5+t.entropy*6,48]}/><meshBasicMaterial color="#a9a1d8" transparent opacity={.06+Math.sin(time*2)*.012} side={THREE.DoubleSide} depthWrite={false}/></mesh>}</group>
  })}{frame.resources.map((r,i)=>{
    const p=resourcePositions[i],selected=selection.kind==='resource'&&selection.id===r.id
    const targetIndex=frame.tracks.findIndex(t=>t.id===r.assigned_track)
    const points:Vec3[]=[]
    if(layers.trails&&r.state!=='STAGED'){
      for(let j=0;j<trailFrames.length-1;j++){const a=trailFrames[j].resources[i],b=trailFrames[j+1].resources[i];for(let k=0;k<4;k++)points.push(smoothPosition(a.position,a.velocity,a.acceleration,b.position,b.velocity,b.acceleration,k/4))}points.push(p)
    }
    return <group key={r.id}>{layers.assignments&&targetIndex>=0&&<Line points={[p,positions[targetIndex]]} color="#88a8f1" dashed dashSize={1.2} gapSize={.9} lineWidth={selected?1.3:.7} transparent opacity={selected||selection.id===r.assigned_track?.65:.22}/>} {points.length>2&&<Line points={points} color="#8daef5" lineWidth={selected?2:1.1} transparent opacity={.45}/>}<group position={p} onClick={e=>{e.stopPropagation();onSelect({kind:'resource',id:r.id})}}><mesh rotation={[0,Math.PI/4,0]}><boxGeometry args={[.65,.65,.65]}/><meshStandardMaterial color="#b0c8ff" emissive="#769eea" emissiveIntensity={.8}/></mesh><mesh><sphereGeometry args={[1.5,8,8]}/><meshBasicMaterial transparent opacity={0} depthWrite={false}/></mesh>{selected&&<Html position={[0,2,0]} center><button className="resource-map-label">{r.id} → {r.assigned_track??'AVAILABLE'}</button></Html>}</group></group>
  })}{selectedTrack&&layers.uncertainty&&scenario.config.destinations.map(d=>{
    const index=frame.tracks.findIndex(t=>t.id===selectedTrack.id),p=selectedTrack.probabilities[d.id]
    return <Line key={d.id} points={[positions[index],[d.position[0],1,d.position[2]]]} color={d.id==='A08'?'#70c7c0':'#c8b49a'} lineWidth={.5+p*2} transparent opacity={.035+p*.4} dashed dashSize={.55} gapSize={1}/>
  })}</group>
}

export function TacticalFallback({frame,scenario,onSelect}:{frame:Frame;scenario:Scenario;onSelect:(s:Selection)=>void}){
  return <div className="tactical-fallback"><span>2D fallback · WebGL unavailable</span><svg viewBox="-90 -85 190 170" aria-label="Tactical city fallback map"><polygon points={coast.map(([x,,z])=>`${x},${z}`).join(' ')} fill="#183b40" stroke="#4b7a7d" strokeWidth=".5"/>{scenario.config.destinations.map(d=><g key={d.id} onClick={()=>onSelect({kind:'destination',id:d.id})}><circle cx={d.position[0]} cy={d.position[2]} r={d.radius} fill="none" stroke="#719698" strokeWidth=".4"/><text x={d.position[0]} y={d.position[2]} fill="#b4cdd0" fontSize="3">{d.short_name}</text></g>)}{frame.resources.map(r=><g key={r.id}>{r.assigned_track&&<line x1={r.position[0]} y1={r.position[2]} x2={frame.tracks.find(t=>t.id===r.assigned_track)!.position[0]} y2={frame.tracks.find(t=>t.id===r.assigned_track)!.position[2]} stroke="#92b3ec" strokeWidth=".4" strokeDasharray="1 1"/>}<rect x={r.position[0]-1} y={r.position[2]-1} width="2" height="2" fill="#a3c0fc" onClick={()=>onSelect({kind:'resource',id:r.id})}/></g>)}{frame.tracks.map(t=><g key={t.id} onClick={()=>onSelect({kind:'track',id:t.id})}><circle cx={t.position[0]} cy={t.position[2]} r="1.6" fill={trackColor(t)}/><text x={t.position[0]+2} y={t.position[2]} fill={trackColor(t)} fontSize="3">{t.id}</text></g>)}</svg></div>
}
export function CityScene({time,run,scenario,selection,onSelect,layers,cameraReset,demoFocus}:{time:number;run:Run;scenario:Scenario;selection:Selection;onSelect:(s:Selection)=>void;layers:Layers;cameraReset:number;demoFocus:Vec3|null}){
  const frame=frameAt(run.frames,time),next=frameAt(run.frames,time+1),alpha=time>=run.duration?0:time-Math.floor(time)
  const fallback=<TacticalFallback frame={frame} scenario={scenario} onSelect={onSelect}/>
  return <Boundary fallback={fallback}><Canvas fallback={fallback} camera={{position:[88,100,112],fov:48,near:.1,far:700}} dpr={[1,1.5]} gl={{antialias:true,alpha:false,powerPreference:'high-performance'}} onCreated={({gl})=>{gl.setClearColor('#09151f');gl.toneMapping=THREE.ACESFilmicToneMapping;gl.toneMappingExposure=1.25}}><fog attach="fog" args={['#09151f',240,490]}/><ambientLight intensity={1.4}/><directionalLight position={[-40,80,30]} color="#b1dee3" intensity={2.5}/><directionalLight position={[50,30,-40]} color="#6286b5" intensity={1.8}/><City scenario={scenario}/><ZoneMarkers scenario={scenario} selection={selection} onSelect={onSelect} labels={layers.labels}/><DynamicObjects frame={frame} next={next} alpha={alpha} time={time} run={run} scenario={scenario} selection={selection} onSelect={onSelect} layers={layers}/><CameraRig focus={demoFocus} reset={cameraReset}/></Canvas></Boundary>
}
