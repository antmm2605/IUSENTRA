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
  fontFamily?: string
  headingFontFamily?: string
  uiFontFamily?: string
  placeholderFontFamily?: string
  fallbackFontFamily?: string
  stylePreset?: string
  headingSize?: number
  textAlign?: string
  pageOrientation?: string
  marginTop?: number
  marginRight?: number
  marginBottom?: number
  marginLeft?: number
  paragraphSpacing?: number
  signatureSpacing?: number
  stampPosition?: string
  stampOffsetY?: number
  stampFontFamily?: string
  stampFontSize?: number
  stampLineHeight?: number
  printCleanPlaceholders?: boolean
}

export type TemplateFontRegistryFont = {
  key: string
  label: string
  category: string
  cssStack: string
  docxFamily: string
  pdfFamily: string
  rtfFamily: string
  tone: string
  usage: string[]
}

export type TemplateStylePreset = {
  key: string
  label: string
  documentFont: string
  headingFont: string
  fontSize: number
  headingSize: number
  lineHeight: number
  textAlign: string
  margins: number[]
  paragraphSpacing: number
}

export type TemplateFontRegistry = {
  schemaVersion: string
  policy: Record<string, unknown>
  defaults: {
    document: string
    heading: string
    ui: string
    placeholder: string
    fallback: string
    stylePreset: string
  }
  fonts: TemplateFontRegistryFont[]
  stylePresets: TemplateStylePreset[]
  exportFallbacks: Record<string, string[]>
}

export type TemplateEditorWorkflowStep = {
  id: string
  label: string
  state: 'done' | 'active' | 'pending'
}

export type TemplateExample = {
  id: string
  code: string
  title: string
  description: string
  category: string
  tags: string[]
  fieldsCount: number
  href: string
  selected: boolean
}

export type TemplateLexAction = {
  id: string
  label: string
  mode: string
}

export type TemplateLexProposal = {
  id: string
  mode: string
  title: string
  original: string
  proposed: string
  reason: string
  risk: AdminTone
  status: 'pending' | 'accepted' | 'rejected' | 'modified'
}

export type TemplateLexRevision = {
  title: string
  assistantTitle: string
  privacyPolicy: {
    localOnly: boolean
    externalAllowed: boolean
    message: string
  }
  auditPolicy: {
    proposalVersioning: boolean
    acceptRejectRequired: boolean
    automaticApply: boolean
    tenantIsolated: boolean
  }
  modes: string[]
  actions: TemplateLexAction[]
  seedProposals: TemplateLexProposal[]
  analysisSummary: string
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
  rtfHref: string
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
  lastVerifiedAt: string
  scope: string
  sourceType: string
  coverageRole: string
  deprecated: boolean
  matchReason: string
  registryVersion: string
  confidence: number
}

