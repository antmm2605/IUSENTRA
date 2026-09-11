import { useEffect, useState } from 'react'

/**
 * Cliente del fascicolo collegato a una PEC.
 *
 * Le comunicazioni di cancelleria e le ricevute del deposito telematico
 * (D.M. 44/2011 artt. 13 e 16) identificano il procedimento con ufficio e
 * numero di ruolo: il nominativo del cliente arriva solo dall'anagrafica del
 * fascicolo dello studio (GET /api/pec/messages/<id>/cliente-fascicolo).
 */

export type PecFascicoloClienteStato = 'collegato' | 'da_confermare' | 'non_collegato' | 'non_disponibile' | ''

export type PecFascicoloCliente = {
  stato: PecFascicoloClienteStato
  messaggio: string
  fascicolo: {
    id: string
    label: string
    rg: string
    ufficio: string
    aperto: boolean
    href: string
  }
  cliente: {
    id: string
    tipo: string
    nome: string
    cognome: string
    ragioneSociale: string
    nomeCompleto: string
  }
}

const emptyResult: PecFascicoloCliente = {
  stato: '',
  messaggio: '',
  fascicolo: { id: '', label: '', rg: '', ufficio: '', aperto: false, href: '' },
  cliente: { id: '', tipo: '', nome: '', cognome: '', ragioneSociale: '', nomeCompleto: '' },
}

const cache = new Map<string, Promise<PecFascicoloCliente>>()

function text(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function normalise(payload: unknown): PecFascicoloCliente {
  const root = record(payload)
  const data = Object.keys(record(root.data)).length ? record(root.data) : root
  const fascicolo = record(data.fascicolo)
  const cliente = record(data.cliente)
  const stato = text(data.stato)
  return {
    stato: (['collegato', 'da_confermare', 'non_collegato', 'non_disponibile'].includes(stato) ? stato : '') as PecFascicoloClienteStato,
    messaggio: text(data.messaggio ?? data.message),
    fascicolo: {
      id: text(fascicolo.id),
      label: text(fascicolo.label),
      rg: text(fascicolo.rg),
      ufficio: text(fascicolo.ufficio),
      aperto: fascicolo.aperto === true,
      href: text(fascicolo.href),
    },
    cliente: {
      id: text(cliente.id),
      tipo: text(cliente.tipo),
      nome: text(cliente.nome),
      cognome: text(cliente.cognome),
      ragioneSociale: text(cliente.ragione_sociale ?? cliente.ragioneSociale),
      nomeCompleto: text(cliente.nome_completo ?? cliente.nomeCompleto),
    },
  }
}

export function pecFascicoloClienteUrl(pecId: string): string {
  return pecId ? `/api/pec/messages/${encodeURIComponent(pecId)}/cliente-fascicolo` : ''
}

export function pecFascicoloClienteUrlFromSaveUrl(saveUrl: string): string {
  return /\/salva-fascicolo(?:\?.*)?$/.test(saveUrl) ? saveUrl.replace(/\/salva-fascicolo(?:\?.*)?$/, '/cliente-fascicolo') : ''
}

export function fetchPecFascicoloCliente(url: string): Promise<PecFascicoloCliente> {
  if (!url) return Promise.resolve(emptyResult)
  const cached = cache.get(url)
  if (cached) return cached
  const request = fetch(url, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
    .then((response) => (response.ok ? response.json() : {}))
    .then(normalise)
    .catch(() => {
      cache.delete(url)
      return emptyResult
    })
  cache.set(url, request)
  return request
}

export function invalidatePecFascicoloCliente(url: string): void {
  if (url) cache.delete(url)
}

export function usePecFascicoloCliente(url: string): PecFascicoloCliente | null {
  const [state, setState] = useState<{ url: string; value: PecFascicoloCliente } | null>(null)
  useEffect(() => {
    if (!url) return undefined
    let active = true
    fetchPecFascicoloCliente(url).then((value) => {
      if (active) setState({ url, value })
    })
    return () => { active = false }
  }, [url])
  return state && state.url === url ? state.value : null
}

/** Voci per il Profilo processuale: nome e cognome separati, ragione sociale per le società. */
export function pecFascicoloClienteFacts(result: PecFascicoloCliente | null): Array<[string, string]> {
  if (!result || !result.fascicolo.id) return []
  const suffix = result.stato === 'da_confermare' ? ' (da confermare)' : ''
  const facts: Array<[string, string]> = []
  const { cliente } = result
  if (cliente.nome || cliente.cognome) {
    if (cliente.nome) facts.push(['Nome cliente', cliente.nome])
    if (cliente.cognome) facts.push(['Cognome cliente', cliente.cognome])
  } else if (cliente.ragioneSociale || cliente.nomeCompleto) {
    facts.push(['Cliente', cliente.ragioneSociale || cliente.nomeCompleto])
  }
  const fascicoloLabel = result.fascicolo.label
  if (fascicoloLabel) facts.push(['Fascicolo', `${fascicoloLabel}${suffix}`])
  return facts
}
