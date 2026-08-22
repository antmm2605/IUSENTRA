import { useEffect, useMemo, useState } from 'react'
import {
  Archive,
  BookOpenCheck,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FilePlus2,
  FileText,
  FolderOpen,
  FolderOutput,
  PenLine,
  RotateCcw,
  Search,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react'
import {
  loadDocumentArchive,
  type DocumentArchiveData,
  type DocumentArchiveQuery,
  type DocumentArchiveRow,
  type DocumentArchiveScope,
} from '../documentArchiveData'
import { csrfToken } from '../formSubmit'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './EditorProfessionalePage.css'

const EMPTY_DATA: DocumentArchiveData = {
  source: 'vuoto',
  message: '',
  summary: { active: 0, trash: 0, matters: 0, formats: 0 },
  filters: { scope: 'attivi', q: '', type: '', format: '', matter: '' },
  facets: { types: [], formats: [], matters: [] },
  pagination: { page: 1, perPage: 50, pages: 1, total: 0, from: 0, to: 0 },
  items: [],
  actions: { newDocument: '/template-atti/editor', openMatters: '/fascicoli', searchStudio: '/global-search?tipo=documenti' },
}

type PendingAction = {
  row: DocumentArchiveRow
  kind: 'trash' | 'restore' | 'permanent-delete'
  url: string
}

type WritableFileHandle = { createWritable: () => Promise<{ write: (data: Blob) => Promise<void>; close: () => Promise<void> }> }
type WritableDirectoryHandle = {
  getDirectoryHandle: (name: string, options: { create: boolean }) => Promise<WritableDirectoryHandle>
  getFileHandle: (name: string, options: { create: boolean }) => Promise<WritableFileHandle>
}

function initialQuery(): DocumentArchiveQuery {
  const params = new URLSearchParams(window.location.search)
  return {
    scope: params.get('scope') === 'cestino' ? 'cestino' : 'attivi',
    q: params.get('q') || '',
    type: params.get('tipo') || '',
    format: params.get('formato') || '',
    matter: params.get('fascicolo') || '',
    page: Math.max(1, Number(params.get('page') || 1) || 1),
  }
}

function rowKey(row: DocumentArchiveRow): string {
  return `${row.matterId}:${row.id}`
}

function safeDirectoryName(value: string): string {
  return value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 90) || 'Fascicolo'
}

function scopeLabel(scope: DocumentArchiveScope): string {
  return scope === 'cestino' ? 'Cestino' : 'Documenti'
}