export type TemplateNormativeSource = {
  id: string
  title: string
  officialUrl: string
  verificationStatus: string
  lastVerifiedAt: string
  scope: string
  sourceType: string
  coverageRole: string
  deprecated: boolean
  matchReason: string
  registryVersion: string
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
  contextFields: TemplateCompilerField[]
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
    officialTemplateSources: TemplateNormativeReference[]
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
  templateExamples: TemplateExample[]
  officialTemplateSources: TemplateNormativeReference[]
  fontRegistry: TemplateFontRegistry
  editorLayout: TemplateEditorLayout
  editorWorkflow: TemplateEditorWorkflowStep[]
  lexRevision: TemplateLexRevision
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
  contextFields: [],
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
    officialTemplateSources: [],
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
  templateExamples: [],
  officialTemplateSources: [],
  fontRegistry: {
    schemaVersion: '',
    policy: {},
    defaults: {
      document: 'merriweather',
      heading: 'merriweather',
      ui: 'inter',
      placeholder: 'ibm_plex_mono',
      fallback: 'times_new_roman',
      stylePreset: 'giudiziario_civile',
    },
    fonts: [
      {
        key: 'source_serif',
        label: 'Source Serif 4',
        category: 'classico',
        cssStack: "'Source Serif 4', Georgia, 'Times New Roman', serif",
        docxFamily: 'Source Serif 4',
        pdfFamily: 'times',
        rtfFamily: 'Times New Roman',
        tone: 'serif',
        usage: ['documento'],
      },
      {
        key: 'merriweather',
        label: 'Merriweather',
        category: 'giudiziario',
        cssStack: "Merriweather, Georgia, 'Times New Roman', serif",
        docxFamily: 'Merriweather',
        pdfFamily: 'times',
        rtfFamily: 'Times New Roman',
        tone: 'serif',
        usage: ['titoli'],
      },
      {
        key: 'inter',
        label: 'Inter',
        category: 'moderno',
        cssStack: 'Inter, Arial, Helvetica, sans-serif',
        docxFamily: 'Inter',
        pdfFamily: 'helvetica',
        rtfFamily: 'Arial',
        tone: 'sans',
        usage: ['interfaccia'],
      },
      {
        key: 'ibm_plex_mono',
        label: 'IBM Plex Mono',
        category: 'placeholder',
        cssStack: "'IBM Plex Mono', 'Courier New', monospace",
        docxFamily: 'IBM Plex Mono',
        pdfFamily: 'courier',
        rtfFamily: 'Courier New',
        tone: 'mono',
        usage: ['placeholder'],
      },
    ],
    stylePresets: [],
    exportFallbacks: { docx: ['Times New Roman'], pdf: ['Times-Roman'], rtf: ['Times New Roman'] },
  },
  editorLayout: {
    fontSize: 12,
    lineHeight: 1.9,
    pageScale: 100,
    fontFamily: 'merriweather',
    headingFontFamily: 'merriweather',
    uiFontFamily: 'inter',
    placeholderFontFamily: 'ibm_plex_mono',
    fallbackFontFamily: 'times_new_roman',
    stylePreset: 'giudiziario_civile',
    headingSize: 16,
    textAlign: 'justify',
    pageOrientation: 'verticale',
    marginTop: 25,
    marginRight: 22,
    marginBottom: 25,
    marginLeft: 32,
    paragraphSpacing: 8,
    signatureSpacing: 42,
    stampPosition: 'top-center',
    stampOffsetY: 0,
    stampFontFamily: 'ibm_plex_mono',
    stampFontSize: 8,
    stampLineHeight: 1.16,
    printCleanPlaceholders: false,
  },
  editorWorkflow: [],
  lexRevision: {
    title: 'Revisione testo',
    assistantTitle: 'Assistente redazionale Lex',
    privacyPolicy: {
      localOnly: true,
      externalAllowed: false,
      message: 'Analisi locale nello studio; nessun invio a servizi esterni senza policy privacy esplicita.',
    },
    auditPolicy: {
      proposalVersioning: true,
      acceptRejectRequired: true,
      automaticApply: false,
      tenantIsolated: true,
    },
    modes: ['Correttore', 'Redattore', 'Revisore Normativo', 'Revisore Privacy', 'Revisore Placeholder', 'Template Builder', 'Final Check'],
    actions: [],
    seedProposals: [],
    analysisSummary: '',
  },
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
    rtfHref: '',
    saveEndpoint: '',
    renderEndpoint: '',
    importLabel: 'Importa documento',
    previewLabel: 'Anteprima PDF',
    saveLabel: 'Salva nel fascicolo',
    initialText: '',
    reason: '',
    steps: [],
    template: { code: '', name: '', reason: '', autoLoad: false },
    import: { enabled: false, formats: 'PDF/DOCX/RTF/TXT', note: '' },
    layoutChecks: [],
    editorLayout: {
      fontSize: 12,
      lineHeight: 1.9,
      pageScale: 100,
      fontFamily: 'merriweather',
      headingFontFamily: 'merriweather',
      uiFontFamily: 'inter',
      placeholderFontFamily: 'ibm_plex_mono',
      fallbackFontFamily: 'times_new_roman',
      stylePreset: 'giudiziario_civile',
      headingSize: 16,
      textAlign: 'justify',
      pageOrientation: 'verticale',
      marginTop: 25,
      marginRight: 22,
      marginBottom: 25,
      marginLeft: 32,
      paragraphSpacing: 8,
      signatureSpacing: 42,
      stampPosition: 'top-center',
      stampOffsetY: 0,
      stampFontFamily: 'ibm_plex_mono',
      stampFontSize: 8,
      stampLineHeight: 1.16,
      printCleanPlaceholders: false,
    },
  },
}

