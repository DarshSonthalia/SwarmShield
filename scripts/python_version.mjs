import { spawnSync } from 'node:child_process'

export function parsePythonVersion(output){
  const match=String(output).match(/Python\s+(\d+)\.(\d+)(?:\.(\d+))?/i)
  if(!match)throw new Error(`Could not determine Python version from: ${String(output).trim()||'(no output)'}`)
  return {major:Number(match[1]),minor:Number(match[2]),patch:Number(match[3]??0)}
}

export function validatePythonVersion(version){
  if(version.major===3&&version.minor>=10&&version.minor<=13)return null
  return `Unsupported Python version: ${version.major}.${version.minor}\n\nSwarmShield currently supports Python 3.10–3.13.\nRecommended: Python 3.13.\n\nOn Windows, check installed versions with:\n    py -0p`
}

export function checkPythonVersion(command){
  const result=spawnSync(command,['--version'],{encoding:'utf8'})
  if(result.error)throw new Error(`Could not run ${command}: ${result.error.message}`)
  const version=parsePythonVersion(`${result.stdout??''}${result.stderr??''}`)
  const problem=validatePythonVersion(version)
  if(problem)throw new Error(problem)
  return version
}
