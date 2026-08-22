import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import {
  Archive,
  AlertTriangle,
  BadgeCheck,
  BriefcaseBusiness,
  CalendarPlus,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  FileText,
  Filter,
  FolderOpen,
  Mail,
  Maximize2,
  Minimize2,
  PencilLine,
  Phone,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserPlus,
  UsersRound,
  X,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { SyncedTopScrollbar } from './SyncedTopScrollbar'
import {
  emptyClientiPage,
  deleteCliente,
  deleteClienti,
  formatClienteStatus,
  formatClienteType,
  getClientiPage,
  type ClienteRow,
  type ClienteStato,
  type ClienteTipo,
  type ClientiPageData,
} from '../clientiData'
import { getCartellaClientePage, type CartellaClienteMatter } from '../clientiCartellaData'
import './AnagraficaClientiPage.css'

type SortKey = 'nome' | 'recenti' | 'pratiche' | 'completezza'

const sortLabels: Record<SortKey, string> = {
  nome: 'Nome cliente',
  recenti: 'Aggiornati di recente',
  pratiche: 'Più procedimenti',
  completezza: 'Da completare prima',
}

function StatCard({
  icon,
  label,
  value,
  note,
  tone = 'primary',
}:{
  icon: ReactNode
  label: string
  value: number | string
  note: string
  tone?: ClienteRow['tone']
}) {
  return (
    <article className={`iu-cli-stat iu-cli-stat--${tone}`}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function normaliseText(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function hasNoContacts(item: ClienteRow): boolean {
  return !item.email && !item.phone && !item.pec
}

function hasQualityIssue(item: ClienteRow): boolean {
  return item.missingFields.length > 0 || !item.privacyOk || item.documentExpired || hasNoContacts(item)
}

function isInsideQuery(item: ClienteRow, query: string): boolean {
  const needle = normaliseText(query.trim())
  if (!needle) return true
  return normaliseText([
    item.name,
    item.subtitle,
    item.fiscalId,
    item.email,
    item.phone,
    item.pec,
    item.attorney,
    item.tags.join(' '),
    formatClienteType(item.type),
    formatClienteStatus(item.status),
  ].join(' ')).includes(needle)
}

function qualityTone(item: ClienteRow): ClienteRow['tone'] {
  if (item.documentExpired) return 'danger'
  if (item.missingFields.length > 2) return 'orange'
  if (item.missingFields.length || !item.privacyOk || hasNoContacts(item)) return 'warning'
  return 'success'
}

function qualityLabel(item: ClienteRow): string {
  if (item.documentExpired) return 'Documento scaduto'
  if (item.missingFields.length) return 'Da completare'
  if (!item.privacyOk) return 'Privacy da verificare'
  if (hasNoContacts(item)) return 'Recapiti assenti'
  return 'Completa'
}

function sortRows(rows: ClienteRow[], sort: SortKey): ClienteRow[] {
  const copy = [...rows]
  if (sort === 'pratiche') return copy.sort((a, b) => b.matters - a.matters || a.name.localeCompare(b.name, 'it'))
  if (sort === 'completezza') {
    return copy.sort((a, b) => Number(hasQualityIssue(b)) - Number(hasQualityIssue(a)) || b.missingFields.length - a.missingFields.length)
  }
  if (sort === 'recenti') return copy.sort((a, b) => (b.lastUpdated || '').localeCompare(a.lastUpdated || ''))
  return copy.sort((a, b) => a.name.localeCompare(b.name, 'it'))
}

type ClienteQuickPanelState = {
  item: ClienteRow
  x: number
  y: number
}

type ClienteQuickPanelMatters = {
  loading: boolean
  itemId: string
  matters: CartellaClienteMatter[]
  message: string
}

function placeQuickPanel(event: MouseEvent<HTMLElement>): Pick<ClienteQuickPanelState, 'x' | 'y'> {
  const padding = 12
  const panelWidth = 430
  const panelHeight = 660
  return {
    x: Math.max(padding, Math.min(event.clientX, window.innerWidth - panelWidth - padding)),
    y: Math.max(padding, Math.min(event.clientY, window.innerHeight - panelHeight - padding)),
  }
}

function clientePortalHref(item: ClienteRow): string {
  return `/app/portale-clienti?id_cliente=${encodeURIComponent(item.id)}`
}

function clienteNuovoFascicoloHref(item: ClienteRow): string {
  return `/fascicoli/nuovo?id_cliente=${encodeURIComponent(item.id)}`
}

function clienteNuovoPreventivoHref(item: ClienteRow): string {
  return `/preventivi/nuovo?id_cliente=${encodeURIComponent(item.id)}`
}

function clienteNuovoMessaggioHref(item: ClienteRow): string {
  return `/messaggi/nuovo?id_cliente=${encodeURIComponent(item.id)}&canale=EMAIL&from_cliente=${encodeURIComponent(item.id)}`
}

function clienteNuovaScadenzaHref(item: ClienteRow): string {
  return `/scadenze/nuova?id_cliente=${encodeURIComponent(item.id)}&from_cliente=${encodeURIComponent(item.id)}`
}

function clienteFatturaHref(item: ClienteRow): string {
  return `/fatturazione/nuova?id_cliente=${encodeURIComponent(item.id)}`
}

function buildClienteContactText(item: ClienteRow): string {
  return [
    item.name,
    item.fiscalId ? `C.F. / P.IVA: ${item.fiscalId}` : '',
    item.pec ? `PEC: ${item.pec}` : '',
    item.email ? `Email: ${item.email}` : '',
    item.phone ? `Telefono: ${item.phone}` : '',
  ].filter(Boolean).join('\n')
}

function RowActions({
  item,
  deleting,
  onDelete,
}:{
  item: ClienteRow
  deleting: boolean
  onDelete: (item: ClienteRow) => void
}) {
  return (
    <div className="iu-cli-actions" aria-label={`Azioni cliente ${item.name}`}>
      <a href={item.href} aria-label={`Apri scheda cliente ${item.name}`} title="Apri scheda cliente"><Eye size={15}/></a>
      <a href={item.editHref} aria-label={`Modifica cliente ${item.name}`} title="Modifica cliente"><PencilLine size={15}/></a>
      <a href={item.folderHref} aria-label={`Apri cartella cliente ${item.name}`} title="Apri cartella cliente"><FolderOpen size={15}/></a>
      <button type="button" onClick={() => onDelete(item)} disabled={deleting} aria-label={`Elimina cliente ${item.name}`} title="Elimina cliente">
        <Trash2 size={15}/>
      </button>
    </div>
  )
}

function ClienteQuickPanel({
  state,
  onClose,
  onDelete,
}:{
  state: ClienteQuickPanelState
  onClose: () => void
  onDelete: (item: ClienteRow) => void
}) {
  const { item } = state
  const [copied, setCopied] = useState(false)
  const [matterState, setMatterState] = useState<ClienteQuickPanelMatters>({
    loading: false,
    itemId: item.id,
    matters: [],
    message: '',
  })

  useEffect(() => {
    setCopied(false)
    let active = true
    const hasDeclaredMatters = item.matters > 0 || item.activeMatters > 0
    if (!hasDeclaredMatters) {
      setMatterState({ loading: false, itemId: item.id, matters: [], message: 'Nessun fascicolo collegato visibile.' })
      return () => {
        active = false
      }
    }

    setMatterState({ loading: true, itemId: item.id, matters: [], message: 'Carico i fascicoli collegati...' })
    getCartellaClientePage(item.id)
      .then((payload) => {
        if (!active) return
        const matters = [...payload.matters.active, ...payload.matters.archived]
        setMatterState({
          loading: false,
          itemId: item.id,
          matters,
          message: matters.length ? '' : 'Nessun fascicolo collegato visibile.',
        })
      })
      .catch(() => {
        if (!active) return
        setMatterState({
          loading: false,
          itemId: item.id,
          matters: [],
          message: 'Cartella cliente non disponibile in questo momento.',
        })
      })

    return () => {
      active = false
    }
  }, [item.id, item.matters, item.activeMatters])

  const copyContacts = () => {
    const text = buildClienteContactText(item)
    if (!text || !navigator.clipboard?.writeText) {
      setCopied(false)
      return
    }
    void navigator.clipboard.writeText(text).then(() => setCopied(true)).catch(() => setCopied(false))
  }

  const matters = matterState.itemId === item.id ? matterState.matters : []
  const matterMessage = matterState.itemId === item.id ? matterState.message : ''

  return (
    <aside
      className="iu-cli-quick-panel"
      role="dialog"
      aria-label={`Pannello rapido cliente ${item.name}`}
      style={{ left: state.x, top: state.y }}
      onClick={(event) => event.stopPropagation()}
      onContextMenu={(event) => event.preventDefault()}
    >
      <header className="iu-cli-quick-panel__header">
        <div>
          <strong>{item.name}</strong>
          <span>{item.subtitle || item.fiscalId || formatClienteType(item.type)}</span>
        </div>
        <button type="button" onClick={onClose} aria-label="Chiudi pannello rapido">
          <X size={16}/>
        </button>
      </header>

      <div className="iu-cli-quick-panel__meta">
        <Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge>
        <span>{item.matters === 1 ? '1 fascicolo' : `${item.matters} fascicoli`}</span>
        {item.pec ? <span>PEC presente</span> : <span>PEC da completare</span>}
      </div>

      <div className="iu-cli-quick-panel__contacts">
        {item.fiscalId ? <span>C.F. / P.IVA: {item.fiscalId}</span> : null}
        {item.phone ? <span><Phone size={13}/> {item.phone}</span> : null}
        {item.email ? <span><Mail size={13}/> {item.email}</span> : null}
        {item.pec ? <span><ShieldCheck size={13}/> {item.pec}</span> : null}
      </div>

      <section className="iu-cli-quick-panel__section" aria-label="Fascicoli del cliente">
        <div className="iu-cli-quick-panel__section-title">
          <strong>Fascicoli cliente</strong>
          <a href={item.folderHref}>Cartella completa</a>
        </div>
        {matterState.loading ? <small>{matterMessage}</small> : null}
        {!matterState.loading && matters.length ? (
          <div className="iu-cli-quick-panel__matters">
            {matters.slice(0, 8).map((matter) => (
              <a key={matter.id} href={matter.href || `/fascicoli/${encodeURIComponent(matter.id)}`}>
                <strong>{matter.title}</strong>
                <span>{matter.subtitle || matter.counterparty || 'Fascicolo cliente'}</span>
                <small>{matter.documents} documenti · {matter.activities} attività</small>
              </a>
            ))}
          </div>
        ) : null}
        {!matterState.loading && !matters.length ? <small>{matterMessage}</small> : null}
      </section>

      <nav className="iu-cli-quick-panel__actions" aria-label="Azioni rapide cliente">
        <a href={item.href}><Eye size={15}/> Apri scheda cliente</a>
        <a href={item.editHref}><PencilLine size={15}/> Modifica anagrafica</a>
        <a href={item.folderHref}><FolderOpen size={15}/> Visualizza fascicoli cliente</a>
        <a href={clientePortalHref(item)}><UsersRound size={15}/> Portale clienti</a>
        <a href={clienteNuovoFascicoloHref(item)}><BriefcaseBusiness size={15}/> Nuovo fascicolo</a>
        <a href={clienteNuovoPreventivoHref(item)}><FileText size={15}/> Nuovo preventivo</a>
        <a href={clienteNuovoMessaggioHref(item)}><Mail size={15}/> Nuovo messaggio</a>
        <a href={clienteNuovaScadenzaHref(item)}><CalendarPlus size={15}/> Nuova scadenza</a>
        <a href={clienteFatturaHref(item)}><FileText size={15}/> Nuova fattura</a>
        <button type="button" onClick={copyContacts}><Copy size={15}/> {copied ? 'Contatti copiati' : 'Copia contatti'}</button>
        <button type="button" className="iu-cli-quick-panel__danger" onClick={() => onDelete(item)}><Trash2 size={15}/> Elimina cliente</button>
      </nav>
    </aside>
  )
}

function ContactBlock({ item }:{item: ClienteRow}) {
  if (hasNoContacts(item)) return <span className="iu-cli-muted">-</span>
  return (
    <div className="iu-cli-contact">
      {item.phone ? <span><Phone size={13}/> {item.phone}</span> : null}
      {item.email ? <span><Mail size={13}/> {item.email}</span> : null}
      {item.pec ? <span><ShieldCheck size={13}/> {item.pec}</span> : null}
    </div>
  )
}

function ClienteMobileCard({
  item,
  checked,
  onToggle,
  deleting,
  onDelete,
  onOpenQuickPanel,
}:{
  item: ClienteRow
  checked: boolean
  onToggle: () => void
  deleting: boolean
  onDelete: (item: ClienteRow) => void
  onOpenQuickPanel: (event: MouseEvent<HTMLElement>, item: ClienteRow) => void
}) {
  return (
    <article className="iu-cli-mobile-card" onContextMenu={(event) => onOpenQuickPanel(event, item)}>
      <header>
        <label><input type="checkbox" checked={checked} onChange={onToggle}/><span>{item.name}</span></label>
        <Badge tone={item.tone}>{formatClienteStatus(item.status)}</Badge>
      </header>
      <a href={item.href} className="iu-cli-mobile-card__title">{item.name}</a>
      <p>{item.subtitle || item.fiscalId || 'Anagrafica cliente'}</p>
      <dl>
        <div><dt>Tipo</dt><dd>{formatClienteType(item.type)}</dd></div>
        <div><dt>C.F. / P.IVA</dt><dd>{item.fiscalId || '-'}</dd></div>
        <div><dt>Avv. referente</dt><dd>{item.attorney || '-'}</dd></div>
        <div><dt>Pratiche</dt><dd>{item.matters}</dd></div>
      </dl>
      <ContactBlock item={item}/>
      <footer>
        <Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge>
        <span><BriefcaseBusiness size={14}/> {item.activeMatters} attive</span>
        <RowActions item={item} deleting={deleting} onDelete={onDelete}/>
      </footer>
    </article>
  )
}

function ClientiTable({
  items,
  selected,
  onToggle,
  onToggleAll,
  deletingIds,
  onDelete,
  onOpenQuickPanel,
}:{
  items: ClienteRow[]
  selected: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
  deletingIds: Set<string>
  onDelete: (item: ClienteRow) => void
  onOpenQuickPanel: (event: MouseEvent<HTMLElement>, item: ClienteRow) => void
}) {
  const tableCardRef = useRef<HTMLElement>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))

  useEffect(() => {
    const syncFullscreenState = () => setFullscreen(document.fullscreenElement === tableCardRef.current)
    document.addEventListener('fullscreenchange', syncFullscreenState)
    return () => document.removeEventListener('fullscreenchange', syncFullscreenState)
  }, [])

  useEffect(() => {
    if (!fullscreen) return undefined
    const previousOverflow = document.body.style.overflow
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setFullscreen(false)
    }
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [fullscreen])

  const toggleFullscreen = async () => {
    const tableCard = tableCardRef.current
    if (!tableCard) return
    if (fullscreen) {
      if (document.fullscreenElement === tableCard) {
        try {
          await document.exitFullscreen()
        } catch {
          // La vista espansa dell'app resta disponibile anche quando il browser nega l'uscita nativa.
        }
      }
      setFullscreen(false)
      return
    }
    if (tableCard.requestFullscreen) {
      try {
        await tableCard.requestFullscreen()
        setFullscreen(true)
        return
      } catch {
        // La vista espansa dell'app mantiene la tabella operativa quando il browser nega il fullscreen nativo.
      }
    }
    setFullscreen(true)
  }

  return (
    <section
      className={`iu-cli-table-card${fullscreen ? ' iu-cli-table-card--fullscreen' : ''}`}
      aria-label="Elenco clienti"
      ref={tableCardRef}
    >
      <div className="iu-cli-table-head">
        <div className="iu-cli-table-head__summary">
          <strong><UsersRound size={16}/> {items.length} clienti</strong>
          <span>{items.length === 1 ? '1 risultato visibile' : `${items.length} risultati visibili`}</span>
        </div>
        <div className="iu-cli-table-head__actions">
          <button
            className="iu-cli-table-fullscreen"
            type="button"
            onClick={() => void toggleFullscreen()}
            aria-label={fullscreen ? 'Chiudi elenco clienti a schermo intero' : 'Apri elenco clienti a schermo intero'}
            aria-pressed={fullscreen}
            title={fullscreen ? 'Chiudi schermo intero' : 'Apri a schermo intero'}
          >
            {fullscreen ? <Minimize2 size={16}/> : <Maximize2 size={16}/>}
            <span>{fullscreen ? 'Chiudi schermo intero' : 'Apri a schermo intero'}</span>
          </button>
        </div>
      </div>
      <SyncedTopScrollbar className="iu-cli-table-wrap">
        <table className="iu-cli-table">
          <thead>
            <tr>
              <th><input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Seleziona tutti i clienti visibili"/></th>
              <th>Cliente</th>
              <th>Tipo</th>
              <th>C.F. / P.IVA</th>
              <th>Contatti</th>
              <th>Avv. referente</th>
              <th>Pratiche</th>
              <th>Qualità</th>
              <th>Stato</th>
              <th className="iu-cli-table-actions-head">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="iu-cli-client-row" onContextMenu={(event) => onOpenQuickPanel(event, item)}>
                <td><input type="checkbox" checked={selected.has(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.name}`}/></td>
                <td className="iu-cli-title-cell">
                  <a href={item.href}>{item.name}</a>
                  <span>{item.subtitle || item.tags.join(', ') || 'Anagrafica cliente'}</span>
                </td>
                <td><Badge tone="neutral">{formatClienteType(item.type)}</Badge></td>
                <td>{item.fiscalId || '-'}</td>
                <td><ContactBlock item={item}/></td>
                <td>{item.attorney || '-'}</td>
                <td><span className="iu-cli-matter-count">{item.matters}</span></td>
                <td><Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge></td>
                <td><Badge tone={item.tone}>{formatClienteStatus(item.status)}</Badge></td>
                <td className="iu-cli-table-actions-cell"><RowActions item={item} deleting={deletingIds.has(item.id)} onDelete={onDelete}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </SyncedTopScrollbar>
      <div className="iu-cli-mobile-list">
        {items.map((item) => (
          <ClienteMobileCard
            item={item}
            checked={selected.has(item.id)}
            onToggle={() => onToggle(item.id)}
            deleting={deletingIds.has(item.id)}
            onDelete={onDelete}
            onOpenQuickPanel={onOpenQuickPanel}
            key={item.id}
          />
        ))}
      </div>
      {!items.length ? <p className="iu-empty">Nessun cliente corrisponde ai filtri impostati.</p> : null}
    </section>
  )
}

function InsightPanel({ data, visible }:{data: ClientiPageData; visible: ClienteRow[]}) {
  const daCompletare = visible.filter(hasQualityIssue).slice(0, 4)
  const withProcedures = visible.filter((item) => item.matters > 0 || item.activeMatters > 0).length
  return (
    <aside className="iu-cli-insights">
      <Panel title="Cabina anagrafiche" subtitle="Controlli utili prima di incarico, deposito e fatturazione" icon={<BadgeCheck size={17}/>}>
        <div className="iu-cli-briefing">
          <article>
            <span>Completezza operativa</span>
            <strong>{data.summary.incomplete} anagrafiche da completare</strong>
            <small>Controllo su recapiti, privacy, documento e dati minimi per conferimento.</small>
          </article>
          <article>
            <span>Clienti collegati</span>
            <strong>{withProcedures} clienti con procedimenti visibili</strong>
            <small>La nuova interfaccia è attiva: salvataggi e controlli restano tracciati nello studio.</small>
          </article>
        </div>
      </Panel>
      <Panel title="Da verificare" icon={<AlertTriangle size={17}/>} count={daCompletare.length}>
        {daCompletare.length ? (
          <div className="iu-cli-alerts">
            {daCompletare.map((item) => (
              <a href={item.href} key={item.id}>
                <Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge>
                <strong>{item.name}</strong>
                <span>
                  {item.missingFields.length
                    ? `Mancano: ${item.missingFields.slice(0, 3).join(', ')}`
                    : item.documentExpired
                      ? 'Documento di identità scaduto'
                      : 'Consenso privacy o recapiti da verificare'}
                </span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna criticità sulle anagrafiche visibili.</p>}
      </Panel>
      <Panel title="Azioni rapide" icon={<Sparkles size={17}/>}>
        <div className="iu-cli-quick-actions">
          <a href="/clienti/nuovo"><UserPlus size={15}/> Nuovo cliente</a>
          <a href="/soggetti/nuovo"><UsersRound size={15}/> Nuovo soggetto</a>
          <a href="/preventivi/"><FileText size={15}/> Preventivi e incarichi</a>
          <a href="#lex" data-lex-open data-lex-context="clienti"><Sparkles size={15}/> Chiedi a Lex</a>
        </div>
      </Panel>
    </aside>
  )
}

export function AnagraficaClientiPage() {
  const [data, setData] = useState<ClientiPageData>(emptyClientiPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [type, setType] = useState<ClienteTipo>('tutti')
  const [status, setStatus] = useState<ClienteStato>('tutti')
  const [sort, setSort] = useState<SortKey>('nome')
  const [attorney, setAttorney] = useState('')
  const [onlyIncomplete, setOnlyIncomplete] = useState(false)
  const [withoutContacts, setWithoutContacts] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')
  const [quickPanel, setQuickPanel] = useState<ClienteQuickPanelState | null>(null)

  const refresh = () => {
    setLoading(true)
    getClientiPage().then(setData).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getClientiPage()
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const visible = useMemo(() => {
    const attorneyNeedle = normaliseText(attorney)
    return sortRows(data.items.filter((item) => {
      if (!isInsideQuery(item, query)) return false
      if (type !== 'tutti' && item.type !== type) return false
      if (status !== 'tutti' && item.status !== status) return false
      if (onlyIncomplete && !hasQualityIssue(item)) return false
      if (withoutContacts && !hasNoContacts(item)) return false
      if (attorneyNeedle && !normaliseText(item.attorney).includes(attorneyNeedle)) return false
      return true
    }), sort)
  }, [attorney, data.items, onlyIncomplete, query, sort, status, type, withoutContacts])

  const selectedIds = useMemo(
    () => visible.filter((item) => selected.has(item.id)).map((item) => item.id),
    [selected, visible],
  )
  const selectedVisible = selectedIds.length
  const toggle = (id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const toggleAll = () => {
    setSelected((current) => {
      const allSelected = visible.length > 0 && visible.every((item) => current.has(item.id))
      if (allSelected) return new Set([...current].filter((id) => !visible.some((item) => item.id === id)))
      return new Set([...current, ...visible.map((item) => item.id)])
    })
  }

  useEffect(() => {
    if (!quickPanel) return undefined
    const closePanel = () => setQuickPanel(null)
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closePanel()
    }
    window.addEventListener('click', closePanel)
    window.addEventListener('resize', closePanel)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      window.removeEventListener('click', closePanel)
      window.removeEventListener('resize', closePanel)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [quickPanel])

  const openQuickPanel = (event: MouseEvent<HTMLElement>, item: ClienteRow) => {
    event.preventDefault()
    event.stopPropagation()
    const position = placeQuickPanel(event)
    setQuickPanel({ item, ...position })
  }

  const handleDelete = async (item: ClienteRow) => {
    setQuickPanel(null)
    if (!window.confirm(`Eliminare il cliente "${item.name}"?`)) return
    setError('')
    setFeedback('')
    setDeletingIds((current) => new Set(current).add(item.id))
    try {
      const result = await deleteCliente(item.id)
      setFeedback(result.message)
      setSelected((current) => {
        const next = new Set(current)
        next.delete(item.id)
        return next
      })
      refresh()
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Eliminazione cliente non riuscita.')
    } finally {
      setDeletingIds((current) => {
        const next = new Set(current)
        next.delete(item.id)
        return next
      })
    }
  }

  const handleBulkDelete = async () => {
    if (!selectedIds.length) return
    const label = selectedIds.length === 1 ? '1 cliente selezionato' : `${selectedIds.length} clienti selezionati`
    if (!window.confirm(`Eliminare ${label}?`)) return
    setError('')
    setFeedback('')
    setBulkDeleting(true)
    try {
      const result = await deleteClienti(selectedIds)
      setFeedback(result.message)
      setSelected((current) => new Set([...current].filter((id) => !selectedIds.includes(id))))
      refresh()
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Eliminazione multipla clienti non riuscita.')
    } finally {
      setBulkDeleting(false)
    }
  }

  return (
    <main className="iu-content iu-clienti-page">
      <section className="iu-cli-hero">
        <div>
          <span className="iu-cli-eyebrow"><UsersRound size={16}/> Clienti e anagrafiche</span>
          <h1>Anagrafica Clienti</h1>
          <p>Persone fisiche e giuridiche assistite dallo studio, con stato, recapiti, procedimenti, qualità dati e privacy sempre leggibili.</p>
        </div>
        <div className="iu-cli-hero__actions">
          <Button href="/clienti/esporta"><Download size={15}/> Esporta</Button>
          <Button href="/clienti?stato=ARCHIVIATO"><Archive size={15}/> Archivio clienti</Button>
          <Button variant="primary" href="/clienti/nuovo"><UserPlus size={16}/> Nuovo cliente</Button>
        </div>
      </section>

      <section className="iu-cli-stats" aria-label="Indicatori anagrafica clienti">
        <StatCard icon={<UsersRound size={19}/>} label="Totali" value={data.summary.total} note="clienti in anagrafica" tone="primary"/>
        <StatCard icon={<CheckCircle2 size={19}/>} label="Attivi" value={data.summary.active} note="assistiti operativi" tone="success"/>
        <StatCard icon={<Sparkles size={19}/>} label="Potenziali" value={data.summary.potential} note="da convertire" tone="warning"/>
        <StatCard icon={<Archive size={19}/>} label="Archiviati" value={data.summary.archived} note="non operativi" tone="neutral"/>
        <StatCard icon={<BriefcaseBusiness size={19}/>} label="Con procedimenti" value={data.summary.withMatters} note="fascicoli o pratiche" tone="info"/>
        <StatCard icon={<AlertTriangle size={19}/>} label="Da completare" value={data.summary.incomplete} note="dati mancanti" tone="orange"/>
        <StatCard icon={<Phone size={19}/>} label="Senza recapiti" value={data.summary.withoutContacts} note="telefono, email o PEC assenti" tone="warning"/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Privacy" value={data.summary.privacyMissing} note="consenso da verificare" tone="purple"/>
        <StatCard icon={<FileText size={19}/>} label="Documenti scaduti" value={data.summary.documentsExpired} note="identità da aggiornare" tone="danger"/>
      </section>

      <section className="iu-cli-toolbar" aria-label="Filtri clienti">
        <label className="iu-cli-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca per nome, CF, P.IVA, email, telefono..."/></label>
        <label><span>Tipo</span><select value={type} onChange={(event) => setType(event.target.value as ClienteTipo)}>{data.facets.types.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}</select></label>
        <label><span>Stato</span><select value={status} onChange={(event) => setStatus(event.target.value as ClienteStato)}>{data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}</select></label>
        <button className="iu-cli-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><Filter size={16}/> Filtri</button>
        <button className="iu-cli-icon-btn" type="button" onClick={refresh} aria-label="Aggiorna clienti"><RefreshCw size={17}/></button>
      </section>

      {advancedOpen ? (
        <section className="iu-cli-advanced" aria-label="Filtri avanzati clienti">
          <label><span>Avvocato referente</span><input value={attorney} onChange={(event) => setAttorney(event.target.value)} placeholder="Nome referente..."/></label>
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          <label className="iu-cli-check"><input type="checkbox" checked={onlyIncomplete} onChange={(event) => setOnlyIncomplete(event.target.checked)}/><span>Solo incomplete, privacy, recapiti o documenti da verificare</span></label>
          <label className="iu-cli-check"><input type="checkbox" checked={withoutContacts} onChange={(event) => setWithoutContacts(event.target.checked)}/><span>Solo senza recapiti</span></label>
        </section>
      ) : null}

      <section className="iu-cli-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione anagrafiche...' : 'Dati aggiornati'}</span>
        <small><ShieldCheck size={14}/> Dettaglio, modifica e invii usano i dati di studio senza duplicazioni.</small>
        {selectedVisible ? <small className="iu-cli-selected">{selectedVisible} selezionati</small> : null}
        {feedback ? <small className="iu-cli-feedback">{feedback}</small> : null}
        {error ? <small className="iu-cli-error">{error}</small> : null}
      </section>

      <section className="iu-cli-layout">
        <div className="iu-cli-main-list">
          {selectedVisible ? (
            <div className="iu-cli-bulkbar">
              <strong>{selectedVisible} clienti selezionati</strong>
              <a href="/clienti/esporta"><Download size={14}/> Esporta selezione</a>
              <a href="#lex" data-lex-open data-lex-context="clienti"><Sparkles size={14}/> Chiedi controllo a Lex</a>
              <button type="button" onClick={handleBulkDelete} disabled={bulkDeleting}>
                <Trash2 size={14}/> {bulkDeleting ? 'Eliminazione...' : 'Elimina selezione'}
              </button>
              <button type="button" onClick={() => setSelected(new Set())}>Annulla</button>
            </div>
          ) : null}
          <ClientiTable
            items={visible}
            selected={selected}
            onToggle={toggle}
            onToggleAll={toggleAll}
            deletingIds={deletingIds}
            onDelete={handleDelete}
            onOpenQuickPanel={openQuickPanel}
          />
        </div>
        <InsightPanel data={data} visible={visible}/>
      </section>

      {quickPanel ? (
        <ClienteQuickPanel
          state={quickPanel}
          onClose={() => setQuickPanel(null)}
          onDelete={handleDelete}
        />
      ) : null}

      <section className="iu-cli-lower-grid">
        <Panel title="Qualità dati anagrafici" subtitle="Informazioni da tenere pulite prima di incarico, atto e fattura" icon={<BadgeCheck size={17}/>}>
          <div className="iu-cli-checklist">
            <span><CheckCircle2 size={16}/> C.F. / P.IVA e recapiti sempre visibili nella lista</span>
            <span><ShieldCheck size={16}/> Privacy e documenti segnalati senza aprire la scheda</span>
            <span><BriefcaseBusiness size={16}/> Procedimenti collegati separati dal semplice stato cliente</span>
          </div>
        </Panel>
        <Panel title="Collegamenti operativi" subtitle="Azioni tipiche dalla pagina anagrafica" icon={<FolderOpen size={17}/>}>
          <div className="iu-cli-integrations">
            <a href="/clienti/nuovo">Nuovo cliente</a>
            <a href="/soggetti/nuovo">Nuovo soggetto</a>
            <a href="/preventivi/">Preventivo</a>
            <a href="/fascicoli/nuovo">Fascicolo</a>
          </div>
        </Panel>
      </section>

      <FloatingLex
        context="clienti"
        title="Lex AI anagrafiche"
        body="Posso controllare quali clienti bloccano conferimento, privacy, preventivo o fascicolo, e preparare una checklist di completamento senza modificare i dati."
        primaryHref="#lex"
        primaryLabel="Apri Lex sui clienti"
        secondaryHref="/global-search?tipo=clienti"
        secondaryLabel="Cerca nello studio"
      />
    </main>
  )
}