export function buildFreeEditorFallbackPage(): TemplateCompilerData {
  return normaliseCompilerPage({
    ...emptyTemplateCompilerPage,
    ok: true,
    message: 'Editor libero disponibile.',
    model: { code: 'STR_COM_001', name: 'Documento libero', area: 'Studio' },
    summary: 'Foglio libero indipendente dai modelli, pronto per scrittura e salvataggio nel fascicolo.',
    catalogHref: '/template-atti/catalogo',
    submitLabel: 'Salva documento',
    compliance: {
      ...emptyTemplateCompilerPage.compliance,
      available: true,
      state: 'ready',
      ready: true,
      requiresReview: false,
      overallState: 'ready',
      canGenerateWorkingDraft: true,
      canOpenEditor: true,
      sourceLabel: 'Editor libero',
    },
    guidePreview: {
      enabled: true,
      eyebrow: 'Editor libero',
      title: 'Documento libero',
      subtitle: 'Foglio indipendente dai modelli.',
      badge: 'Pronto',
      initialText: '',
      template: {
        code: 'STR_COM_001',
        name: 'Documento libero',
        reason: 'Scrittura libera con timbro studio e strumenti professionali.',
        autoLoad: true,
      },
      import: {
        enabled: true,
        formats: 'PDF, Word, RTF, TXT',
        note: 'Puoi importare un documento e continuare a lavorarlo nel foglio libero.',
      },
      steps: [
        { id: 'scrittura', label: 'Scrittura libera', state: 'active' },
        { id: 'salvataggio', label: 'Salvataggio fascicolo', state: 'pending' },
      ],
      layoutChecks: [],
    },
    templateExamples: [
      {
        id: 'STR_COM_001',
        code: 'STR_COM_001',
        title: 'Documento libero',
        description: 'Foglio libero con timbro studio, formattazione, import e salvataggio.',
        category: 'Editor',
        tags: ['editor', 'libero'],
        href: '/template-atti/editor',
        selected: true,
      },
    ],
  })
}

function timeoutSignal(timeoutMs: number): AbortSignal | undefined {
  if (typeof AbortController === 'undefined') return undefined
  const controller = new AbortController()
  globalThis.setTimeout(() => controller.abort(), timeoutMs)
  return controller.signal
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

function matchVisibleCase(match: string, replacement: string) {
  if (match.toUpperCase() === match) return replacement.toUpperCase()
  if (match[0]?.toUpperCase() === match[0]) return replacement.charAt(0).toUpperCase() + replacement.slice(1)
  return replacement
}

function replaceVisibleWord(value: string, source: string, replacement: string) {
  return value.replace(new RegExp(`\\b${source}\\b`, 'gi'), (match) => matchVisibleCase(match, replacement))
}

function visibleText(value: unknown, fallback = ''): string {
  let result = text(value, fallback)
  result = result
    .replace(/\binformazioni\s+operativi\b/gi, (match) => matchVisibleCase(match, 'informazioni operative'))
    .replace(/\bindicazioni\s+operativi\b/gi, (match) => matchVisibleCase(match, 'indicazioni operative'))
    .replace(/\bmetadati\s+operativi\b/gi, (match) => matchVisibleCase(match, 'informazioni operative'))
    .replace(/\btemplate\s+del\s+catalogo\s+master\s+1\.1\.0\b/gi, (match) => matchVisibleCase(match, 'modello del catalogo professionale'))
    .replace(/\bcatalogo\s+master\b/gi, (match) => matchVisibleCase(match, 'catalogo professionale'))
    .replace(/\bcanale\s+NESSUNO\b/g, 'senza deposito telematico')
    .replace(/\bcanale\s+nessuno\b/gi, 'senza deposito telematico')
    .replace(/\bAccordo saldo e stralcio:\s+o crediti\b/g, 'Accordo saldo e stralcio: Recupero crediti')
  for (const [source, replacement] of [
    ['conformita', 'conformità'],
    ['qualita', 'qualità'],
    ['attivita', 'attività'],
    ['autorita', 'autorità'],
    ['facolta', 'facoltà'],
    ['eredita', 'eredità'],
    ['modalita', 'modalità'],
    ['gia', 'già'],
    ['puo', 'può'],
    ['piu', 'più'],
    ['perche', 'perché'],
  ] as const) {
    result = replaceVisibleWord(result, source, replacement)
  }
  return result
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
    label: visibleText(item.label) || visibleText(item.name) || 'Variabile',
    kind: visibleText(item.kind) || 'metadato',
    source: visibleText(item.source) || 'metadata',
  }
}

