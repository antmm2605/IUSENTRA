import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type TemplateVariableMeta = {
  name: string
  label: string
  kind: string
  source: string
}

export type TemplateAttiRecord = {
  id: string
  kind: string
  title: string
  subtitle: string
  description: string
  category: string
  matter: string
  area: string
  branch: string
  channel: string
  portal: string
  stateLabel: string
  stateTone: AdminTone
  complianceLabel: string
  cartabiaState: string
  cartabiaLabel: string
  processArea: string
  requiresLawyerReview: boolean
  prefillStatus: string
  prefillAvailable: number
  prefillMissing: number
  blockingChecks: string[]
  recommendedChecks: string[]
  dataSources: string[]
  updatedAt: string
  tags: string[]
  requiredVariables: TemplateVariableMeta[]
  href: string
  primaryActionLabel: string
  detailHref: string
}

export type StudioStampPreview = {
  lines: Array<{ text: string; size: number; bold: boolean }>
  text: string
  scope: Record<string, boolean>
}

export type TemplateAttiPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: TemplateAttiRecord[]
  studioStamp: StudioStampPreview
  actions: AdminAction[]
  forms: []
  warnings: AdminWarning[]
}

export type TemplateCompilerOption = {
  value: string
  label: string
  clienteId?: string
}

export type TemplateCompilerNote = {
  tone: 'found' | 'missing' | 'error'
  text: string
}

export type TemplateGuidePreviewStep = {
  id: string
  label: string
  state: 'done' | 'active' | 'pending'
}

export type TemplateGuidePreviewCheck = {
  label: string
  value: string
  tone: AdminTone
}

export type TemplateEditorLayout = {
  fontSize: number
  lineHeight: number
  pageScale: number
}

export type TemplateGuidePreview = {
  enabled: boolean
  eyebrow: string
  title: string
  subtitle: string
  badge: string
  guideCode: string
  guideTitle: string
  fascicoloHref: string
  uploadEndpoint: string
  importEndpoint: string
  previewPdfHref: string
  wordHref: string
  saveEndpoint: string
  renderEndpoint: string
  importLabel: string
  previewLabel: string
  saveLabel: string
  initialText: string
  reason: string
  steps: TemplateGuidePreviewStep[]
  template: {
    code: string
    name: string
    reason: string
    autoLoad: boolean
  }
  import: {
    enabled: boolean
    formats: string
    note: string
  }
  layoutChecks: TemplateGuidePreviewCheck[]
  editorLayout: TemplateEditorLayout
}

export type TemplateNormativeReference = {
  id: string
  title: string
  sourceId: string
  sourceTitle: string
  article: string
  officialUrl: string
  reasonForApplication: string
  verificationStatus: string
  confidence: number
}

export type TemplateNormativeSource = {
  id: string
  title: string
  officialUrl: string
  verificationStatus: string
  lastVerifiedAt: string
}

export type TemplateCompilerField = {
  name: string
  label: string
  type: string
  placeholder: string
  required: boolean
  value: string
  options: TemplateCompilerOption[]
  error: string
  note?: TemplateCompilerNote
  warnings: string[]
}

export type TemplateCompilerData = {
  ok: boolean
  message: string
  model: {
    code: string
    name: string
    area: string
  }
  summary: string
  formAction: string
  catalogHref: string
  submitLabel: string
  selectors: {
    clienti: TemplateCompilerOption[]
    fascicoli: TemplateCompilerOption[]
    selectedClienteId: string
    selectedFascicoloId: string
    selectedClienteLabel: string
    selectedFascicoloLabel: string
  }
  hidden: Record<string, string>
  baseFields: TemplateCompilerField[]
  extraFields: TemplateCompilerField[]
  stamp: StudioStampPreview
  compliance: {
    available: boolean
    state: string
    ready: boolean
    requiresReview: boolean
    processArea: string
    profile: string
    rulesetVersion: string
    sourceLabel: string
    evidenceCount: number
    overallState: string
    canGenerateFinalDraft: boolean
    canGenerateWorkingDraft: boolean
    canOpenEditor: boolean
    reliabilityScore: { value: number; label: string; capsApplied: string[]; factors: string[] }
    layoutProfile: Record<string, unknown>
    stampPolicy: Record<string, unknown>
    missingFields: string[]
    missingFieldRows: Array<Record<string, unknown>>
    missingDocuments: Array<Record<string, unknown>>
    blocking: string[]
    recommended: string[]
    normativeReferences: TemplateNormativeReference[]
    sources: TemplateNormativeSource[]
    nextActions: string[]
    reasonedExplanation: string
    procedibility: string[]
    deadlines: string[]
    cartabiaControls: string[]
    editorialControls: string[]
    depositControls: string[]
    validationRules: string[]
    warnings: string[]
  }
  checks: {
    blocking: string[]
    recommended: string[]
  }
  attachments: string[]
  sections: Array<{ label: string; state: string }>
  guidePreview: TemplateGuidePreview
}

