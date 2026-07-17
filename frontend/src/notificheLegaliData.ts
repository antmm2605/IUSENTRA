export type LegalOption = {
  value: string
  label: string
  needsAttestazione?: boolean
}

export type LegalSourceReference = {
  id: string
  label: string
  rule: string
}

export type LegalNotificationDirective = {
  value: string
  label: string
  allowedRegisters: string[]
  allowedRecipientRoles: string[]
  templateId: string
  requiredFields: string[]
  proceedingRequired: boolean
  recipientRule: string
  legalBasis: LegalSourceReference[]
  roleLegalBasis?: LegalSourceReference[]
  caseLegalBasis?: LegalSourceReference[]
  attachmentRules?: LegalSourceReference[]
  note: string
}

export type LegalTemplateField = {
  name: string
  label: string
}

export type LegalTemplateOption = {
  value: string
  code: string
  label: string
  description: string
  requiresProceeding: boolean
  privacyDescription: boolean
  custom: boolean
  previewText: string
  fields: LegalTemplateField[]
}

export type LegalTemplateFieldToken = {
  group: string
  label: string
  token: string
}

export type ClientCommunicationTemplateOption = {
  value: string
  label: string
  description: string
  subjectPreview: string
  bodyPreview: string
}

export type LegalDocumentSuggestion = {
  id: string
  label: string
  nomeFile: string
  nomeOriginale: string
  descrizione: string
  origine: string
  hashSha256: string
  dataDocumento: string
  fonte: string
  riferimentoPortale: string
  servizioPortale: string
  documentoUfficio: boolean
  acquisitoDaPortale: boolean
  notificaRichiesta: boolean
  provaNotifica: boolean
  tipoProvaNotifica: string
  dataRilascioPortale: string
  necessitaAttestazione: boolean
}

export type LegalOfficeRelease = {
  fascicoloId: string
  fascicoloNumero: string
  fascicoloTitolo: string
  ufficio: string
  numeroRg: string
  annoRg: string
  depositoId: string
  idDepositoEsterno: string
  documentoId: string
  nome: string
  tipo: string
  dataDeposito: string
  mittente: string
  fontePortale: string
  servizioPortale: string
  riferimentoPortale: string
  notificaRichiesta: boolean
  pecId?: string
  pecHref?: string
  pecMessageId?: string
  pecEmlFile?: string
  pecEmlSha256?: string
  acquisitionHref?: string
  acquisitionActionLabel?: string
  singleDocumentAcquisition?: boolean
  acquisito?: boolean
}

export type LegalRecipientSuggestion = {
  id: string
  label: string
  nome: string
  codiceFiscalePiva: string
  pec: string
  ruolo: string
  ruoloPratica: string
  fontePecSuggerita: string
  parteRappresentata: string
  verificaRichiesta: boolean
}

export type LegalPracticeIndexItem = {
  id: string
  label: string
  numero: string
  titolo: string
  assistitoNome: string
  controparte: string
  ufficio: string
  numeroRg: string
  annoRg: string
  oggetto: string
  stato: string
  archiviata: boolean
}

export type LegalPracticeSuggestion = {
  id: string
  label: string
  numero: string
  titolo: string
  assistitoNome: string
  assistitoCf: string
  clienteId: string
  controparte: string
  controparteCf: string
  procedimento: {
    presente: boolean
    ufficio: string
    sezione: string
    numeroRg: string
    annoRg: string
    giudice: string
    tipoProcedimento: string
  }
  destinatari: LegalRecipientSuggestion[]
  documenti: LegalDocumentSuggestion[]
  portaleAcquisizioneHref: string
  documentoUfficioMonitor: {
    stato: string
    rilascioRilevato: boolean
    documentiAcquisiti: number
    documentiDaAcquisire: number
    documentiDaNotificare: number
    documentiRilevati: LegalOfficeRelease[]
    documentiRilasciati: LegalOfficeRelease[]
    messaggio: string
  }
  modelloSuggerito: string
}

export type LegalClientSuggestion = {
  id: string
  nome: string
  codiceFiscalePiva: string
  pec: string
}

export type LegalAutomationStep = {
  id: string
  title: string
  body: string
  source: string
}