function normaliseRecord(input: unknown): TemplateAttiRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'template',
    kind: text(item.kind) || 'catalogo',
    title: visibleText(item.title) || 'Template',
    subtitle: visibleText(item.subtitle),
    description: visibleText(item.description),
    category: visibleText(item.category),
    matter: visibleText(item.matter),
    area: visibleText(item.area),
    branch: visibleText(item.branch),
    channel: visibleText(item.channel),
    portal: visibleText(item.portal),
    stateLabel: visibleText(item.stateLabel),
    stateTone: tone(item.stateTone),
    complianceLabel: visibleText(item.complianceLabel),
    cartabiaState: text(item.cartabiaState),
    cartabiaLabel: visibleText(item.cartabiaLabel),
    processArea: visibleText(item.processArea),
    requiresLawyerReview: item.requiresLawyerReview === true,
    prefillStatus: visibleText(item.prefillStatus),
    prefillAvailable: Number(item.prefillAvailable || 0),
    prefillMissing: Number(item.prefillMissing || 0),
    blockingChecks: list(item.blockingChecks).map((value) => visibleText(value)).filter(Boolean),
    recommendedChecks: list(item.recommendedChecks).map((value) => visibleText(value)).filter(Boolean),
    dataSources: list(item.dataSources).map((value) => visibleText(value)).filter(Boolean),
    updatedAt: text(item.updatedAt),
    tags: list(item.tags).map((tag) => visibleText(tag)).filter(Boolean),
    requiredVariables: list(item.requiredVariables).map(normaliseVariable).filter((variable) => variable.name),
    href: safeHref(item.href, '/template-atti/catalogo'),
    primaryActionLabel: visibleText(item.primaryActionLabel) || 'Compila con dati IUSENTRA',
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
    label: visibleText(item.label) || visibleText(item.value),
    clienteId: text(item.clienteId),
  }
}

function normaliseCompilerNote(input: unknown): TemplateCompilerNote | undefined {
  const item = asRecord(input)
  const noteText = visibleText(item.text)
  if (!noteText) return undefined
  const noteTone = ['found', 'missing', 'error'].includes(String(item.tone)) ? String(item.tone) as TemplateCompilerNote['tone'] : 'missing'
  return { tone: noteTone, text: noteText }
}

function normaliseCompilerField(input: unknown): TemplateCompilerField {
  const item = asRecord(input)
  return {
    name: text(item.name),
    label: visibleText(item.label) || visibleText(item.name) || 'Campo',
    type: text(item.type) || 'text',
    placeholder: visibleText(item.placeholder),
    required: item.required === true,
    value: text(item.value),
    options: list(item.options).map(normaliseCompilerOption).filter((option) => option.value || option.label),
    error: visibleText(item.error),
    note: normaliseCompilerNote(item.note),
    warnings: list(item.warnings).map((value) => visibleText(value)).filter(Boolean),
  }
}

function normaliseGuidePreviewStep(input: unknown): TemplateGuidePreviewStep {
  const item = asRecord(input)
  const rawState = text(item.state)
  const state: TemplateGuidePreviewStep['state'] = rawState === 'done' || rawState === 'active' || rawState === 'pending' ? rawState : 'pending'
  return {
    id: text(item.id) || text(item.label) || 'step',
    label: visibleText(item.label) || 'Passaggio',
    state,
  }
}

function normaliseGuidePreviewCheck(input: unknown): TemplateGuidePreviewCheck {
  const item = asRecord(input)
  return {
    label: visibleText(item.label) || 'Controllo',
    value: visibleText(item.value) || 'ok',
    tone: tone(item.tone || 'success'),
  }
}

