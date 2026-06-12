import { apiJson, apiPostJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type RedazioneAttiRecord = {
  id: string
  title: string
  subtitle: string
  meta: string
  stateLabel: string
  stateTone: AdminTone
  href: string
}

export type RedazioneAttiPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: RedazioneAttiRecord[]
  actions: AdminAction[]
  forms: []
  warnings: AdminWarning[]
  summary: string
  production: RedazioneProduction
}

export type RedazioneField = {
  name: string
  label: string
  type: string
  required: boolean
  value: string
  options: Array<{ value: string; label: string }>
}

export type RedazioneModel = {
  code: string
  title: string
  area: string
  summary: string
  fields: RedazioneField[]
}

export type RedazioneProduction = {
  defaultModelCode: string
  models: RedazioneModel[]
  endpoint: string
}

export type RedazioneProduceResult = {
  ok: boolean
  title: string
  preview: string
  errors: Record<string, string>
  warnings: string[]
}

export const emptyRedazioneAttiPage: RedazioneAttiPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  records: [],
  actions: [],
  forms: [],
  warnings: [],
  summary: '',
  production: { defaultModelCode: '', models: [], endpoint: '/api/v1/ui/redazione-atti/produci' },
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

function tone(value: unknown): AdminTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as AdminTone
    : 'neutral'
}

function safeHref(value: unknown, fallback = ''): string {
  const href = text(value)
  return href.startsWith('/') && href !== '#' ? href : fallback
}

function normaliseMetric(input: unknown): AdminMetric {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(input: unknown): AdminSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'Distribuzione',
    items: list(item.items).map((entryInput) => {
      const entry = asRecord(entryInput)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: display(entry.label) || 'Voce',
        value: scalar(entry.value),
        note: display(entry.note),
        tone: tone(entry.tone),
      }
    }),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(input: unknown): AdminAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: safeHref(item.href, '/redazione-atti'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(input: unknown): AdminWarning {
  const item = asRecord(input)
  return {
    code: display(item.code) || 'warning',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseRecord(input: unknown): RedazioneAttiRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'record',
    title: display(item.title) || 'Voce operativa',
    subtitle: display(item.subtitle),
    meta: display(item.meta),
    stateLabel: display(item.stateLabel),
    stateTone: tone(item.stateTone),
    href: safeHref(item.href, '/redazione-atti'),
  }
}

function normaliseField(input: unknown): RedazioneField {
  const item = asRecord(input)
  return {
    name: text(item.name) || 'campo',
    label: display(item.label) || 'Campo',
    type: text(item.type) || 'text',
    required: item.required === true,
    value: text(item.value),
    options: list(item.options).map((option) => {
      const row = asRecord(option)
      return { value: text(row.value), label: display(row.label) || text(row.value) }
    }),
  }
}

function normaliseProduction(input: unknown): RedazioneProduction {
  const item = asRecord(input)
  const models = list(item.models).map((modelInput) => {
    const model = asRecord(modelInput)
    return {
      code: text(model.code),
      title: display(model.title) || text(model.code),
      area: display(model.area),
      summary: display(model.summary),
      fields: list(model.fields).map(normaliseField).filter((field) => field.name),
    }
  }).filter((model) => model.code)
  return {
    defaultModelCode: text(item.defaultModelCode ?? item.default_model_code) || models[0]?.code || '',
    models,
    endpoint: safeHref(item.endpoint, '/api/v1/ui/redazione-atti/produci'),
  }
}

function normalisePage(input: unknown): RedazioneAttiPageData {
  const page = asRecord(input)
  const contracts = asRecord(page.contracts)
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'none',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
    summary: display(page.summary),
    production: normaliseProduction(page.production),
  }
}

export async function getRedazioneAttiPage(): Promise<RedazioneAttiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/redazione-atti', emptyRedazioneAttiPage)
  return normalisePage(payload)
}

