import { existsSync } from 'node:fs'
import { root,python,npm,run,windows } from './common.mjs'
if(!existsSync(python))run(windows?'python':'python3',['-m','venv','backend/.venv'])
run(python,['-m','pip','install','-r','backend/requirements.txt'])
run(npm,['ci'],root+'/frontend')
console.log('\nSwarmShield is ready. Run npm run dev, then open http://localhost:5173')
