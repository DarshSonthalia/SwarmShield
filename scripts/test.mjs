import { root,python,npm,run } from './common.mjs'
run(python,['-m','pytest','-q'],root+'/backend')
run(npm,['test'],root+'/frontend')
