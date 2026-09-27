import { apiJson, apiPostJson } from './lib/apiClient'
import { submitFormJson } from './formSubmit'

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

function num(value: unknown): number {
  return Number(value) || 0
}

function internal(value: unknown): string {
  const raw = text(value)
  return raw.startsWith('/') && !raw.startsWith('//') ? raw : ''
}

export type ChecklistRoute =
  | { mode: 'catalogo' }
  | { mode: 'scheda'; templateId: string }
  | { mode: 'avvia' | 'completa'; matterId: string; templateId: string }
  | { mode: 'passo'; matterId: string; templateId: string; step: number }

export function checklistRoute(pathname: string): ChecklistRoute | null {
  const path = pathname.replace(/\/+$/, '')
  if (/^\/checklist$/i.test(path)) return { mode: 'catalogo' }
  const scheda = path.match(/^\/checklist\/([^/]+)$/i)
  if (scheda) return { mode: 'scheda', templateId: decodeURIComponent(scheda[1]) }
  const wizard = path.match(/^\/fascicoli\/([^/]+)\/wizard\/([^/]+)(?:\/(completa|step\/(\d+)))?$/i)
  if (!wizard) return null
  const matterId = decodeURIComponent(wizard[1])
  const templateId = decodeURIComponent(wizard[2])
  if (!wizard[3]) return { mode: 'avvia', matterId, templateId }
  if (wizard[3].toLowerCase() === 'completa') return { mode: 'completa', matterId, templateId }
  return { mode: 'passo', matterId, templateId, step: Number(wizard[4]) }
}

export type Canale = { code: string; label: string; note: string }

export type ChecklistTemplateSummary = {
  id: string
  name: string
  category: string
  area: string
  branch: string
  subbranch: string
  description: string
  channel: Canale
  requiredDocuments: number
  criticalChecks: number
  href: string
}

export type ChecklistCatalog = {
  ok: boolean
  areas: Array<{ name: string; count: number }>
  totals: { templates: number; areas: number; requiredDocuments: number; criticalChecks: number; catalogTemplates: number }
  catalog: Array<{
    name: string
    templates: number
    requiredDocuments: number
    criticalChecks: number
    branches: Array<{ name: string; subbranches: Array<{ name: string; templates: ChecklistTemplateSummary[] }> }>
  }>
}

export type ChecklistCheck = { text: string; critical: boolean; note: string }

export type ChecklistDetail = ChecklistTemplateSummary & {
  folderName: string
  context: { party: string; rg: string; date: string }
  documents: Array<{ number: number; fileName: string; description: string; required: boolean; note: string }>
  checks: ChecklistCheck[]
  generalNotes: string
  matter: { id: string; title: string; wizardHref: string } | null
}

export type WizardStep = {
  number: number
  fileName: string
  description: string
  required: boolean
  note: string
  status: 'done' | 'skipped' | 'pending'
  uploadName: string
  uploadNote: string
  document: { id: string; name: string; date: string; viewHref: string; downloadHref: string } | null
}

export type WizardData = {
  ok: boolean
  message: string
  matter: { id: string; title: string; rg: string; client: string; counterpart: string; office: string; href: string; uploadAction: string; depositHref: string; depositLabel: string }
  template: ChecklistTemplateSummary & { checks: ChecklistCheck[] }
  folderName: string
  steps: WizardStep[]
  nextStep: number | null
  complete: boolean
  missingRequired: number
  documentTypes: Array<{ value: string; label: string }>
  skipAction: string
  indexAction: string
}

function summary(raw: unknown): ChecklistTemplateSummary {
  const item = obj(raw)
  const channel = obj(item.channel)
  return {
    id: text(item.id),
    name: text(item.name),
    category: text(item.category),
    area: text(item.area),
    branch: text(item.branch),
    subbranch: text(item.subbranch),
    description: text(item.description),
    channel: { code: text(channel.code), label: text(channel.label), note: text(channel.note) },
    requiredDocuments: num(item.requiredDocuments),
    criticalChecks: num(item.criticalChecks),
    href: internal(item.href),
  }
}

function checks(value: unknown): ChecklistCheck[] {
  return list(value).map((raw) => ({ text: text(obj(raw).text), critical: obj(raw).critical === true, note: text(obj(raw).note) }))
}

export async function getChecklistCatalog(area = '', q = ''): Promise<ChecklistCatalog> {
  const params = new URLSearchParams()
  if (area) params.set('area', area)
  if (q) params.set('q', q)
  const query = params.toString()
  const payload = obj(await apiJson<unknown>(`/api/v1/ui/checklist${query ? `?${query}` : ''}`, { ok: false }))
  const totals = obj(payload.totals)
  return {
    ok: payload.ok === true,
    areas: list(payload.areas).map((raw) => ({ name: text(obj(raw).name), count: num(obj(raw).count) })),
    totals: {
      templates: num(totals.templates),
      areas: num(totals.areas),
      requiredDocuments: num(totals.requiredDocuments),
      criticalChecks: num(totals.criticalChecks),
      catalogTemplates: num(totals.catalogTemplates),
    },
    catalog: list(payload.catalog).map((rawArea) => {
      const area = obj(rawArea)
      return {
        name: text(area.name),
        templates: num(area.templates),
        requiredDocuments: num(area.requiredDocuments),
        criticalChecks: num(area.criticalChecks),
        branches: list(area.branches).map((rawBranch) => ({
          name: text(obj(rawBranch).name),
          subbranches: list(obj(rawBranch).subbranches).map((rawSub) => ({
            name: text(obj(rawSub).name),
            templates: list(obj(rawSub).templates).map(summary),
          })),
        })),
      }
    }),
  }
}

