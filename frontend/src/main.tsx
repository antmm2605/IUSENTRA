import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'
import SupportOperatorRoom from './components/SupportOperatorRoom'
import './index.css'
import './styles/iusentra-design-system.css'

const supportOperatorRoot = document.getElementById('support-operator-react-root')
const root = supportOperatorRoot ?? document.getElementById('root') ?? document.getElementById('iusentra-react-root')
if (!root) throw new Error('Elemento #root non trovato.')

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    {supportOperatorRoot ? <SupportOperatorRoom /> : <App />}
  </React.StrictMode>,
)