export const emptyTemplateAttiPage: TemplateAttiPageData = {
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
  studioStamp: { lines: [], text: '', scope: {} },
  actions: [],
  forms: [],
  warnings: [],
}

export const emptyTemplateCompilerPage: TemplateCompilerData = {
  ok: false,
  message: '',
  model: { code: '', name: '', area: '' },
  summary: '',
  formAction: '',
  catalogHref: '/template-atti/catalogo',
  submitLabel: "Crea bozza dell'atto",
  selectors: {
    clienti: [],
    fascicoli: [],
    selectedClienteId: '',
    selectedFascicoloId: '',
    selectedClienteLabel: '',
    selectedFascicoloLabel: '',
  },
  hidden: {},
  baseFields: [],
  extraFields: [],
  stamp: { lines: [], text: '', scope: {} },
  compliance: {
    available: false,
    state: '',
    ready: false,
    requiresReview: true,
    processArea: '',
    profile: '',
    rulesetVersion: '',
    sourceLabel: '',
    evidenceCount: 0,
    overallState: '',
    canGenerateFinalDraft: false,
    canGenerateWorkingDraft: false,
    canOpenEditor: false,
    reliabilityScore: { value: 0, label: '', capsApplied: [], factors: [] },
    layoutProfile: {},
    stampPolicy: {},
    missingFields: [],
    missingFieldRows: [],
    missingDocuments: [],
    blocking: [],
    recommended: [],
    normativeReferences: [],
    sources: [],
    nextActions: [],
    reasonedExplanation: '',
    procedibility: [],
    deadlines: [],
    cartabiaControls: [],
    editorialControls: [],
    depositControls: [],
    validationRules: [],
    warnings: [],
  },
  checks: { blocking: [], recommended: [] },
  attachments: [],
  sections: [],
  guidePreview: {
    enabled: false,
    eyebrow: 'Anteprima modifica',
    title: 'Editor documento con impaginazione modello',
    subtitle: '',
    badge: 'template filtrato dalla guida',
    guideCode: '',
    guideTitle: '',
    fascicoloHref: '',
    uploadEndpoint: '',
    importEndpoint: '',
    previewPdfHref: '',
    wordHref: '',
    saveEndpoint: '',
    renderEndpoint: '',
    importLabel: 'Importa PDF/Word',
    previewLabel: 'Anteprima PDF',
    saveLabel: 'Salva nel fascicolo',
    initialText: '',
    reason: '',
    steps: [],
    template: { code: '', name: '', reason: '', autoLoad: false },
    import: { enabled: false, formats: 'PDF/DOCX', note: '' },
    layoutChecks: [],
    editorLayout: { fontSize: 15, lineHeight: 1.72, pageScale: 100 },
  },
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

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return value.trim()
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
    label: text(item.label) || 'Metrica',
    value: scalar(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(input: unknown): AdminSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: text(item.title) || 'Sezione',
    kind: text(item.kind) || 'distribution',
    items: list(item.items).map((entryInput) => {
      const entry = asRecord(entryInput)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: text(entry.label) || 'Voce',
        value: scalar(entry.value),
        note: text(entry.note),
        tone: tone(entry.tone),
      }
    }),
    emptyMessage: text(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(input: unknown): AdminAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: safeHref(item.href, '/template-atti'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(input: unknown): AdminWarning {
  const item = asRecord(input)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso tecnico disponibile.',
  }
}

function normaliseVariable(input: unknown): TemplateVariableMeta {
  const item = asRecord(input)
  return {
    name: text(item.name) || text(item.label) || 'variabile',
    label: text(item.label) || text(item.name) || 'Variabile',
    kind: text(item.kind) || 'metadato',
    source: text(item.source) || 'metadata',
  }
}

function normaliseRecord(input: unknown): TemplateAttiRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'template',
    kind: text(item.kind) || 'catalogo',
    title: text(item.title) || 'Template',
    subtitle: text(item.subtitle),
    description: text(item.description),
    category: text(item.category),
    matter: text(item.matter),
    area: text(item.area),
    branch: text(item.branch),
    channel: text(item.channel),
    portal: text(item.portal),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
    complianceLabel: text(item.complianceLabel),
    cartabiaState: text(item.cartabiaState),
    cartabiaLabel: text(item.cartabiaLabel),
    processArea: text(item.processArea),
    requiresLawyerReview: item.requiresLawyerReview === true,
    prefillStatus: text(item.prefillStatus),
    prefillAvailable: Number(item.prefillAvailable || 0),
    prefillMissing: Number(item.prefillMissing || 0),
    blockingChecks: list(item.blockingChecks).map((value) => text(value)).filter(Boolean),
    recommendedChecks: list(item.recommendedChecks).map((value) => text(value)).filter(Boolean),
    dataSources: list(item.dataSources).map((value) => text(value)).filter(Boolean),
    updatedAt: text(item.updatedAt),
    tags: list(item.tags).map((tag) => text(tag)).filter(Boolean),
    requiredVariables: list(item.requiredVariables).map(normaliseVariable).filter((variable) => variable.name),
    href: safeHref(item.href, '/template-atti/catalogo'),
    primaryActionLabel: text(item.primaryActionLabel) || 'Compila con dati IUSENTRA',
    detailHref: safeHref(item.detailHref, ''),
  }
}

