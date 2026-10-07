import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Download, Search, X } from 'lucide-react'
import type { IncassiCardRecord } from '../incassiPagamentiData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { csrfToken } from '../formSubmit'

export function IncassiCardCatalog({ rows, metric, title, onClear, unavailable, onFilterChange }: { rows: IncassiCardRecord[]; metric: string; title: string; onClear: () => void; unavailable: boolean; onFilterChange: (ids: string[]) => void }) {
  const [search, setSearch] = useState('')
  const [state, setState] = useState('')
  const [page, setPage] = useState(1)
  const [selection, setSelection] = useState<Set<string>>(new Set())
  const [onlySelected, setOnlySelected] = useState(false)
  const stateFieldId = useId()
  const downloadFrameName = `incassi-export-${stateFieldId}`
  const downloadForm = useRef<HTMLFormElement>(null)
  const [exportError, setExportError] = useState('')
  const contextRows = useMemo(() => rows.filter((row) => !metric || row.metricIds.includes(metric) || (metric === 'crediti' && (row.metricIds.includes('da_incassare') || row.metricIds.includes('scaduto')))), [rows, metric])
  const matching = useMemo(() => contextRows.filter((row) => (!state || row.state === state) && `${row.label} ${row.customer} ${row.kind} ${row.stateLabel} ${row.dateLabel}`.toLocaleLowerCase('it-IT').includes(search.toLocaleLowerCase('it-IT').trim())), [contextRows, state, search])
  const filtered = useMemo(() => onlySelected ? matching.filter((row) => selection.has(row.id)) : matching, [matching, onlySelected, selection])
  const pages = Math.max(1, Math.ceil(filtered.length / 30))
  const currentPage = Math.min(page, pages)
  const visible = filtered.slice((currentPage - 1) * 30, currentPage * 30)
  const selected = rows.filter((row) => selection.has(row.id))
  const states = [...new Map(contextRows.map((row) => [row.state, row.stateLabel])).entries()]
  const allSelected = matching.length > 0 && matching.every((row) => selection.has(row.id))
  useEffect(() => { setPage(1); setState(''); setOnlySelected(false) }, [metric])
  useEffect(() => { setPage(1) }, [search, state, onlySelected])
  useEffect(() => { onFilterChange(filtered.map((row) => row.id)) }, [filtered, onFilterChange])
  useEffect(() => { const available = new Set(rows.map((row) => row.id)); setSelection((current) => new Set([...current].filter((id) => available.has(id)))) }, [rows])
  function selectAll() {
    setSelection((current) => { const next = new Set(current); for (const row of matching) { if (allSelected) next.delete(row.id); else next.add(row.id) } return next })
  }
  function downloadSelection() {
    setExportError('')
    if (!csrfToken()) { setExportError('Conferma di sicurezza non disponibile. Riapri la pagina prima di esportare.'); return }
    downloadForm.current?.requestSubmit()
  }
  return <section className="iu-pay-catalog" aria-label="Ricerca nei riepiloghi incassi">
    <form ref={downloadForm} action="/api/v1/ui/incassi-pagamenti/esporta" method="post" target={downloadFrameName} hidden>
      <input type="hidden" name="_csrf_token" value={csrfToken()}/>
      <input type="hidden" name="selezione" value={JSON.stringify([...selection])}/>
    </form>
    <iframe name={downloadFrameName} title="Esito esportazione incassi" hidden onLoad={(event) => {
      try {
        const doc = event.currentTarget.contentDocument
        const text = doc?.body?.textContent || ''
        if (!text) return
        const result: unknown = JSON.parse(text)
        if (result && typeof result === 'object' && 'message' in result) setExportError(String(result.message))
      } catch { setExportError('Impossibile confermare l’esportazione. Riprova senza modificare gli incassi.') }
    }}/>
    {exportError ? <p role="alert">{exportError}</p> : null}
    <header><div><h2>{title}</h2><p>{metric === 'incassato' ? 'Parcelle emesse nell’anno corrente e registrate come pagate.' : metric === 'da_incassare' ? 'Parcelle emesse ancora da incassare, di tutti gli anni.' : metric === 'scaduto' ? 'Parcelle registrate come scadute e non pagate, di tutti gli anni.' : metric.startsWith('link_') ? 'Collegamenti di pagamento corrispondenti al riepilogo selezionato.' : 'Parcelle e collegamenti distinti, senza escludere lo storico.'}</p></div>{metric ? <Button tone="neutral" onClick={onClear}><X size={15}/>Tutti i documenti</Button> : null}</header>
    <div className="iu-pay-catalog__filters"><label><Search size={15}/> Cerca documento o cliente<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Numero, cliente, stato o data..." /></label><div className="iu-pay-catalog__state"><label htmlFor={stateFieldId}>Stato</label><select id={stateFieldId} value={state} onChange={(event) => setState(event.target.value)}><option value="">Tutti gli stati</option>{states.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
    <div className="iu-pay-catalog__selection"><label><input type="checkbox" checked={allSelected} disabled={!matching.length || unavailable} onChange={selectAll}/>{matching.length === 1 ? 'Seleziona il risultato filtrato' : `Seleziona tutti i ${matching.length} risultati filtrati`}</label><span>{selected.length === 1 ? '1 selezionato' : `${selected.length} selezionati`}</span><Button tone="neutral" disabled={!selection.size} onClick={() => setOnlySelected((value) => !value)}>{onlySelected ? 'Mostra tutti' : 'Mostra selezionati'}</Button><Button tone="neutral" disabled={!selection.size || unavailable} onClick={downloadSelection}><Download size={15}/>Esporta selezionati</Button></div>
    {selection.size ? <div className="iu-pay-catalog__selection"><p>La selezione resta conservata quando cambi filtro. L’esportazione comprende tutti i documenti selezionati.</p><Button tone="neutral" onClick={() => { setSelection(new Set()); setOnlySelected(false) }}>Azzera selezione</Button></div> : null}
    {unavailable ? <p role="alert">Una parte degli archivi non è disponibile. I conteggi e la ricerca devono essere verificati prima di operare.</p> : null}
    {!filtered.length ? <p role="status">{unavailable ? 'Elenco non verificabile in questo momento.' : 'Nessun documento corrisponde ai filtri selezionati.'}</p> : <div className="iu-pay-catalog__rows">{visible.map((row) => <article key={row.id}><input type="checkbox" aria-label={`Seleziona ${row.label}, ${row.customer}`} checked={selection.has(row.id)} onChange={(event) => setSelection((current) => { const next = new Set(current); if (event.target.checked) next.add(row.id); else next.delete(row.id); return next })}/><div data-allow-technical-text="true"><strong>{row.label}</strong><span>{row.customer}</span><small>{row.kind} · {row.dateLabel || 'Data non presente'}</small></div><Badge tone={row.stateTone}>{row.stateLabel}</Badge><strong>{row.amountDisplay}</strong>{row.href ? <ButtonLink href={row.href} tone="neutral">Apri parcella</ButtonLink> : <small>Parcella non collegata</small>}</article>)}</div>}
    <footer><span>{filtered.length} {filtered.length === 1 ? 'risultato' : 'risultati'} · Pagina {currentPage} di {pages}</span><Button tone="neutral" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Precedente</Button><Button tone="neutral" disabled={currentPage >= pages} onClick={() => setPage(currentPage + 1)}>Successiva</Button></footer>
  </section>
}
