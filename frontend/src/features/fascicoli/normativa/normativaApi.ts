import { ensureJson } from '../../../api/client'
import type { ArticoloTrovato, NormativaFascicolo, TestoArchivio } from './types'

/**
 * Le tre letture del pannello «Normativa» del fascicolo. La ricerca riusa l'archivio di
 * «Codici e leggi» (`/api/v1/ui/ricerca-legale/normativa/articoli`), limitato alle materie
 * della pratica: nessun motore di ricerca parallelo.
 */
const base = (fascicoloId: string) => `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/normativa`

export function leggiNormativa(fascicoloId: string, signal?: AbortSignal) {
  return ensureJson<{ ok: boolean; normativa: NormativaFascicolo }>(base(fascicoloId), { signal, activity: 'Normativa del fascicolo…' })
}

export function leggiTestoArchivio(fascicoloId: string, urn: string, articolo: string) {
  const params = new URLSearchParams({ urn, articolo })
  return ensureJson<{ ok: boolean; testo: TestoArchivio }>(`${base(fascicoloId)}/testo?${params}`, { activity: 'Testo dall’archivio Normattiva…' })
}

export function cercaNormativa(parole: string, materie: string[], soloMaterie: boolean, signal?: AbortSignal) {
  const params = new URLSearchParams({ q: parole, offset: '0' })
  if (soloMaterie) materie.forEach((materia) => params.append('materia', materia))
  return ensureJson<{ ok: boolean; items: ArticoloTrovato[]; total: number }>(
    `/api/v1/ui/ricerca-legale/normativa/articoli?${params}`, { signal, activity: 'Ricerca nella normativa…' },
  )
}

export function leggiArticolo(id: number) {
  return ensureJson<{ ok: boolean; item: { text: string; number: string; title: string; act_label?: string; act_title: string; source_url: string; source_label?: string; updated_at: string; consolidated_at?: string; only_heading?: boolean } }>(
    `/api/v1/ui/ricerca-legale/normativa/articoli/${id}`, { activity: 'Apertura dell’articolo…' },
  )
}
