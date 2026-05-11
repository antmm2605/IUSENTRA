import { useDeferredValue, useId, useMemo, useState } from 'react'
import { CheckCircle2, Search, X } from 'lucide-react'
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

function searchCodici(query: string, selected?: CodiceOggettoPstRecord): CodiceOggettoPstRecord[] {
  const normalized = normalize(query)
  if (!normalized) {
    if (!selected) return []
    return CODICI_OGGETTO_PST
      .filter((item) => item.codice !== selected.codice && item.codicePadre === selected.codicePadre)
      .slice(0, 6)
  }
  const tokens = normalized.split(/\s+/).filter(Boolean)
  if (!tokens.length) return []
  return searchIndex
    .filter(({ haystack }) => tokens.every((token) => haystack.includes(token)))
    .map(({ item }) => ({ item, score: score(item, normalized, tokens) }))
    .sort((left, right) => right.score - left.score || left.item.codice.localeCompare(right.item.codice, 'it'))
    .slice(0, 12)
    .map(({ item }) => item)
}

function registriLabel(registri: string[]): string {
  return registri.length ? registri.join(', ') : 'PST'
}

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
  const deferredQuery = useDeferredValue(query)
  const selected = findCodiceOggettoPst(value)
  const results = useMemo(() => searchCodici(deferredQuery, selected), [deferredQuery, selected])
  const hasSearch = normalize(deferredQuery).length > 0
  const resultLabel = hasSearch
    ? `${results.length} risultati nel catalogo ufficiale`
    : selected
      ? 'Procedimenti collegati allo stesso gruppo'
      : `${CODICI_OGGETTO_PST_CATALOG.totaleCodici} codici ufficiali disponibili`

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
          onChange={(event) => setQuery(event.currentTarget.value)}
        />
        {query ? (
          <button type="button" onClick={() => setQuery('')} aria-label="Pulisci ricerca codice oggetto">
            <X size={15} />
          </button>
        ) : null}
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
      ) : hasSearch ? (
        <div className="iu-code-search__empty">Nessun codice ufficiale trovato. Prova con meno parole o con il codice numerico.</div>
      ) : null}
    </div>
  )
}
