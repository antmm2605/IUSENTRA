export type FormSubmitResult = {
  ok: boolean
  message?: string
  redirect?: string
  editor_url?: string
  editorUrl?: string
  signature_url?: string
  signatureUrl?: string
  requires_confirmation?: boolean
  compliance_state?: string
  created_as?: string
  id?: string
  document_id?: string
  redirect_url?: string
  testo_generato?: string
  text?: string
  contenuto?: string
  content?: string
  filename?: string
  fonts?: string[]
  detectedFonts?: string[]
  encoding?: string
  codifica?: string
  note?: string
  tipo?: string
  errore?: string
  error?: string
  whatsappLink?: string
}

export function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.map((item) => String(item || '').trim()).filter(Boolean)
}

export async function submitFormJson(endpoint: string, formData: FormData): Promise<FormSubmitResult> {
  const token = csrfToken()
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: formData,
  })
  const contentType = response.headers.get('content-type') || ''
  const rawText = contentType.includes('application/json') ? '' : await response.text().catch(() => '')
  const payload = contentType.includes('application/json')
    ? await response.json().catch(() => ({})) as Partial<FormSubmitResult> & { errore?: string; error?: string; redirect_url?: string }
    : {} as Partial<FormSubmitResult> & { errore?: string; error?: string; redirect_url?: string }
  const visibleText = rawText
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!response.ok || payload.ok === false) {
    throw new Error(String(payload.message || payload.errore || payload.error || visibleText || 'Non ho potuto completare l\'operazione: controlla i campi richiesti e riprova.'))
  }
  const redirect = typeof payload.redirect === 'string'
    ? payload.redirect
    : typeof payload.redirect_url === 'string'
      ? payload.redirect_url
      : typeof payload.editor_url === 'string'
        ? payload.editor_url
      : response.redirected
        ? response.url
        : ''
  return {
    ok: true,
    message: String(payload.message || 'Operazione completata.'),
    redirect,
    editor_url: typeof payload.editor_url === 'string' ? payload.editor_url : '',
    editorUrl: typeof payload.editor_url === 'string' ? payload.editor_url : '',
    signature_url: typeof payload.signature_url === 'string' ? payload.signature_url : '',
    signatureUrl: typeof payload.signature_url === 'string' ? payload.signature_url : '',
    requires_confirmation: payload.requires_confirmation === true,
    compliance_state: typeof payload.compliance_state === 'string' ? payload.compliance_state : '',
    created_as: typeof payload.created_as === 'string' ? payload.created_as : '',
    id: typeof payload.id === 'string' ? payload.id : '',
    document_id: typeof payload.document_id === 'string' ? payload.document_id : '',
    redirect_url: typeof payload.redirect_url === 'string' ? payload.redirect_url : '',
    testo_generato: typeof payload.testo_generato === 'string' ? payload.testo_generato : '',
    text: typeof payload.text === 'string' ? payload.text : '',
    contenuto: typeof payload.contenuto === 'string' ? payload.contenuto : '',
    content: typeof payload.content === 'string' ? payload.content : '',
    filename: typeof payload.filename === 'string' ? payload.filename : '',
    fonts: stringArray(payload.fonts),
    detectedFonts: stringArray(payload.detectedFonts),
    encoding: typeof payload.encoding === 'string' ? payload.encoding : '',
    codifica: typeof payload.codifica === 'string' ? payload.codifica : '',
    note: typeof payload.note === 'string' ? payload.note : '',
    tipo: typeof payload.tipo === 'string' ? payload.tipo : '',
    errore: typeof payload.errore === 'string' ? payload.errore : '',
    error: typeof payload.error === 'string' ? payload.error : '',
    whatsappLink: typeof payload.whatsappLink === 'string' ? payload.whatsappLink : '',
  }
}

export function redirectAfterSuccess(result: FormSubmitResult, fallback: string): void {
  window.setTimeout(() => {
    window.location.assign(result.redirect || fallback)
  }, 350)
}
