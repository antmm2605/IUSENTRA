import type { FascicoloDocument } from '../../fascicoliData'

export type DocumentSortKey = 'data_documento_desc' | 'data_documento_asc' | 'caricamento_desc' | 'caricamento_asc' | 'nome_asc'

export const DEFAULT_DOCUMENT_SORT: DocumentSortKey = 'data_documento_desc'

export const DOCUMENT_SORT_OPTIONS: ReadonlyArray<{ value: DocumentSortKey; label: string }> = [
  { value: 'data_documento_desc', label: 'Data documento · più recenti' },
  { value: 'data_documento_asc', label: 'Data documento · meno recenti' },
  { value: 'caricamento_desc', label: 'Caricamento · ultimi caricati' },
  { value: 'caricamento_asc', label: 'Caricamento · primi caricati' },
  { value: 'nome_asc', label: 'Nome · dalla A alla Z' },
]

const ITALIAN_MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']

export function isDocumentSortKey(value: unknown): value is DocumentSortKey {
  return DOCUMENT_SORT_OPTIONS.some((option) => option.value === value)
}

export function normaliseSearchText(value: string): string {
  return String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

/** Converte le date del payload (gg/mm/aaaa, ISO o parsabili) in timestamp; 0 se assente. */
export function parseDocumentDate(value: string): number {
  const raw = String(value || '').trim()
  if (!raw) return 0
  const italian = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/)
  if (italian) {
    const [, day, month, year, hour = '0', minute = '0', second = '0'] = italian
    return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second))
  }
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?/)
  if (iso) {
    const [, year, month, day, hour = '0', minute = '0', second = '0'] = iso
    return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second))
  }
  const parsed = Date.parse(raw)
  return Number.isFinite(parsed) ? parsed : 0
}

export function documentDateTimestamp(doc: FascicoloDocument): number {
  return parseDocumentDate(doc.documentDate) || parseDocumentDate(doc.portalDate) || parseDocumentDate(doc.uploadedAt)
}

export function documentUploadTimestamp(doc: FascicoloDocument): number {
  return parseDocumentDate(doc.uploadedAt) || parseDocumentDate(doc.portalDate) || parseDocumentDate(doc.documentDate)
}

function compareNames(a: FascicoloDocument, b: FascicoloDocument): number {
  return normaliseSearchText(a.name).localeCompare(normaliseSearchText(b.name), 'it', { numeric: true })
}

/** I documenti senza data restano sempre in fondo, qualunque sia la direzione scelta. */
function compareTimestamps(left: number, right: number, direction: 'asc' | 'desc'): number {
  if (!left && !right) return 0
  if (!left) return 1
  if (!right) return -1
  return direction === 'desc' ? right - left : left - right
}

export function compareDocuments(sort: DocumentSortKey, a: FascicoloDocument, b: FascicoloDocument): number {
  let result = 0
  if (sort === 'data_documento_desc' || sort === 'data_documento_asc') {
    result = compareTimestamps(documentDateTimestamp(a), documentDateTimestamp(b), sort.endsWith('desc') ? 'desc' : 'asc')
  } else if (sort === 'caricamento_desc' || sort === 'caricamento_asc') {
    result = compareTimestamps(documentUploadTimestamp(a), documentUploadTimestamp(b), sort.endsWith('desc') ? 'desc' : 'asc')
  }
  return result || compareNames(a, b)
}

/** Varianti testuali di una data: "08/03/2024", "03/2024", "2024", "marzo 2024", "8 marzo 2024". */
function dateSearchVariants(value: string): string[] {
  const match = String(value || '').trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/)
  if (!match) return value ? [value] : []
  const [, day, month, year] = match
  const monthName = ITALIAN_MONTHS[Number(month) - 1] || ''
  const paddedMonth = month.padStart(2, '0')
  return [value, `${paddedMonth}/${year}`, year, `${monthName} ${year}`, `${Number(day)} ${monthName} ${year}`]
}

export function buildDocumentHaystack(doc: FascicoloDocument, extra: string[] = []): string {
  return normaliseSearchText([
    doc.name,
    doc.type,
    doc.rawType,
    doc.catalogLabel,
    doc.catalogRole,
    doc.source,
    doc.portalName,
    doc.portalClass,
    doc.portalSender,
    doc.statusLabel,
    doc.notes,
    ...(doc.tags || []),
    ...dateSearchVariants(doc.documentDate),
    ...dateSearchVariants(doc.uploadedAt),
    ...dateSearchVariants(doc.portalDate),
    ...extra,
  ].filter(Boolean).join(' • '))
}

export function searchTerms(query: string): string[] {
  return normaliseSearchText(query).split(/\s+/).map((term) => term.trim()).filter(Boolean)
}

/** Tutti i termini devono comparire (AND), senza distinzione di maiuscole e accenti. */
export function matchesSearchTerms(haystack: string, terms: string[]): boolean {
  return terms.every((term) => haystack.includes(term))
}
