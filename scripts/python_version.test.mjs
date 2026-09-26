import test from 'node:test'
import assert from 'node:assert/strict'
import { parsePythonVersion, validatePythonVersion } from './python_version.mjs'

test('parses CPython version output',()=>{
  assert.deepEqual(parsePythonVersion('Python 3.13.7\r\n'),{major:3,minor:13,patch:7})
})

test('accepts Python 3.10 through 3.13',()=>{
  for(const minor of [10,11,12,13])assert.equal(validatePythonVersion({major:3,minor,patch:0}),null)
})

test('rejects Python 3.14 before dependency installation',()=>{
  assert.match(validatePythonVersion({major:3,minor:14,patch:0}),/Unsupported Python version: 3\.14[\s\S]*Python 3\.10–3\.13[\s\S]*Recommended: Python 3\.13[\s\S]*py -0p/)
})

test('rejects versions older than Python 3.10',()=>{
  assert.match(validatePythonVersion({major:3,minor:9,patch:0}),/Unsupported Python version: 3\.9/)
})
