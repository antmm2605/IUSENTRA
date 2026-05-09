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
  const payload = await response.json().catch(() => ({})) as Partial<FormSubmitResult> & { errore?: string; error?: string }
  if (!response.ok || payload.ok === false) {
    throw new Error(String(payload.message || payload.errore || payload.error || 'Operazione non riuscita.'))
  }
  return {
    ok: true,
    message: String(payload.message || 'Operazione completata.'),
    redirect: typeof payload.redirect === 'string' ? payload.redirect : response.redirected ? response.url : '',
    id: typeof payload.id === 'string' ? payload.id : '',
    whatsappLink: typeof payload.whatsappLink === 'string' ? payload.whatsappLink : '',
  }
}

export function redirectAfterSuccess(result: FormSubmitResult, fallback: string): void {
  window.setTimeout(() => {
    window.location.assign(result.redirect || fallback)
  }, 350)
}
