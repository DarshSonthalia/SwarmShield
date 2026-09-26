import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { root,python,npm,windows } from './common.mjs'
if(!existsSync(python)||!existsSync(root+'/frontend/node_modules')){console.error('Run npm run setup first.');process.exit(1)}
const children=[spawn(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],{cwd:root+'/backend',stdio:'inherit'}),spawn(npm,['run','dev'],{cwd:root+'/frontend',stdio:'inherit',shell:windows})]
let closing=false
function close(code=0){if(closing)return;closing=true;for(const child of children){if(windows&&child.pid)spawn('taskkill',['/pid',String(child.pid),'/T','/F']);else child.kill('SIGTERM')}setTimeout(()=>process.exit(code),500)}
for(const child of children){child.on('error',e=>{console.error(e.message);close(1)});child.on('exit',code=>{if(!closing)close(code??1)})}
process.on('SIGINT',()=>close());process.on('SIGTERM',()=>close())
console.log('SwarmShield → http://localhost:5173 · Ctrl+C stops both services.')
