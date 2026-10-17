import type { TemplateAttiRecord } from './templateAttiData'

export type CatalogScope = 'all' | 'catalogo' | 'studio' | 'precompilabili' | 'verifica'
export const CATALOG_SCOPES: Array<{ id: CatalogScope; label: string; note: string }> = [
  { id: 'all', label: 'Tutti i modelli', note: 'Catalogo e modelli dello studio' },
  { id: 'catalogo', label: 'Catalogo', note: 'Modelli del catalogo professionale' },
  { id: 'studio', label: 'Studio', note: 'Modelli disponibili allo studio' },
  { id: 'precompilabili', label: 'Precompilabili', note: 'Predisposti per i dati della pratica' },
  { id: 'verifica', label: 'Da verificare', note: 'Fonti o regole da verificare' },
]

export function matchesCatalogScope(record: TemplateAttiRecord, scope: CatalogScope): boolean {
  if (scope === 'catalogo' || scope === 'studio') return record.kind === scope
  if (scope === 'precompilabili') return record.prefillStatus === 'precompilabile'
  if (scope === 'verifica') return record.requiresLawyerReview
  return true
}

export function catalogScopeCounts(records: TemplateAttiRecord[]) {
  return CATALOG_SCOPES.map(scope => ({ ...scope, count: records.filter(record => matchesCatalogScope(record, scope.id)).length }))
}

export function catalogPage(records: TemplateAttiRecord[], requestedPage: number) {
  const size = 24
  const totalPages = Math.max(1, Math.ceil(records.length / size))
  const page = Math.min(totalPages, Math.max(1, Number.isFinite(requestedPage) ? Math.trunc(requestedPage) : 1))
  const offset = (page - 1) * size
  return { page, totalPages, items: records.slice(offset, offset + size), start: records.length ? offset + 1 : 0, end: Math.min(offset + size, records.length) }
}

export function catalogScopeFromQuery(search: string): CatalogScope {
  const scope = new URLSearchParams(search).get('scope')
  return CATALOG_SCOPES.some(item => item.id === scope) ? scope as CatalogScope : 'all'
}
