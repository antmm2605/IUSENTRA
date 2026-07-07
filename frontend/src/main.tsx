import React from 'react'
import ReactDOM from 'react-dom/client'
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

function startupErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return String(error || 'Modulo operativo non caricato')
}

function showStartupError(error: unknown) {
  if (!root) return
  const message = startupErrorMessage(error)
  root.innerHTML = [
    '<main class="iu-content iu-react-error" role="alert">',
    '<div>',
    '<h1>Interfaccia non avviata</h1>',
    '<p>Il modulo operativo non è stato caricato. Ricarica la pagina; se il problema resta, IUSENTRA registra il dettaglio tecnico senza modificare i dati dello studio.</p>',
    `<small>${message.replace(/[<>&"]/g, (char) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' })[char] || char)}</small>`,
    '<a href="/fascicoli">Apri fascicoli</a>',
    '<button type="button" onclick="window.location.reload()">Ricarica</button>',
    '</div>',
    '</main>',
  ].join('')
}

async function mountReactApp() {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      {shouldMountSupportOperator
        ? React.createElement((await import('./components/SupportOperatorRoom')).default)
        : React.createElement((await import('./app/App')).default)}
    </React.StrictMode>,
  )
  bootstrapState.renderScheduled = true
}

mountReactApp().catch((error) => {
  const message = startupErrorMessage(error)
  bootstrapState.errors?.push(message)
  document.documentElement.dataset.iusentraEntryRuntime = 'error'
  document.documentElement.dataset.iusentraEntryRuntimeError = message
  showStartupError(error)
})
