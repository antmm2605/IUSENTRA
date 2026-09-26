import { apiJson, apiPostJson } from './lib/apiClient'

export type StudioTemplateSummary = {
  id: string
  title: string
  category: string
  area: string
  branch: string
  notes: string
  builtin: boolean
  keywords: string[]
  updatedAt: string
  useHref: string
  editHref: string
  detailHref: string
  cloneAction: string
  deleteAction: string
  pdfAction: string
}

export type StudioTemplateField = {
  name: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'date' | 'select' | 'email'
  placeholder: string
  rows: number
  options: { value: string; label: string }[]
  required: boolean
}

export type StudioTemplateSection = { title: string; fields: StudioTemplateField[] }

export type StudioTemplateDetail = StudioTemplateSummary & {
  sections: StudioTemplateSection[]
  body: string
  related: { id: string; title: string; href: string }[]
  compilerHref: string
}

export type StudioTemplateForm = {
  ok: boolean
  message: string
  categories: string[]
  values: { titolo: string; categoria: string; corpo: string; note: string }
  item: StudioTemplateSummary | null
  variableGroups: { title: string; variables: string[] }[]
  importAction: string
}

export type StudioTemplateUse = {
  ok: boolean
  message: string
  item: StudioTemplateSummary | null
  sections: StudioTemplateSection[]
  values: Record<string, string>
  clients: { id: string; label: string }[]
  matters: { id: string; label: string }[]
  selectedClientId: string
  selectedMatterId: string
}

export type StudioTemplateResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item: StudioTemplateSummary | null
  text: string
  html: string
  pdfAction: string
}

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

function href(value: unknown): string {
  const raw = text(value)
  return raw.startsWith('/') && !raw.startsWith('//') ? raw : ''
}

function summary(raw: unknown): StudioTemplateSummary | null {
  const item = obj(raw)
  if (!text(item.id)) return null
  return {
    id: text(item.id),
    title: text(item.title),
    category: text(item.category),
    area: text(item.area),
    branch: text(item.branch),
    notes: text(item.notes),
    builtin: item.builtin === true,
    keywords: list(item.keywords).map(text).filter(Boolean),
    updatedAt: text(item.updatedAt),
    useHref: href(item.useHref),
    editHref: href(item.editHref),
    detailHref: href(item.detailHref),
    cloneAction: href(item.cloneAction),
    deleteAction: href(item.deleteAction),
    pdfAction: href(item.pdfAction),
  }
}

function sections(value: unknown): StudioTemplateSection[] {
  return list(value).map((raw) => {
    const section = obj(raw)
    return {
      title: text(section.title) || 'Contenuto',
      fields: list(section.fields).map((fieldRaw) => {
        const field = obj(fieldRaw)
        const tipo = text(field.type)
        return {
          name: text(field.name),
          label: text(field.label) || text(field.name),
          type: (['text', 'textarea', 'number', 'date', 'select', 'email'].includes(tipo) ? tipo : 'text') as StudioTemplateField['type'],
          placeholder: text(field.placeholder),
          rows: Number(field.rows) || 1,
          options: list(field.options).map((opt) => ({ value: text(obj(opt).value), label: text(obj(opt).label) || text(obj(opt).value) })),
          required: field.required === true,
        }
      }).filter((field) => field.name),
    }
  })
}

const BASE = '/api/v1/ui/template-atti/studio'

export async function getStudioTemplateDetail(id: string): Promise<{ ok: boolean; message: string; item: StudioTemplateDetail | null }> {
  const payload = obj(await apiJson<unknown>(`${BASE}/${encodeURIComponent(id)}`, { ok: false }))
  const base = summary(payload.item)
  const raw = obj(payload.item)
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    item: base ? {
      ...base,
      sections: sections(raw.sections),
      body: text(raw.body),
      related: list(raw.related).map((r) => ({ id: text(obj(r).id), title: text(obj(r).title), href: href(obj(r).href) })).filter((r) => r.href),
      compilerHref: href(raw.compilerHref),
    } : null,
  }
}

export async function getStudioTemplateForm(id = ''): Promise<StudioTemplateForm> {
  const url = id ? `${BASE}/${encodeURIComponent(id)}/modifica` : `${BASE}/nuovo`
  const payload = obj(await apiJson<unknown>(url, { ok: false }))
  const values = obj(payload.values)
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    categories: list(payload.categories).map(text).filter(Boolean),
    values: { titolo: text(values.titolo), categoria: text(values.categoria), corpo: text(values.corpo), note: text(values.note) },
    item: summary(payload.item),
    variableGroups: list(payload.variableGroups).map((g) => ({ title: text(obj(g).title), variables: list(obj(g).variables).map(text).filter(Boolean) })),
    importAction: href(payload.importAction),
  }
}

