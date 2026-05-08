import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'
import './index.css'

const root = document.getElementById('root') ?? document.getElementById('iusentra-react-root')
if (!root) throw new Error('Elemento #root non trovato.')

ReactDOM.createRoot(root).render(<React.StrictMode><App /></React.StrictMode>)