export type LegalWorkflowResult = {
  ok: boolean
  blockers: string[]
  warnings: string[]
  subject: string
  body: string
  relataText: string
  nextActions: string[]
  templateId: string
  templateLabel: string
  templateVersion: string
  selectedBlocks: string[]
  checklistText: string
  logJson: Record<string, unknown>
  outputPlan: Record<string, unknown>
  message?: string
}

export type LegalRelataPreviewResult = {
  ok: boolean
  previewText: string
  missingFields: string[]
  warnings: string[]
  blockers: string[]
  templateId: string
  templateLabel: string
}

export type LegalRelataDraftResult = {
  ok: boolean
  message: string
  draftId: string
  savedAt: string
}

export type NotificheLegaliData = {
  source: string
  generatedAt: string
  contracts: {
    separateLegalNotification: boolean
    clientCommunicationWithoutRelata: boolean
    depositProofWithOriginalReceipts: boolean
    parametricTemplateEngine: boolean
    officeDocumentPortalAcquisition: boolean
    officeDocumentPecEvidence: boolean
    recipientCaseMatrix: boolean
  }
  templateCatalogVersion: string
  mandatorySubject: string
  defaults: {
    studioNome: string
    avvocatoNome: string
    avvocatoCf: string
    avvocatoForo: string
    studioIndirizzo: string
    studioCap: string
    studioCitta: string
    studioProvincia: string
    mittentePec: string
    fontePecMittente: string
  }
  registriPec: LegalOption[]
  matriceNotifica: {
    roles: LegalNotificationDirective[]
    cases: LegalNotificationDirective[]
  }
  ruoliDestinatario: LegalOption[]
  tipiNotificaUnep: LegalOption[]
  tipiNotificaNonPec: LegalOption[]
  originiDocumento: LegalOption[]
  modelliRelata: LegalTemplateOption[]
  modelliControllo: LegalTemplateOption[]
  modelliComunicazioneCliente: ClientCommunicationTemplateOption[]
  clientCommunicationTemplateVersion: string
  campiDisponibili: LegalTemplateFieldToken[]
  precompilazione: {
    pratiche: LegalPracticeSuggestion[]
    indicePratiche: LegalPracticeIndexItem[]
    totalePratiche: number
    clienti: LegalClientSuggestion[]
    destinatari: LegalRecipientSuggestion[]
    note: string[]
  }
  automazioneGuidata: {
    notifica: LegalAutomationStep[]
    deposito: LegalAutomationStep[]
    allegati: LegalAutomationStep[]
    unep: LegalAutomationStep[]
    nonPec: LegalAutomationStep[]
  }
  portaleServizi: {
    defaultPortal: string
    label: string
    acquisizioneHref: string
    assistantStartApi: string
    downloadWatchApi: string
    collectApi: string
    localSignerRequired: boolean
  }
  azioni: {
    notifica: string
    anteprimaRelata: string
    attestazioneConformita: string
    relataPdf: string
    relataFirmata: string
    bozzaRelata: string
    comunicazioneCliente: string
    provaDeposito: string
    unep: string
    nonPec: string
    areaWebPst: string
    pecCompose: string
    clientCompose: string
    firmaDigitale: string
    fascicoli: string
    depositoChecklist: string
  }
  fontiOperative: string[]
}

const emptyResult: LegalWorkflowResult = {
  ok: false,
  blockers: [],
  warnings: [],
  subject: '',
  body: '',
  relataText: '',
  nextActions: [],
  templateId: '',
  templateLabel: '',
  templateVersion: '',
  selectedBlocks: [],
  checklistText: '',
  logJson: {},
  outputPlan: {},
}

