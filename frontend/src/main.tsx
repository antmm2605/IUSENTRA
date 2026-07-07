import './index.css'
import './styles/iusentra-design-system.css'

type ReactBootstrapState = {
  entryLoaded?: boolean
  entryStartedAt?: string
  renderScheduled?: boolean
  renderCompleted?: boolean
  shellRendered?: boolean
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

const moduleUrl = new URL(import.meta.url)
const shouldRunBootstrap = import.meta.env.DEV
  || moduleUrl.searchParams.has('v')
  || moduleUrl.searchParams.has('iu_boot_retry')

const appRoot = document.getElementById('root') ?? document.getElementById('iusentra-react-root')
const supportOperatorRoot = document.getElementById('support-operator-react-root')
const shouldMountSupportOperator = Boolean(supportOperatorRoot?.dataset.supportOperatorRoom === '1' && !appRoot)
const root = shouldMountSupportOperator ? supportOperatorRoot : appRoot ?? supportOperatorRoot

function escapeHtml(value: string): string {
  return value.replace(/[<>&"]/g, (char) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' })[char] || char)
}

function startupErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return String(error || 'Modulo operativo non caricato')
}

function renderLoadingShell(target: HTMLElement) {
  bootstrapState.shellRendered = true
  target.innerHTML = [
    '<main class="iu-content iu-react-loading" aria-live="polite">',
    '<div>',
    '<h1>Caricamento interfaccia operativa</h1>',
    "<p>Sto aprendo i dati dello studio. L'operazione non modifica fascicoli, documenti o scadenze.</p>",
    '</div>',
    '</main>',
  ].join('')
}

function renderStartupError(target: HTMLElement, error: unknown) {
  const message = startupErrorMessage(error)
  target.innerHTML = [
    '<main class="iu-content iu-react-error" role="alert">',
    '<div>',
    '<h1>Interfaccia non avviata</h1>',
    '<p>Il modulo operativo non è stato caricato. Ricarica la pagina; se il problema resta, IUSENTRA registra il dettaglio tecnico senza modificare i dati dello studio.</p>',
    `<small>${escapeHtml(message)}</small>`,
    '<a href="/fascicoli">Apri fascicoli</a>',
    '<button type="button" onclick="window.location.reload()">Ricarica</button>',
    '</div>',
    '</main>',
  ].join('')
}

async function bootReact() {
  if (!root) throw new Error('Elemento #root non trovato.')
  renderLoadingShell(root)
  bootstrapState.renderScheduled = true
  const { mountReactApp } = await import('./reactEntry')
  await mountReactApp({ root, shouldMountSupportOperator })
  bootstrapState.renderCompleted = true
}

if (shouldRunBootstrap) {
  bootReact().catch((error) => {
    const message = startupErrorMessage(error)
    bootstrapState.errors?.push(message)
    document.documentElement.dataset.iusentraEntryRuntime = 'error'
    document.documentElement.dataset.iusentraEntryRuntimeError = message
    if (root) renderStartupError(root, error)
  })
}
