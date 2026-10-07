import { useEffect, useRef, useState } from 'react'
import { Download, Search, FolderOpen, AlertTriangle } from 'lucide-react'
import { OperationalModal } from './OperationalModal'
import { getTelematicoCases, type TelematicoCase } from '../telematicoData'
import { formatDateTimeIt } from '../formatting'
import { csrfHeader } from '../api/csrf'
import './TelematicoCardsPanel.css'

export type TelematicoCardScope = '' | 'pst-pdp' | 'pat' | 'ptt' | 'presidi'
const titles: Record<string, string> = { '': 'Pratiche telematiche', 'pst-pdp': 'Pratiche PST e PDP', pst: 'Pratiche PST / PolisWeb', pdp: 'Pratiche PDP Penale', pat: 'Pratiche PAT / SIGA', ptt: 'Pratiche PTT / SIGIT', altro: 'Pratiche di altri canali', presidi: 'Presidi telematici' }
type Row = { id: string; title: string; subtitle: string; portal: string; portalLabel: string; status: string; href: string; detail: string; date?: string }
function caseRow(value: TelematicoCase): Row {
  return { id: value.id, title: value.title, subtitle: value.subtitle, portal: value.portal, portalLabel: value.portalLabel, status: value.statusText, href: value.href, detail: `${value.controlCategory ? value.controlCategory + ' · ' : ''}${value.documentsCount} ${value.documentsCount === 1 ? 'documento' : 'documenti'} · ${value.openTasks} ${value.openTasks === 1 ? 'attività aperta' : 'attività aperte'}`, date: value.syncedAt }
}
export function TelematicoCardsPanel({ scope, refreshToken, onClose }: { scope: TelematicoCardScope; refreshToken: number; onClose: () => void }) {
  const [portal, setPortal] = useState<string>(scope === 'presidi' ? '' : scope)
  const [query, setQuery] = useState('')
  const [needle, setNeedle] = useState('')
  const [page, setPage] = useState(1)
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')
  const [download, setDownload] = useState<{ url: string; filename: string; count: number } | null>(null)
  const [retry, setRetry] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [all, setAll] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [excluded, setExcluded] = useState<Set<string>>(new Set())
  const exportController = useRef<AbortController | null>(null)
  const busy = loading || query !== needle
  const title = scope === 'presidi' ? titles.presidi : titles[portal]
  const clearSelection = () => { setAll(false); setSelected(new Set()); setExcluded(new Set()); setFeedback(''); setDownload(null) }
  useEffect(() => {
    const timer = setTimeout(() => { setNeedle(query); setPage(1); clearSelection() }, 180)
    return () => clearTimeout(timer)
  }, [query])
  useEffect(() => { setPage(1); clearSelection() }, [portal, refreshToken])
  useEffect(() => () => exportController.current?.abort(), [])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    getTelematicoCases(portal, needle, page, controller.signal, 25, scope === 'presidi').then(result => {
      if (!controller.signal.aborted) { setRows(result.items.map(caseRow)); setTotal(result.total); setPages(result.pages); if (result.page !== page) setPage(result.page) }
    }).catch(() => { if (!controller.signal.aborted) setError('Le pratiche non sono state caricate. Riprova mantenendo i filtri scelti.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [scope, portal, needle, page, refreshToken, retry])
  const checked = (id: string) => all ? !excluded.has(id) : selected.has(id)
  const count = all ? Math.max(0, total - excluded.size) : selected.size
  const toggle = (id: string) => {
    const update = (previous: Set<string>) => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next }
    if (all) setExcluded(update); else setSelected(update)
    setFeedback(''); setDownload(null)
  }
  const exportSelected = async () => {
    const controller = new AbortController(); exportController.current = controller; setExporting(true); setError(''); setFeedback('')
    try {
      const response = await fetch('/api/v1/ui/telematico/pratiche/esporta', {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...csrfHeader() },
        body: JSON.stringify({ portal, query: needle, scope: scope === 'presidi' ? 'presidi' : '', all, selected: [...selected], excluded: [...excluded], total, count }),
      })
      const result = await response.json()
      if (!response.ok || result.ok !== true) throw new Error(result.message || 'Il riepilogo non è stato esportato. Riprova.')
      if (typeof result.downloadUrl !== 'string' || !/^\/api\/v1\/ui\/document-tools\/results\/[^/]+\/scarica$/.test(result.downloadUrl) || result.count !== count) throw new Error('Il file selezionato non è stato confermato. Riprova.')
      if (controller.signal.aborted) return
      setDownload({ url: result.downloadUrl, filename: result.filename, count: result.count })
      setFeedback(`Esportazione preparata: ${result.count} ${result.count === 1 ? 'elemento selezionato' : 'elementi selezionati'}. La copia temporanea è disponibile per un’ora.`)
    } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Esportazione non riuscita. Riprova.') }
    finally { if (!controller.signal.aborted) setExporting(false); exportController.current = null }
  }
  return <OperationalModal open draggable ariaLabel={title} title={title} eyebrow={scope === 'presidi' ? <><AlertTriangle size={14}/> Attività da presidiare</> : <><FolderOpen size={14}/> Archivio dello studio</>} subtitle={scope === 'presidi' ? 'Consulta ogni controllo e apri il fascicolo collegato.' : 'Ricerca nell’intero archivio telematico dello studio.'} onClose={onClose} boxClassName="iu-tel-card-panel" bodyClassName="iu-tel-card-panel__body">
    <div className="iu-tel-card-panel__filters">
      <label>Cerca pratiche<div><Search size={16}/><input aria-label="Cerca nel riepilogo telematico" placeholder="Titolo, RG, ufficio o stato…" value={query} disabled={exporting} onChange={event => { setQuery(event.target.value); clearSelection() }}/></div></label>
      <label>Canale<select aria-label="Filtra il riepilogo per canale" value={portal} disabled={exporting} onChange={event => { setPortal(event.target.value); clearSelection() }}><option value="">Tutti i canali</option><option value="pst-pdp">PST e PDP</option><option value="pst">PST / PolisWeb</option><option value="pdp">PDP Penale</option><option value="pat">PAT / SIGA</option><option value="ptt">PTT / SIGIT</option><option value="altro">Altri canali</option></select></label>
    </div>
    <div className="iu-tel-card-panel__selection">
      <label><input type="checkbox" aria-label="Seleziona tutti i risultati telematici" checked={all && excluded.size === 0 && total > 0} disabled={busy || exporting || !!error || !total} onChange={event => { setAll(event.target.checked); setSelected(new Set()); setExcluded(new Set()); setFeedback(''); setDownload(null) }}/>Seleziona tutti{!busy ? ` (${total})` : ''}</label>
      <span role="status">{busy ? 'Ricerca in corso…' : `${count} ${count === 1 ? 'selezionato' : 'selezionati'} · ${total} ${total === 1 ? 'risultato' : 'risultati'}`}</span>
      {download && !busy && !exporting && !error ? <a className="iu-tel-card-panel__download" href={download.url} download={download.filename}><Download size={15}/>Scarica CSV ({download.count})</a> : <button type="button" disabled={!count || busy || exporting || !!error} onClick={() => void exportSelected()}><Download size={15}/>{exporting ? 'Preparazione…' : 'Esporta selezionati'}</button>}
    </div>
    {feedback ? <p role="status" className="iu-tel-card-panel__feedback">{feedback}</p> : null}
    {error ? <div role="alert" className="iu-tel-card-panel__error"><span>{error}</span><button type="button" disabled={busy || exporting} onClick={() => { clearSelection(); setRetry(value => value + 1) }}>Riprova</button></div> : null}
    {busy ? <p role="status">Caricamento delle informazioni…</p> : error ? null : rows.length ? <ul className="iu-tel-card-panel__rows">{rows.map(row => <li key={row.id}>
      <input type="checkbox" aria-label={`Seleziona ${row.title}${scope === 'presidi' ? ` · ${row.detail}` : ''}`} checked={checked(row.id)} disabled={exporting} onChange={() => toggle(row.id)}/>
      <div><strong>{row.title}</strong><span>{row.subtitle}</span><small>{row.portalLabel} · {row.status}</small><small>{row.detail}{row.date ? ` · ${formatDateTimeIt(row.date, 'Data da verificare')}` : ''}</small></div>
      {/^\/fascicoli\/[^/]+(?:[/?#]|$)/.test(row.href) ? <a href={row.href} aria-label={`Apri fascicolo ${row.title}`}>Apri fascicolo</a> : <span className="iu-tel-card-panel__unlinked">Fascicolo non collegato: verifica l’associazione della pratica.</span>}
    </li>)}</ul> : <p className="iu-empty">Nessun risultato per i filtri scelti. Modifica la ricerca o seleziona tutti i canali.</p>}
    {!busy && !error && pages > 1 ? <nav aria-label="Pagine del riepilogo telematico" className="iu-tel-card-panel__pages"><button type="button" disabled={page <= 1 || exporting} onClick={() => setPage(value => value - 1)}>Precedente</button><span>Pagina {page} di {pages}</span><button type="button" disabled={page >= pages || exporting} onClick={() => setPage(value => value + 1)}>Successiva</button></nav> : null}
  </OperationalModal>
}
