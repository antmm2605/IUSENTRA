import { apiJson } from './api/client'
import { csrfHeader } from './api/csrf'
import { clientPortalPost, readClientPortalToken, type ClientPortalResponse } from './clientPortalData'

export type SigningStepStatus =
  | 'da_fare'
  | 'in_attesa'
  | 'in_revisione'
  | 'completato'
  | 'rifiutato'

export type SigningStep = {
  key: string
  title: string
  status: SigningStepStatus
}

export type PreventivoSummary = {
  id: string
  numero: string
  oggetto: string
  stato: string
  versione: number
  totale: number
  dataEmissione: string
  dataScadenza: string
  documentId: string
  pdfSha256: string
  highlighted: boolean
  accettatoIl: string
}

export type ConferimentoState = {
  available: boolean
  id: string
  numero: string
  oggetto: string
  stato: string
  documentId: string
  pdfSha256: string
  missingClientData: string[]
  requisiti: string[]
  preventivoId?: string
}

export type SigningConsent = { key: string; text: string }

export type SigningConsentsPayload = {
  version: string
  identity: SigningConsent
  preventivo: SigningConsent
  conferimento: SigningConsent
  signing: SigningConsent[]
  manualUploadDeclaration: string
}

export type IdentityState = {
  consentAccepted: boolean
  document: Record<string, unknown> | null
}

export type SignatureState = {
  firmaEseguita: boolean
  firmaVia: string
  signedDocument: Record<string, unknown> | null
}

export type SigningOverview = {
  ok: boolean
  code?: string
  message?: string
  steps: SigningStep[]
  preventivi: PreventivoSummary[]
  conferimento: ConferimentoState
  signature: SignatureState
  identity: IdentityState
  consents: SigningConsentsPayload
  otpStepUp: boolean
  qualifiedSignature: { available: boolean; note: string }
}

export type SignPosition = {
  pageIndex: number
  xMm: number
  yMm: number
  widthMm: number
  heightMm: number
}

export type SigningReceipt = {
  ok: boolean
  message?: string
  receipt?: Record<string, unknown>
  steps?: SigningStep[]
}

export const emptySigningOverview: SigningOverview = {
  ok: false,
  steps: [],
  preventivi: [],
  conferimento: {
    available: false,
    id: '',
    numero: '',
    oggetto: '',
    stato: '',
    documentId: '',
    pdfSha256: '',
    missingClientData: [],
    requisiti: [],
  },
  signature: { firmaEseguita: false, firmaVia: '', signedDocument: null },
  identity: { consentAccepted: false, document: null },
  consents: {
    version: '',
    identity: { key: '', text: '' },
    preventivo: { key: '', text: '' },
    conferimento: { key: '', text: '' },
    signing: [],
    manualUploadDeclaration: '',
  },
  otpStepUp: false,
  qualifiedSignature: { available: false, note: '' },
}

type SigningResponse = ClientPortalResponse<{ overview?: SigningOverview; signedDocumentId?: string }>

export async function loadSigningOverview(token = readClientPortalToken()): Promise<SigningOverview> {
  if (!token) return emptySigningOverview
  return apiJson<SigningOverview>('/api/v1/ui/client-portal/public/signing/overview', emptySigningOverview, {
    headers: { 'X-Client-Portal-Token': token },
  })
}

export async function acceptPreventivo(
  preventivoId: string,
  body: { accepted: boolean; pdfSha256: string; declaration?: string },
): Promise<SigningResponse> {
  return clientPortalPost<SigningResponse>(
    `/api/v1/ui/client-portal/public/signing/preventivi/${encodeURIComponent(preventivoId)}/accept`,
    body,
  )
}

export async function declinePreventivo(preventivoId: string, reason: string): Promise<SigningResponse> {
  return clientPortalPost<SigningResponse>(
    `/api/v1/ui/client-portal/public/signing/preventivi/${encodeURIComponent(preventivoId)}/decline`,
    { reason },
  )
}

export async function signConferimento(
  conferimentoId: string,
  body: {
    mode: 'canvas' | 'typed' | 'image'
    signatureImage?: string
    typedName?: string
    consents: Record<string, boolean>
    position: SignPosition
    pdfSha256: string
    declaration?: string
  },
): Promise<SigningResponse> {
  return clientPortalPost<SigningResponse>(
    `/api/v1/ui/client-portal/public/signing/conferimento/${encodeURIComponent(conferimentoId)}/sign`,
    body,
  )
}

async function postSigningForm(url: string, form: FormData, token = readClientPortalToken()): Promise<SigningResponse> {
  try {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        ...csrfHeader(),
        ...(token ? { 'X-Client-Portal-Token': token } : {}),
      },
      body: form,
    })
    return (await response.json()) as SigningResponse
  } catch {
    return { ok: false, message: 'Operazione non completata.' } as SigningResponse
  }
}

export async function uploadSignedConferimento(
  conferimentoId: string,
  file: File,
  consents: Record<string, boolean>,
  declaration: string,
): Promise<SigningResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('declaration', declaration)
  Object.entries(consents).forEach(([key, value]) => {
    form.append(key, value ? 'true' : 'false')
  })
  return postSigningForm(
    `/api/v1/ui/client-portal/public/signing/conferimento/${encodeURIComponent(conferimentoId)}/upload-signed`,
    form,
  )
}

export async function uploadIdentityDocument(file: File | Blob, filename?: string): Promise<SigningResponse> {
  const form = new FormData()
  if (file instanceof File) {
    form.append('file', file)
  } else {
    form.append('file', file, filename || 'documento-identita.jpg')
  }
  return postSigningForm('/api/v1/ui/client-portal/public/signing/identity-document', form)
}

export async function startSigningOtp(): Promise<ClientPortalResponse<{ expiresMinutes?: number }>> {
  return clientPortalPost('/api/v1/ui/client-portal/public/signing/otp/start', {})
}

export async function verifySigningOtp(code: string): Promise<ClientPortalResponse> {
  return clientPortalPost('/api/v1/ui/client-portal/public/signing/otp/verify', { code })
}

export async function loadSigningReceipt(token = readClientPortalToken()): Promise<SigningReceipt> {
  if (!token) return { ok: false }
  return apiJson<SigningReceipt>('/api/v1/ui/client-portal/public/signing/receipt', { ok: false }, {
    headers: { 'X-Client-Portal-Token': token },
  })
}

export async function reviewStudioDocument(
  documentId: string,
  decision: 'approvato' | 'respinto',
  note = '',
): Promise<ClientPortalResponse> {
  const { apiPostJson } = await import('./api/client')
  return apiPostJson(
    `/api/v1/ui/client-portal/studio/documents/${encodeURIComponent(documentId)}/review`,
    { decision, note },
    { ok: false, message: 'Revisione non registrata.' },
  )
}