function normaliseStudioStamp(input: unknown): StudioStampPreview {
  const item = asRecord(input)
  return {
    lines: list(item.lines).map((lineInput) => {
      const line = asRecord(lineInput)
      return {
        text: text(line.text),
        size: Number(line.size || 9),
        bold: line.bold === true,
      }
    }).filter((line) => line.text),
    text: text(item.text),
    scope: asRecord(item.scope) as Record<string, boolean>,
  }
}

function normaliseCompilerOption(input: unknown): TemplateCompilerOption {
  const item = asRecord(input)
  return {
    value: text(item.value),
    label: text(item.label) || text(item.value),
    clienteId: text(item.clienteId),
  }
}

function normaliseCompilerNote(input: unknown): TemplateCompilerNote | undefined {
  const item = asRecord(input)
  const noteText = text(item.text)
  if (!noteText) return undefined
  const noteTone = ['found', 'missing', 'error'].includes(String(item.tone)) ? String(item.tone) as TemplateCompilerNote['tone'] : 'missing'
  return { tone: noteTone, text: noteText }
}

function normaliseCompilerField(input: unknown): TemplateCompilerField {
  const item = asRecord(input)
  return {
    name: text(item.name),
    label: text(item.label) || text(item.name) || 'Campo',
    type: text(item.type) || 'text',
    placeholder: text(item.placeholder),
    required: item.required === true,
    value: text(item.value),
    options: list(item.options).map(normaliseCompilerOption).filter((option) => option.value || option.label),
    error: text(item.error),
    note: normaliseCompilerNote(item.note),
    warnings: list(item.warnings).map((value) => text(value)).filter(Boolean),
  }
}

function normaliseGuidePreviewStep(input: unknown): TemplateGuidePreviewStep {
  const item = asRecord(input)
  const rawState = text(item.state)
  const state: TemplateGuidePreviewStep['state'] = rawState === 'done' || rawState === 'active' || rawState === 'pending' ? rawState : 'pending'
  return {
    id: text(item.id) || text(item.label) || 'step',
    label: text(item.label) || 'Passaggio',
    state,
  }
}

function normaliseGuidePreviewCheck(input: unknown): TemplateGuidePreviewCheck {
  const item = asRecord(input)
  return {
    label: text(item.label) || 'Controllo',
    value: text(item.value) || 'ok',
    tone: tone(item.tone || 'success'),
  }
}

