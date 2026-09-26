import { z } from 'zod'

const vec3 = z.tuple([z.number().finite(),z.number().finite(),z.number().finite()])
const unit = z.number().min(0).max(1.000000001)
const recordSchema = z.object({time:z.number(),track_id:z.string(),resource_id:z.string(),action:z.string(),reason:z.string()})
const factorsSchema = z.object({expected_consequence:unit,confidence:unit,uncertainty:unit,urgency:unit,escalation:unit,scarcity:unit,reassignment_penalty:unit,persistence:z.number(),consequence_term:z.number(),uncertainty_term:z.number(),escalation_term:z.number(),scarcity_term:z.number()})
export const trackSchema = z.object({
  id:z.string(),position:vec3,animation_velocity:vec3,animation_acceleration:vec3,velocity:vec3,altitude:z.number(),heading:z.number(),noise_level:z.number(),maneuver_uncertainty:unit,
  observations:z.array(z.object({time:z.number(),position:vec3,velocity:vec3,heading:z.number()})),
  probabilities:z.record(unit).refine(p=>Object.keys(p).length===8 && Math.abs(Object.values(p).reduce((a,b)=>a+b,0)-1)<1e-6,'Invalid destination distribution'),
  confidence:unit,entropy:unit,stability:unit,heading_variance:unit,expected_consequence:unit,priority:unit,urgency:unit,escalation:unit,last_major_turn:z.number(),low_consequence_cycles:z.number(),
  state:z.enum(['OBSERVE','HOLD','COMMIT','REASSESS','RELEASE','REALLOCATE']),assigned_resource:z.string().nullable(),assignment_history:z.array(recordSchema),event_history:z.array(z.string()),reason:z.string(),factors:factorsSchema,
})
const resourceSchema = z.object({id:z.string(),site_id:z.string(),position:vec3,velocity:vec3,acceleration:vec3,state:z.enum(['STAGED','ASSIGNED','MOVING','RETURNING']),assigned_track:z.string().nullable(),assignment_start:z.number().nullable(),last_change:z.number(),visual_destination:vec3,assignment_history:z.array(recordSchema),reason:z.string()})
const comparisonSchema = z.object({critical_tracks_covered:z.number(),critical_tracks:z.number(),exposure:z.number(),cumulative_exposure:z.number(),low_consequence_commitments:z.number(),reassignments:z.number(),utilization:unit,stability:unit,critical_assets_covered:z.number()})
const metricsSchema = z.object({total_tracks:z.number(),active_tracks:z.number(),resources_available:z.number(),resources_committed:z.number(),high_consequence_tracks:z.number(),low_consequence_tracks:z.number(),mean_confidence:unit,mean_uncertainty:unit,assignment_changes:z.number(),released_resources:z.number(),critical_assets_covered:z.number(),swarm:comparisonSchema,baseline:comparisonSchema})
export const auditSchema = z.object({id:z.number(),time:z.number(),track_id:z.string(),resource_id:z.string().nullable(),action:z.string(),leading_destination:z.string(),previous_leading_destination:z.string().nullable(),probability:unit,factors:factorsSchema,priority:unit,reason:z.string(),assignments:z.record(z.string())})
export const frameSchema = z.object({time:z.number(),tracks:z.array(trackSchema).min(1),resources:z.array(resourceSchema).min(1),assignments:z.record(z.string()),baseline_assignments:z.record(z.string()),metrics:metricsSchema,audit_count:z.number(),event_ids:z.array(z.number())}).superRefine((f,ctx)=>{
  const entries=Object.entries(f.assignments)
  if(new Set(entries.map(([,t])=>t)).size!==entries.length || entries.some(([r,t])=>!f.resources.some(x=>x.id===r&&x.assigned_track===t)||!f.tracks.some(x=>x.id===t&&x.assigned_resource===r))) ctx.addIssue({code:'custom',message:'Inconsistent assignment snapshot'})
})
export const runSchema=z.object({seed:z.number(),duration:z.number(),frames:z.array(frameSchema),audit:z.array(auditSchema)}).refine(r=>r.frames.length===r.duration+1&&r.frames.every((f,i)=>f.time===i&&f.audit_count<=r.audit.length),'Incomplete timeline')
export const destinationSchema=z.object({id:z.string(),name:z.string(),short_name:z.string(),position:vec3,radius:z.number(),weight:unit,category:z.string()})
export const scenarioSchema=z.object({name:z.string(),description:z.string(),units:z.string(),baseline:z.string(),config:z.object({seed:z.number(),track_count:z.number(),resource_count:z.number(),duration:z.number(),initial_observation_period:z.number(),destinations:z.array(destinationSchema),sites:z.array(z.object({id:z.string(),name:z.string(),position:vec3})),hysteresis:z.object({release_persistence_cycles:z.number(),water_probability:unit,release_confidence:unit,release_consequence:unit,turn_quiet_period:z.number(),improvement_threshold:z.number(),challenger_persistence:z.number(),minimum_assignment_duration:z.number(),reassignment_cooldown:z.number()})}),events:z.array(z.object({time:z.number(),title:z.string(),description:z.string(),track_id:z.string().nullable()}))})
export type Vec3=z.infer<typeof vec3>
export type Track=z.infer<typeof trackSchema>
export type Resource=z.infer<typeof resourceSchema>
export type Frame=z.infer<typeof frameSchema>
export type AuditEntry=z.infer<typeof auditSchema>
export type Run=z.infer<typeof runSchema>
export type Scenario=z.infer<typeof scenarioSchema>
export type Destination=z.infer<typeof destinationSchema>
export type Comparison=z.infer<typeof comparisonSchema>
export type Selection={kind:'track'|'resource'|'destination'|'site';id:string}
export type Layers={trails:boolean;assignments:boolean;uncertainty:boolean;labels:boolean}
