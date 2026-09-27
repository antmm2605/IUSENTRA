import { csrfHeader } from './api/csrf'

/**
 * Chiamate delle pagine pubbliche con link personale (portale storico e link di
 * pagamento). A differenza di `apiJson` conservano lo stato HTTP: 410 (link
 * scaduto) e 403 (sezione non consentita) cambiano la schermata.
 */

export type Grezzo = Record<string, unknown>

export type RispostaPubblica = {
  status: number
  dati: Grezzo
  messaggio: string
  codice: string
}

export function oggetto(value: unknown): Grezzo {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Grezzo) : {}
}

export function elenco(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

export function testo(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

export function vero(value: unknown): boolean {
  return value === true
}

export function numero(value: unknown, predefinito = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : predefinito
}

const ERRORE_RETE = 'Connessione non riuscita. Controlla la rete e riprova.'

async function leggiRisposta(response: Response): Promise<RispostaPubblica> {
  let dati: Grezzo = {}
  if ((response.headers.get('content-type') || '').includes('application/json')) {
    try {
      dati = oggetto(await response.json())
    } catch {
      dati = {}
    }
  }
  return {
    status: response.status,
    dati,
    messaggio: testo(dati.message || dati.errore),
    codice: testo(dati.code || dati.codice),
  }
}

export async function leggiPubblico(url: string, signal?: AbortSignal): Promise<RispostaPubblica> {
  try {
    const response = await fetch(url, { credentials: 'same-origin', signal, headers: { Accept: 'application/json' } })
    return await leggiRisposta(response)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    return { status: 0, dati: {}, messaggio: ERRORE_RETE, codice: 'rete' }
  }
}

/** Scrittura pubblica: JSON oppure FormData (file), sempre con la conferma CSRF della pagina. */
export async function scriviPubblico(url: string, corpo: Grezzo | FormData): Promise<RispostaPubblica> {
  const multipart = corpo instanceof FormData
  try {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(multipart ? {} : { 'Content-Type': 'application/json' }),
        ...csrfHeader(),
      },
      body: multipart ? corpo : JSON.stringify(corpo),
    })
    return await leggiRisposta(response)
  } catch {
    return { status: 0, dati: {}, messaggio: ERRORE_RETE, codice: 'rete' }
  }
}

export type MessaggioPagina = { categoria: 'success' | 'warning' | 'danger' | 'info'; testo: string }

function categoria(value: unknown): MessaggioPagina['categoria'] {
  const raw = testo(value)
  if (raw === 'warning' || raw === 'danger' || raw === 'info') return raw
  return 'success'
}

export function messaggiDa(value: unknown): MessaggioPagina[] {
  return elenco(value)
    .map((item) => oggetto(item))
    .map((item) => ({ categoria: categoria(item.categoria), testo: testo(item.testo) }))
    .filter((item) => item.testo)
}

/** Messaggi lasciati dalla vista classica nella shell (`data-messaggi`). */
export function messaggiDaAttributo(raw: string | undefined): MessaggioPagina[] {
  if (!raw) return []
  try {
    return messaggiDa(JSON.parse(raw))
  } catch {
    return []
  }
}

/** Solo indirizzi https dei gestori di pagamento: nessun redirect verso schemi diversi. */
export function urlEsternoSicuro(value: unknown): string {
  const raw = testo(value)
  try {
    const url = new URL(raw)
    return url.protocol === 'https:' ? url.toString() : ''
  } catch {
    return ''
  }
}

/** Solo percorsi interni (stessa origine). */
export function percorsoInterno(value: unknown): string {
  const raw = testo(value)
  return raw.startsWith('/') && !raw.startsWith('//') ? raw : ''
}