function result(raw: unknown): StudioTemplateResult {
  const payload = obj(raw)
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    errors: Object.fromEntries(Object.entries(obj(payload.errors)).map(([k, v]) => [k, text(v)])),
    item: summary(payload.item),
    text: text(payload.text),
    html: text(payload.html),
    pdfAction: href(payload.pdfAction),
  }
}

export async function saveStudioTemplate(values: StudioTemplateForm['values'], id = ''): Promise<StudioTemplateResult> {
  const url = id ? `${BASE}/${encodeURIComponent(id)}/modifica` : `${BASE}/nuovo`
  return result(await apiPostJson<unknown>(url, values, { ok: false, message: 'Salvataggio non riuscito.' }))
}

export async function getStudioTemplateUse(id: string, clientId = '', matterId = ''): Promise<StudioTemplateUse> {
  const params = new URLSearchParams()
  if (clientId) params.set('id_cliente', clientId)
  if (matterId) params.set('id_fascicolo', matterId)
  const query = params.toString()
  const payload = obj(await apiJson<unknown>(`${BASE}/${encodeURIComponent(id)}/usa${query ? `?${query}` : ''}`, { ok: false }))
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    item: summary(payload.item),
    sections: sections(payload.sections),
    values: Object.fromEntries(Object.entries(obj(payload.values)).map(([k, v]) => [k, text(v)])),
    clients: list(payload.clients).map((c) => ({ id: text(obj(c).id), label: text(obj(c).label) })).filter((c) => c.id),
    matters: list(payload.matters).map((m) => ({ id: text(obj(m).id), label: text(obj(m).label) })).filter((m) => m.id),
    selectedClientId: text(payload.selectedClientId),
    selectedMatterId: text(payload.selectedMatterId),
  }
}

export async function generateStudioTemplate(id: string, body: { clientId: string; matterId: string; fields: Record<string, string> }): Promise<StudioTemplateResult> {
  return result(await apiPostJson<unknown>(`${BASE}/${encodeURIComponent(id)}/genera`, body, { ok: false, message: 'Generazione non riuscita.' }))
}

export type StudioTemplateRoute =
  | { mode: 'nuovo'; id: '' }
  | { mode: 'scheda' | 'modifica' | 'usa'; id: string }

export function studioTemplateRoute(pathname: string): StudioTemplateRoute | null {
  const path = pathname.replace(/\/+$/, '').toLowerCase()
  const original = pathname.replace(/\/+$/, '')
  if (path === '/template-atti/nuovo') return { mode: 'nuovo', id: '' }
  const scheda = original.match(/^\/template-atti\/scheda\/([^/]+)$/i)
  if (scheda) return { mode: 'scheda', id: decodeURIComponent(scheda[1]) }
  const azione = original.match(/^\/template-atti\/([^/]+)\/(modifica|usa)$/i)
  if (azione && !['compila', 'catalogo', 'editor'].includes(azione[1].toLowerCase())) {
    return { mode: azione[2].toLowerCase() as 'modifica' | 'usa', id: decodeURIComponent(azione[1]) }
  }
  return null
}

export type ImportedDocument = { ok: boolean; kind: 'html' | 'testo'; content: string; message: string }

export async function importDocumentForTemplate(action: string, file: File): Promise<ImportedDocument> {
  const body = new FormData()
  body.append('file', file)
  const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
  try {
    const response = await fetch(action, { method: 'POST', body, credentials: 'same-origin', headers: token ? { 'X-CSRF-Token': token } : {} })
    const payload = obj(await response.json())
    if (payload.ok !== true) return { ok: false, kind: 'testo', content: '', message: text(payload.errore) || 'Documento non importato.' }
    const tipo = text(payload.tipo)
    return { ok: true, kind: tipo === 'testo' ? 'testo' : 'html', content: text(payload.contenuto), message: text(payload.note) }
  } catch {
    return { ok: false, kind: 'testo', content: '', message: 'Documento non importato: riprova.' }
  }
}

export async function runStudioTemplateAction(endpoint: string): Promise<{ ok: boolean; message: string; redirectHref: string }> {
  const payload = obj(await apiPostJson<unknown>(endpoint, {}, { ok: false, message: 'Operazione non riuscita.' }))
  return { ok: payload.ok === true, message: text(payload.message), redirectHref: href(payload.redirect_href) }
}