export async function produceRedazioneAtto(endpoint: string, modelCode: string, values: Record<string, string>): Promise<RedazioneProduceResult> {
  const payload = await apiPostJson<Record<string, unknown>>(
    endpoint || '/api/v1/ui/redazione-atti/produci',
    { modelCode, values },
    { ok: false, errors: { generale: 'Produzione non completata.' } },
  )
  return {
    ok: payload.ok === true,
    title: display(payload.title) || 'Anteprima atto',
    preview: text(payload.preview),
    errors: asRecord(payload.errors) as Record<string, string>,
    warnings: list(payload.warnings).map((item) => display(item)).filter(Boolean),
  }
}

// ---------------------------------------------------------------------------
// Flusso guidato: cliente -> fascicolo -> tipo atto -> anteprima campi -> editor
// ---------------------------------------------------------------------------

export type RedazioneCliente = {
  id: string
  label: string
  tipo: string
  codiceFiscale: string
  fascicoli: number
}

export type RedazioneFascicolo = {
  id: string
  numero: string
  titolo: string
  materia: string
  areaPratica: string
  oggetto: string
  ufficio: string
  rg: string
  stato: string
  valoreCausa: number
  prossimaUdienza: string
  controparte: string
}

export type RedazioneCampoTracciato = {
  etichetta: string
  valore: string
  mancante: boolean
}

export type RedazioneSchedaParte = {
  id: string
  ruolo: string
  personaGiuridica: boolean
  denominazione: RedazioneCampoTracciato
  codiceFiscale: RedazioneCampoTracciato
  pec: RedazioneCampoTracciato
}

export type RedazioneSuggerimento = {
  code: string
  name: string
  area: string
  areaLabel: string
  score: number
  motivi: string[]
}

export type RedazioneCatalogoArea = {
  area: string
  label: string
  modelli: Array<{ code: string; name: string }>
}

export type RedazioneContesto = {
  ok: boolean
  errore: string
  fascicolo: Record<string, RedazioneCampoTracciato>
  cliente: RedazioneSchedaParte | null
  controparti: RedazioneSchedaParte[]
  difensori: RedazioneSchedaParte[]
  allegati: Array<{ id: string; nome: string; tipo: string }>
  contributoUnificato: { disponibile: boolean; totale: number | null; descrizione: string; fonte: string }
  condizioniAttive: string[]
  suggerimenti: RedazioneSuggerimento[]
  catalogo: RedazioneCatalogoArea[]
}

export type RedazioneCampoAnteprima = {
  name: string
  label: string
  type: string
  value: string
  fonte: string
  motivo?: string
}

export type RedazioneRiferimentoNormativo = {
  id: string
  riferimento: string
  fonte: string
  fonteLabel: string
  articolo: string
  rubrica: string
  ambito: string
  motivo: string
  url: string
  selezionato: boolean
}

export type RedazioneAnteprima = {
  ok: boolean
  errore: string
  model: { code: string; name: string; area: string }
  campiTrovati: RedazioneCampoAnteprima[]
  campiMancanti: RedazioneCampoAnteprima[]
  riferimenti: RedazioneRiferimentoNormativo[]
  condizioniAttive: string[]
}

export type RedazioneGeneraEsito = {
  ok: boolean
  errore: string
  editorUrl: string
  documentId: string
  campiMancanti: RedazioneCampoAnteprima[]
  campiMarcati: string[]
  richiedeConfermaBozza: boolean
  richiedeConfermaAvvisi: boolean
}

function campoTracciato(input: unknown): RedazioneCampoTracciato {
  const item = asRecord(input)
  return {
    etichetta: display(item.etichetta) || 'Campo',
    valore: display(item.valore),
    mancante: item.mancante === true,
  }
}

function schedaParte(input: unknown): RedazioneSchedaParte {
  const item = asRecord(input)
  return {
    id: text(item.id),
    ruolo: display(item.ruolo),
    personaGiuridica: item.personaGiuridica === true,
    denominazione: campoTracciato(item.denominazione),
    codiceFiscale: campoTracciato(item.codiceFiscale),
    pec: campoTracciato(item.pec),
  }
}

function normaliseCampoAnteprima(input: unknown): RedazioneCampoAnteprima {
  const item = asRecord(input)
  return {
    name: text(item.name),
    label: display(item.label) || text(item.name),
    type: text(item.type) || 'text',
    value: typeof item.value === 'string' ? item.value : display(item.value),
    fonte: display(item.fonte),
    motivo: display(item.motivo),
  }
}

