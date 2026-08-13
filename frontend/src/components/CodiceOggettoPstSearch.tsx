import { useDeferredValue, useId, useMemo, useState } from 'react'
import { CheckCircle2, FolderTree, Search, X } from 'lucide-react'
import {
  CODICI_OGGETTO_PST,
  CODICI_OGGETTO_PST_CATALOG,
  findCodiceOggettoPst,
  type CodiceOggettoPstRecord,
} from '../data/praticheCollegateCatalog'
import { Badge } from '../ui/Badge'
import './CodiceOggettoPstSearch.css'

type CodiceOggettoPstSearchProps = {
  value: string
  name?: string
  id?: string
  label?: string
  help?: string
  placeholder?: string
  className?: string
  onChange: (codice: string, label: string, record?: CodiceOggettoPstRecord) => void
}

const searchIndex = CODICI_OGGETTO_PST.map((item) => ({
  item,
  haystack: normalize([
    item.codice,
    item.descrizione,
    ...(item.descrizioniAlternative || []),
    item.area,
    item.codicePadre,
    item.descrizionePadre,
    item.registri.join(' '),
  ].join(' ')),
}))

const MAX_VISIBLE_RESULTS = 40

type CatalogFilter = {
  area: string
  group: string
  register: string
}

type CatalogOption = {
  value: string
  label: string
  count: number
}

type SearchOutcome = {
  items: CodiceOggettoPstRecord[]
  total: number
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[^\p{Letter}\p{Number}]+/gu, ' ')
    .trim()
}

function score(item: CodiceOggettoPstRecord, normalized: string, tokens: string[]): number {
  const codice = item.codice.toLowerCase()
  const description = normalize(item.descrizione)
  let total = 0
  if (codice === normalized) total += 180
  if (codice.startsWith(normalized)) total += 90
  if (description.startsWith(normalized)) total += 60
  for (const token of tokens) {
    if (codice === token) total += 80
    else if (codice.startsWith(token)) total += 45
    if (description.includes(token)) total += 22
    if (normalize(item.area).includes(token)) total += 12
    if (normalize(item.descrizionePadre).includes(token)) total += 10
  }
  return total
}

function classificationKey(item: CodiceOggettoPstRecord): string {
  return `${item.area}::${item.codicePadre || 'senza-gruppo'}`
}

function groupLabel(item: CodiceOggettoPstRecord): string {
  if (item.descrizionePadre) return item.descrizionePadre
  if (item.codicePadre) return `Gruppo ${item.codicePadre}`
  return 'Altri procedimenti'
}

function matchesFilter(item: CodiceOggettoPstRecord, filter: CatalogFilter): boolean {
  return (!filter.area || item.area === filter.area)
    && (!filter.group || classificationKey(item) === filter.group)
    && (!filter.register || item.registri.includes(filter.register))
}

function searchCodici(
  query: string,
  selected: CodiceOggettoPstRecord | undefined,
  filter: CatalogFilter,
): SearchOutcome {
  const normalized = normalize(query)
  const filteredIndex = searchIndex.filter(({ item }) => matchesFilter(item, filter))
  if (!normalized) {
    if (filter.area || filter.group || filter.register) {
      const items = filteredIndex
        .map(({ item }) => item)
        .sort((left, right) => left.codice.localeCompare(right.codice, 'it'))
      return { items: items.slice(0, MAX_VISIBLE_RESULTS), total: items.length }
    }
    if (!selected) return { items: [], total: 0 }
    const items = CODICI_OGGETTO_PST
      .filter((item) => item.codice !== selected.codice && classificationKey(item) === classificationKey(selected))
      .sort((left, right) => left.codice.localeCompare(right.codice, 'it'))
    return { items: items.slice(0, 6), total: items.length }
  }
  const tokens = normalized.split(/\s+/).filter(Boolean)
  if (!tokens.length) return { items: [], total: 0 }
  const items = filteredIndex
    .filter(({ haystack }) => tokens.every((token) => haystack.includes(token)))
    .map(({ item }) => ({ item, score: score(item, normalized, tokens) }))
    .sort((left, right) => right.score - left.score || left.item.codice.localeCompare(right.item.codice, 'it'))
    .map(({ item }) => item)
  return { items: items.slice(0, MAX_VISIBLE_RESULTS), total: items.length }
}

