export type LegalOption = {
  value: string
  label: string
  needsAttestazione?: boolean
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

export type LegalDocumentSuggestion = {
  id: string
  label: string
  nomeFile: string
  descrizione: string
  origine: string
  hashSha256: string
  dataDocumento: string
  fonte: string
  necessitaAttestazione: boolean
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
  modelloSuggerito: string
}

export type LegalClientSuggestion = {
  id: string
  nome: string
  codiceFiscalePiva: string
  pec: string
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

export type NotificheLegaliData = {
  source: string
  generatedAt: string
  contracts: {
    separateLegalNotification: boolean
    clientCommunicationWithoutRelata: boolean
    depositProofWithOriginalReceipts: boolean
    parametricTemplateEngine: boolean
  }
  templateCatalogVersion: string
  mandatorySubject: string
  defaults: {
    studioNome: string
    avvocatoNome: string
    avvocatoCf: string
    avvocatoForo: string
    studioIndirizzo: string
    studioCitta: string
    mittentePec: string
    fontePecMittente: string
  }
  registriPec: LegalOption[]
  ruoliDestinatario: LegalOption[]
  originiDocumento: LegalOption[]
  modelliRelata: LegalTemplateOption[]
  modelliControllo: LegalTemplateOption[]
  campiDisponibili: LegalTemplateFieldToken[]
  precompilazione: {
    pratiche: LegalPracticeSuggestion[]
    clienti: LegalClientSuggestion[]
    destinatari: LegalRecipientSuggestion[]
    note: string[]
  }
  azioni: {
    notifica: string
    comunicazioneCliente: string
    provaDeposito: string
    pecCompose: string
    clientCompose: string
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
  },
  templateCatalogVersion: '',
  mandatorySubject: 'notificazione ai sensi della legge n. 53 del 1994',
  defaults: {
    studioNome: '',
    avvocatoNome: '',
    avvocatoCf: '',
    avvocatoForo: '',
    studioIndirizzo: '',
    studioCitta: '',
    mittentePec: '',
    fontePecMittente: 'ReGIndE',
  },
  registriPec: [],
  ruoliDestinatario: [],
  originiDocumento: [],
  modelliRelata: [],
  modelliControllo: [],
  campiDisponibili: [],
  precompilazione: {
    pratiche: [],
    clienti: [],
    destinatari: [],
    note: [],
  },
  azioni: {
    notifica: '/api/v1/ui/notifiche-legali/notifica',
    comunicazioneCliente: '/api/v1/ui/notifiche-legali/comunicazione-cliente',
    provaDeposito: '/api/v1/ui/notifiche-legali/prova-deposito',
    pecCompose: '/email/scrivi?tipo=notifica_l53',
    clientCompose: '/email-ordinaria/scrivi?tipo=comunicazione_cliente',
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

function documentSuggestions(value: unknown): LegalDocumentSuggestion[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: text(row.id),
      label: text(row.label, text(row.nomeFile)),
      nomeFile: text(row.nomeFile),
      descrizione: text(row.descrizione),
      origine: text(row.origine, 'originale_informatico'),
      hashSha256: text(row.hashSha256),
      dataDocumento: text(row.dataDocumento),
      fonte: text(row.fonte),
      necessitaAttestazione: bool(row.necessitaAttestazione),
    }
  }).filter((item) => item.id && item.label)
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
      modelloSuggerito: text(row.modelloSuggerito, 'relata_pec_base_l53'),
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

function normalisePayload(payload: unknown): NotificheLegaliData {
  if (!isRecord(payload)) return emptyNotificheLegaliData
  const defaults = isRecord(payload.defaults) ? payload.defaults : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  const azioni = isRecord(payload.azioni) ? payload.azioni : {}
  const precompilazione = isRecord(payload.precompilazione) ? payload.precompilazione : {}
  return {
    source: text(payload.source, 'configurazione_studio'),
    generatedAt: text(payload.generatedAt),
    contracts: {
      separateLegalNotification: bool(contracts.separateLegalNotification),
      clientCommunicationWithoutRelata: bool(contracts.clientCommunicationWithoutRelata),
      depositProofWithOriginalReceipts: bool(contracts.depositProofWithOriginalReceipts),
      parametricTemplateEngine: bool(contracts.parametricTemplateEngine),
    },
    templateCatalogVersion: text(payload.templateCatalogVersion),
    mandatorySubject: text(payload.mandatorySubject, emptyNotificheLegaliData.mandatorySubject),
    defaults: {
      studioNome: text(defaults.studioNome),
      avvocatoNome: text(defaults.avvocatoNome),
      avvocatoCf: text(defaults.avvocatoCf),
      avvocatoForo: text(defaults.avvocatoForo),
      studioIndirizzo: text(defaults.studioIndirizzo),
      studioCitta: text(defaults.studioCitta),
      mittentePec: text(defaults.mittentePec),
      fontePecMittente: text(defaults.fontePecMittente, 'ReGIndE'),
    },
    registriPec: options(payload.registriPec),
    ruoliDestinatario: options(payload.ruoliDestinatario),
    originiDocumento: options(payload.originiDocumento),
    modelliRelata: templateOptions(payload.modelliRelata),
    modelliControllo: templateOptions(payload.modelliControllo),
    campiDisponibili: fieldTokens(payload.campiDisponibili),
    precompilazione: {
      pratiche: practiceSuggestions(precompilazione.pratiche),
      clienti: clientSuggestions(precompilazione.clienti),
      destinatari: recipientSuggestions(precompilazione.destinatari),
      note: Array.isArray(precompilazione.note) ? precompilazione.note.map((item) => text(item)).filter(Boolean) : [],
    },
    azioni: {
      notifica: text(azioni.notifica, emptyNotificheLegaliData.azioni.notifica),
      comunicazioneCliente: text(azioni.comunicazioneCliente, emptyNotificheLegaliData.azioni.comunicazioneCliente),
      provaDeposito: text(azioni.provaDeposito, emptyNotificheLegaliData.azioni.provaDeposito),
      pecCompose: text(azioni.pecCompose, emptyNotificheLegaliData.azioni.pecCompose),
      clientCompose: text(azioni.clientCompose, emptyNotificheLegaliData.azioni.clientCompose),
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