function normaliseRiferimenti(payload: Record<string, unknown>): RedazioneRiferimentoNormativo[] {
  const normativa = asRecord(payload.normativa)
  const blocchi: Array<[string, unknown[]]> = [
    ['processuale', list(normativa.processuali)],
    ['sostanziale', list(normativa.sostanziali)],
  ]
  const risultato: RedazioneRiferimentoNormativo[] = []
  for (const [ambito, voci] of blocchi) {
    for (const voce of voci) {
      const item = asRecord(voce)
      const id = text(item.id)
      if (!id) continue
      risultato.push({
        id,
        riferimento: display(item.riferimento) || `art. ${display(item.articolo)} ${display(item.fonte)}`,
        fonte: display(item.fonte),
        fonteLabel: display(item.fonte_label),
        articolo: display(item.articolo),
        rubrica: display(item.rubrica),
        ambito,
        motivo: display(item.motivo_contestuale) || display(item.motivo),
        url: text(item.url_fonte),
        selezionato: true,
      })
    }
  }
  return risultato
}

export async function getRedazioneClienti(): Promise<{ clienti: RedazioneCliente[]; errore: string }> {
  const payload = await apiJson<Record<string, unknown>>('/api/v1/ui/redazione-atti/clienti', { ok: false, clienti: [] })
  return {
    errore: payload.ok === true ? '' : display(payload.errore) || 'Clienti non disponibili.',
    clienti: list(payload.clienti).map((input) => {
      const item = asRecord(input)
      return {
        id: text(item.id),
        label: display(item.label) || text(item.id),
        tipo: display(item.tipo),
        codiceFiscale: display(item.codiceFiscale),
        fascicoli: typeof item.fascicoli === 'number' ? item.fascicoli : 0,
      }
    }).filter((item) => item.id),
  }
}

export async function getRedazioneFascicoli(clienteId: string): Promise<{ fascicoli: RedazioneFascicolo[]; errore: string }> {
  const payload = await apiJson<Record<string, unknown>>(
    `/api/v1/ui/redazione-atti/clienti/${encodeURIComponent(clienteId)}/fascicoli`,
    { ok: false, fascicoli: [] },
  )
  return {
    errore: payload.ok === true ? '' : display(payload.errore) || 'Fascicoli non disponibili.',
    fascicoli: list(payload.fascicoli).map((input) => {
      const item = asRecord(input)
      return {
        id: text(item.id),
        numero: display(item.numero),
        titolo: display(item.titolo),
        materia: display(item.materia),
        areaPratica: display(item.areaPratica),
        oggetto: display(item.oggetto),
        ufficio: display(item.ufficio),
        rg: display(item.rg),
        stato: display(item.stato),
        valoreCausa: typeof item.valoreCausa === 'number' ? item.valoreCausa : 0,
        prossimaUdienza: display(item.prossimaUdienza),
        controparte: display(item.controparte),
      }
    }).filter((item) => item.id),
  }
}