export async function getChecklistDetail(templateId: string, search: string): Promise<{ ok: boolean; message: string; item: ChecklistDetail | null }> {
  const allowed = new URLSearchParams()
  const current = new URLSearchParams(search)
  for (const key of ['id_fasc', 'parte', 'rg', 'data']) {
    const value = current.get(key)
    if (value) allowed.set(key, value)
  }
  const query = allowed.toString()
  const payload = obj(await apiJson<unknown>(`/api/v1/ui/checklist/${encodeURIComponent(templateId)}${query ? `?${query}` : ''}`, { ok: false }))
  const item = obj(payload.item)
  const context = obj(item.context)
  const matter = item.matter ? obj(item.matter) : null
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    item: payload.ok === true ? {
      ...summary(item),
      folderName: text(item.folderName),
      context: { party: text(context.party), rg: text(context.rg), date: text(context.date) },
      documents: list(item.documents).map((raw) => {
        const doc = obj(raw)
        return { number: num(doc.number), fileName: text(doc.fileName), description: text(doc.description), required: doc.required === true, note: text(doc.note) }
      }),
      checks: checks(item.checks),
      generalNotes: text(item.generalNotes),
      matter: matter ? { id: text(matter.id), title: text(matter.title), wizardHref: internal(matter.wizardHref) } : null,
    } : null,
  }
}

function wizard(raw: unknown): WizardData {
  const payload = obj(raw)
  const matter = obj(payload.matter)
  const template = obj(payload.template)
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    matter: {
      id: text(matter.id),
      title: text(matter.title),
      rg: text(matter.rg),
      client: text(matter.client),
      counterpart: text(matter.counterpart),
      office: text(matter.office),
      href: internal(matter.href),
      uploadAction: internal(matter.uploadAction),
      depositHref: internal(matter.depositHref),
      depositLabel: text(matter.depositLabel) || 'Prepara il deposito',
    },
    template: { ...summary(template), checks: checks(template.checks) },
    folderName: text(payload.folderName),
    steps: list(payload.steps).map((rawStep) => {
      const step = obj(rawStep)
      const document = step.document ? obj(step.document) : null
      const status = text(step.status)
      return {
        number: num(step.number),
        fileName: text(step.fileName),
        description: text(step.description),
        required: step.required === true,
        note: text(step.note),
        status: (status === 'done' || status === 'skipped' ? status : 'pending') as WizardStep['status'],
        uploadName: text(step.uploadName),
        uploadNote: text(step.uploadNote),
        document: document ? { id: text(document.id), name: text(document.name), date: text(document.date), viewHref: internal(document.viewHref), downloadHref: internal(document.downloadHref) } : null,
      }
    }),
    nextStep: payload.nextStep === null || payload.nextStep === undefined ? null : num(payload.nextStep),
    complete: payload.complete === true,
    missingRequired: num(payload.missingRequired),
    documentTypes: list(payload.documentTypes).map((rawType) => ({ value: text(obj(rawType).value), label: text(obj(rawType).label) })),
    skipAction: internal(payload.skipAction),
    indexAction: internal(payload.indexAction),
  }
}

export async function getWizard(matterId: string, templateId: string): Promise<WizardData> {
  return wizard(await apiJson<unknown>(`/api/v1/ui/checklist/percorso/${encodeURIComponent(matterId)}/${encodeURIComponent(templateId)}`, { ok: false }))
}

export async function skipWizardStep(action: string, step: number): Promise<WizardData> {
  return wizard(await apiPostJson<unknown>(action, { numero: step }, { ok: false, message: 'Passo non saltato.' }))
}

export async function uploadWizardDocument(
  action: string,
  step: WizardStep,
  file: File,
  fields: { documentType: string; documentDate: string; signed: boolean; note: string },
): Promise<{ ok: boolean; message: string }> {
  // Il file prende il nome previsto dalla checklist e la nota del passo: la via
  // di caricamento è quella comune dei documenti del fascicolo.
  const extension = (file.name.match(/\.[A-Za-z0-9]{1,8}$/) || ['.pdf'])[0]
  const renamed = new File([file], `${step.uploadName}${extension}`, { type: file.type })
  const form = new FormData()
  form.append('file', renamed)
  form.append('note', [step.uploadNote, fields.note.trim()].filter(Boolean).join(' '))
  if (fields.documentType) {
    form.append('tipo_doc', fields.documentType)
    form.append('classificazione_modalita', 'manuale')
  }
  if (fields.documentDate) form.append('data_documento', fields.documentDate)
  if (fields.signed) form.append('firmato', '1')
  const result = await submitFormJson(action, form)
  return { ok: result.ok === true, message: text(result.message) }
}

export async function createWizardIndex(indexAction: string): Promise<{ ok: boolean; message: string }> {
  const payload = obj(await apiPostJson<unknown>(indexAction, {}, { ok: false, message: 'Indice non preparato.' }))
  if (payload.ok !== true) return { ok: false, message: text(payload.message) || 'Indice non preparato.' }
  const action = internal(payload.uploadAction)
  const form = new FormData()
  form.append('file', new File([text(payload.text)], text(payload.fileName) || 'Indice.txt', { type: 'text/plain' }))
  form.append('note', text(payload.note))
  form.append('tipo_doc', 'ALTRO')
  form.append('classificazione_modalita', 'manuale')
  const result = await submitFormJson(action, form)
  return { ok: result.ok === true, message: result.ok ? `Indice «${text(payload.fileName)}» aggiunto al fascicolo.` : text(result.message) || 'Indice non salvato.' }
}