export const emptyNotificheLegaliData: NotificheLegaliData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: {
    separateLegalNotification: true,
    clientCommunicationWithoutRelata: true,
    depositProofWithOriginalReceipts: true,
    parametricTemplateEngine: true,
    officeDocumentPortalAcquisition: true,
    officeDocumentPecEvidence: true,
    recipientCaseMatrix: true,
  },
  templateCatalogVersion: '',
  mandatorySubject: 'notificazione ai sensi della legge n. 53 del 1994',
  defaults: {
    studioNome: '',
    avvocatoNome: '',
    avvocatoCf: '',
    avvocatoForo: '',
    studioIndirizzo: '',
    studioCap: '',
    studioCitta: '',
    studioProvincia: '',
    mittentePec: '',
    fontePecMittente: 'ReGIndE',
  },
  registriPec: [],
  matriceNotifica: {
    roles: [],
    cases: [],
  },
  ruoliDestinatario: [],
  tipiNotificaUnep: [
    { value: 'mani', label: 'A mani' },
    { value: 'posta', label: 'A mezzo posta' },
    { value: 'estero', label: "All'estero" },
    { value: 'telematica', label: 'Telematica' },
  ],
  tipiNotificaNonPec: [
    { value: 'raccomandata', label: 'Raccomandata' },
    { value: 'ufficiale_giudiziario', label: 'Ufficiale giudiziario' },
    { value: 'mani', label: 'Consegna a mani' },
    { value: 'estero', label: "Notifica all'estero" },
    { value: 'altro', label: 'Altro canale non PEC' },
  ],
  originiDocumento: [],
  modelliRelata: [],
  modelliControllo: [],
  modelliComunicazioneCliente: [],
  clientCommunicationTemplateVersion: '',
  campiDisponibili: [],
  precompilazione: {
    pratiche: [],
    indicePratiche: [],
    totalePratiche: 0,
    clienti: [],
    destinatari: [],
    note: [],
  },
  automazioneGuidata: {
    notifica: [],
    deposito: [],
    allegati: [],
    unep: [],
    nonPec: [],
  },
  portaleServizi: {
    defaultPortal: 'pst',
    label: 'Portale Servizi Telematici',
    acquisizioneHref: '/portali/pst/acquisizione?focus=documenti',
    assistantStartApi: '/api/portali/pst/assistant/start',
    downloadWatchApi: '/api/portali/pst/assistant/{session_id}/watch-downloads',
    collectApi: '/api/portali/pst/assistant/{session_id}/collect',
    localSignerRequired: true,
  },
  azioni: {
    notifica: '/api/v1/ui/notifiche-legali/notifica',
    anteprimaRelata: '/api/v1/ui/notifiche-legali/anteprima-relata',
    attestazioneConformita: '/api/v1/ui/notifiche-legali/attestazione-conformita',
    relataPdf: '/api/v1/ui/notifiche-legali/relata-pdf',
    relataFirmata: '/api/v1/ui/notifiche-legali/relata-firmata',
    bozzaRelata: '/api/v1/ui/notifiche-legali/bozze-relata',
    comunicazioneCliente: '/api/v1/ui/notifiche-legali/comunicazione-cliente',
    provaDeposito: '/api/v1/ui/notifiche-legali/prova-deposito',
    unep: '/api/v1/ui/notifiche-legali/unep',
    nonPec: '/api/v1/ui/notifiche-legali/non-pec',
    areaWebPst: '/api/v1/ui/notifiche-legali/area-web-pst',
    pecCompose: '/email/scrivi?tipo=notifica_l53',
    clientCompose: '/email-ordinaria/scrivi?tipo=comunicazione_cliente',
    firmaDigitale: '/guida/firma-digitale',
    fascicoli: '/fascicoli',
    depositoChecklist: '/deposito/checklist',
  },
  fontiOperative: [],
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function options(value: unknown): LegalOption[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      value: text(row.value),
      label: text(row.label, text(row.value)),
      needsAttestazione: bool(row.needsAttestazione),
    }
  }).filter((item) => item.value && item.label)
}

function templateOptions(value: unknown): LegalTemplateOption[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    const rawFields = Array.isArray(row.fields) ? row.fields : []
    return {
      value: text(row.value),
      code: text(row.code),
      label: text(row.label, text(row.value)),
      description: text(row.description),
      requiresProceeding: bool(row.requiresProceeding),
      privacyDescription: bool(row.privacyDescription),
      custom: bool(row.custom),
      previewText: text(row.previewText),
      fields: rawFields.map((field) => {
        const fieldRow = isRecord(field) ? field : {}
        return { name: text(fieldRow.name), label: text(fieldRow.label, text(fieldRow.name)) }
      }).filter((field) => field.name && field.label),
    }
  }).filter((item) => item.value && item.label)
}

