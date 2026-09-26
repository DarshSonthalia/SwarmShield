import { runSchema, scenarioSchema } from './types'

export async function request(path:string,method='GET',signal?:AbortSignal):Promise<unknown>{
  const response=await fetch(path,{method,signal,headers:{Accept:'application/json'}})
  if(!response.ok) throw new Error(`Simulation service returned ${response.status}. Check that the backend is running on port 8000.`)
  return response.json()
}
export async function loadSimulation(signal?:AbortSignal){
  const [scenario,run]=await Promise.all([request('/api/scenario','GET',signal),request('/api/run','POST',signal)])
  return {scenario:scenarioSchema.parse(scenario),run:runSchema.parse(run)}
}