export function EditorProfessionalePage() {
  const [query, setQuery] = useState<DocumentArchiveQuery>(() => initialQuery())
  const [searchDraft, setSearchDraft] = useState(query.q)
  const [data, setData] = useState<DocumentArchiveData>(EMPTY_DATA)
  const [loading, setLoading] = useState(true)
  const [refreshToken, setRefreshToken] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [exporting, setExporting] = useState(false)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [actionBusy, setActionBusy] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery((current) => current.q === searchDraft ? current : { ...current, q: searchDraft, page: 1 })
    }, 250)
    return () => window.clearTimeout(timer)
  }, [searchDraft])

  useEffect(() => {
    const params = new URLSearchParams()
    if (query.scope === 'cestino') params.set('scope', query.scope)
    if (query.q.trim()) params.set('q', query.q.trim())
    if (query.type) params.set('tipo', query.type)
    if (query.format) params.set('formato', query.format)
    if (query.matter) params.set('fascicolo', query.matter)
    if (query.page > 1) params.set('page', String(query.page))
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ''}`
    window.history.replaceState(null, '', next)

    let active = true
    setLoading(true)
    setError('')
    loadDocumentArchive(query).then((payload) => {
      if (!active) return
      setData(payload)
      setError(payload.message)
      const visible = new Set(payload.items.map(rowKey))
      setSelected((current) => new Set([...current].filter((key) => visible.has(key))))
      setLoading(false)
    })
    return () => { active = false }
  }, [query, refreshToken])

  const selectedRows = useMemo(
    () => data.items.filter((row) => selected.has(rowKey(row)) && row.actions.download),
    [data.items, selected],
  )

  const updateFilter = <K extends keyof DocumentArchiveQuery>(key: K, value: DocumentArchiveQuery[K]) => {
    setQuery((current) => ({ ...current, [key]: value, page: key === 'page' ? Number(value) : 1 }))
    setMessage('')
    setError('')
  }

  const resetFilters = () => {
    setSearchDraft('')
    setQuery((current) => ({ scope: current.scope, q: '', type: '', format: '', matter: '', page: 1 }))
  }

  const toggleRow = (row: DocumentArchiveRow) => {
    const key = rowKey(row)
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const togglePage = () => {
    const downloadable = data.items.filter((row) => row.actions.download)
    const allSelected = downloadable.length > 0 && downloadable.every((row) => selected.has(rowKey(row)))
    setSelected(allSelected ? new Set() : new Set(downloadable.map(rowKey)))
  }

  const exportOriginals = async () => {
    if (!selectedRows.length || exporting) return
    if (selectedRows.length === 1) {
      const link = document.createElement('a')
      link.href = selectedRows[0].actions.download
      link.download = selectedRows[0].name
      document.body.appendChild(link)
      link.click()
      link.remove()
      return
    }
    const picker = (window as Window & { showDirectoryPicker?: () => Promise<WritableDirectoryHandle> }).showDirectoryPicker
    if (!picker) {
      setError('Il browser in uso non consente di scegliere una cartella. Esporta un documento alla volta con il pulsante Scarica.')
      return
    }
    setExporting(true)
    setError('')
    setMessage('Scegli la cartella in cui salvare gli originali.')
    try {
      const root = await picker()
      const matterIds = new Set(selectedRows.map((row) => row.matterId))
      for (const row of selectedRows) {
        const target = matterIds.size > 1
          ? await root.getDirectoryHandle(safeDirectoryName(`${row.matterRef} ${row.matterTitle}`), { create: true })
          : root
        const response = await fetch(row.actions.download, { credentials: 'same-origin' })
        if (!response.ok) throw new Error(`Impossibile scaricare ${row.name}.`)
        const file = await target.getFileHandle(row.name, { create: true })
        const writer = await file.createWritable()
        await writer.write(await response.blob())
        await writer.close()
      }
      setMessage(`${selectedRows.length} originali salvati senza modificare nomi o contenuto.`)
    } catch (exportError) {
      const name = exportError instanceof Error ? exportError.name : ''
      if (name !== 'AbortError') setError(exportError instanceof Error ? exportError.message : 'Esportazione non completata.')
    } finally {
      setExporting(false)
    }
  }

  const runPendingAction = async () => {
    if (!pendingAction || actionBusy) return
    setActionBusy(true)
    setMessage('')
    setError('')
    try {
      const response = await fetch(pendingAction.url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken(),
        },
      })
      const payload = await response.json().catch(() => ({})) as Record<string, unknown>
      const responseMessage = String(payload.messaggio || payload.message || '')
      if (!response.ok || payload.ok === false) throw new Error(responseMessage || 'Operazione non completata.')
      setMessage(responseMessage || 'Archivio documentale aggiornato.')
      setPendingAction(null)
      setSelected(new Set())
      setRefreshToken((current) => current + 1)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Operazione non completata.')
    } finally {
      setActionBusy(false)
    }
  }

  const confirmTitle = pendingAction?.kind === 'permanent-delete'
    ? 'Elimina definitivamente'
    : pendingAction?.kind === 'restore'
      ? 'Ripristina documento'
      : 'Sposta nel cestino'
  const confirmMessage = pendingAction?.kind === 'permanent-delete'
    ? `Eliminare definitivamente ${pendingAction.row.name}? Il file non potrà più essere ripristinato.`
    : pendingAction?.kind === 'restore'
      ? `Ripristinare ${pendingAction.row.name} nel fascicolo ${pendingAction.row.matterRef}?`
      : `Spostare ${pendingAction?.row.name || 'il documento'} nel cestino? Potrai ripristinarlo.`

  const pageAllSelected = data.items.some((row) => row.actions.download)
    && data.items.filter((row) => row.actions.download).every((row) => selected.has(rowKey(row)))
  const hasFilters = Boolean(query.q || query.type || query.format || query.matter)

  return (
    <Page
      title="Archivio documenti"
      subtitle="Cerca, apri, modifica ed esporta i documenti conservati nei fascicoli dello studio."
      actions={
        <>
          <ButtonLink href="/template-atti/editor" tone="primary" title="Apre subito un foglio vuoto con timbro studio"><FilePlus2 size={15} /> Nuovo documento</ButtonLink>
          <ButtonLink href="/redazione-atti" tone="neutral"><PenLine size={15} /> Redazione atti</ButtonLink>
          <ButtonLink href="/template-atti/catalogo" tone="neutral"><BookOpenCheck size={15} /> Modelli</ButtonLink>
        </>
      }
    >
      <section className="iu-editor-pro-summary" aria-label="Riepilogo archivio documenti">
        <span><FileText size={16} /><b>{data.summary.active}</b> documenti</span>
        <span><Trash2 size={16} /><b>{data.summary.trash}</b> nel cestino</span>
        <span><Archive size={16} /><b>{data.summary.matters}</b> fascicoli</span>
        <span><ShieldCheck size={16} /><b>{data.summary.formats}</b> formati</span>
      </section>

      <Panel
        title={scopeLabel(query.scope)}
        subtitle={`${data.pagination.total} ${data.pagination.total === 1 ? 'risultato' : 'risultati'} nell'archivio dello studio.`}
        actions={query.scope === 'attivi' ? (
          <Button type="button" tone="neutral" onClick={exportOriginals} disabled={!selectedRows.length || exporting}>
            <FolderOutput size={15} /> {exporting ? 'Esporto...' : `Esporta originali${selectedRows.length ? ` (${selectedRows.length})` : ''}`}
          </Button>
        ) : undefined}
      >
        <div className="iu-editor-pro-scope" role="tablist" aria-label="Stato documenti">
          <button type="button" role="tab" aria-selected={query.scope === 'attivi'} className={query.scope === 'attivi' ? 'is-active' : ''} onClick={() => updateFilter('scope', 'attivi')}>
            <FileText size={15} /> Documenti <span>{data.summary.active}</span>
          </button>
          <button type="button" role="tab" aria-selected={query.scope === 'cestino'} className={query.scope === 'cestino' ? 'is-active' : ''} onClick={() => updateFilter('scope', 'cestino')}>
            <Trash2 size={15} /> Cestino <span>{data.summary.trash}</span>
          </button>
        </div>

        <div className="iu-editor-pro-filters">
          <label className="iu-editor-pro-search">
            <Search size={17} />
            <span className="sr-only">Cerca documenti</span>
            <input value={searchDraft} onChange={(event) => setSearchDraft(event.currentTarget.value)} placeholder="Nome, fascicolo, tipo, nota o fonte" />
          </label>
          <label>
            <span>Tipo</span>
            <select value={query.type} onChange={(event) => updateFilter('type', event.currentTarget.value)}>
              <option value="">Tutti i tipi</option>
              {data.facets.types.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}
            </select>
          </label>
          <label>
            <span>Formato</span>
            <select value={query.format} onChange={(event) => updateFilter('format', event.currentTarget.value)}>
              <option value="">Tutti i formati</option>
              {data.facets.formats.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}
            </select>
          </label>
          <label>
            <span>Fascicolo</span>
            <select value={query.matter} onChange={(event) => updateFilter('matter', event.currentTarget.value)}>
              <option value="">Tutti i fascicoli</option>
              {data.facets.matters.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}
            </select>
          </label>
          <button type="button" className="iu-editor-pro-reset" onClick={resetFilters} disabled={!hasFilters} title="Azzera filtri" aria-label="Azzera filtri"><X size={17} /></button>
        </div>

        {message ? <div className="iu-editor-pro-feedback is-success" role="status">{message}</div> : null}
        {error ? <div className="iu-editor-pro-feedback is-error" role="alert">{error}</div> : null}

        <div className={`iu-editor-pro-table-wrap${loading ? ' is-loading' : ''}`} aria-busy={loading}>
          {loading ? <div className="iu-editor-pro-loading">Aggiornamento archivio...</div> : data.items.length ? (
            <table className="iu-editor-pro-table">
              <thead>
                <tr>
                  {query.scope === 'attivi' ? <th className="is-select"><input type="checkbox" checked={pageAllSelected} onChange={togglePage} aria-label="Seleziona i documenti della pagina" /></th> : null}
                  <th>Documento</th>
                  <th>Fascicolo</th>
                  <th>Tipo e formato</th>
                  <th>Data</th>
                  <th className="is-actions">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={rowKey(row)}>
                    {query.scope === 'attivi' ? <td className="is-select" data-label="Seleziona"><input type="checkbox" checked={selected.has(rowKey(row))} onChange={() => toggleRow(row)} aria-label={`Seleziona ${row.name}`} /></td> : null}
                    <td data-label="Documento">
                      <strong>{row.name}</strong>
                      <span>{row.source} · {row.size || 'dimensione non disponibile'}</span>
                      {row.notes ? <small>{row.notes}</small> : null}
                    </td>
                    <td data-label="Fascicolo">
                      {row.actions.matter ? <a href={row.actions.matter}>{row.matterRef}</a> : <span>{row.matterRef}</span>}
                      <span>{row.matterTitle}</span>
                      {row.matterArchived ? <Badge tone="neutral">Archiviato</Badge> : null}
                    </td>
                    <td data-label="Tipo e formato"><Badge tone="primary">{row.typeLabel}</Badge><span>{row.format}</span></td>
                    <td data-label={row.inTrash ? 'Eliminato il' : 'Data'}>
                      <span>{row.inTrash ? row.deletedAt || 'data non disponibile' : row.documentDate || row.uploadedAt || 'data non disponibile'}</span>
                      {row.inTrash && row.deletedBy ? <small>{row.deletedBy}</small> : null}
                    </td>
                    <td className="is-actions" data-label="Azioni">
                      {row.actions.preview ? <a href={row.actions.preview} title="Visualizza" aria-label={`Visualizza ${row.name}`}><Eye size={16} /></a> : null}
                      {row.actions.download ? <a href={row.actions.download} title="Scarica originale" aria-label={`Scarica originale ${row.name}`}><Download size={16} /></a> : null}
                      {row.actions.edit ? <a href={row.actions.edit} title="Modifica" aria-label={`Modifica ${row.name}`}><PenLine size={16} /></a> : null}
                      {row.actions.matter ? <a href={row.actions.matter} title="Apri fascicolo" aria-label={`Apri fascicolo ${row.matterRef}`}><FolderOpen size={16} /></a> : null}
                      {row.actions.delete ? <button type="button" className="is-danger" title="Sposta nel cestino" aria-label={`Sposta nel cestino ${row.name}`} onClick={() => setPendingAction({ row, kind: 'trash', url: row.actions.delete })}><Trash2 size={16} /></button> : null}
                      {row.actions.restore ? <button type="button" title="Ripristina" aria-label={`Ripristina ${row.name}`} onClick={() => setPendingAction({ row, kind: 'restore', url: row.actions.restore })}><RotateCcw size={16} /></button> : null}
                      {row.actions.permanentDelete ? <button type="button" className="is-danger" title="Elimina definitivamente" aria-label={`Elimina definitivamente ${row.name}`} onClick={() => setPendingAction({ row, kind: 'permanent-delete', url: row.actions.permanentDelete })}><Trash2 size={16} /></button> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="iu-editor-pro-empty">
              <FileText size={24} />
              <strong>{query.scope === 'cestino' ? 'Il cestino è vuoto' : 'Nessun documento trovato'}</strong>
              <span>{hasFilters ? 'Azzera i filtri o modifica la ricerca.' : query.scope === 'cestino' ? 'I documenti spostati nel cestino appariranno qui.' : 'Apri un fascicolo per caricare il primo documento.'}</span>
              {hasFilters ? <Button type="button" tone="neutral" onClick={resetFilters}>Azzera filtri</Button> : query.scope === 'attivi' ? <ButtonLink href={data.actions.openMatters} tone="neutral">Apri fascicoli</ButtonLink> : null}
            </div>
          )}
        </div>

        {data.pagination.pages > 1 ? (
          <nav className="iu-editor-pro-pagination" aria-label="Pagine archivio documenti">
            <button type="button" onClick={() => updateFilter('page', query.page - 1)} disabled={query.page <= 1} aria-label="Pagina precedente"><ChevronLeft size={17} /></button>
            <span>{data.pagination.from}-{data.pagination.to} di {data.pagination.total} · pagina {data.pagination.page} di {data.pagination.pages}</span>
            <button type="button" onClick={() => updateFilter('page', query.page + 1)} disabled={query.page >= data.pagination.pages} aria-label="Pagina successiva"><ChevronRight size={17} /></button>
          </nav>
        ) : null}
      </Panel>

      <ConfirmDialog
        title={confirmTitle}
        message={actionBusy ? 'Operazione in corso...' : confirmMessage}
        open={Boolean(pendingAction)}
        onCancel={() => { if (!actionBusy) setPendingAction(null) }}
        onConfirm={runPendingAction}
      />
    </Page>
  )
}

export default EditorProfessionalePage