function clientCommunicationTemplateOptions(value: unknown): ClientCommunicationTemplateOption[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      value: text(row.value),
      label: text(row.label, text(row.value)),
      description: text(row.description),
      subjectPreview: text(row.subjectPreview),
      bodyPreview: text(row.bodyPreview),
    }
  }).filter((item) => item.value && item.label)
}

function fieldTokens(value: unknown): LegalTemplateFieldToken[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      group: text(row.group, 'Dati'),
      label: text(row.label),
      token: text(row.token),
    }
  }).filter((item) => item.label && item.token)
}

function legalSources(value: unknown): LegalSourceReference[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: text(row.id),
      label: text(row.label),
      rule: text(row.rule),
    }
  }).filter((item) => item.id && item.label)
}

function notificationDirectives(value: unknown): LegalNotificationDirective[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      value: text(row.value),
      label: text(row.label, text(row.value)),
      allowedRegisters: Array.isArray(row.allowedRegisters) ? row.allowedRegisters.map((entry) => text(entry)).filter(Boolean) : [],
      allowedRecipientRoles: Array.isArray(row.allowedRecipientRoles) ? row.allowedRecipientRoles.map((entry) => text(entry)).filter(Boolean) : [],
      templateId: text(row.templateId),
      requiredFields: Array.isArray(row.requiredFields) ? row.requiredFields.map((entry) => text(entry)).filter(Boolean) : [],
      proceedingRequired: bool(row.proceedingRequired),
      recipientRule: text(row.recipientRule),
      legalBasis: legalSources(row.legalBasis),
      roleLegalBasis: legalSources(row.roleLegalBasis),
      caseLegalBasis: legalSources(row.caseLegalBasis),
      attachmentRules: legalSources(row.attachmentRules),
      note: text(row.note),
    }
  }).filter((item) => item.value && item.label)
}

function documentSuggestions(value: unknown): LegalDocumentSuggestion[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: text(row.id),
      label: text(row.label, text(row.nomeFile)),
      nomeFile: text(row.nomeFile),
      nomeOriginale: text(row.nomeOriginale),
      descrizione: text(row.descrizione),
      origine: text(row.origine, 'originale_informatico'),
      hashSha256: text(row.hashSha256),
      dataDocumento: text(row.dataDocumento),
      fonte: text(row.fonte),
      riferimentoPortale: text(row.riferimentoPortale),
      servizioPortale: text(row.servizioPortale),
      documentoUfficio: bool(row.documentoUfficio),
      acquisitoDaPortale: bool(row.acquisitoDaPortale),
      notificaRichiesta: bool(row.notificaRichiesta),
      provaNotifica: bool(row.provaNotifica),
      tipoProvaNotifica: text(row.tipoProvaNotifica),
      dataRilascioPortale: text(row.dataRilascioPortale),
      necessitaAttestazione: bool(row.necessitaAttestazione),
    }
  }).filter((item) => item.id && item.label)
}

function officeReleases(value: unknown): LegalOfficeRelease[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      fascicoloId: text(row.fascicoloId),
      fascicoloNumero: text(row.fascicoloNumero),
      fascicoloTitolo: text(row.fascicoloTitolo),
      ufficio: text(row.ufficio),
      numeroRg: text(row.numeroRg),
      annoRg: text(row.annoRg),
      depositoId: text(row.depositoId),
      idDepositoEsterno: text(row.idDepositoEsterno),
      documentoId: text(row.documentoId),
      nome: text(row.nome),
      tipo: text(row.tipo),
      dataDeposito: text(row.dataDeposito),
      mittente: text(row.mittente),
      fontePortale: text(row.fontePortale),
      servizioPortale: text(row.servizioPortale),
      riferimentoPortale: text(row.riferimentoPortale),
      notificaRichiesta: bool(row.notificaRichiesta),
      pecId: text(row.pecId),
      pecHref: text(row.pecHref),
      pecMessageId: text(row.pecMessageId),
      pecEmlFile: text(row.pecEmlFile),
      pecEmlSha256: text(row.pecEmlSha256),
      acquisitionHref: text(row.acquisitionHref),
      acquisitionActionLabel: text(row.acquisitionActionLabel),
      singleDocumentAcquisition: bool(row.singleDocumentAcquisition),
      acquisito: bool(row.acquisito),
    }
  }).filter((item) => item.nome || item.documentoId)
}

