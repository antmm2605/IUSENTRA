import { getCsrfToken } from './api/csrf'

/*
 * Dati e chiamate della pagina pubblica di accesso (AccessoApp).
 * Il server decide tutto (blocco tentativi, secondo fattore, destinazione):
 * qui si inviano i campi e si legge l'esito, senza conservare password.
 */

const API_ACCESSO = '/api/v1/pubblico/accesso'

export type VistaAccesso = 'login' | '2fa' | 'password'
export type TonoMessaggio = 'success' | 'info' | 'warning' | 'danger'

export type MessaggioAccesso = { tono: TonoMessaggio; testo: string }

export type StatoAccesso = {
  ok: boolean
  autenticato: boolean
  multiStudio: boolean
  studi: Array<{ slug: string; nome: string }>
  verificaInAttesa: boolean
  utenteVerifica: string
  passwordObbligatoria: boolean
  utente: string
  destinazione: string
  messaggi: MessaggioAccesso[]
}

export type EsitoAccesso = {
  ok: boolean
  esito: string
  redirect: string
  message: string
  code: string
  retryAfter: number
}

export type ConfigurazionePagina = {
  vista: VistaAccesso
  next: string
  sessioneScaduta: boolean
  logo: string
  vistaClassica: string
}

type Raw = Record<string, unknown>

function obj(value: unknown): Raw {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Raw) : {}
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : value === null || value === undefined ? '' : String(value)
}

/** Solo percorsi interni: mai un indirizzo esterno ricevuto dal server o dalla pagina. */
export function percorsoInterno(value: unknown, fallback = '/'): string {
  const raw = text(value).trim()
  return raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/\\') ? raw : fallback
}

function tono(value: unknown): TonoMessaggio {
  const raw = text(value)
  if (raw === 'error') return 'danger'
  return (['success', 'info', 'warning', 'danger'].includes(raw) ? raw : 'info') as TonoMessaggio
}

export function configurazionePagina(root: HTMLElement | null): ConfigurazionePagina {
  const dataset = root?.dataset ?? {}
  const vista = dataset.vista === '2fa' || dataset.vista === 'password' ? dataset.vista : 'login'
  return {
    vista,
    next: dataset.next ? percorsoInterno(dataset.next, '') : '',
    sessioneScaduta: dataset.sessioneScaduta === '1',
    logo: percorsoInterno(dataset.logo, ''),
    vistaClassica: percorsoInterno(dataset.vistaClassica, ''),
  }
}

/** Il server rinnova il token CSRF quando la sessione cambia: la pagina lo segue. */
function aggiornaCsrf(token: unknown) {
  const valore = text(token)
  if (!valore || typeof document === 'undefined') return
  const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
  if (meta) meta.content = valore
}

function statoDa(raw: Raw): StatoAccesso {
  const verifica = obj(raw.verifica_2fa)
  return {
    ok: raw.ok === true,
    autenticato: raw.autenticato === true,
    multiStudio: raw.multi_studio === true,
    studi: (Array.isArray(raw.studi) ? raw.studi : [])
      .map((studio) => ({ slug: text(obj(studio).slug), nome: text(obj(studio).nome) }))
      .filter((studio) => studio.slug),
    verificaInAttesa: verifica.in_attesa === true,
    utenteVerifica: text(verifica.utente),
    passwordObbligatoria: raw.password_obbligatoria === true,
    utente: text(raw.utente),
    destinazione: percorsoInterno(raw.destinazione),
    messaggi: (Array.isArray(raw.messaggi) ? raw.messaggi : [])
      .map((m) => ({ tono: tono(obj(m).categoria), testo: text(obj(m).testo) }))
      .filter((m) => m.testo),
  }
}

const STATO_NON_DISPONIBILE: StatoAccesso = {
  ok: false,
  autenticato: false,
  multiStudio: false,
  studi: [],
  verificaInAttesa: false,
  utenteVerifica: '',
  passwordObbligatoria: false,
  utente: '',
  destinazione: '/',
  messaggi: [],
}

export async function leggiStatoAccesso(signal?: AbortSignal): Promise<StatoAccesso> {
  try {
    const response = await fetch(`${API_ACCESSO}/stato`, {
      credentials: 'same-origin',
      cache: 'no-store',
      signal,
      headers: { Accept: 'application/json' },
    })
    const raw = obj(await response.json().catch(() => ({})))
    aggiornaCsrf(raw.csrf_token)
    return response.ok ? statoDa(raw) : STATO_NON_DISPONIBILE
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    return STATO_NON_DISPONIBILE
  }
}

