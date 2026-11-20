import { useId } from 'react'
import { ArrowDownUp, BookmarkCheck, RotateCcw, Search, X } from 'lucide-react'
import { DOCUMENT_SORT_OPTIONS, isDocumentSortKey } from './documentListOrdering'
import type { DocumentListControls, DocumentStatusFilter } from './useDocumentListControls'
import './documentListToolbar.css'

export type DocumentSectionOption = { id: string; label: string }

// «Senza firma digitale»: la firma si verifica in automatico sui byte di ogni file (busta CAdES/.p7m e firma PAdES).
// Copie, PEC e ricevute di norma non hanno firma: non è un difetto, la firma serve agli atti che lo studio deposita.
const STATUS_OPTIONS: ReadonlyArray<{ id: DocumentStatusFilter; label: string; title: string }> = [
  { id: 'tutti', label: 'Tutti gli stati', title: 'Tutti i documenti del fascicolo (le bozze dello studio sono a parte)' },
  { id: 'da_firmare', label: 'Senza firma digitale', title: 'File senza una firma digitale valida: la verifica è automatica sul contenuto (CAdES/.p7m e PAdES). Per copie, PEC e ricevute è la condizione normale; la firma serve solo agli atti da depositare o notificare.' },
  { id: 'da_verificare', label: 'Da confermare o verificare', title: 'Proposte di catalogazione sotto la soglia di certezza e documenti da verificare' },
]

export function DocumentListToolbar<T>({
  controls,
  sections,
  visibleCount,
  catalogoDisponibile,
}: {
  controls: DocumentListControls<T>
  sections: DocumentSectionOption[]
  visibleCount: number
  catalogoDisponibile: boolean
}) {
  const searchId = useId()
  const sortId = useId()
  const hintId = useId()
  const { query, setQuery, sort, setSort, section, setSection, status, setStatus, searchRef, total, sectionCounts, statusCounts, filtersActive, resetFilters, searchMode, relevanceActive } = controls
  const { vistaConfigurata, vistaModificata, vistaStato, vistaMessaggio, salvaVista, ripristinaVista } = controls
  const vistaOccupata = vistaStato !== 'inattivo'
  const orderLabel = relevanceActive ? 'ordinati per pertinenza' : DOCUMENT_SORT_OPTIONS.find((option) => option.value === sort)?.label.toLowerCase()
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
            placeholder="Cerca nome, tipo, sigla o data (es. DI, PEC giugno 2026, procura)"
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
          ) : null}
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
          <button key={option.id} type="button" title={option.title} aria-pressed={status === option.id} disabled={option.id === 'da_verificare' && !catalogoDisponibile} onClick={() => setStatus(status === option.id && option.id !== 'tutti' ? 'tutti' : option.id)}>
            {option.label} {option.id !== 'da_verificare' || catalogoDisponibile ? <b>{statusCounts[option.id]}</b> : null}
          </button>
        ))}
        {statusCounts.firma_non_confermata ? <span className="iu-doclist-toolbar__firma-avviso" role="note">{statusCounts.firma_non_confermata === 1 ? '1 file ha una firma che la verifica non conferma' : `${statusCounts.firma_non_confermata} file hanno una firma che la verifica non conferma`}</span> : null}
      </div>
      <div className="iu-doclist-toolbar__vista">
        {/* La vista salvata vale per tutti i fascicoli: si salva quando l'avvocato
            lo chiede, non si registra da sola mentre naviga. */}
        <button
          type="button"
          className="iu-doclist-toolbar__save"
          disabled={vistaOccupata || !vistaModificata}
          onClick={() => { void salvaVista() }}
          title={vistaModificata ? 'Apri i fascicoli con ordinamento e filtri attuali' : 'La vista a schermo è già quella salvata'}
        >
          <BookmarkCheck size={15} aria-hidden="true"/>
          {vistaStato === 'salvo' ? 'Salvataggio…' : 'Salva impostazioni'}
        </button>
        {vistaConfigurata ? (
          <button
            type="button"
            className="iu-doclist-toolbar__reset-view"
            disabled={vistaOccupata}
            onClick={() => { void ripristinaVista() }}
            title="Torna alla vista predefinita di IUSENTRA"
          >
            <RotateCcw size={14} aria-hidden="true"/>Ripristina predefinita
          </button>
        ) : null}
        <span className="iu-doclist-toolbar__vista-nota" role="status" aria-live="polite">
          {vistaMessaggio || (vistaConfigurata
            ? (vistaModificata ? 'Vista modificata rispetto a quella salvata.' : 'Vista dello studio applicata.')
            : 'Salva ordinamento e filtri come vista predefinita dello studio.')}
        </span>
      </div>
      <p id={hintId} className="iu-doclist-toolbar__result" aria-live="polite">
        <span>
          {filtersActive ? `${visibleCount} di ${total} ${total === 1 ? 'documento' : 'documenti'}` : `${total} ${total === 1 ? 'documento' : 'documenti'}`} · {orderLabel}
          {searchMode === 'simili' ? <em className="iu-doclist-toolbar__similar"> · nessun documento contiene tutti i termini: mostro i più simili</em> : null}
        </span>
        {filtersActive ? <button type="button" onClick={resetFilters}>Azzera filtri</button> : null}
      </p>
    </div>
  )
}
