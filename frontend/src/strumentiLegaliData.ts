import { apiJson, apiPostJson } from './lib/apiClient'
import { formatEuroIt } from './formatting'

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
  /** Il campo si mostra solo quando un altro campo ha uno di questi valori (vuoto = primo valore). */
  quando?: { campo: string; valori: string[] }
}

export type StrumentoForense = {
  id: string
  title: string
  subtitle: string
  categoria: string
  icon: string
  reso_in_react: boolean
  /** Componente React dedicato, per gli strumenti che non sono moduli di calcolo. */
  componente?: string
  azione: string
  campi: CampoStrumento[]
}

export type StrumentiLegaliPayload = {
  funzioni?: FunzioneUtility[]
  strumenti: StrumentoForense[]
  categorie: string[]
  tool_attivo: string
  totale: number
  totale_in_react: number
  endpoint_calcolo: string
  warning?: string
}

export type FunzioneUtility = {
  id: string
  title: string
  description: string
  section: string
  href: string
  toolId: string
  preset: Record<string, string>
  unavailable: { reason: string; label: string; href: string } | null
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
const CHIAVI_NON_SINTETICHE = new Set(['notes', 'warnings', 'sources', 'scadenze_proposte', 'scadenza_iso'])

/** Presentazione italiana del calcolo interessi; i valori API restano numerici/ISO. */
export function valoreRisultato(chiave: string, valore: unknown, tool = ''): string {
  if (valore === null || valore === undefined || typeof valore === 'object') return ''
  if (tool === 'interessi') {
    if (['capital', 'total_amount', 'total_interest', 'interest'].includes(chiave) && typeof valore === 'number') return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', useGrouping: true }).format(valore)
    if (['start_date', 'end_date', 'from', 'to'].includes(chiave) && typeof valore === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valore)) return valore.split('-').reverse().join('/')
    if (['rate', 'reference_rate'].includes(chiave) && typeof valore === 'number') return `${valore.toLocaleString('it-IT', { maximumFractionDigits: 4 })}%`
    if (chiave === 'mode') return valore === 'legali' ? 'Interessi legali' : valore === 'mora_commerciale' ? 'Mora commerciale' : String(valore)
    if (typeof valore === 'number') return valore.toLocaleString('it-IT')
  }
  return String(valore)
}

/** Estrae le righe leggibili di un risultato, senza conoscere lo strumento. */
export function righeRisultato(result: Record<string, unknown> | undefined, tool = ''): { label: string; value: string }[] {
  if (!result) return []
  if (tool === 'indennita_mediazione') {
    const campi: [string, string, 'testo' | 'euro' | 'booleano'][] = [
      ['regime_label', 'Regime', 'testo'], ['esito_label', 'Esito', 'testo'],
      ['scaglione', 'Scaglione', 'testo'], ['valore', 'Valore della lite', 'euro'],
      ['spese_avvio', 'Spese di avvio', 'euro'],
      ['spese_mediazione_primo_incontro', 'Spese del primo incontro', 'euro'],
      ['ulteriori_spese_mediazione', 'Ulteriori spese di mediazione', 'euro'],
      ['totale_organismo', 'Totale dovuto all’organismo', 'euro'],
      ['spese_avvio_base', 'Spese di avvio prima delle riduzioni', 'euro'],
      ['spese_mediazione_primo_base', 'Primo incontro prima delle riduzioni', 'euro'],
      ['tabella_a_minimo', 'Minimo della tabella A', 'euro'],
      ['riduzione_obbligatoria_applicata', 'Riduzione per mediazione obbligatoria applicata', 'booleano'],
      ['art31_comma3_maggiorazione_20', 'Maggiorazione del 20% (art. 31, comma 3)', 'booleano'],
    ]
    return campi.flatMap(([chiave, label, formato]) => {
      const valore = result[chiave]
      if (valore === undefined || valore === null || valore === '') return []
      const value = formato === 'euro' && typeof valore === 'number' ? formatEuroIt(valore)
        : formato === 'booleano' && typeof valore === 'boolean' ? (valore ? 'Sì' : 'No') : String(valore)
      return [{ label, value }]
    })
  }
  const righe: { label: string; value: string }[] = []
  for (const [chiave, valore] of Object.entries(result)) {
    if (CHIAVI_NON_SINTETICHE.has(chiave)) continue
    if (valore === null || valore === undefined || valore === '') continue
    if (typeof valore === 'object') continue
    const value = tool === 'percentuali' && chiave === 'quota' && typeof valore === 'number'
      ? formatEuroIt(valore)
      : tool === 'percentuali' && ['incidenza', 'variazione'].includes(chiave) && typeof valore === 'number'
        ? `${valore.toLocaleString('it-IT', { maximumFractionDigits: 4 })}%`
        : valoreRisultato(chiave, valore, tool)
    righe.push({ label: etichettaChiave(chiave), value })
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
export function tabelleRisultato(result: Record<string, unknown> | undefined, tool = ''): TabellaRisultato[] {
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
          riga[campo] = valoreRisultato(campo, cella, tool)
        }
        return riga
      }),
    })
  }
  return tabelle
}

export function etichettaChiave(chiave: string): string {
  const etichette: Record<string, string> = { capital: 'Capitale', covered_days: 'Giorni coperti', days: 'Giorni', end_date: 'Data finale', start_date: 'Data iniziale', label: 'Descrizione', mode: 'Regime', total_amount: 'Totale dovuto', total_interest: 'Interessi totali', segments: 'Dettaglio per periodo', from: 'Dal', to: 'Al', interest: 'Interessi', rate: 'Tasso annuo', reference_rate: 'Tasso di riferimento' }
  if (etichette[chiave]) return etichette[chiave]
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

export type ScadenzaProposta = { titolo: string; data: string; norma: string }

export function scadenzeProposte(result: Record<string, unknown> | undefined): ScadenzaProposta[] {
  const valore = result?.scadenze_proposte
  if (!Array.isArray(valore)) return []
  return valore
    .filter((voce): voce is Record<string, unknown> => typeof voce === 'object' && voce !== null)
    .map((voce) => ({ titolo: String(voce.titolo ?? ''), data: String(voce.data ?? ''), norma: String(voce.norma ?? '') }))
    .filter((voce) => /^\d{4}-\d{2}-\d{2}$/.test(voce.data))
}

export type EsitoScadenza = { ok: boolean; messaggio?: string; errore?: string; href?: string; giaPresente?: boolean }

export function aggiungiScadenza(tool: string, dati: Record<string, string>, indice: number, idFascicolo: string): Promise<EsitoScadenza> {
  return apiPostJson<EsitoScadenza>(
    '/api/v1/ui/strumenti-legali/scadenza',
    { tool, dati, indice, id_fascicolo: idFascicolo },
    { ok: false, errore: 'Scadenza non creata.' },
  )
}

/** Un campo condizionato si mostra quando il campo di controllo ha uno dei valori (vuoto = prima opzione). */
export function campoVisibile(campo: CampoStrumento, campi: CampoStrumento[], valori: Record<string, string>): boolean {
  if (!campo.quando) return true
  const controllo = campi.find((voce) => voce.name === campo.quando?.campo)
  const valore = valori[campo.quando.campo] || controllo?.options?.[0]?.value || ''
  if (controllo && !campoVisibile(controllo, campi, valori)) return false
  return campo.quando.valori.includes(valore)
}