function esitoDa(raw: Raw, status: number, retryHeader: string | null): EsitoAccesso {
  const retry = Number(raw.retry_after ?? retryHeader ?? 0)
  return {
    ok: raw.ok === true,
    esito: text(raw.esito),
    redirect: text(raw.redirect) ? percorsoInterno(raw.redirect) : '',
    message: text(raw.message) || (status >= 500 ? 'Servizio momentaneamente non disponibile. Riprova tra poco.' : ''),
    code: text(raw.code),
    retryAfter: Number.isFinite(retry) && retry > 0 ? Math.ceil(retry) : 0,
  }
}

const ESITO_RETE: EsitoAccesso = {
  ok: false,
  esito: 'errore',
  redirect: '',
  message: 'Connessione non riuscita. Controlla la rete e riprova.',
  code: 'rete',
  retryAfter: 0,
}

async function postAccesso(percorso: string, campi: Record<string, string>, tentativo = 0): Promise<EsitoAccesso> {
  let response: Response
  try {
    const token = getCsrfToken()
    response = await fetch(`${API_ACCESSO}${percorso}`, {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        ...(token ? { 'X-CSRF-Token': token } : {}),
      },
      body: JSON.stringify(campi),
    })
  } catch {
    return ESITO_RETE
  }
  const raw = obj(await response.json().catch(() => ({})))
  aggiornaCsrf(raw.csrf_token)
  const esito = esitoDa(raw, response.status, response.headers.get('Retry-After'))
  // Token della pagina superato (sessione rinnovata in un'altra scheda): il
  // server ne ha appena consegnato uno nuovo, si ripete una sola volta.
  if (esito.code === 'csrf_non_valido' && tentativo === 0) {
    return postAccesso(percorso, campi, 1)
  }
  if (!esito.message && !esito.ok) {
    return { ...esito, message: 'Accesso non riuscito. Riprova.' }
  }
  return esito
}

export function inviaCredenziali(form: HTMLFormElement, next: string): Promise<EsitoAccesso> {
  const dati = new FormData(form)
  return postAccesso('/login', {
    username: text(dati.get('username')),
    password: text(dati.get('password')),
    studio_slug: text(dati.get('studio_slug')),
    next,
  })
}

export function inviaCodiceVerifica(form: HTMLFormElement): Promise<EsitoAccesso> {
  const dati = new FormData(form)
  return postAccesso('/2fa', { codice: text(dati.get('codice')).replace(/\s+/g, '') })
}

export type EsitoCambioPassword = { ok: boolean; message: string; sessioneScaduta: boolean }

/** Cambio obbligatorio: stessa azione `/profilo` (azione=password) della vista classica. */
export async function cambiaPasswordObbligatoria(form: HTMLFormElement): Promise<EsitoCambioPassword> {
  const origine = new FormData(form)
  const dati = new FormData()
  dati.set('azione', 'password')
  dati.set('password_old', text(origine.get('password_old')))
  dati.set('password_new', text(origine.get('password_new')))
  let response: Response
  try {
    const token = getCsrfToken()
    response = await fetch('/profilo', {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        ...(token ? { 'X-CSRF-Token': token } : {}),
      },
      body: dati,
    })
  } catch {
    return { ok: false, message: ESITO_RETE.message, sessioneScaduta: false }
  }
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) {
    // Sessione chiusa (rimando alla pagina di accesso) o conferma di sicurezza scaduta.
    const sessioneScaduta = response.redirected || response.status === 401
    return {
      ok: false,
      sessioneScaduta,
      message: sessioneScaduta
        ? 'La sessione è scaduta: accedi di nuovo per impostare la nuova password.'
        : 'La pagina è scaduta: ricaricala e riprova.',
    }
  }
  const raw = obj(await response.json().catch(() => ({})))
  return {
    ok: raw.ok === true && response.ok,
    message: text(raw.message) || (response.ok ? 'Password aggiornata.' : 'Password non aggiornata. Riprova.'),
    sessioneScaduta: false,
  }
}

export async function esciDallaSessione(): Promise<void> {
  const token = getCsrfToken()
  try {
    await fetch('/logout', {
      method: 'POST',
      credentials: 'same-origin',
      redirect: 'manual',
      headers: token ? { 'X-CSRF-Token': token } : {},
    })
  } finally {
    window.location.assign('/login')
  }
}