function normaliseEditorLayout(input: unknown): TemplateEditorLayout {
  const item = asRecord(input)
  const fallback = emptyTemplateCompilerPage.editorLayout
  return {
    fontSize: Number(item.fontSize || item.font_size || item.font_size_pt || fallback.fontSize),
    lineHeight: Number(item.lineHeight || item.line_height || fallback.lineHeight),
    pageScale: Number(item.pageScale || item.page_scale || fallback.pageScale),
    fontFamily: text(item.fontFamily) || text(item.font_family) || fallback.fontFamily,
    headingFontFamily: text(item.headingFontFamily) || text(item.heading_font_family) || fallback.headingFontFamily,
    uiFontFamily: text(item.uiFontFamily) || text(item.ui_font_family) || fallback.uiFontFamily,
    placeholderFontFamily: text(item.placeholderFontFamily) || text(item.placeholder_font_family) || fallback.placeholderFontFamily,
    fallbackFontFamily: text(item.fallbackFontFamily) || text(item.fallback_font_family) || fallback.fallbackFontFamily,
    stylePreset: text(item.stylePreset) || text(item.document_style_preset) || fallback.stylePreset,
    headingSize: Number(item.headingSize || item.heading_size || item.heading_size_pt || fallback.headingSize),
    textAlign: text(item.textAlign) || text(item.text_align) || fallback.textAlign,
    pageOrientation: text(item.pageOrientation) || text(item.page_orientation) || fallback.pageOrientation,
    marginTop: Number(item.marginTop || item.margin_top_mm || fallback.marginTop),
    marginRight: Number(item.marginRight || item.margin_right_mm || fallback.marginRight),
    marginBottom: Number(item.marginBottom || item.margin_bottom_mm || fallback.marginBottom),
    marginLeft: Number(item.marginLeft || item.margin_left_mm || fallback.marginLeft),
    paragraphSpacing: Number(item.paragraphSpacing || item.paragraph_spacing_pt || fallback.paragraphSpacing),
    signatureSpacing: Number(item.signatureSpacing || item.signature_spacing_pt || fallback.signatureSpacing),
    stampPosition: text(item.stampPosition) || text(item.stamp_position) || fallback.stampPosition,
    stampOffsetY: Number(item.stampOffsetY ?? item.stamp_offset_y_mm ?? fallback.stampOffsetY ?? 0),
    stampFontFamily: text(item.stampFontFamily) || text(item.stamp_font_family) || fallback.stampFontFamily,
    stampFontSize: Number(item.stampFontSize || item.stamp_font_size_pt || fallback.stampFontSize || 8),
    stampLineHeight: Number(item.stampLineHeight || item.stamp_line_height || fallback.stampLineHeight || 1.16),
    printCleanPlaceholders: item.printCleanPlaceholders === true || item.print_clean_placeholders === true,
  }
}

function normaliseFont(input: unknown): TemplateFontRegistryFont {
  const item = asRecord(input)
  return {
    key: text(item.key),
    label: text(item.label) || text(item.key) || 'Font',
    category: text(item.category) || 'documento',
    cssStack: text(item.css_stack) || text(item.cssStack) || 'Georgia, serif',
    docxFamily: text(item.docx_family) || text(item.docxFamily) || text(item.label) || 'Times New Roman',
    pdfFamily: text(item.pdf_family) || text(item.pdfFamily) || 'times',
    rtfFamily: text(item.rtf_family) || text(item.rtfFamily) || 'Times New Roman',
    tone: text(item.tone) || 'serif',
    usage: list(item.usage).map((value) => text(value)).filter(Boolean),
  }
}

function normaliseStylePreset(input: unknown): TemplateStylePreset {
  const item = asRecord(input)
  return {
    key: text(item.key),
    label: text(item.label) || text(item.key) || 'Preset',
    documentFont: text(item.document_font) || text(item.documentFont),
    headingFont: text(item.heading_font) || text(item.headingFont),
    fontSize: Number(item.font_size_pt || item.fontSize || 12),
    headingSize: Number(item.heading_size_pt || item.headingSize || 16),
    lineHeight: Number(item.line_height || item.lineHeight || 1.8),
    textAlign: text(item.text_align) || text(item.textAlign) || 'justify',
    margins: list(item.margins_mm || item.margins).map((value) => Number(value)).filter((value) => Number.isFinite(value)),
    paragraphSpacing: Number(item.paragraph_spacing_pt || item.paragraphSpacing || 8),
  }
}

