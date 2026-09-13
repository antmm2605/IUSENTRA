/**
 * Ricerca dei fascicoli per nome e cognome del cliente.
 * L'elenco completo dei fascicoli non è una ricerca: quando l'archivio cresce,
 * l'avvocato trova la pratica scrivendo il nome della persona che assiste.
 */

export type MatterMatch = {
  value: string
  label: string
  numero: string
  titolo: string
  cliente: string
  stato: string
  punteggio: number
  certo: boolean
}

type SearchPayload = { ok?: boolean; results?: unknown; message?: string }

/** Lunghezza sotto la quale non si interroga il server: sarebbe rumore. */
export const LUNGHEZZA_MINIMA_RICERCA = 2

function normalizeMatch(row: unknown): MatterMatch | null {
  if (!row || typeof row !== 'object') return null
  const record = row as Record<string, unknown>
  const value = String(record.value || '').trim()
  if (!value) return null
  return {
    value,
    label: String(record.label || '').trim() || value,
    numero: String(record.numero || '').trim(),
    titolo: String(record.titolo || '').trim(),
    cliente: String(record.cliente || '').trim(),
    stato: String(record.stato || '').trim(),
    punteggio: Number(record.punteggio) || 0,
    certo: record.certo === true,
  }
}

export async function searchMatters(query: string, signal?: AbortSignal): Promise<MatterMatch[]> {
  const testo = query.trim()
  if (testo.length < LUNGHEZZA_MINIMA_RICERCA) return []
  const response = await fetch(`/api/v1/ui/document-tools/fascicoli?q=${encodeURIComponent(testo)}`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload = await response.json().catch(() => null) as SearchPayload | null
  if (!response.ok || !payload?.ok) {
    throw new Error(payload?.message || 'Ricerca dei fascicoli non riuscita. Riprova tra qualche istante.')
  }
  const rows = Array.isArray(payload.results) ? payload.results : []
  return rows.map(normalizeMatch).filter((row): row is MatterMatch => row !== null)
}
