import { useId } from 'react'
import { ArrowDownUp, Search, X } from 'lucide-react'
import { DOCUMENT_SORT_OPTIONS, isDocumentSortKey } from './documentListOrdering'
import type { DocumentListControls, DocumentStatusFilter } from './useDocumentListControls'
import './documentListToolbar.css'

export type DocumentSectionOption = { id: string; label: string }

const STATUS_OPTIONS: ReadonlyArray<{ id: DocumentStatusFilter; label: string }> = [
  { id: 'tutti', label: 'Tutti gli stati' },
  { id: 'da_firmare', label: 'Da firmare' },
  { id: 'da_verificare', label: 'Da verificare' },
]

export function DocumentListToolbar<T>({
  controls,
  sections,
  visibleCount,
}: {
  controls: DocumentListControls<T>
  sections: DocumentSectionOption[]
  visibleCount: number
}) {
  const searchId = useId()
  const sortId = useId()
  const hintId = useId()
  const { query, setQuery, sort, setSort, section, setSection, status, setStatus, searchRef, total, sectionCounts, statusCounts, filtersActive, resetFilters } = controls
  const sectionTotal = Array.from(sectionCounts.values()).reduce((sum, value) => sum + value, 0)
  const availableSections = sections.filter((option) => (sectionCounts.get(option.id) || 0) > 0 || option.id === section)

  return (
    <div className="iu-doclist-toolbar" role="search" aria-label="Ricerca e ordinamento documenti del fascicolo">
      <div className="iu-doclist-toolbar__main">
        <label className="iu-doclist-toolbar__search" htmlFor={searchId}>
          <Search size={16} aria-hidden="true"/>
          <span className="iu-doclist-toolbar__sr">Cerca nei documenti</span>
          <input
            id={searchId}
            ref={searchRef}
            type="search"
            value={query}
            autoComplete="off"
            spellCheck={false}
            placeholder="Cerca nome, tipo, nota o data (es. procura marzo 2024)"
            aria-describedby={hintId}
            onChange={(event) => setQuery(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape' && query) {
                event.preventDefault()
                setQuery('')
              }
            }}
          />
          {query ? (
            <button type="button" className="iu-doclist-toolbar__clear" onClick={() => { setQuery(''); searchRef.current?.focus() }} aria-label="Cancella ricerca" title="Cancella ricerca">
              <X size={14} aria-hidden="true"/>
            </button>
          ) : <kbd aria-hidden="true" title="Premi / per cercare">/</kbd>}
        </label>
        <label className="iu-doclist-toolbar__sort" htmlFor={sortId}>
          <ArrowDownUp size={15} aria-hidden="true"/>
          <span className="iu-doclist-toolbar__sr">Ordina documenti</span>
          <select id={sortId} value={sort} onChange={(event) => { const next = event.currentTarget.value; if (isDocumentSortKey(next)) setSort(next) }}>
            {DOCUMENT_SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
      </div>
      <div className="iu-doclist-toolbar__chips" aria-label="Filtra per sezione">
        <button type="button" aria-pressed={section === 'tutte'} onClick={() => setSection('tutte')}>
          Tutte le sezioni <b>{sectionTotal}</b>
        </button>
        {availableSections.map((option) => (
          <button key={option.id} type="button" aria-pressed={section === option.id} onClick={() => setSection(section === option.id ? 'tutte' : option.id)}>
            {option.label} <b>{sectionCounts.get(option.id) || 0}</b>
          </button>
        ))}
      </div>
      <div className="iu-doclist-toolbar__chips iu-doclist-toolbar__chips--status" aria-label="Filtra per stato">
        {STATUS_OPTIONS.map((option) => (
          <button key={option.id} type="button" aria-pressed={status === option.id} onClick={() => setStatus(status === option.id && option.id !== 'tutti' ? 'tutti' : option.id)}>
            {option.label} <b>{statusCounts[option.id]}</b>
          </button>
        ))}
      </div>
      <p id={hintId} className="iu-doclist-toolbar__result" aria-live="polite">
        <span>{filtersActive ? `${visibleCount} di ${total} documenti` : `${total} documenti`} · {DOCUMENT_SORT_OPTIONS.find((option) => option.value === sort)?.label.toLowerCase()}</span>
        {filtersActive ? <button type="button" onClick={resetFilters}>Azzera filtri</button> : <small>Premi / per cercare, Esc per cancellare.</small>}
      </p>
    </div>
  )
}
