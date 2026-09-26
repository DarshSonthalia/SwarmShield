import { existsSync } from 'node:fs'
import { root,python,npm,run,windows } from './common.mjs'
import { checkPythonVersion } from './python_version.mjs'
const bootstrap=existsSync(python)?python:(windows?'python':'python3')
try{checkPythonVersion(bootstrap)}catch(error){console.error(`\n${error.message}\n`);process.exit(1)}
if(!existsSync(python))run(bootstrap,['-m','venv','backend/.venv'])
run(python,['-m','pip','install','-r','backend/requirements.txt'])
run(npm,['ci'],root+'/frontend')
console.log('\nSwarmShield is ready. Run npm run dev, then open http://localhost:5173')
