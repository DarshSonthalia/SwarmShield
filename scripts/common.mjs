import { fileURLToPath } from 'node:url'
import { resolve,dirname } from 'node:path'
import { spawnSync } from 'node:child_process'
export const root=resolve(dirname(fileURLToPath(import.meta.url)),'..')
export const windows=process.platform==='win32'
export const python=resolve(root,'backend','.venv',windows?'Scripts/python.exe':'bin/python')
export const npm=windows?'npm.cmd':'npm'
export function run(command,args,cwd=root){const r=spawnSync(command,args,{cwd,stdio:'inherit',shell:windows&&command.endsWith('.cmd')});if(r.error){console.error(r.error.message);process.exit(1)}if(r.status!==0)process.exit(r.status??1)}