function recipientSuggestions(value: unknown): LegalRecipientSuggestion[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: text(row.id),
      label: text(row.label, text(row.nome)),
      nome: text(row.nome),
      codiceFiscalePiva: text(row.codiceFiscalePiva),
      pec: text(row.pec),
      ruolo: text(row.ruolo, 'terzo'),
      ruoloPratica: text(row.ruoloPratica),
      fontePecSuggerita: text(row.fontePecSuggerita, 'inad'),
      parteRappresentata: text(row.parteRappresentata),
      verificaRichiesta: bool(row.verificaRichiesta),
    }
  }).filter((item) => item.id && item.label)
}

function practiceSuggestions(value: unknown): LegalPracticeSuggestion[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    const procedimento = isRecord(row.procedimento) ? row.procedimento : {}
    const monitor = isRecord(row.documentoUfficioMonitor) ? row.documentoUfficioMonitor : {}
    return {
      id: text(row.id),
      label: text(row.label, text(row.titolo)),
      numero: text(row.numero),
      titolo: text(row.titolo),
      assistitoNome: text(row.assistitoNome),
      assistitoCf: text(row.assistitoCf),
      clienteId: text(row.clienteId),
      controparte: text(row.controparte),
      controparteCf: text(row.controparteCf),
      procedimento: {
        presente: bool(procedimento.presente),
        ufficio: text(procedimento.ufficio),
        sezione: text(procedimento.sezione),
        numeroRg: text(procedimento.numeroRg),
        annoRg: text(procedimento.annoRg),
        giudice: text(procedimento.giudice),
        tipoProcedimento: text(procedimento.tipoProcedimento),
      },
      destinatari: recipientSuggestions(row.destinatari),
      documenti: documentSuggestions(row.documenti),
      portaleAcquisizioneHref: text(row.portaleAcquisizioneHref, '/portali/pst/acquisizione?focus=documenti'),
      documentoUfficioMonitor: {
        stato: text(monitor.stato, 'non_rilevato'),
        rilascioRilevato: bool(monitor.rilascioRilevato),
        documentiAcquisiti: Number(monitor.documentiAcquisiti || 0),
        documentiDaAcquisire: Number(monitor.documentiDaAcquisire || 0),
        documentiDaNotificare: Number(monitor.documentiDaNotificare || 0),
        documentiRilevati: officeReleases(monitor.documentiRilevati),
        documentiRilasciati: officeReleases(monitor.documentiRilasciati),
        messaggio: text(monitor.messaggio),
      },
      modelloSuggerito: text(row.modelloSuggerito, 'relata_pec_base_l53'),
    }
  }).filter((item) => item.id && item.label)
}

function practiceIndexSuggestions(value: unknown): LegalPracticeIndexItem[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: text(row.id),
      label: text(row.label, text(row.titolo)),
      numero: text(row.numero),
      titolo: text(row.titolo),
      assistitoNome: text(row.assistitoNome),
      controparte: text(row.controparte),
      ufficio: text(row.ufficio),
      numeroRg: text(row.numeroRg),
      annoRg: text(row.annoRg),
      oggetto: text(row.oggetto),
      stato: text(row.stato),
      archiviata: bool(row.archiviata),
    }
  }).filter((item) => item.id && item.label)
}

function clientSuggestions(value: unknown): LegalClientSuggestion[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: text(row.id),
      nome: text(row.nome),
      codiceFiscalePiva: text(row.codiceFiscalePiva),
      pec: text(row.pec),
    }
  }).filter((item) => item.id && item.nome)
}

function automationSteps(value: unknown): LegalAutomationStep[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: text(row.id),
      title: text(row.title),
      body: text(row.body),
      source: text(row.source),
    }
  }).filter((item) => item.id && item.title)
}

