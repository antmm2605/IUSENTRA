import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'
import SupportOperatorRoom from './components/SupportOperatorRoom'
import './index.css'
import './styles/iusentra-design-system.css'

type ReactBootstrapState = {
  entryLoaded?: boolean
  entryStartedAt?: string
  renderScheduled?: boolean
  errors?: string[]
}

declare global {
  interface Window {
    __IUSENTRA_REACT_BOOTSTRAP_STATE__?: ReactBootstrapState
  }
}

const bootstrapState = window.__IUSENTRA_REACT_BOOTSTRAP_STATE__ ?? {}
bootstrapState.entryLoaded = true
bootstrapState.entryStartedAt = new Date().toISOString()
bootstrapState.errors = Array.isArray(bootstrapState.errors) ? bootstrapState.errors : []
window.__IUSENTRA_REACT_BOOTSTRAP_STATE__ = bootstrapState

const appRoot = document.getElementById('root') ?? document.getElementById('iusentra-react-root')
const supportOperatorRoot = document.getElementById('support-operator-react-root')
const shouldMountSupportOperator = Boolean(supportOperatorRoot?.dataset.supportOperatorRoom === '1' && !appRoot)
const root = shouldMountSupportOperator ? supportOperatorRoot : appRoot ?? supportOperatorRoot
if (!root) throw new Error('Elemento #root non trovato.')

try {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      {shouldMountSupportOperator ? <SupportOperatorRoom /> : <App />}
    </React.StrictMode>,
  )
  bootstrapState.renderScheduled = true
} catch (error) {
  bootstrapState.errors?.push(error instanceof Error ? error.message : String(error))
  throw error
}
