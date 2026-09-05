/** A public website from the register is a navigation link, never executable input. */
export function mediazioneWebsite(value: string): string {
  const raw = value.trim()
  if (!raw || /[\s\\]/.test(raw)) return ''
  try {
    const url = new URL(/^[a-z][a-z\d+.-]*:/i.test(raw) ? raw : `https://${raw}`)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || !url.hostname.includes('.')) return ''
    return url.href
  } catch {
    return ''
  }
}