function resultFromPayload(payload: unknown): LegalWorkflowResult {
  if (!isRecord(payload)) return emptyResult
  return {
    ok: bool(payload.ok),
    blockers: Array.isArray(payload.blockers) ? payload.blockers.map((item) => text(item)).filter(Boolean) : [],
    warnings: Array.isArray(payload.warnings) ? payload.warnings.map((item) => text(item)).filter(Boolean) : [],
    subject: text(payload.subject),
    body: text(payload.body),
    relataText: text(payload.relataText),
    nextActions: Array.isArray(payload.nextActions) ? payload.nextActions.map((item) => text(item)).filter(Boolean) : [],
    templateId: text(payload.templateId),
    templateLabel: text(payload.templateLabel),
    templateVersion: text(payload.templateVersion),
    selectedBlocks: Array.isArray(payload.selectedBlocks) ? payload.selectedBlocks.map((item) => text(item)).filter(Boolean) : [],
    checklistText: text(payload.checklistText),
    logJson: isRecord(payload.logJson) ? payload.logJson : {},
    outputPlan: isRecord(payload.outputPlan) ? payload.outputPlan : {},
    message: text(payload.message),
  }
}

function previewFromPayload(payload: unknown): LegalRelataPreviewResult {
  if (!isRecord(payload)) {
    return { ok: false, previewText: '', missingFields: [], warnings: [], blockers: ['Anteprima non disponibile.'], templateId: '', templateLabel: '' }
  }
  return {
    ok: bool(payload.ok),
    previewText: text(payload.previewText),
    missingFields: Array.isArray(payload.missingFields) ? payload.missingFields.map((item) => text(item)).filter(Boolean) : [],
    warnings: Array.isArray(payload.warnings) ? payload.warnings.map((item) => text(item)).filter(Boolean) : [],
    blockers: Array.isArray(payload.blockers) ? payload.blockers.map((item) => text(item)).filter(Boolean) : [],
    templateId: text(payload.templateId),
    templateLabel: text(payload.templateLabel),
  }
}

