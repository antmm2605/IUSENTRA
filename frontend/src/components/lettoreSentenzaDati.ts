/** Dati del lettore dei provvedimenti: JSON dello stesso indirizzo della pagina (`?format=json`). */
export type BloccoTesto = { tipo: 'titolo' | 'paragrafo'; testo: string; ancora: string }
export type ParteTradotta = { originale: string; traduzione: string; avviso: string }
export type VoceIntegrita = { etichetta: string; valore: string }

export type DocumentoLettore = {
  tipo: 'provvedimento' | 'traduzione' | 'testo_ufficiale'
  occhiello: string
  titolo: string
  righe: string[]
  provenienza: string
  fonteTesto?: string
  fonteUrl?: string
  avvisi: string[]
  blocchi: BloccoTesto[]
  parti?: ParteTradotta[]
  linguaOriginale?: string
  originaleUrl?: string
  integrita: VoceIntegrita[]
  nota: string
  testoSempliceUrl?: string
}

/** Indirizzo del JSON: stessa pagina, `embed=source` e `format=json`. */
export function indirizzoDati(location: Pick<Location, 'pathname' | 'search'> = window.location): string {
  const parametri = new URLSearchParams(location.search)
  parametri.set('embed', 'source')
  parametri.set('format', 'json')
  return `${location.pathname}?${parametri.toString()}`
}

/** Solo collegamenti http(s) verso l'esterno, mai `javascript:` o altri schemi. */
export function urlEsternoSicuro(valore: string | undefined): string {
  if (!valore) return ''
  try {
    const url = new URL(valore)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : ''
  } catch {
    return ''
  }
}

/** Solo percorsi interni dell'archivio giurisprudenza. */
export function percorsoInterno(valore: string | undefined): string {
  return valore && valore.startsWith('/giurisprudenza/') && !valore.startsWith('//') ? valore : ''
}

export async function leggiDocumento(signal?: AbortSignal): Promise<DocumentoLettore> {
  const risposta = await fetch(indirizzoDati(), { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }, signal })
  if (!risposta.ok) {
    const testo = await risposta.text().catch(() => '')
    throw new Error(testo && !testo.trimStart().startsWith('<') ? testo.slice(0, 300) : 'Testo del provvedimento non disponibile.')
  }
  const dati = await risposta.json() as { documento?: DocumentoLettore }
  if (!dati.documento) throw new Error('Testo del provvedimento non disponibile.')
  return dati.documento
}
