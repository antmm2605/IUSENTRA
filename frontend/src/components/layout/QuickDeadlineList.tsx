import { publishMutationRefresh } from '../../operationalRefresh'
import { useOperationalRefresh } from '../../hooks/useOperationalRefresh'
import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { OperationalModal } from '../OperationalModal'
import type { TopbarDeadlinesPayload } from '../../types/topbar'
import { formatDateIt } from '../../formatting'
import './QuickDeadlineList.css'

export type QuickDeadlinePeriod = 'today' | 'tomorrow' | 'week' | 'overdue'
const labels = { today: 'Scadenze di oggi', tomorrow: 'Scadenze di domani', week: 'Prossimi 7 giorni', overdue: 'Scadenze scadute' }
async function request(url: string, init?: RequestInit) {
  const response = await fetch(url, { credentials: 'same-origin', ...init })
  const value = await response.json()
  if (!response.ok || !value.ok) throw new Error(value.message || 'Scadenze non disponibili.')
  return value
}
export function QuickDeadlineList({ period, onClose }: { period: QuickDeadlinePeriod; onClose: () => void }) {
  const [data, setData] = useState<TopbarDeadlinesPayload | null>(null)
  const [query, setQuery] = useState(''), [reading, setReading] = useState('unread')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false)
  const [page, setPage] = useState(1)
  const load = () => request('/api/v1/ui/scadenze-rapide').then(setData)
  useOperationalRefresh(['scadenze', 'agenda'], () => load().catch(reason => setError(reason instanceof Error ? reason.message : 'Scadenze non disponibili.')))
  useEffect(() => { let live = true; request('/api/v1/ui/scadenze-rapide').then(v => { if (live) setData(v) }).catch(e => { if (live) setError(e.message) }); return () => { live = false } }, [])
  const rows = useMemo(() => {
    const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Rome' }).format(new Date())
    const day = new Date(`${today}T12:00:00`)
    const shift = (n: number) => { const d = new Date(day); d.setDate(d.getDate() + n); return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Rome' }).format(d) }
    const q = query.trim().toLocaleLowerCase('it-IT')
    return (data?.deadlines || []).filter(v => {
      const date = v.dueDate.slice(0, 10)
      const inPeriod = period === 'overdue' ? v.status === 'overdue' : period === 'today' ? date === today : period === 'tomorrow' ? date === shift(1) : date >= today && date <= shift(7)
      return inPeriod && (reading === 'all' || (reading === 'read' ? v.letta : !v.letta)) && (!q || `${v.title} ${v.caseTitle || ''} ${v.clientName || ''} ${formatDateIt(date)}`.toLocaleLowerCase('it-IT').includes(q))
    }).sort((a, b) => a.dueDate.localeCompare(b.dueDate))
  }, [data, period, query, reading])
  const chosen = rows.filter(v => selected.has(v.id))
  useEffect(() => { setPage(1) }, [query, reading, period])
  async function markRead() {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await request('/api/v1/ui/scadenze-rapide/lette', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids: chosen.map(v => v.id) }) })
      publishMutationRefresh('/api/v1/ui/scadenze-rapide/lette')
      await load(); setSelected(new Set()); setMessage(result.message); setReading('unread'); window.dispatchEvent(new Event('iusentra:scadenze-lette'))
    } catch (e) { setError(e instanceof Error ? e.message : 'Lettura non salvata.') }
    finally { setBusy(false) }
  }
  return createPortal(<OperationalModal open ariaLabel={labels[period]} boxClassName="iu-quick-list" eyebrow="Presa visione e gestione" title={labels[period]} onClose={onClose}
    >
    {data && <p role="status">{period === 'overdue' ? `${data.summary.overdue} ${data.summary.overdue === 1 ? 'scaduta' : 'scadute'} · ${data.summary.unreadOverdue ?? 0} da leggere` : `${rows.length} ${rows.length === 1 ? 'scadenza nei risultati' : 'scadenze nei risultati'}`}</p>}
    <p>La presa visione registra la lettura. Le scadenze restano aperte fino all’adempimento.</p>
    <div className="iu-quick-list__filters">
      <label>Cerca nelle scadenze<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Titolo, fascicolo, cliente o data"/></label>
      <label>Lettura<select value={reading} onChange={e => setReading(e.target.value)}><option value="all">Tutte</option><option value="unread">Da leggere</option><option value="read">Già lette</option></select></label>
    </div>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {!data && !error && <p role="status">Caricamento scadenze…</p>}
    <div className="iu-quick-list__selection">
      <label><input type="checkbox" checked={!!rows.length && chosen.length === rows.length} disabled={busy || !rows.length} onChange={e => setSelected(e.target.checked ? new Set(rows.map(v => v.id)) : new Set())}/> {rows.length === 1 ? 'Seleziona la scadenza filtrata' : `Seleziona tutte le ${rows.length} scadenze filtrate`}</label>
      <button type="button" disabled={busy || !chosen.length} onClick={() => void markRead()}>{busy ? 'Salvataggio…' : `Segna lette le selezionate (${chosen.length})`}</button>
    </div>
    <ul>{rows.slice((page - 1) * 30, page * 30).map(v => <li key={v.id}>
      <input type="checkbox" aria-label={`Seleziona ${v.title}`} checked={selected.has(v.id)} disabled={busy} onChange={e => setSelected(prev => { const next = new Set(prev); if (e.target.checked) next.add(v.id); else next.delete(v.id); return next })}/>
      <div><a href={v.href}>{v.title}</a><small>{v.caseTitle || v.clientName || 'Scadenziario'}</small><span>{formatDateIt(v.dueDate)} · {v.letta ? 'Già letta' : 'Da leggere'} · {v.status === 'overdue' ? 'Scaduta, da gestire' : 'Aperta'}</span></div>
    </li>)}</ul>
    {data && !rows.length && <div><p>{reading === 'unread' && !query ? 'Non restano scadenze da leggere in questo periodo.' : 'Nessuna scadenza corrisponde ai filtri.'}</p>{reading !== 'all' && <button className="iu-button" type="button" onClick={() => setReading('all')}>Mostra tutte, comprese le già lette</button>}</div>}
    {rows.length > 30 && <nav aria-label="Pagine scadenze"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Precedente</button><span>Pagina {page} di {Math.ceil(rows.length / 30)}</span><button disabled={page * 30 >= rows.length} onClick={() => setPage(p => p + 1)}>Successiva</button></nav>}
  </OperationalModal>, document.body)
}