export async function getRedazioneContesto(fascicoloId: string, clienteId: string): Promise<RedazioneContesto> {
  const query = clienteId ? `?id_cliente=${encodeURIComponent(clienteId)}` : ''
  const payload = await apiJson<Record<string, unknown>>(
    `/api/v1/ui/redazione-atti/fascicoli/${encodeURIComponent(fascicoloId)}/contesto${query}`,
    { ok: false },
  )
  const contesto = asRecord(payload.contesto)
  const fascicoloRaw = asRecord(contesto.fascicolo)
  const fascicolo: Record<string, RedazioneCampoTracciato> = {}
  for (const [chiave, valore] of Object.entries(fascicoloRaw)) {
    if (chiave === 'id') continue
    fascicolo[chiave] = campoTracciato(valore)
  }
  const economia = asRecord(contesto.economia)
  const contributo = asRecord(economia.contributoUnificato)
  return {
    ok: payload.ok === true,
    errore: payload.ok === true ? '' : display(payload.errore) || 'Contesto non disponibile.',
    fascicolo,
    cliente: contesto.cliente ? schedaParte(contesto.cliente) : null,
    controparti: list(contesto.controparti).map(schedaParte),
    difensori: list(contesto.difensori).map(schedaParte),
    allegati: list(contesto.allegati).map((input) => {
      const item = asRecord(input)
      return { id: text(item.id), nome: display(item.nome), tipo: display(item.tipo) }
    }),
    contributoUnificato: {
      disponibile: contributo.disponibile === true,
      totale: typeof contributo.totale === 'number' ? contributo.totale : null,
      descrizione: display(contributo.descrizione),
      fonte: display(contributo.fonte),
    },
    condizioniAttive: list(contesto.condizioniAttive).map((item) => display(item)).filter(Boolean),
    suggerimenti: list(payload.suggerimenti).map((input) => {
      const item = asRecord(input)
      return {
        code: text(item.code),
        name: display(item.name) || text(item.code),
        area: display(item.area),
        areaLabel: display(item.areaLabel),
        score: typeof item.score === 'number' ? item.score : 0,
        motivi: list(item.motivi).map((motivo) => display(motivo)).filter(Boolean),
      }
    }).filter((item) => item.code),
    catalogo: list(payload.catalogo).map((input) => {
      const item = asRecord(input)
      return {
        area: text(item.area),
        label: display(item.label) || text(item.area),
        modelli: list(item.modelli).map((modello) => {
          const riga = asRecord(modello)
          return { code: text(riga.code), name: display(riga.name) || text(riga.code) }
        }).filter((modello) => modello.code),
      }
    }).filter((item) => item.modelli.length > 0),
  }
}

export async function getRedazioneAnteprima(modelCode: string, fascicoloId: string, clienteId: string): Promise<RedazioneAnteprima> {
  const params = new URLSearchParams({ id_fascicolo: fascicoloId })
  if (clienteId) params.set('id_cliente', clienteId)
  const payload = await apiJson<Record<string, unknown>>(
    `/api/v1/ui/redazione-atti/anteprima/${encodeURIComponent(modelCode)}?${params.toString()}`,
    { ok: false },
  )
  const model = asRecord(payload.model)
  return {
    ok: payload.ok === true,
    errore: payload.ok === true ? '' : display(payload.errore) || 'Anteprima non disponibile.',
    model: { code: text(model.code), name: display(model.name), area: display(model.area) },
    campiTrovati: list(payload.campiTrovati).map(normaliseCampoAnteprima).filter((item) => item.name),
    campiMancanti: list(payload.campiMancanti).map(normaliseCampoAnteprima).filter((item) => item.name),
    riferimenti: normaliseRiferimenti(payload),
    condizioniAttive: list(payload.condizioniAttive).map((item) => display(item)).filter(Boolean),
  }
}

export async function generaRedazioneAtto(input: {
  modelCode: string
  fascicoloId: string
  clienteId: string
  valori: Record<string, string>
  riferimenti: Array<{ ambito: string; riferimento: string; rubrica: string; motivo: string }>
  confermaBozza: boolean
  confermaAvvisi: boolean
}): Promise<RedazioneGeneraEsito> {
  const payload = await apiPostJson<Record<string, unknown>>(
    '/api/v1/ui/redazione-atti/genera',
    {
      modelCode: input.modelCode,
      idFascicolo: input.fascicoloId,
      idCliente: input.clienteId,
      valori: input.valori,
      riferimenti: input.riferimenti,
      confermaBozza: input.confermaBozza,
      confermaAvvisi: input.confermaAvvisi,
    },
    { ok: false, errore: 'Generazione non completata.' },
  )
  return {
    ok: payload.ok === true,
    errore: display(payload.errore),
    editorUrl: text(payload.editorUrl),
    documentId: text(payload.documentId),
    campiMancanti: list(payload.campiMancanti).map(normaliseCampoAnteprima).filter((item) => item.name),
    campiMarcati: list(payload.campiMarcati).map((item) => display(item)).filter(Boolean),
    richiedeConfermaBozza: payload.richiedeConfermaBozza === true,
    richiedeConfermaAvvisi: payload.richiedeConfermaAvvisi === true,
  }
}
