import { apiPostJson } from './lib/apiClient'

export type OpenGADecision = {
  relazione_id: string; organo_giudicante: string; numero_sentenza: string
  anno_sentenza: number; numero_ricorso: string; oggetto: string; esito: string
  official_search_url: string; resource_id: string; resource_sha256: string
}
export type OpenGAResult = {
  ok: boolean; message?: string; risultati: OpenGADecision[]; semantic_available?: boolean
}
export type OpenGAQuery = { q: string; dal: string; al: string; semantica: boolean }

// Le due richieste usano lo stesso snapshot e il servizio autenticato esistente.
// Nessuna memorizzazione persistente delle domande o passaggio automatico di lista.
export async function searchOpenGA(
  query: OpenGAQuery, signal: AbortSignal,
  onRapid: (result: OpenGAResult) => void,
  onDeep: (result: OpenGAResult) => void,
): Promise<void> {
  const snapshot = { ...query }
  const request = (semantic: boolean) => apiPostJson<OpenGAResult>(
    '/api/v1/ui/giurisprudenza/ricerca-amministrativa',
    { ...snapshot, semantica: semantic },
    { ok: false, message: 'Ricerca non disponibile. Riprova più tardi.', risultati: [] },
    { signal, activity: false },
  )
  const rapid = await request(false)
  if (signal.aborted) return
  onRapid(rapid)
  if (!rapid.ok || !snapshot.semantica) return
  const deep = await request(true)
  if (!signal.aborted) onDeep(deep)
}


export function officialDecisionNumber(value: string, year: number): string {
  return /^[0-9]{9}$/.test(value) && value.startsWith(String(year))
    ? value.slice(String(year).length).replace(/^0+(?=[0-9])/, '')
    : value
}