function normalisePayload(payload: unknown): NotificheLegaliData {
  if (!isRecord(payload)) return emptyNotificheLegaliData
  const defaults = isRecord(payload.defaults) ? payload.defaults : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  const azioni = isRecord(payload.azioni) ? payload.azioni : {}
  const precompilazione = isRecord(payload.precompilazione) ? payload.precompilazione : {}
  const automazioneGuidata = isRecord(payload.automazioneGuidata) ? payload.automazioneGuidata : {}
  const portaleServizi = isRecord(payload.portaleServizi) ? payload.portaleServizi : {}
  return {
    source: text(payload.source, 'configurazione_studio'),
    generatedAt: text(payload.generatedAt),
    contracts: {
      separateLegalNotification: bool(contracts.separateLegalNotification),
      clientCommunicationWithoutRelata: bool(contracts.clientCommunicationWithoutRelata),
      depositProofWithOriginalReceipts: bool(contracts.depositProofWithOriginalReceipts),
      parametricTemplateEngine: bool(contracts.parametricTemplateEngine),
      officeDocumentPortalAcquisition: bool(contracts.officeDocumentPortalAcquisition),
      officeDocumentPecEvidence: bool(contracts.officeDocumentPecEvidence),
      recipientCaseMatrix: bool(contracts.recipientCaseMatrix),
    },
    templateCatalogVersion: text(payload.templateCatalogVersion),
    mandatorySubject: text(payload.mandatorySubject, emptyNotificheLegaliData.mandatorySubject),
    defaults: {
      studioNome: text(defaults.studioNome),
      avvocatoNome: text(defaults.avvocatoNome),
      avvocatoCf: text(defaults.avvocatoCf),
      avvocatoForo: text(defaults.avvocatoForo),
      studioIndirizzo: text(defaults.studioIndirizzo),
      studioCap: text(defaults.studioCap),
      studioCitta: text(defaults.studioCitta),
      studioProvincia: text(defaults.studioProvincia),
      mittentePec: text(defaults.mittentePec),
      fontePecMittente: text(defaults.fontePecMittente, 'ReGIndE'),
    },
    registriPec: options(payload.registriPec),
    matriceNotifica: {
      roles: notificationDirectives(isRecord(payload.matriceNotifica) ? payload.matriceNotifica.roles : []),
      cases: notificationDirectives(isRecord(payload.matriceNotifica) ? payload.matriceNotifica.cases : []),
    },
    ruoliDestinatario: options(payload.ruoliDestinatario),
    tipiNotificaUnep: options(payload.tipiNotificaUnep).length ? options(payload.tipiNotificaUnep) : emptyNotificheLegaliData.tipiNotificaUnep,
    tipiNotificaNonPec: options(payload.tipiNotificaNonPec).length ? options(payload.tipiNotificaNonPec) : emptyNotificheLegaliData.tipiNotificaNonPec,
    originiDocumento: options(payload.originiDocumento),
    modelliRelata: templateOptions(payload.modelliRelata),
    modelliControllo: templateOptions(payload.modelliControllo),
    modelliComunicazioneCliente: clientCommunicationTemplateOptions(payload.modelliComunicazioneCliente),
    clientCommunicationTemplateVersion: text(payload.clientCommunicationTemplateVersion),
    campiDisponibili: fieldTokens(payload.campiDisponibili),
    precompilazione: {
      pratiche: practiceSuggestions(precompilazione.pratiche),
      indicePratiche: practiceIndexSuggestions(precompilazione.indicePratiche),
      totalePratiche: Number(precompilazione.totalePratiche || 0),
      clienti: clientSuggestions(precompilazione.clienti),
      destinatari: recipientSuggestions(precompilazione.destinatari),
      note: Array.isArray(precompilazione.note) ? precompilazione.note.map((item) => text(item)).filter(Boolean) : [],
    },
    automazioneGuidata: {
      notifica: automationSteps(automazioneGuidata.notifica),
      deposito: automationSteps(automazioneGuidata.deposito),
      allegati: automationSteps(automazioneGuidata.allegati),
      unep: automationSteps(automazioneGuidata.unep),
      nonPec: automationSteps(automazioneGuidata.nonPec),
    },
    portaleServizi: {
      defaultPortal: text(portaleServizi.defaultPortal, emptyNotificheLegaliData.portaleServizi.defaultPortal),
      label: text(portaleServizi.label, emptyNotificheLegaliData.portaleServizi.label),
      acquisizioneHref: text(portaleServizi.acquisizioneHref, emptyNotificheLegaliData.portaleServizi.acquisizioneHref),
      assistantStartApi: text(portaleServizi.assistantStartApi, emptyNotificheLegaliData.portaleServizi.assistantStartApi),
      downloadWatchApi: text(portaleServizi.downloadWatchApi, emptyNotificheLegaliData.portaleServizi.downloadWatchApi),
      collectApi: text(portaleServizi.collectApi, emptyNotificheLegaliData.portaleServizi.collectApi),
      localSignerRequired: bool(portaleServizi.localSignerRequired),
    },
    azioni: {
      notifica: text(azioni.notifica, emptyNotificheLegaliData.azioni.notifica),
      anteprimaRelata: text(azioni.anteprimaRelata, emptyNotificheLegaliData.azioni.anteprimaRelata),
      attestazioneConformita: text(azioni.attestazioneConformita, emptyNotificheLegaliData.azioni.attestazioneConformita),
      relataPdf: text(azioni.relataPdf, emptyNotificheLegaliData.azioni.relataPdf),
      relataFirmata: text(azioni.relataFirmata, emptyNotificheLegaliData.azioni.relataFirmata),
      bozzaRelata: text(azioni.bozzaRelata, emptyNotificheLegaliData.azioni.bozzaRelata),
      comunicazioneCliente: text(azioni.comunicazioneCliente, emptyNotificheLegaliData.azioni.comunicazioneCliente),
      provaDeposito: text(azioni.provaDeposito, emptyNotificheLegaliData.azioni.provaDeposito),
      unep: text(azioni.unep, emptyNotificheLegaliData.azioni.unep),
      nonPec: text(azioni.nonPec, emptyNotificheLegaliData.azioni.nonPec),
      areaWebPst: text(azioni.areaWebPst, emptyNotificheLegaliData.azioni.areaWebPst),
      pecCompose: text(azioni.pecCompose, emptyNotificheLegaliData.azioni.pecCompose),
      clientCompose: text(azioni.clientCompose, emptyNotificheLegaliData.azioni.clientCompose),
      firmaDigitale: text(azioni.firmaDigitale, emptyNotificheLegaliData.azioni.firmaDigitale),
      fascicoli: text(azioni.fascicoli, emptyNotificheLegaliData.azioni.fascicoli),
      depositoChecklist: text(azioni.depositoChecklist, emptyNotificheLegaliData.azioni.depositoChecklist),
    },
    fontiOperative: Array.isArray(payload.fontiOperative) ? payload.fontiOperative.map((item) => text(item)).filter(Boolean) : [],
  }
}