function normaliseGuidePreview(input: unknown, modelCode: string, modelName: string): TemplateGuidePreview {
  const item = asRecord(input)
  const template = asRecord(item.template)
  const importInfo = asRecord(item.import)
  const editorLayout = asRecord(item.editorLayout || item.editor_layout)
  const fallback = emptyTemplateCompilerPage.guidePreview
  return {
    enabled: item.enabled === true,
    eyebrow: text(item.eyebrow) || fallback.eyebrow,
    title: text(item.title) || fallback.title,
    subtitle: text(item.subtitle),
    badge: text(item.badge) || fallback.badge,
    guideCode: text(item.guideCode),
    guideTitle: text(item.guideTitle),
    fascicoloHref: safeHref(item.fascicoloHref, ''),
    uploadEndpoint: safeHref(item.uploadEndpoint, ''),
    importEndpoint: safeHref(item.importEndpoint, ''),
    previewPdfHref: safeHref(item.previewPdfHref, ''),
    wordHref: safeHref(item.wordHref, ''),
    saveEndpoint: safeHref(item.saveEndpoint, ''),
    renderEndpoint: safeHref(item.renderEndpoint, ''),
    importLabel: text(item.importLabel) || fallback.importLabel,
    previewLabel: text(item.previewLabel) || fallback.previewLabel,
    saveLabel: text(item.saveLabel) || fallback.saveLabel,
    initialText: text(item.initialText),
    reason: text(item.reason),
    steps: list(item.steps).map(normaliseGuidePreviewStep).filter((step) => step.id || step.label),
    template: {
      code: text(template.code) || modelCode,
      name: text(template.name) || modelName || modelCode || 'Template atto',
      reason: text(template.reason),
      autoLoad: template.autoLoad === true || template.auto_load === true,
    },
    import: {
      enabled: importInfo.enabled !== false,
      formats: text(importInfo.formats) || fallback.import.formats,
      note: text(importInfo.note),
    },
    layoutChecks: list(item.layoutChecks).map(normaliseGuidePreviewCheck).filter((check) => check.label),
    editorLayout: {
      fontSize: Number(editorLayout.fontSize || editorLayout.font_size || fallback.editorLayout.fontSize),
      lineHeight: Number(editorLayout.lineHeight || editorLayout.line_height || fallback.editorLayout.lineHeight),
      pageScale: Number(editorLayout.pageScale || editorLayout.page_scale || fallback.editorLayout.pageScale),
    },
  }
}

function normaliseNormativeReference(input: unknown): TemplateNormativeReference {
  const item = asRecord(input)
  const rawText = typeof input === 'string' ? input : ''
  return {
    id: text(item.id) || rawText,
    title: text(item.title) || rawText,
    sourceId: text(item.source_id) || text(item.sourceId),
    sourceTitle: text(item.source_title) || text(item.sourceTitle),
    article: text(item.article),
    officialUrl: text(item.official_url) || text(item.officialUrl),
    reasonForApplication: text(item.reason_for_application) || text(item.reasonForApplication),
    verificationStatus: text(item.verification_status) || text(item.verificationStatus),
    confidence: Number(item.confidence || 0),
  }
}

function normaliseNormativeSource(input: unknown): TemplateNormativeSource {
  const item = asRecord(input)
  return {
    id: text(item.id),
    title: text(item.title),
    officialUrl: text(item.official_url) || text(item.officialUrl),
    verificationStatus: text(item.verification_status) || text(item.verificationStatus),
    lastVerifiedAt: text(item.last_verified_at) || text(item.lastVerifiedAt),
  }
}

