import { Component, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'
export class Boundary extends Component<{children:ReactNode;fallback?:ReactNode},{failed:boolean}>{
  state={failed:false}
  static getDerivedStateFromError(){return {failed:true}}
  render(){return this.state.failed?this.props.fallback??<div className="failure"><AlertTriangle size={30}/><h2>The dashboard could not render this state.</h2><p>Reload to request a fresh, validated simulation snapshot.</p><button onClick={()=>location.reload()}><RotateCcw size={15}/>Reload dashboard</button></div>:this.props.children}
}
