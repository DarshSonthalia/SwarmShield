import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource-variable/inter/wght.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import './styles.css'
import App from './App'
import { Boundary } from './components/Boundary'

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><Boundary><App/></Boundary></React.StrictMode>)
