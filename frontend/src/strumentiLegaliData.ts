import { apiJson, apiPostJson } from './lib/apiClient'
import { formatEuroIt } from './formatting'

export type CampoStrumento = {
  name: string
  label: string
  /** `textarea`: una voce per riga, celle separate da «;» (bilanci e prospetti delle stime motivate). */
  type: 'number' | 'select' | 'date' | 'text' | 'textarea'
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
const CHIAVI_NON_SINTETICHE = new Set([
  'notes', 'warnings', 'sources', 'scadenze_proposte', 'scadenza_iso',
  // Il documento si mostra come testo (documentoRisultato), mai come codice HTML.
  'rendered_html', 'rendered_text',
])

/** Etichette italiane delle chiavi ricorrenti dei calcolatori (le altre si ricavano dal nome). */
const ETICHETTE: Record<string, string> = {
  capital: 'Capitale', covered_days: 'Giorni coperti dalle tabelle', days: 'Giorni', end_date: 'Data finale',
  start_date: 'Data iniziale', label: 'Descrizione', mode: 'Regime', total_amount: 'Totale dovuto',
  total_interest: 'Interessi totali', segments: 'Dettaglio per periodo', from: 'Dal', to: 'Al',
  interest: 'Interessi', rate: 'Tasso annuo', reference_rate: 'Tasso di riferimento BCE', base: 'Base di calcolo',
  breakdown: 'Prospetto', amount: 'Importo', interest_mode: 'Regime degli interessi', interest_result: 'Calcolo degli interessi',
  days_inclusive: 'Giorni (estremi compresi)', months_full: 'Mesi interi', years_full: 'Anni interi',
  weeks: 'Settimane', next_anniversary: 'Prossima ricorrenza', preview_schedule: 'Prime rate del piano',
  quarter: 'Trimestre', rows: 'Righe', count: 'Numero', detail: 'Dettaglio', data_domanda: 'Data della domanda giudiziale',
  esito_classe: '', is_selected: '', richiede_verifica: 'Da verificare', regole_applicate: '',
  tegm: 'TEGM (tasso medio)', soglia: 'Soglia antiusura', margine: 'Margine rispetto alla soglia',
  supera_soglia: 'Supera la soglia', eta: 'Età', anzianita: 'Anzianità', affidabilita: 'Affidabilità',
  interrogatorio_entra: 'Interrogatorio di garanzia entro', riesame_entra: 'Istanza di riesame entro',
  decisione_entra: 'Decisione sul riesame entro', deposito_entra: 'Deposito della motivazione entro',
  giorni_inclusivi: 'Giorni (estremi compresi)', dettaglio_annuale: 'Accantonamento e rivalutazione anno per anno',
}

/** Chiavi tecniche che non si mostrano all'avvocato. */
const CHIAVI_TECNICHE = /(^|_)(classe|css|badge|is_selected|regole_applicate|codice_regola|id_interno)$/

const RE_DATA_ISO = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}).*)?$/
const RE_EURO = /(importo|totale|total_amount|total_interest|capitale|capital$|^amount$|^interest$|interess|rivalut|quota_(annua|periodo|accantonata|lorda|parte|interessi|capitale|netta|pignorabile|disponibile)|compens|onorar|imposta|spese|spesa|cpa$|^iva$|_iva$|^iva_|canone|valore|retribuzion|stipend|pension|reddito|detrazion|contribut|indennit|risarciment|danno|acconti|anticipazion|montante|residuo|netto|lordo|rata_importo|^importo_rata|ritenuta|trattenuta|fondo|minimo_protetto|pignorabile|eccedenza|provvigion|bollo|sanzion|assegno|fabbisogno|trasferimento|patrimonio|asse|massa|legittima|disponibile|prezzo|costo|risparmio|liquidabil|differenza|incremento|base_calcolo|^base$)/
const RE_PERCENTUALE = /(perc|percentuale|aliquota|tasso|^rate$|rate$|tegm|soglia|margine|variazion|incidenza|coefficiente_perc|taeg|tan$|rendimento)/
const RE_NON_EURO = /(giorni|mesi|anni|numero|^n_|count|eta$|punti|percentuale|perc|aliquota|tasso|coefficiente|indice|anno|mese|rate_count|parti|figli|scaglione)/