function normaliseCompilerPage(input: unknown): TemplateCompilerData {
  const page = asRecord(input)
  const model = asRecord(page.model)
  const selectors = asRecord(page.selectors)
  const checks = asRecord(page.checks)
  const compliance = asRecord(page.compliance)
  const hiddenInput = asRecord(page.hidden)
  const hidden: Record<string, string> = {}
  Object.entries(hiddenInput).forEach(([key, value]) => {
    hidden[key] = text(value)
  })
  return {
    ok: page.ok !== false,
    message: text(page.message),
    model: {
      code: text(model.code),
      name: text(model.name) || text(model.code) || 'Template atto',
      area: text(model.area),
    },
    summary: text(page.summary),
    formAction: safeHref(page.formAction, ''),
    catalogHref: safeHref(page.catalogHref, '/template-atti/catalogo'),
    submitLabel: text(page.submitLabel) || "Crea bozza dell'atto",
    selectors: {
      clienti: list(selectors.clienti).map(normaliseCompilerOption).filter((option) => option.value || option.label),
      fascicoli: list(selectors.fascicoli).map(normaliseCompilerOption).filter((option) => option.value || option.label),
      selectedClienteId: text(selectors.selectedClienteId),
      selectedFascicoloId: text(selectors.selectedFascicoloId),
      selectedClienteLabel: text(selectors.selectedClienteLabel),
      selectedFascicoloLabel: text(selectors.selectedFascicoloLabel),
    },
    hidden,
    baseFields: list(page.baseFields).map(normaliseCompilerField).filter((field) => field.name),
    extraFields: list(page.extraFields).map(normaliseCompilerField).filter((field) => field.name),
    stamp: normaliseStudioStamp(page.stamp),
    compliance: {
      available: compliance.available === true,
      state: text(compliance.state),
      ready: compliance.ready === true,
      requiresReview: compliance.requiresReview === true,
      processArea: text(compliance.processArea),
      profile: text(compliance.profile),
      rulesetVersion: text(compliance.rulesetVersion),
      sourceLabel: text(compliance.sourceLabel),
      evidenceCount: Number(compliance.evidenceCount || 0),
      overallState: text(compliance.overallState) || text(compliance.overall_state) || text(compliance.state),
      canGenerateFinalDraft: compliance.canGenerateFinalDraft === true || compliance.can_generate_final_draft === true,
      canGenerateWorkingDraft: compliance.canGenerateWorkingDraft === true || compliance.can_generate_working_draft === true,
      canOpenEditor: compliance.canOpenEditor === true || compliance.can_open_editor === true,
      reliabilityScore: {
        value: Number(asRecord(compliance.reliabilityScore).value || asRecord(compliance.reliability_score).value || 0),
        label: text(asRecord(compliance.reliabilityScore).label) || text(asRecord(compliance.reliability_score).label),
        capsApplied: list(asRecord(compliance.reliabilityScore).capsApplied || asRecord(compliance.reliability_score).caps_applied).map((value) => text(value)).filter(Boolean),
        factors: list(asRecord(compliance.reliabilityScore).factors || asRecord(compliance.reliability_score).factors).map((value) => text(value)).filter(Boolean),
      },
      layoutProfile: asRecord(compliance.layoutProfile) || asRecord(compliance.layout_profile),
      stampPolicy: asRecord(compliance.stampPolicy) || asRecord(compliance.stamp_policy),
      missingFields: list(compliance.missingFields).map((value) => text(value)).filter(Boolean),
      missingFieldRows: list(compliance.missingFieldRows).map((value) => asRecord(value)),
      missingDocuments: list(compliance.missingDocuments).map((value) => asRecord(value)),
      blocking: list(compliance.blocking).map((value) => text(value)).filter(Boolean),
      recommended: list(compliance.recommended).map((value) => text(value)).filter(Boolean),
      normativeReferences: list(compliance.normativeReferences).map(normaliseNormativeReference).filter((value) => value.title || value.article),
      sources: list(compliance.sources).map(normaliseNormativeSource).filter((value) => value.id || value.title),
      nextActions: list(compliance.nextActions).map((value) => text(value)).filter(Boolean),
      reasonedExplanation: text(compliance.reasonedExplanation),
      procedibility: list(compliance.procedibility).map((value) => text(value)).filter(Boolean),
      deadlines: list(compliance.deadlines).map((value) => text(value)).filter(Boolean),
      cartabiaControls: list(compliance.cartabiaControls).map((value) => text(value)).filter(Boolean),
      editorialControls: list(compliance.editorialControls).map((value) => text(value)).filter(Boolean),
      depositControls: list(compliance.depositControls).map((value) => text(value)).filter(Boolean),
      validationRules: list(compliance.validationRules).map((value) => text(value)).filter(Boolean),
      warnings: list(compliance.warnings).map((value) => text(value)).filter(Boolean),
    },
    checks: {
      blocking: list(checks.blocking).map((value) => text(value)).filter(Boolean),
      recommended: list(checks.recommended).map((value) => text(value)).filter(Boolean),
    },
    attachments: list(page.attachments).map((value) => text(value)).filter(Boolean),
    sections: list(page.sections).map((value) => {
      const item = asRecord(value)
      return { label: text(item.label), state: text(item.state) }
    }).filter((section) => section.label),
    guidePreview: normaliseGuidePreview(page.guidePreview, text(model.code), text(model.name)),
  }
}

function normalisePage(input: unknown): TemplateAttiPageData {
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
    studioStamp: normaliseStudioStamp(page.studioStamp),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getTemplateAttiPage(): Promise<TemplateAttiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/template-atti', emptyTemplateAttiPage)
  return normalisePage(payload)
}

export async function getTemplateAttiCatalogoPage(): Promise<TemplateAttiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/template-atti/catalogo', emptyTemplateAttiPage)
  return normalisePage(payload)
}

export async function getTemplateAttiCompilerPage(modelCode: string): Promise<TemplateCompilerData> {
  const search = window.location.search || ''
  const payload = await apiJson<unknown>(
    `/api/v1/ui/template-atti/compila/${encodeURIComponent(modelCode)}${search}`,
    emptyTemplateCompilerPage,
  )
  return normaliseCompilerPage(payload)
}
