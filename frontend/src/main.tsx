import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'
import SupportOperatorRoom from './components/SupportOperatorRoom'
import './index.css'
import './styles/iusentra-design-system.css'

const appRoot = document.getElementById('root') ?? document.getElementById('iusentra-react-root')
const supportOperatorRoot = document.getElementById('support-operator-react-root')
const shouldMountSupportOperator = Boolean(supportOperatorRoot?.dataset.supportOperatorRoom === '1' && !appRoot)
const root = shouldMountSupportOperator ? supportOperatorRoot : appRoot ?? supportOperatorRoot
if (!root) throw new Error('Elemento #root non trovato.')

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    {shouldMountSupportOperator ? <SupportOperatorRoom /> : <App />}
  </React.StrictMode>,
)
