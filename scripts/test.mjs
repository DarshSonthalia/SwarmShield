import { root,python,npm,run } from './common.mjs'
run('node',['--test','scripts/python_version.test.mjs'])
run(python,['-m','pytest','-q'],root+'/backend')
run(npm,['test'],root+'/frontend')
