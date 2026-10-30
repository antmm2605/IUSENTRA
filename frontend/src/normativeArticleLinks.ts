/** Destinazioni di sola lettura: il testo viene risolto dal repository pubblico, mai dal browser. */
export function articleNumbers(reference: string): string[] {
  const value = String(reference || '').trim()
  if (/^\d{1,5}(?:[ .-]?[a-z]{2,24})?(?:\.\d{1,4})?$/i.test(value)) return [value]
  const match = value.match(/\bart(?:t|icoli|icolo)?\.?\s+(\d[^;()]*?)(?=\s+(?:c\.|codice|l\.|legge|d\.|del\b|della\b)|$)/i)
  if (!match) return []
  const group = match[1].replace(/\s+(?:comma|commi|co\.).*$/i, '')
  // Non interpretare il numero della legge o l'anno come un altro articolo.
  if (/\//.test(group)) return []
  return [...new Set(group.split(/\s*[,;]\s*|\s+e\s+/).map(s => s.trim()).filter(s => /^\d{1,5}(?:[ .-]?[a-z]{2,24})?(?:\.\d{1,4})?$/i.test(s)))]
}
export function normativeReaderHref({ url = '', article = '', act = '', id = 0, sha = '' }: { url?: string; article?: string; act?: string; id?: number; sha?: string }) {
  const pointed = url.match(/~art([0-9]+(?:[a-z]+)?(?:\.[0-9]+)?)/i)?.[1] || ''
  const number = articleNumbers(article || pointed)
  if (!id && number.length !== 1) return ''
  const params = new URLSearchParams()
  if (id) params.set('id', String(id))
  if (number.length === 1) params.set('articolo', number[0])
  if (act) params.set('atto', act)
  if (url) params.set('url', url)
  if (sha) params.set('sha', sha)
  return `/api/v1/ui/ricerca-legale/normativa/visualizza?${params}`
}
