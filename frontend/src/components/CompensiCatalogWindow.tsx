import { useEffect, useMemo, useRef, useState } from 'react'
import type { CompensiForensiRecord } from '../compensiForensiData'
import { OperationalModal } from './OperationalModal'
import './CompensiCatalogWindow.css'

export function CompensiCatalogWindow({ kind, records, onClose, focusToken, canOpenTariffario }: {
  kind: 'profili' | 'regole'
  records: CompensiForensiRecord[]
  onClose: () => void
  focusToken: number
  canOpenTariffario: boolean
}) {
  const catalogRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const filtered = useMemo(() => records.filter(record => record.kind === kind &&
    `${record.id} ${record.title} ${record.subtitle} ${record.meta}`.toLocaleLowerCase('it').includes(query.trim().toLocaleLowerCase('it'))), [records, kind, query])
  const lastPage = Math.max(0, Math.ceil(filtered.length / 30) - 1)
  const currentPage = Math.min(page, lastPage)
  useEffect(() => { catalogRef.current?.closest('.iu-comp-catalog-body')?.scrollTo({ top: 0 }) }, [currentPage, query])
  const title = kind === 'profili' ? 'Profili tariffari' : 'Regole disponibili'
  return <OperationalModal open focusToken={focusToken} ariaLabel={title} title={title} eyebrow="Catalogo compensi" subtitle="Dati delle tabelle normative dello studio. Il calcolo mantiene i parametri già inseriti." bodyClassName="iu-comp-catalog-body" onClose={onClose}>
    <div ref={catalogRef} className="iu-comp-catalog">
      <label>Ricerca nel catalogo<input type="search" value={query} onChange={event => { setQuery(event.currentTarget.value); setPage(0) }} placeholder="Nome, materia, grado o codice…"/></label>
      <p role="status">{filtered.length} {filtered.length === 1 ? 'voce' : 'voci'}{query ? ' nella ricerca' : ' disponibili'}</p>
      <ul>{filtered.slice(currentPage * 30, (currentPage + 1) * 30).map(record => <li key={`${record.kind}:${record.id}`}>
        <div><strong>{record.title}</strong><span>{record.subtitle}</span><small>{record.meta} · {record.id}</small></div>
        {canOpenTariffario ? <a href={record.href}>Apri nel tariffario</a> : null}
      </li>)}</ul>
      {!filtered.length ? <p>Nessuna voce corrisponde alla ricerca.</p> : null}
      {lastPage > 0 ? <nav aria-label="Pagine del catalogo"><button type="button" disabled={!currentPage} onClick={() => setPage(currentPage - 1)}>Precedenti</button><span>Pagina {currentPage + 1} di {lastPage + 1}</span><button type="button" disabled={currentPage >= lastPage} onClick={() => setPage(currentPage + 1)}>Successive</button></nav> : null}
    </div>
  </OperationalModal>
}