function normaliseFontRegistry(input: unknown): TemplateFontRegistry {
  const item = asRecord(input)
  const defaults = asRecord(item.defaults)
  const fallback = emptyTemplateCompilerPage.fontRegistry
  const fonts = list(item.fonts).map(normaliseFont).filter((font) => font.key)
  const stylePresets = list(item.style_presets || item.stylePresets).map(normaliseStylePreset).filter((preset) => preset.key)
  return {
    schemaVersion: text(item.schema_version) || text(item.schemaVersion) || fallback.schemaVersion,
    policy: asRecord(item.policy),
    defaults: {
      document: text(defaults.document) || fallback.defaults.document,
      heading: text(defaults.heading) || fallback.defaults.heading,
      ui: text(defaults.ui) || fallback.defaults.ui,
      placeholder: text(defaults.placeholder) || fallback.defaults.placeholder,
      fallback: text(defaults.fallback) || fallback.defaults.fallback,
      stylePreset: text(defaults.style_preset) || text(defaults.stylePreset) || fallback.defaults.stylePreset,
    },
    fonts: fonts.length ? fonts : fallback.fonts,
    stylePresets,
    exportFallbacks: asRecord(item.export_fallbacks || item.exportFallbacks) as Record<string, string[]>,
  }
}

function normaliseWorkflowStep(input: unknown): TemplateEditorWorkflowStep {
  const item = asRecord(input)
  const rawState = text(item.state)
  const state: TemplateEditorWorkflowStep['state'] = rawState === 'done' || rawState === 'active' || rawState === 'pending' ? rawState : 'pending'
  return {
    id: text(item.id) || text(item.label) || 'passaggio',
    label: visibleText(item.label) || 'Passaggio',
    state,
  }
}

function normaliseTemplateExample(input: unknown): TemplateExample {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.code) || 'template',
    code: text(item.code),
    title: visibleText(item.title) || visibleText(item.code) || 'Template',
    description: visibleText(item.description),
    category: visibleText(item.category) || 'Atti',
    tags: list(item.tags).map((value) => visibleText(value)).filter(Boolean),
    fieldsCount: Number(item.fieldsCount || item.fields_count || 0),
    href: safeHref(item.href, ''),
    selected: item.selected === true,
  }
}

function normaliseLexAction(input: unknown): TemplateLexAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione_lex',
    label: visibleText(item.label) || 'Azione Lex',
    mode: visibleText(item.mode) || 'Correttore',
  }
}

function normaliseLexProposal(input: unknown): TemplateLexProposal {
  const item = asRecord(input)
  const rawStatus = text(item.status)
  const status: TemplateLexProposal['status'] = rawStatus === 'accepted' || rawStatus === 'rejected' || rawStatus === 'modified' ? rawStatus : 'pending'
  return {
    id: text(item.id) || text(item.title) || 'proposta_lex',
    mode: visibleText(item.mode) || 'Correttore',
    title: visibleText(item.title) || 'Proposta Lex',
    original: visibleText(item.original),
    proposed: visibleText(item.proposed),
    reason: visibleText(item.reason),
    risk: tone(item.risk || 'warning'),
    status,
  }
}

