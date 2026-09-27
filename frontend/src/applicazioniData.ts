import { apiJson, apiPostJson } from './lib/apiClient'

type Raw = Record<string, unknown>

function obj(value: unknown): Raw {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Raw) : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

function internal(value: unknown): string {
  const raw = text(value)
  return raw.startsWith('/') && !raw.startsWith('//') ? raw : ''
}

function stringMap(value: unknown): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [key, item] of Object.entries(obj(value))) result[key] = text(item)
  return result
}

/** `/applicazioni/<id>` oppure `/applicazioni/?app=<id>`; stringa vuota per il catalogo. */
export function applicazioneDaUrl(pathname: string, search: string): string {
  const path = pathname.replace(/\/+$/, '')
  const match = path.match(/^\/applicazioni\/([^/]+)$/i)
  if (match) return decodeURIComponent(match[1])
  const params = new URLSearchParams(search)
  return (params.get('app') || params.get('app_id') || '').trim()
}

export type TipoApplicazione = 'utility' | 'lookup' | 'tool' | 'collegamento' | 'non_disponibile'

export type CampoApplicazione = {
  name: string
  label: string
  kind: 'text' | 'number' | 'date' | 'select'
  options: Array<{ value: string; label: string }>
  required: boolean
  value: string
  step: string
}

export type Applicazione = {
  id: string
  title: string
  description: string
  section: string
  status: string
  type: TipoApplicazione
  basis: string
  href: string
  form: { action: string; submitLabel: string; fields: CampoApplicazione[] } | null
  toolId: string
  preset: Record<string, string>
  prefill: Record<string, string>
  fascicolo: { id: string; label: string } | null
  unavailable: { reason: string; label: string; href: string } | null
}

export type SchedaApplicazione = { ok: boolean; message: string; item: Applicazione | null; warnings: string[] }

export type EsitoApplicazione = {
  ok: boolean
  message: string
  rows: Array<{ label: string; value: string; note: string }>
  notes: string[]
}

const TIPI: TipoApplicazione[] = ['utility', 'lookup', 'tool', 'collegamento', 'non_disponibile']
const KINDS: CampoApplicazione['kind'][] = ['text', 'number', 'date', 'select']

function campo(raw: unknown): CampoApplicazione {
  const item = obj(raw)
  const kind = text(item.kind) as CampoApplicazione['kind']
  return {
    name: text(item.name),
    label: text(item.label),
    kind: KINDS.includes(kind) ? kind : 'text',
    options: list(item.options).map((option) => ({ value: text(obj(option).value), label: text(obj(option).label) })),
    required: item.required === true,
    value: text(item.value),
    step: text(item.step),
  }
}

function applicazione(raw: unknown): Applicazione {
  const item = obj(raw)
  const form = item.form ? obj(item.form) : null
  const fascicolo = item.fascicolo ? obj(item.fascicolo) : null
  const unavailable = item.unavailable ? obj(item.unavailable) : null
  const type = text(item.type) as TipoApplicazione
  return {
    id: text(item.id),
    title: text(item.title),
    description: text(item.description),
    section: text(item.section),
    status: text(item.status),
    type: TIPI.includes(type) ? type : 'collegamento',
    basis: text(item.basis),
    href: internal(item.href),
    form: form ? { action: internal(form.action), submitLabel: text(form.submitLabel) || 'Calcola', fields: list(form.fields).map(campo) } : null,
    toolId: text(item.toolId),
    preset: stringMap(item.preset),
    prefill: stringMap(item.prefill),
    fascicolo: fascicolo ? { id: text(fascicolo.id), label: text(fascicolo.label) } : null,
    unavailable: unavailable ? { reason: text(unavailable.reason), label: text(unavailable.label), href: internal(unavailable.href) } : null,
  }
}

export async function getApplicazione(appId: string, idFascicolo = '', signal?: AbortSignal): Promise<SchedaApplicazione> {
  const query = idFascicolo ? `?id_fascicolo=${encodeURIComponent(idFascicolo)}` : ''
  const payload = obj(await apiJson<unknown>(
    `/api/v1/ui/applicazioni/${encodeURIComponent(appId)}${query}`,
    { ok: false, message: 'Funzione non trovata nel catalogo o momentaneamente non disponibile.' },
    { signal },
  ))
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    item: payload.ok === true ? applicazione(payload.item) : null,
    warnings: list(payload.warnings).map(text).filter(Boolean),
  }
}

export async function eseguiApplicazione(action: string, values: Record<string, string>, signal?: AbortSignal): Promise<EsitoApplicazione> {
  const payload = obj(await apiPostJson<unknown>(
    action,
    { values },
    { ok: false, message: 'Calcolo non riuscito. Controlla i dati e riprova.', rows: [], notes: [] },
    { signal },
  ))
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    rows: list(payload.rows).map((raw) => ({ label: text(obj(raw).label), value: text(obj(raw).value), note: text(obj(raw).note) })),
    notes: list(payload.notes).map(text).filter(Boolean),
  }
}

export type ContestoStrumento = {
  toolId: string
  preset: Record<string, string>
  prefill: Record<string, string>
  fascicolo: { id: string; label: string } | null
  warnings: string[]
}

/**
 * Preset della voce del catalogo (`?app=`) e campi ricavati dalla pratica
 * (`?id_fascicolo=`) per la pagina Strumenti forensi.
 */
export async function getContestoStrumento(appId: string, idFascicolo: string, signal?: AbortSignal): Promise<ContestoStrumento> {
  if (appId) {
    const scheda = await getApplicazione(appId, idFascicolo, signal)
    const item = scheda.item
    return {
      toolId: item?.type === 'tool' ? item.toolId : '',
      preset: item?.type === 'tool' ? item.preset : {},
      prefill: item?.prefill ?? {},
      fascicolo: item?.fascicolo ?? null,
      warnings: scheda.warnings,
    }
  }
  const payload = obj(await apiJson<unknown>(
    `/api/v1/ui/applicazioni/contesto-fascicolo?id_fascicolo=${encodeURIComponent(idFascicolo)}`,
    { ok: false, warnings: ['Dati della pratica non disponibili.'] },
    { signal },
  ))
  const fascicolo = payload.fascicolo ? obj(payload.fascicolo) : null
  return {
    toolId: '',
    preset: {},
    prefill: stringMap(payload.prefill),
    fascicolo: fascicolo ? { id: text(fascicolo.id), label: text(fascicolo.label) } : null,
    warnings: list(payload.warnings).map(text).filter(Boolean),
  }
}
