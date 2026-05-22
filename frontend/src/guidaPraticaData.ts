export type GuidaCoverage = {
  level: string
  source: string
  needs_reviewer: boolean
  message: string
}

export type CodiceDepositoStatus = {
  codice?: string
  ufficiale?: boolean
  depositabile?: boolean
  fonte?: string
  messaggio?: string
}

export type GuidaNormativa = {
  fonte?: string
  articolo?: string
  descrizione?: string
}

export type GuidaCampo = {
  id: string
  label: string
  type?: string
  required?: boolean
  options?: string[]
  depends_on?: string
  formula?: string
}

export type GuidaAllegato = {
  id: string
  label: string
  required?: boolean
}

export type GuidaSezione = {
  sezione: string
  contenuto?: string
}

export type GuidaAdempimento = {
  step?: number | string
  azione?: string
  descrizione?: string
  obbligatorio?: boolean
  consigliato?: boolean
  modalita?: string[]
  sanzione_omissione?: string
}

export type GuidaPratica = {
  codice: string
  denominazione: string
  categoria?: string
  sottocategoria?: string
  registro_sicid?: string
  coverage: GuidaCoverage
  codice_deposito?: CodiceDepositoStatus
  quick_help?: {
    titolo?: string
    prima_cosa_da_fare?: string
    atto_da_redigere?: string
    schema_xsd?: string
    totale_campi_obbligatori?: number
    totale_allegati_obbligatori?: number
    totale_avvertimenti?: number
  }
  normativa?: {
    riferimenti_primari?: GuidaNormativa[]
    riferimenti_secondari?: GuidaNormativa[]
    novita_rilevanti?: Array<Record<string, unknown>>
  }
  tipologie_di_intervento?: Array<string | Record<string, unknown>>
  presupposti_sostanziali?: string[]
  legittimati_attivi?: Array<string | Record<string, unknown>>
  obbligo_mediazione?: string | boolean | Record<string, unknown>
  obbligo_mediazione_o_negoziazione_assistita?: string | boolean | Record<string, unknown>
  richiesta_provvedimenti_urgenti?: string | boolean | Record<string, unknown>
  avvertimenti_obbligatori?: string[]
  adempimenti_propedeutici?: GuidaAdempimento[]
  atto_principale?: {
    tipo_atto?: string
    denominazione?: string
    schema_xsd_ministeriale?: string
    struttura_obbligatoria?: GuidaSezione[]
    campi_obbligatori?: GuidaCampo[]
    avvertimenti_obbligatori?: string[]
  }
  allegati_obbligatori?: GuidaAllegato[]
  avvertenze_redazionali?: string[]
  adempimenti_fiscali_telematici?: Record<string, unknown>
  termini_processuali?: Array<Record<string, unknown>>
  esiti_processuali_tipici?: Array<string | Record<string, unknown>>
  esiti_processuali_attesi?: Array<Record<string, unknown>>
}

export type GuidaChecklist = {
  ok: boolean
  codice: string
  denominazione: string
  coverage: GuidaCoverage
  codice_deposito?: CodiceDepositoStatus
  campi_mancanti: GuidaCampo[]
  allegati_mancanti: GuidaAllegato[]
  avvertimenti: Array<{ testo: string; presente: boolean; bloccante?: boolean }>
  avvertimenti_mancanti: Array<{ testo: string; presente: boolean; bloccante?: boolean }>
  adempimenti: Array<GuidaAdempimento & { completato?: boolean }>
  totale: number
  completati: number
  percentuale_completamento: number
  pronto_per_generazione: boolean
  requires_review: boolean
  blockers: Array<Record<string, unknown>>
}

export type GuidaTemplateSuggestion = {
  id: string
  compilerCode: string
  title: string
  matter: string
  area: string
  channel: string
  prefillStatus: string
  score: number
  reasons: string[]
  href: string
  editorHint: string
}

export type GuidaDocumentPlan = {
  enabled: boolean
  documentoSuggerito: string
  template: {
    status: string
    autoLoad: boolean
    reason: string
    recommended: GuidaTemplateSuggestion | null
    alternatives: GuidaTemplateSuggestion[]
  }
  import: {
    enabled: boolean
    formats: string[]
    message: string
  }
}

export type GuidaPraticaResponse = {
  ok: boolean
  source?: string
  generatedAt?: string
  message?: string
  code?: string
  notFound?: boolean
  guidaPraticaFacoltativa?: boolean
  guidaPraticaDisponibile?: boolean
  bloccaLavoro?: boolean
  fascicolo?: Record<string, unknown>
  matchedFromFascicolo?: {
    codice?: string
    denominazione?: string
    score?: number
    source_field?: string
    matched_by?: string
    confirmation_required?: boolean
    message?: string
  }
  guida?: GuidaPratica
  checklist?: GuidaChecklist
  documentPlan?: GuidaDocumentPlan
  catalogoSize?: number
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

async function getJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    const payload = await response.json().catch(() => fallback)
    if (!response.ok) return { ...(fallback as object), ...(isRecord(payload) ? payload : {}), ok: false } as T
    return payload as T
  } catch {
    return fallback
  }
}

export function emptyGuidaPraticaResponse(message = 'Guida Pratica non disponibile.'): GuidaPraticaResponse {
  return { ok: false, message }
}

export function codiceFromResponse(response: GuidaPraticaResponse): string {
  return text(response.guida?.codice || response.checklist?.codice || response.fascicolo?.codice_oggetto_pst || response.fascicolo?.codiceOggettoPst || response.matchedFromFascicolo?.codice)
}

export function getFascicoloGuidaPratica(fascicoloId: string): Promise<GuidaPraticaResponse> {
  if (!fascicoloId) return Promise.resolve(emptyGuidaPraticaResponse('Fascicolo non indicato.'))
  return getJson<GuidaPraticaResponse>(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/guida-pratica`, emptyGuidaPraticaResponse())
}

export function getCodiceGuidaPratica(codice: string): Promise<GuidaPraticaResponse> {
  if (!codice) return Promise.resolve(emptyGuidaPraticaResponse('Codice materia non indicato.'))
  return getJson<GuidaPraticaResponse>(`/api/v1/ui/guida-pratica/${encodeURIComponent(codice)}`, emptyGuidaPraticaResponse())
}
