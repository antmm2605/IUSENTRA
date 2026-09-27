import {
  elenco,
  leggiPubblico,
  oggetto,
  percorsoInterno,
  scriviPubblico,
  testo,
  urlEsternoSicuro,
  type Grezzo,
} from './pubblicoTokenApi'

/** Link di pagamento del cliente (`/pagamenti/paga/<token>`): dati e avvio. */

export type Provider = 'stripe' | 'paypal' | 'satispay' | 'sumup' | 'bonifico'

export const PROVIDER_NOTI: Provider[] = ['stripe', 'paypal', 'satispay', 'sumup', 'bonifico']

export type Importo = { importo: string; valuta: string; descrizione: string }

export type DatiCheckout = Importo & { scadenza: string; cliente: string; providerAttivi: Provider[] }
export type DatiGiaPagato = Importo & { dataPagamento: string; metodo: string }

export type CoordinateBonifico = { intestazione: string; iban: string; banca: string; noteAggiuntive: string }

export type DatiEsito = Importo & {
  vista: 'pagato' | 'bonifico' | 'atteso'
  causale: string
  metodo: string
  idTransazione: string
  dataPagamento: string
  bonifico: CoordinateBonifico | null
}

export type StatoPagamento =
  | { tipo: 'caricamento' }
  | { tipo: 'checkout'; dati: DatiCheckout }
  | { tipo: 'gia_pagato'; dati: DatiGiaPagato }
  | { tipo: 'scaduto' }
  | { tipo: 'sumup'; checkoutId: string; urlEsito: string; importo: string }
  | { tipo: 'esito'; dati: DatiEsito }
  | { tipo: 'errore'; messaggio: string }

function tokenUrl(token: string): string {
  return encodeURIComponent(token)
}

function api(token: string, suffisso = ''): string {
  return `/api/v1/pubblico/pagamenti/${tokenUrl(token)}${suffisso}`
}

export function percorsoCheckout(token: string): string {
  return `/pagamenti/paga/${tokenUrl(token)}`
}

function importo(raw: Grezzo): Importo {
  return { importo: testo(raw.importo), valuta: testo(raw.valuta) || 'EUR', descrizione: testo(raw.descrizione) }
}

function provider(value: unknown): Provider | null {
  const raw = testo(value)
  return (PROVIDER_NOTI as string[]).includes(raw) ? (raw as Provider) : null
}

function coordinate(value: unknown): CoordinateBonifico | null {
  const c = oggetto(value)
  if (!Object.keys(c).length) return null
  return { intestazione: testo(c.intestazione), iban: testo(c.iban), banca: testo(c.banca), noteAggiuntive: testo(c.note_aggiuntive) }
}

export function datiEsito(raw: Grezzo): DatiEsito {
  const vista = testo(raw.vista)
  return {
    ...importo(raw),
    vista: vista === 'pagato' || vista === 'bonifico' ? vista : 'atteso',
    causale: testo(raw.causale) || 'Pagamento parcella',
    metodo: testo(raw.metodo),
    idTransazione: testo(raw.id_transazione),
    dataPagamento: testo(raw.data_pagamento),
    bonifico: coordinate(raw.bonifico),
  }
}

export async function caricaCheckout(token: string, signal?: AbortSignal): Promise<StatoPagamento> {
  const risposta = await leggiPubblico(api(token), signal)
  if (risposta.status === 410) return { tipo: 'scaduto' }
  if (risposta.status !== 200) return { tipo: 'errore', messaggio: risposta.messaggio || 'Pagina di pagamento non disponibile. Riprova più tardi.' }
  const raw = risposta.dati
  if (testo(raw.vista) === 'gia_pagato') {
    return { tipo: 'gia_pagato', dati: { ...importo(raw), dataPagamento: testo(raw.data_pagamento), metodo: testo(raw.metodo) } }
  }
  return {
    tipo: 'checkout',
    dati: {
      ...importo(raw),
      scadenza: testo(raw.scadenza),
      cliente: testo(raw.cliente),
      providerAttivi: elenco(raw.provider_attivi).map(provider).filter((p): p is Provider => p !== null),
    },
  }
}

export async function caricaEsito(token: string, providerScelto: string, signal?: AbortSignal): Promise<StatoPagamento> {
  const parametri = providerScelto && provider(providerScelto) ? `?provider=${encodeURIComponent(providerScelto)}` : ''
  const risposta = await leggiPubblico(api(token, `/esito${parametri}`), signal)
  if (risposta.status === 410) return { tipo: 'scaduto' }
  if (risposta.status !== 200) return { tipo: 'errore', messaggio: risposta.messaggio || 'Esito del pagamento non disponibile. Riprova più tardi.' }
  return { tipo: 'esito', dati: datiEsito(risposta.dati) }
}

export type AvvioPagamento =
  | { tipo: 'redirect'; url: string }
  | { tipo: 'sumup'; checkoutId: string; urlEsito: string }
  | { tipo: 'bonifico'; urlEsito: string; esito: DatiEsito }
  | { tipo: 'scaduto' }
  | { tipo: 'errore'; messaggio: string }

export async function avviaPagamento(token: string, scelto: Provider): Promise<AvvioPagamento> {
  const risposta = await scriviPubblico(api(token, '/avvia'), { provider: scelto })
  if (risposta.status === 410) return { tipo: 'scaduto' }
  const raw = risposta.dati
  const errore = risposta.messaggio || 'Pagamento non avviato. Riprova o scegli un altro metodo.'
  if (risposta.status !== 200) return { tipo: 'errore', messaggio: errore }
  const tipo = testo(raw.tipo)
  if (tipo === 'redirect') {
    const url = urlEsternoSicuro(raw.url)
    return url ? { tipo: 'redirect', url } : { tipo: 'errore', messaggio: errore }
  }
  if (tipo === 'sumup' && testo(raw.checkout_id)) {
    return { tipo: 'sumup', checkoutId: testo(raw.checkout_id), urlEsito: percorsoInterno(raw.url_esito) }
  }
  if (tipo === 'bonifico') {
    return { tipo: 'bonifico', urlEsito: percorsoInterno(raw.url_esito), esito: datiEsito(oggetto(raw.esito)) }
  }
  return { tipo: 'errore', messaggio: errore }
}