function registriLabel(registri: string[]): string {
  return registri.length ? registri.join(', ') : 'PST'
}

function catalogOptions(values: string[]): CatalogOption[] {
  const counts = new Map<string, number>()
  values.forEach((value) => counts.set(value, (counts.get(value) || 0) + 1))
  return Array.from(counts, ([value, count]) => ({ value, label: value, count }))
    .sort((left, right) => left.label.localeCompare(right.label, 'it'))
}

const AREA_OPTIONS = catalogOptions(CODICI_OGGETTO_PST.map((item) => item.area))

export function CodiceOggettoPstSearch({
  value,
  name,
  id,
  label = 'Oggetto deposito',
  help = 'Cerca per codice, materia o parole chiave. Il deposito userà solo codici presenti negli XSD ufficiali PST.',
  placeholder = 'Es. 014001, sfratto, famiglia, ATP',
  className = '',
  onChange,
}: CodiceOggettoPstSearchProps) {
  const generatedId = useId()
  const fieldId = id || `codice-oggetto-${generatedId}`
  const [query, setQuery] = useState('')
  const [areaFilter, setAreaFilter] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [registerFilter, setRegisterFilter] = useState('')
  const deferredQuery = useDeferredValue(query)
  const selected = findCodiceOggettoPst(value)
  const groupOptions = useMemo(() => {
    const groups = new Map<string, CatalogOption>()
    CODICI_OGGETTO_PST
      .filter((item) => (!areaFilter || item.area === areaFilter) && (!registerFilter || item.registri.includes(registerFilter)))
      .forEach((item) => {
        const value = classificationKey(item)
        const current = groups.get(value)
        groups.set(value, {
          value,
          label: groupLabel(item),
          count: (current?.count || 0) + 1,
        })
      })
    return Array.from(groups.values()).sort((left, right) => left.label.localeCompare(right.label, 'it'))
  }, [areaFilter, registerFilter])
  const registerOptions = useMemo(() => catalogOptions(
    CODICI_OGGETTO_PST
      .filter((item) => (!areaFilter || item.area === areaFilter) && (!groupFilter || classificationKey(item) === groupFilter))
      .flatMap((item) => item.registri),
  ), [areaFilter, groupFilter])
  const outcome = useMemo(() => searchCodici(deferredQuery, selected, {
    area: areaFilter,
    group: groupFilter,
    register: registerFilter,
  }), [areaFilter, deferredQuery, groupFilter, registerFilter, selected])
  const results = outcome.items
  const hasSearch = normalize(deferredQuery).length > 0
  const hasClassification = Boolean(areaFilter || groupFilter || registerFilter)
  const resultLabel = hasSearch || hasClassification
    ? `${outcome.total} risultati nel catalogo ufficiale${outcome.total > MAX_VISIBLE_RESULTS ? `, primi ${MAX_VISIBLE_RESULTS} visualizzati` : ''}`
    : selected
      ? 'Procedimenti collegati allo stesso gruppo'
      : `${CODICI_OGGETTO_PST_CATALOG.totaleCodici} codici ufficiali disponibili`
  const handleQueryChange = (nextQuery: string) => {
    setQuery(nextQuery)
    const exact = findCodiceOggettoPst(nextQuery.trim())
    if (exact && exact.codice !== selected?.codice) {
      onChange(exact.codice, exact.descrizione, exact)
    }
  }

  return (
    <div className={['iu-code-search', className].filter(Boolean).join(' ')}>
      {name ? <input type="hidden" name={name} value={selected?.codice || ''} /> : null}
      <label className="iu-code-search__label" htmlFor={`${fieldId}-query`}>
        <span>{label}</span>
      </label>
      <div className="iu-code-search__box">
        <Search size={17} aria-hidden="true" />
        <input
          id={`${fieldId}-query`}
          type="search"
          value={query}
          placeholder={placeholder}
          autoComplete="off"
          aria-describedby={`${fieldId}-help ${fieldId}-summary`}
          onChange={(event) => handleQueryChange(event.currentTarget.value)}
        />
        {query ? (
          <button type="button" onClick={() => setQuery('')} aria-label="Pulisci ricerca codice oggetto">
            <X size={15} />
          </button>
        ) : null}
      </div>
      <div className="iu-code-search__classification">
        <div className="iu-code-search__classification-title">
          <FolderTree size={17} aria-hidden="true" />
          <strong>Classificazione</strong>
          {hasClassification ? (
            <button
              type="button"
              onClick={() => {
                setAreaFilter('')
                setGroupFilter('')
                setRegisterFilter('')
              }}
              aria-label="Azzera classificazione"
              title="Azzera classificazione"
            >
              <X size={15} />
            </button>
          ) : null}
        </div>
        <div className="iu-code-search__filters">
          <label htmlFor={`${fieldId}-area`}>
            <span>Area</span>
            <select
              id={`${fieldId}-area`}
              value={areaFilter}
              onChange={(event) => {
                setAreaFilter(event.currentTarget.value)
                setGroupFilter('')
              }}
            >
              <option value="">Tutte le aree</option>
              {AREA_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label} ({option.count})</option>
              ))}
            </select>
          </label>
          <label htmlFor={`${fieldId}-group`}>
            <span>Gruppo</span>
            <select
              id={`${fieldId}-group`}
              value={groupFilter}
              onChange={(event) => setGroupFilter(event.currentTarget.value)}
            >
              <option value="">Tutti i gruppi</option>
              {groupOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label} ({option.count})</option>
              ))}
            </select>
          </label>
          <label htmlFor={`${fieldId}-register`}>
            <span>Registro</span>
            <select
              id={`${fieldId}-register`}
              value={registerFilter}
              onChange={(event) => {
                setRegisterFilter(event.currentTarget.value)
                setGroupFilter('')
              }}
            >
              <option value="">Tutti i registri</option>
              {registerOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label} ({option.count})</option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {selected ? (
        <div className="iu-code-search__selected">
          <CheckCircle2 size={17} aria-hidden="true" />
          <div>
            <strong>{selected.codice} - {selected.descrizione}</strong>
            <span>{selected.area}{selected.descrizionePadre ? `, ${selected.descrizionePadre}` : ''}</span>
          </div>
          <Badge tone="info">{registriLabel(selected.registri)}</Badge>
          <button type="button" onClick={() => onChange('', '')}>Rimuovi</button>
        </div>
      ) : null}
      <small className="iu-code-search__help" id={`${fieldId}-help`}>{help}</small>
      <div className="iu-code-search__summary" id={`${fieldId}-summary`}>{resultLabel}</div>
      {results.length ? (
        <div className="iu-code-search__results" role="listbox" aria-label="Risultati codice oggetto PST">
          {results.map((item) => (
            <button
              type="button"
              role="option"
              aria-selected={item.codice === selected?.codice}
              key={item.codice}
              onClick={() => {
                onChange(item.codice, item.descrizione, item)
                setQuery('')
              }}
            >
              <span className="iu-code-search__code">{item.codice}</span>
              <span className="iu-code-search__text">
                <strong>{item.descrizione}</strong>
                <small>{item.area}{item.descrizionePadre ? `, ${item.descrizionePadre}` : ''}</small>
              </span>
              <span className="iu-code-search__registers">{registriLabel(item.registri)}</span>
            </button>
          ))}
        </div>
      ) : hasSearch || hasClassification ? (
        <div className="iu-code-search__empty">Nessun codice ufficiale trovato. Prova con meno parole o con il codice numerico.</div>
      ) : null}
    </div>
  )
}