function dataItaliana(valore: string): string | null {
  const m = RE_DATA_ISO.exec(valore)
  if (!m) return null
  const data = `${m[3]}/${m[2]}/${m[1]}`
  return m[4] ? `${data} ${m[4]}:${m[5]}` : data
}

/** Presentazione italiana di un valore del risultato: date gg/mm/aaaa, euro, percentuali, Sì/No. */
export function valoreRisultato(chiave: string, valore: unknown, tool = ''): string {
  if (valore === null || valore === undefined || typeof valore === 'object') return ''
  const nome = chiave.toLowerCase()
  if (typeof valore === 'boolean') return valore ? 'Sì' : 'No'
  if (typeof valore === 'string') {
    const data = dataItaliana(valore.trim())
    if (data) return data
    if (valore === 'true') return 'Sì'
    if (valore === 'false') return 'No'
    if (tool === 'interessi' && chiave === 'mode') {
      return ({ legali: 'Interessi legali', mora_commerciale: 'Mora commerciale', convenzionale: 'Tasso convenzionale', legali_1284_4: 'Legali e, dalla domanda, saggio D.Lgs. 231/2002' } as Record<string, string>)[valore] ?? valore
    }
    return valore
  }
  if (typeof valore === 'number') {
    if (RE_PERCENTUALE.test(nome) && !/(importo|totale)/.test(nome)) {
      return `${valore.toLocaleString('it-IT', { maximumFractionDigits: 4 })}%`
    }
    if (RE_EURO.test(nome) && !RE_NON_EURO.test(nome)) return formatEuroIt(valore)
    return valore.toLocaleString('it-IT', { maximumFractionDigits: 4 })
  }
  return String(valore)
}

function aggiungiRiga(
  righe: { label: string; value: string }[],
  chiave: string,
  valore: unknown,
  tool: string,
  prefisso: string,
  fratelli: Record<string, unknown>,
) {
  if (CHIAVI_NON_SINTETICHE.has(chiave) || CHIAVI_TECNICHE.test(chiave)) return
  if (valore === null || valore === undefined || valore === '') return
  // Se esiste «chiave_label» la riga mostra l'etichetta leggibile, non il codice interno.
  if (typeof valore === 'string' && typeof fratelli[`${chiave}_label`] === 'string' && fratelli[`${chiave}_label`]) return
  const base = chiave.endsWith('_label') ? chiave.slice(0, -'_label'.length) : chiave
  const etichetta = etichettaChiave(base)
  if (!etichetta) return
  const label = prefisso ? `${prefisso} · ${etichetta}` : etichetta
  if (Array.isArray(valore)) {
    if (valore.every((voce) => typeof voce === 'string' || typeof voce === 'number')) {
      righe.push({ label, value: valore.map((voce) => valoreRisultato(base, voce, tool)).join(', ') })
    }
    return
  }
  if (typeof valore === 'object') {
    // Un livello di annidamento: totali e scenari (onorari, art. 96, diffamazione) restano visibili.
    if (prefisso) return
    const figlio = valore as Record<string, unknown>
    for (const [sotto, contenuto] of Object.entries(figlio)) {
      if (typeof contenuto === 'object' && contenuto !== null && !Array.isArray(contenuto)) {
        for (const [foglia, dato] of Object.entries(contenuto as Record<string, unknown>)) {
          if (typeof dato === 'object') continue
          aggiungiRiga(righe, foglia, dato, tool, `${etichetta} · ${etichettaChiave(sotto)}`, contenuto as Record<string, unknown>)
        }
        continue
      }
      aggiungiRiga(righe, sotto, contenuto, tool, etichetta, figlio)
    }
    return
  }
  const value = tool === 'percentuali' && chiave === 'quota' && typeof valore === 'number'
    ? formatEuroIt(valore)
    : tool === 'percentuali' && ['incidenza', 'variazione'].includes(chiave) && typeof valore === 'number'
      ? `${valore.toLocaleString('it-IT', { maximumFractionDigits: 4 })}%`
      : valoreRisultato(base, valore, tool)
  righe.push({ label, value })
}

