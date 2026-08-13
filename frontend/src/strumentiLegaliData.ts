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
  warning: 'Catalogo strumenti momentaneamente non disponibile. Riprova tra poco.',
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
    { ok: false, errore: 'Calcolo non riuscito. Controlla i dati e riprova.' },
    { signal },
  )
}

/** Chiavi che il pannello rende in forma dedicata, non come riga di sintesi. */
const CHIAVI_NON_SINTETICHE = new Set(['notes', 'warnings', 'sources'])

/** Estrae le righe leggibili di un risultato, senza conoscere lo strumento. */
export function righeRisultato(result: Record<string, unknown> | undefined): { label: string; value: string }[] {
  if (!result) return []
  const righe: { label: string; value: string }[] = []
  for (const [chiave, valore] of Object.entries(result)) {
    if (CHIAVI_NON_SINTETICHE.has(chiave)) continue
    if (valore === null || valore === undefined || valore === '') continue
    if (typeof valore === 'object') continue
    righe.push({ label: etichettaChiave(chiave), value: String(valore) })
  }
  return righe
}

export type TabellaRisultato = {
  chiave: string
  titolo: string
  colonne: string[]
  righe: Record<string, string>[]
}

/**
 * Ricava le tabelle di dettaglio da qualunque risultato: ogni calcolatore
 * restituisce elenchi diversi (segmenti di tasso, passaggi di pena, rate del
 * piano, parametri tabellari) e le colonne vengono dedotte dalle chiavi, così
 * la pagina non deve conoscere i singoli strumenti.
 */
export function tabelleRisultato(result: Record<string, unknown> | undefined): TabellaRisultato[] {
  if (!result) return []
  const tabelle: TabellaRisultato[] = []
  for (const [chiave, valore] of Object.entries(result)) {
    if (CHIAVI_NON_SINTETICHE.has(chiave)) continue
    if (!Array.isArray(valore) || !valore.length) continue
    const voci = valore.filter(
      (voce): voce is Record<string, unknown> =>
        typeof voce === 'object' && voce !== null && !Array.isArray(voce),
    )
    if (voci.length !== valore.length) continue
    const colonne: string[] = []
    for (const voce of voci) {
      for (const campo of Object.keys(voce)) {
        if (typeof voce[campo] === 'object' && voce[campo] !== null) continue
        if (!colonne.includes(campo)) colonne.push(campo)
      }
    }
    if (!colonne.length) continue
    tabelle.push({
      chiave,
      titolo: etichettaChiave(chiave),
      colonne,
      righe: voci.map((voce) => {
        const riga: Record<string, string> = {}
        for (const campo of colonne) {
          const cella = voce[campo]
          riga[campo] = cella === null || cella === undefined || typeof cella === 'object' ? '' : String(cella)
        }
        return riga
      }),
    })
  }
  return tabelle
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
