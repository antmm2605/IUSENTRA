export type LegalOption = {
  value: string
  label: string
  needsAttestazione?: boolean
}

export type LegalWorkflowResult = {
  ok: boolean
  blockers: string[]
  warnings: string[]
  subject: string
  body: string
  relataText: string
  nextActions: string[]
  message?: string
}

export type NotificheLegaliData = {
  source: string
  generatedAt: string
  contracts: {
    separateLegalNotification: boolean
    clientCommunicationWithoutRelata: boolean
    depositProofWithOriginalReceipts: boolean
  }
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
}

export const emptyNotificheLegaliData: NotificheLegaliData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: {
    separateLegalNotification: true,
    clientCommunicationWithoutRelata: true,
    depositProofWithOriginalReceipts: true,
  },
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
    message: text(payload.message),
  }
}

function normalisePayload(payload: unknown): NotificheLegaliData {
  if (!isRecord(payload)) return emptyNotificheLegaliData
  const defaults = isRecord(payload.defaults) ? payload.defaults : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  const azioni = isRecord(payload.azioni) ? payload.azioni : {}
  return {
    source: text(payload.source, 'configurazione_studio'),
    generatedAt: text(payload.generatedAt),
    contracts: {
      separateLegalNotification: bool(contracts.separateLegalNotification),
      clientCommunicationWithoutRelata: bool(contracts.clientCommunicationWithoutRelata),
      depositProofWithOriginalReceipts: bool(contracts.depositProofWithOriginalReceipts),
    },
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