export async function getNotificheLegaliData(): Promise<NotificheLegaliData> {
  const response = await fetch('/api/v1/ui/notifiche-legali', {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) return emptyNotificheLegaliData
  return normalisePayload(await response.json())
}

export async function getNotificheLegaliPractice(practiceId: string): Promise<LegalPracticeSuggestion | null> {
  if (!practiceId) return null
  const response = await fetch(`/api/v1/ui/notifiche-legali/pratiche/${encodeURIComponent(practiceId)}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) return null
  const body = await response.json().catch(() => ({}))
  if (!isRecord(body) || !bool(body.ok)) return null
  return practiceSuggestions([body.pratica])[0] || null
}

export async function getNotificheLegaliPracticeDocuments(practiceId: string): Promise<LegalDocumentSuggestion[]> {
  if (!practiceId) return []
  const response = await fetch(`/api/v1/ui/notifiche-legali/pratiche/${encodeURIComponent(practiceId)}/documenti`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) return []
  const body = await response.json().catch(() => ({}))
  if (!isRecord(body) || !bool(body.ok)) return []
  return documentSuggestions(body.documenti)
}

export async function postLegalWorkflow(endpoint: string, payload: Record<string, unknown>): Promise<LegalWorkflowResult> {
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(payload),
  })
  const result = resultFromPayload(await response.json().catch(() => ({})))
  if (!response.ok || !result.ok) return result
  return result
}

export async function previewLegalRelata(payload: Record<string, unknown>): Promise<LegalRelataPreviewResult> {
  const response = await fetch('/api/v1/ui/notifiche-legali/anteprima-relata', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(payload),
  })
  const result = previewFromPayload(await response.json().catch(() => ({})))
  if (!response.ok && !result.blockers.length) {
    return { ...result, ok: false, blockers: ['Anteprima non disponibile.'] }
  }
  return result
}

export async function downloadLegalAttestation(
  endpoint: string,
  payload: Record<string, unknown>,
): Promise<{ ok: boolean; message: string }> {
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document, application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const missing = isRecord(body) && Array.isArray(body.missingFields)
      ? body.missingFields.map((item) => text(item)).filter(Boolean)
      : []
    const detail = missing.length ? ` Dati da completare: ${missing.join(', ')}.` : ''
    return {
      ok: false,
      message: `${isRecord(body) ? text(body.message, 'Attestazione non generata.') : 'Attestazione non generata.'}${detail}`,
    }
  }

  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  const filename = encodedName
    ? decodeURIComponent(encodedName)
    : (plainName || 'Attestazione_di_conformita.docx')
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(href), 1000)
  return { ok: true, message: 'Attestazione unica scaricata.' }
}

export async function saveLegalRelataDraft(payload: {
  practiceId?: string
  templateId: string
  relataText: string
  payloadHash?: string
}): Promise<LegalRelataDraftResult> {
  const response = await fetch('/api/v1/ui/notifiche-legali/bozze-relata', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(payload),
  })
  const body = await response.json().catch(() => ({}))
  if (!isRecord(body)) return { ok: false, message: 'Salvataggio bozza non completato.', draftId: '', savedAt: '' }
  return {
    ok: bool(body.ok) && response.ok,
    message: text(body.message, response.ok ? 'Bozza salvata.' : 'Salvataggio bozza non completato.'),
    draftId: text(body.draftId),
    savedAt: text(body.savedAt),
  }
}

export async function saveLegalRelataTemplate(payload: {
  label: string
  description: string
  body: string
  requiresProceeding?: boolean
}): Promise<{ ok: boolean; message: string; template?: LegalTemplateOption }> {
  const response = await fetch('/api/v1/ui/notifiche-legali/modelli-relata', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(payload),
  })
  const body = await response.json().catch(() => ({}))
  if (!isRecord(body)) return { ok: false, message: 'Salvataggio non completato.' }
  const template = templateOptions([body.template])[0]
  return {
    ok: bool(body.ok) && response.ok,
    message: text(body.message, response.ok ? 'Modello salvato.' : 'Salvataggio non completato.'),
    template,
  }
}