/** Estrae le righe leggibili di un risultato, senza conoscere lo strumento. */
export function righeRisultato(result: Record<string, unknown> | undefined, tool = ''): { label: string; value: string }[] {
  if (!result) return []
  if (tool === 'indennita_mediazione') {
    const campi: [string, string, 'testo' | 'euro' | 'booleano'][] = [
      ['regime_label', 'Regime', 'testo'], ['esito_label', 'Esito', 'testo'],
      ['scaglione', 'Scaglione', 'testo'], ['valore', 'Valore della lite', 'euro'],
      ['spese_avvio', 'Spese di avvio (oltre IVA)', 'euro'],
      ['spese_mediazione_primo_incontro', 'Spese del primo incontro (oltre IVA)', 'euro'],
      ['ulteriori_spese_mediazione', 'Ulteriori spese di mediazione (oltre IVA)', 'euro'],
      ['totale_organismo', 'Totale dovuto all’organismo (oltre IVA)', 'euro'],
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
    // Gli elenchi di oggetti diventano tabelle (tabelleRisultato).
    if (Array.isArray(valore) && valore.some((voce) => typeof voce === 'object' && voce !== null)) continue
    aggiungiRiga(righe, chiave, valore, tool, '', result)
  }
  // Etichette uguali (es. «Giorni» e «Giorni coperti» con lo stesso valore) restano una volta sola.
  const viste = new Set<string>()
  return righe.filter((riga) => {
    const firma = `${riga.label}=${riga.value}`
    if (viste.has(firma)) return false
    viste.add(firma)
    return true
  })
}

/** Testo del documento prodotto dallo strumento (es. nota di precisazione), da leggere e copiare. */
export function documentoRisultato(result: Record<string, unknown> | undefined): string {
  const testo = result?.rendered_text
  return typeof testo === 'string' ? testo : ''
}

export type TabellaRisultato = {
  chiave: string
  titolo: string
  colonne: string[]
  righe: Record<string, string>[]
}

/** Ordine naturale delle colonne di periodo: «Dal» prima di «Al». */
function ordinaColonne(colonne: string[]): string[] {
  const peso = (colonna: string) => (['from', 'dal', 'start', 'data_inizio'].includes(colonna) ? 0 : ['to', 'al', 'end', 'data_fine'].includes(colonna) ? 1 : 2)
  return [...colonne].sort((a, b) => {
    const pa = peso(a), pb = peso(b)
    return pa < 2 && pb < 2 ? pa - pb : 0
  })
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
        if (CHIAVI_TECNICHE.test(campo) || !etichettaChiave(campo)) continue
        // Colonne doppie (es. «scadenza» e «scadenza_it»): resta quella leggibile.
        if (campo.endsWith('_it') && colonne.includes(campo.slice(0, -3))) {
          colonne.splice(colonne.indexOf(campo.slice(0, -3)), 1)
        }
        if (colonne.includes(`${campo}_it`)) continue
        if (!colonne.includes(campo)) colonne.push(campo)
      }
    }
    if (!colonne.length) continue
    const ordinate = ordinaColonne(colonne)
    tabelle.push({
      chiave,
      titolo: etichettaChiave(chiave),
      colonne: ordinate,
      righe: voci.map((voce) => {
        const riga: Record<string, string> = {}
        for (const campo of ordinate) {
          const cella = voce[campo]
          riga[campo] = valoreRisultato(campo.replace(/_it$/, ''), cella, tool)
        }
        return riga
      }),
    })
  }
  return tabelle
}

export function etichettaChiave(chiave: string): string {
  if (chiave in ETICHETTE) return ETICHETTE[chiave]
  const pulita = chiave.replace(/_it$/, '').replace(/_label$/, '')
  if (pulita in ETICHETTE) return ETICHETTE[pulita]
  const testo = pulita.replace(/_/g, ' ').trim()
    .replace(/\banzianita\b/g, 'anzianità').replace(/\beta\b/g, 'età')
    .replace(/\baffidabilita\b/g, 'affidabilità').replace(/\bgia\b/g, 'già')
    .replace(/\bperc\b/g, '%').replace(/\bcpa\b/g, 'CPA').replace(/\biva\b/g, 'IVA')
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
