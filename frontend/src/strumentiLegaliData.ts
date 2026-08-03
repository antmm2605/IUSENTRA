import { apiJson, apiPostJson } from './lib/apiClient'

export type CampoStrumento = {
  name: string
  label: string
  type: 'number' | 'select' | 'date' | 'text'
  value: string
  help?: string
  min?: number
  max?: number
  step?: string
  options?: { value: string; label: string }[]
}

export type StrumentoForense = {
  id: string
  title: string
  subtitle: string
  categoria: string
  icon: string
  reso_in_react: boolean
  azione: string
  campi: CampoStrumento[]
  href_vista_classica: string
}

export type StrumentiLegaliPayload = {
  strumenti: StrumentoForense[]
  categorie: string[]
  tool_attivo: string
  totale: number
  totale_in_react: number
  endpoint_calcolo: string
  warning?: string
}

export type EsitoCalcolo = {
  ok: boolean
  tool?: string
  errore?: string
  result?: Record<string, unknown>
}

const PAYLOAD_VUOTO: StrumentiLegaliPayload = {
  strumenti: [],
  categorie: [],
  tool_attivo: '',
  totale: 0,
  totale_in_react: 0,
  endpoint_calcolo: '/api/v1/ui/strumenti-legali/calcola',
  warning: 'Catalogo strumenti non disponibile. Resta utilizzabile la vista classica.',
}

export async function caricaStrumentiLegali(tool: string, signal?: AbortSignal): Promise<StrumentiLegaliPayload> {
  const query = tool ? `?tool=${encodeURIComponent(tool)}` : ''
  return apiJson<StrumentiLegaliPayload>(`/api/v1/ui/strumenti-legali${query}`, PAYLOAD_VUOTO, { signal })
}

export async function eseguiCalcolo(
  tool: string,
  dati: Record<string, string>,
  signal?: AbortSignal,
): Promise<EsitoCalcolo> {
  return apiPostJson<EsitoCalcolo>(
    '/api/v1/ui/strumenti-legali/calcola',
    { tool, dati },
    { ok: false, errore: 'Calcolo non riuscito. Riprova o usa la vista classica.' },
    { signal },
  )
}

/** Estrae le righe leggibili di un risultato, senza conoscere lo strumento. */
export function righeRisultato(result: Record<string, unknown> | undefined): { label: string; value: string }[] {
  if (!result) return []
  const salta = new Set(['notes', 'warnings', 'sources', 'passaggi', 'benefici', 'rows', 'criteri'])
  const righe: { label: string; value: string }[] = []
  for (const [chiave, valore] of Object.entries(result)) {
    if (salta.has(chiave)) continue
    if (valore === null || valore === undefined || valore === '') continue
    if (typeof valore === 'object') continue
    righe.push({ label: etichettaChiave(chiave), value: String(valore) })
  }
  return righe
}

export function etichettaChiave(chiave: string): string {
  const testo = chiave.replace(/_/g, ' ').trim()
  return testo.charAt(0).toUpperCase() + testo.slice(1)
}

export function elencoTestuale(result: Record<string, unknown> | undefined, chiave: string): string[] {
  const valore = result?.[chiave]
  if (!Array.isArray(valore)) return []
  return valore.filter((voce): voce is string => typeof voce === 'string')
}

export function fontiRisultato(result: Record<string, unknown> | undefined): { title: string; url: string }[] {
  const valore = result?.sources
  if (!Array.isArray(valore)) return []
  return valore
    .filter((voce): voce is { title?: string; url?: string } => typeof voce === 'object' && voce !== null)
    .map((voce) => ({ title: String(voce.title ?? ''), url: String(voce.url ?? '') }))
    .filter((voce) => voce.url)
}
