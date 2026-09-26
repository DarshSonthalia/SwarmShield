import { Check, Minus, X } from 'lucide-react'

const working=['Noisy observation simulation','Destination-probability inference','Uncertainty estimation','Consequence-aware prioritisation','Scarce-resource allocation','Release hysteresis','Reallocation','Audit trail','Baseline comparison']
const simulated=['Track motion','Observation noise','Resource motion']
const absent=['Real sensor integration','Real hardware control','Operational flight guidance','Physical interception or engagement outcome','Real-world deployment validation','Real peer-to-peer drone networking','Real collision avoidance']

export function ModelBoundary({onClose}:{onClose:()=>void}){
  return <div className="modal-backdrop" onClick={onClose}><section className="boundary-modal" role="dialog" aria-modal="true" aria-label="Model boundary" onClick={e=>e.stopPropagation()}><button className="icon-button modal-close" aria-label="Close model boundary" onClick={onClose}><X size={18}/></button><span className="eyebrow">CLAIM DISCIPLINE</span><h2>Model boundary</h2><p>This is a simulation and decision-support prototype. It does not control real systems.</p><div className="boundary-columns"><BoundaryList title="WORKING NOW" items={working} icon="check"/><BoundaryList title="SIMULATED / ABSTRACT" items={simulated}/><BoundaryList title="NOT IMPLEMENTED" items={absent}/></div></section></div>
}

function BoundaryList({title,items,icon}:{title:string;items:string[];icon?:'check'}){return <div><h3>{title}</h3><ul>{items.map(item=><li key={item}>{icon?<Check size={12}/>:<Minus size={12}/>}<span>{item}</span></li>)}</ul></div>}
