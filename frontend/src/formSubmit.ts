export type FormSubmitResult = {
  ok: boolean
  message?: string
  redirect?: string
  id?: string
  whatsappLink?: string
}

export function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
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
      : response.redirected
        ? response.url
        : ''
  return {
    ok: true,
    message: String(payload.message || 'Operazione completata.'),
    redirect,
    id: typeof payload.id === 'string' ? payload.id : '',
    whatsappLink: typeof payload.whatsappLink === 'string' ? payload.whatsappLink : '',
  }
}

export function redirectAfterSuccess(result: FormSubmitResult, fallback: string): void {
  window.setTimeout(() => {
    window.location.assign(result.redirect || fallback)
  }, 350)
}
