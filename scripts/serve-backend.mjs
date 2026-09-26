import { root,python,run } from './common.mjs'
run(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],root+'/backend')
