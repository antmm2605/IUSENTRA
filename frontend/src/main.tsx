import './index.css'
import './styles/iusentra-design-system.css'
import { mountReactApp } from './reactEntry'

type ReactBootstrapState = {
  entryLoaded?: boolean
  entryStartedAt?: string
  renderScheduled?: boolean
  renderCompleted?: boolean
  shellRendered?: boolean
  delegatedEntry?: string
  errors?: string[]
}

declare global {
  interface Window {
    __IUSENTRA_REACT_BOOTSTRAP_STATE__?: ReactBootstrapState
    __IUSENTRA_INLINE_REACT_ENTRY__?: boolean
    __IUSENTRA_REACT_ROOT_OWNER__?: string
  }
}

const bootstrapState = window.__IUSENTRA_REACT_BOOTSTRAP_STATE__ ?? {}
bootstrapState.entryLoaded = true
bootstrapState.entryStartedAt = new Date().toISOString()
bootstrapState.errors = Array.isArray(bootstrapState.errors) ? bootstrapState.errors : []
window.__IUSENTRA_REACT_BOOTSTRAP_STATE__ = bootstrapState

const REACT_ASSETS_PREFIX = '/static/react/assets/'
const moduleUrl = new URL(import.meta.url)
const viteDev = Boolean((import.meta as ImportMeta & { env?: { DEV?: boolean } }).env?.DEV)
const inlineEntryArmed = window.__IUSENTRA_INLINE_REACT_ENTRY__ === true
const isRetryInstance = moduleUrl.searchParams.has('iu_boot_retry')
const shouldRunBootstrap = viteDev
  || moduleUrl.searchParams.has('v')
  || isRetryInstance
  || inlineEntryArmed
// L'entry inline e il file `/static/react/assets/index-*.js` sono due istanze
// distinte dello stesso modulo: i chunk di pagina importano il file reale, che
// quindi viene valutato una seconda volta. Senza un proprietario unico si
// montavano due root React sullo stesso #root e ogni richiesta API partiva due
// volte. La copia inline cede l'avvio al file canonico, che è la stessa istanza
// usata dalle pagine (contesti e stato condivisi).
const isInlineInstance = inlineEntryArmed && !viteDev && !isRetryInstance && !moduleUrl.pathname.startsWith(REACT_ASSETS_PREFIX)

function canonicalEntryPath(): string {
  const script = document.querySelector<HTMLScriptElement>('script[type="module"][data-iusentra-react-entry]')
  const raw = script?.getAttribute('data-iusentra-react-entry') || ''
  if (!raw) return ''
  try {
    const url = new URL(raw, window.location.origin)
    return url.origin === window.location.origin && url.pathname.startsWith(REACT_ASSETS_PREFIX) ? url.pathname : ''
  } catch {
    return ''
  }
}

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
  if (window.__IUSENTRA_REACT_ROOT_OWNER__) return
  window.__IUSENTRA_REACT_ROOT_OWNER__ = moduleUrl.pathname
  renderLoadingShell(root)
  bootstrapState.renderScheduled = true
  await mountReactApp({ root, shouldMountSupportOperator })
  bootstrapState.renderCompleted = true
}

function handleBootError(error: unknown) {
  const message = startupErrorMessage(error)
  bootstrapState.errors?.push(message)
  document.documentElement.dataset.iusentraEntryRuntime = 'error'
  document.documentElement.dataset.iusentraEntryRuntimeError = message
  if (root) renderStartupError(root, error)
}

function startBootstrap() {
  const entryPath = isInlineInstance ? canonicalEntryPath() : ''
  if (!entryPath) {
    bootReact().catch(handleBootError)
    return
  }
  if (root && !window.__IUSENTRA_REACT_ROOT_OWNER__) renderLoadingShell(root)
  bootstrapState.delegatedEntry = entryPath
  import(/* @vite-ignore */ entryPath)
    .then(() => {
      // Il modulo canonico si avvia da solo; se per qualunque motivo non ha
      // preso la root, l'istanza inline resta il presidio di avvio.
      if (!window.__IUSENTRA_REACT_ROOT_OWNER__) return bootReact()
      return undefined
    })
    .catch(() => bootReact())
    .catch(handleBootError)
}

if (shouldRunBootstrap) {
  startBootstrap()
}
