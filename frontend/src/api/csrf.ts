export function getCsrfToken(): string {
  if (typeof document === 'undefined') return ''
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

export function csrfHeader(): Record<string, string> {
  const token = getCsrfToken()
  return token ? { 'X-CSRF-Token': token } : {}
}