function normaliseLexRevision(input: unknown): TemplateLexRevision {
  const item = asRecord(input)
  const privacyPolicy = asRecord(item.privacyPolicy || item.privacy_policy)
  const auditPolicy = asRecord(item.auditPolicy || item.audit_policy)
  const fallback = emptyTemplateCompilerPage.lexRevision
  return {
    title: text(item.title) || fallback.title,
    assistantTitle: text(item.assistantTitle) || text(item.assistant_title) || fallback.assistantTitle,
    privacyPolicy: {
      localOnly: privacyPolicy.localOnly !== false && privacyPolicy.local_only !== false,
      externalAllowed: privacyPolicy.externalAllowed === true || privacyPolicy.external_allowed === true,
      message: text(privacyPolicy.message) || fallback.privacyPolicy.message,
    },
    auditPolicy: {
      proposalVersioning: auditPolicy.proposalVersioning !== false && auditPolicy.proposal_versioning !== false,
      acceptRejectRequired: auditPolicy.acceptRejectRequired !== false && auditPolicy.accept_reject_required !== false,
      automaticApply: auditPolicy.automaticApply === true || auditPolicy.automatic_apply === true,
      tenantIsolated: auditPolicy.tenantIsolated !== false && auditPolicy.tenant_isolated !== false,
    },
    modes: list(item.modes).map((value) => text(value)).filter(Boolean).length
      ? list(item.modes).map((value) => text(value)).filter(Boolean)
      : fallback.modes,
    actions: list(item.actions).map(normaliseLexAction).filter((action) => action.id),
    seedProposals: list(item.seedProposals || item.seed_proposals).map(normaliseLexProposal).filter((proposal) => proposal.id),
    analysisSummary: text(item.analysisSummary) || text(item.analysis_summary),
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
    rtfHref: safeHref(item.rtfHref, ''),
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
    editorLayout: normaliseEditorLayout(editorLayout),
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
    lastVerifiedAt: text(item.last_verified_at) || text(item.lastVerifiedAt),
    scope: text(item.scope),
    sourceType: text(item.source_type) || text(item.sourceType),
    coverageRole: text(item.coverage_role) || text(item.coverageRole),
    deprecated: item.deprecated === true,
    matchReason: text(item.match_reason) || text(item.matchReason),
    registryVersion: text(item.registry_version) || text(item.registryVersion),
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
    scope: text(item.scope),
    sourceType: text(item.source_type) || text(item.sourceType),
    coverageRole: text(item.coverage_role) || text(item.coverageRole),
    deprecated: item.deprecated === true,
    matchReason: text(item.match_reason) || text(item.matchReason),
    registryVersion: text(item.registry_version) || text(item.registryVersion),
  }
}

function normaliseCompilerPage(input: unknown): TemplateCompilerData {
  const page = asRecord(input)
  const model = asRecord(page.model)
  const selectors = asRecord(page.selectors)
  const checks = asRecord(page.checks)
  const compliance = asRecord(page.compliance)
  const hiddenInput = asRecord(page.hidden)
  const officialTemplateSources = list(
    page.officialTemplateSources
    || page.official_template_sources
    || compliance.officialTemplateSources
    || compliance.official_template_sources,
  ).map(normaliseNormativeReference).filter((value) => value.title || value.article)
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
    contextFields: list(page.contextFields).map(normaliseCompilerField).filter((field) => field.name),
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
      officialTemplateSources: list(compliance.officialTemplateSources || compliance.official_template_sources)
        .map(normaliseNormativeReference)
        .filter((value) => value.title || value.article),
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
    templateExamples: list(page.templateExamples || page.template_examples).map(normaliseTemplateExample).filter((example) => example.id),
    officialTemplateSources,
    fontRegistry: normaliseFontRegistry(page.fontRegistry || page.font_registry),
    editorLayout: normaliseEditorLayout(page.editorLayout || page.editor_layout),
    editorWorkflow: list(page.editorWorkflow || page.editor_workflow).map(normaliseWorkflowStep).filter((step) => step.id),
    lexRevision: normaliseLexRevision(page.lexRevision || page.lex_revision),
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
  const params = new URLSearchParams(window.location.search || '')
  const route = (window.location.pathname.replace(/\/+$/, '') || '/').toLowerCase()
  const freeEditorRoute = route === '/template-atti/editor' || route === '/template-atti/editor-libero'
  if (freeEditorRoute) {
    params.set('editor_libero', '1')
  }
  const query = params.toString()
  const search = query ? `?${query}` : ''
  const fallback = freeEditorRoute ? buildFreeEditorFallbackPage() : emptyTemplateCompilerPage
  try {
    const payload = await apiJson<unknown>(
      `/api/v1/ui/template-atti/compila/${encodeURIComponent(modelCode)}${search}`,
      fallback,
      { signal: freeEditorRoute ? timeoutSignal(10000) : undefined },
    )
    return normaliseCompilerPage(payload)
  } catch (_error) {
    return fallback
  }
}
