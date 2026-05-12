import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  FileCheck2,
  FileSignature,
  Inbox,
  Mail,
  MailCheck,
  Paperclip,
  RefreshCw,
  Reply,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Undo2,
  Wrench,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { JsonPostForm } from './JsonPostForm'
import {
  emptyEmailOrdinariaPage,
  emptyEmailPecPage,
  folderLabel,
  getEmailOrdinariaPage,
  getEmailOrdinariaDetail,
  getEmailPecPage,
  getEmailPecDetail,
  submitEmailBulkAction,
  type EmailFolder,
  type EmailDetailData,
  type EmailPecPageData,
  type EmailPecRow,
  type EmailStatus,
} from '../emailData'
import './EmailPecPage.css'

type MailboxMode = 'pec' | 'ordinaria'
type SortKey = 'recenti' | 'mittente' | 'oggetto' | 'pct'

const sortLabels: Record<SortKey, string> = {
  recenti: 'Più recenti',
  mittente: 'Mittente / destinatario',
  oggetto: 'Oggetto',
  pct: 'Esito PCT',
}

const mailboxCopy: Record<MailboxMode, {
  mode: MailboxMode
  includeTelematic: boolean
  emptyData: EmailPecPageData
  title: string
  eyebrow: string
  heroTitle: string
  heroText: string
  openLabel: string
  composeLabel: string
  syncLabel: string
  syncingLabel: string
  updatedLabel: string
  folderAria: string
  filtersAria: string
  statsAria: string
  emptyTitle: string
  emptyText: string
  previewEmptyTitle: string
  previewEmptyText: string
  sourceFallback: string
  lexContext: string
  lexTitle: string
  lexBody: string
  lexPrimaryLabel: string
}> = {
  pec: {
    mode: 'pec',
    includeTelematic: true,
    emptyData: emptyEmailPecPage,
    title: 'Email PEC',
    eyebrow: 'Email PEC',
    heroTitle: 'Casella PEC dello studio',
    heroText: 'Posta certificata, messaggi PST, allegati, esiti PCT e comunicazioni di cancelleria in una vista professionale unica.',
    openLabel: 'Apri casella',
    composeLabel: 'Componi PEC',
    syncLabel: 'Sincronizzazione PEC',
    syncingLabel: 'Sincronizzazione vista PEC...',
    updatedLabel: 'Dati PEC aggiornati',
    folderAria: 'Cartelle PEC',
    filtersAria: 'Filtri casella PEC',
    statsAria: 'Indicatori email PEC',
    emptyTitle: 'Nessuna PEC nella vista corrente',
    emptyText: 'Prova ad aggiornare IMAP, cambiare cartella o rimuovere i filtri.',
    previewEmptyTitle: 'Seleziona una PEC',
    previewEmptyText: 'La lettura rapida comparirà qui, con esiti PCT, allegati e azioni operative.',
    sourceFallback: 'casella PEC',
    lexContext: 'email-pec',
    lexTitle: 'Lex AI PEC',
    lexBody: 'Posso leggere il contesto della PEC selezionata, preparare risposta, estrarre RG, suggerire fascicolo e verificare esito PCT o comunicazione di cancelleria.',
    lexPrimaryLabel: 'Cerca comunicazioni',
  },
  ordinaria: {
    mode: 'ordinaria',
    includeTelematic: false,
    emptyData: emptyEmailOrdinariaPage,
    title: 'Email ordinaria',
    eyebrow: 'Email ordinaria',
    heroTitle: 'Casella email ordinaria dello studio',
    heroText: 'Messaggi ordinari ricevuti e inviati tramite la configurazione SMTP/IMAP dello studio, separati dalla PEC e consultabili senza confondere gli esiti telematici.',
    openLabel: 'Apri email',
    composeLabel: 'Componi email',
    syncLabel: 'Sincronizzazione email ordinaria',
    syncingLabel: 'Sincronizzazione vista email...',
    updatedLabel: 'Email ordinaria aggiornata',
    folderAria: 'Cartelle email ordinaria',
    filtersAria: 'Filtri email ordinaria',
    statsAria: 'Indicatori email ordinaria',
    emptyTitle: 'Nessuna email nella vista corrente',
    emptyText: 'Prova ad aggiornare IMAP, cambiare cartella o rimuovere i filtri.',
    previewEmptyTitle: 'Seleziona una email',
    previewEmptyText: 'La lettura rapida comparirà qui, con allegati, mittente, destinatari e azioni operative.',
    sourceFallback: 'casella email ordinaria',
    lexContext: 'email-ordinaria',
    lexTitle: 'Lex AI Email',
    lexBody: 'Posso aiutarti a preparare risposta, estrarre riferimenti cliente o fascicolo, riassumere il messaggio e proporre la prossima azione.',
    lexPrimaryLabel: 'Cerca comunicazioni',
  },
}

type MailboxCopy = (typeof mailboxCopy)[MailboxMode]

function sourceLabel(source: string, fallback: string): string {
  if (source === 'repository_reali') return 'dati dello studio'
  if (source === 'errore_controllato') return 'dati parziali'
  return source || fallback
}

function StatCard({ icon, label, value, note, tone = 'primary' }: { icon: ReactNode; label: string; value: number | string; note: string; tone?: EmailPecRow['tone'] }) {
  return (
    <article className={`iu-mail-stat iu-mail-stat--${tone}`}>
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

function folderIcon(folder: EmailFolder) {
  if (folder === 'INVIATI') return <Send size={15} />
  if (folder === 'CESTINO') return <Trash2 size={15} />
  return <Inbox size={15} />
}

function rowPerson(item: EmailPecRow): string {
  if (item.folder === 'INVIATI') return item.recipients || 'Destinatario non indicato'
  return item.senderName || item.sender || 'Mittente non indicato'
}

function initials(value: string, fallback: string): string {
  const parts = value.replace(/[<>@.]/g, ' ').split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || fallback
}

function isInsideQuery(item: EmailPecRow, query: string): boolean {
  const needle = normaliseText(query.trim())
  if (!needle) return true
  return normaliseText([
    item.sender,
    item.senderName,
    item.recipients,
    item.subject,
    item.preview,
    item.pctStatus,
    item.origin,
  ].join(' ')).includes(needle)
}

function sortRows(rows: EmailPecRow[], sort: SortKey): EmailPecRow[] {
  const copy = [...rows]
  if (sort === 'mittente') return copy.sort((a, b) => rowPerson(a).localeCompare(rowPerson(b), 'it'))
  if (sort === 'oggetto') return copy.sort((a, b) => a.subject.localeCompare(b.subject, 'it'))
  if (sort === 'pct') return copy.sort((a, b) => (b.pctStatus || '').localeCompare(a.pctStatus || '', 'it'))
  return copy.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
}

async function postMailAction(url: string, label: string): Promise<string> {
  if (!url) throw new Error(`${label}: percorso operativo non configurato`)
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  })
  if (!response.ok) throw new Error(`${label}: operazione non completata`)
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) return `${label}: operazione eseguita.`
  const payload = await response.json() as {
    ok?: boolean
    messaggio?: string
    errore?: string
    sync_errore?: string
    warning?: boolean
    nuove?: number
    allegati_salvati?: number
  }
  if (payload.ok === false) throw new Error(payload.errore || `${label}: errore operativo`)
  if (payload.warning && payload.sync_errore) {
    return `${payload.messaggio || `${label}: completata con avvisi.`} ${payload.sync_errore}`
  }
  if (label.startsWith('Sincronizzazione')) {
    const nuove = Number(payload.nuove || 0)
    const allegati = Number(payload.allegati_salvati || 0)
    if (nuove || allegati) return `${label} completata: ${nuove} nuovi messaggi, ${allegati} allegati recuperati.`
  }
  return payload.messaggio || `${label}: operazione eseguita.`
}

function routeEmailId(mode: MailboxMode): string {
  const segment = mode === 'ordinaria' ? 'email-ordinaria' : 'email'
  const match = window.location.pathname.match(new RegExp(`^/(?:app-v2/)?${segment}/messaggio/([^/]+)`, 'i'))
  return match ? decodeURIComponent(match[1]) : ''
}

function FolderTabs({ data, folder, onChange, ariaLabel }: { data: EmailPecPageData; folder: EmailFolder; onChange: (folder: EmailFolder) => void; ariaLabel: string }) {
  return (
    <div className="iu-mail-folders" role="tablist" aria-label={ariaLabel}>
      {data.facets.folders.map((facet) => (
        <button className={folder === facet.value ? 'is-active' : ''} type="button" onClick={() => onChange(facet.value)} key={facet.value}>
          {folderIcon(facet.value)}
          <span>{facet.label}</span>
          <b>{facet.count}</b>
        </button>
      ))}
    </div>
  )
}

function EmailListRow({
  item,
  selected,
  checked,
  onSelect,
  onToggleChecked,
  includeTelematic,
  fallbackInitials,
}: {
  item: EmailPecRow
  selected: boolean
  checked: boolean
  onSelect: () => void
  onToggleChecked: () => void
  includeTelematic: boolean
  fallbackInitials: string
}) {
  const person = rowPerson(item)
  return (
    <button className={`iu-mail-row ${selected ? 'is-selected' : ''} ${item.unread ? 'is-unread' : ''}`} type="button" onClick={onSelect}>
      <span className="iu-mail-row__check" onClick={(event) => event.stopPropagation()}>
        <input type="checkbox" checked={checked} onChange={onToggleChecked} aria-label={`Seleziona ${item.subject || person}`} />
      </span>
      <span className="iu-mail-avatar">{initials(person, fallbackInitials)}</span>
      <span className="iu-mail-main">
        <span className="iu-mail-row__top">
          <strong>{person}</strong>
          <time>{item.timeLabel}</time>
        </span>
        <span className="iu-mail-subject">{item.subject || '(nessun oggetto)'}</span>
        <span className="iu-mail-preview">{item.preview || 'Nessuna anteprima disponibile.'}</span>
        <span className="iu-mail-tags">
          {includeTelematic && item.isPst ? <Badge tone="primary"><ShieldCheck size={12} /> PST</Badge> : null}
          {includeTelematic && item.pctStatus ? <Badge tone={item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') ? 'danger' : 'warning'}>{item.pctStatus}</Badge> : null}
          {item.attachmentCount ? <em><Paperclip size={12} /> {item.attachmentCount}</em> : null}
        </span>
      </span>
    </button>
  )
}

function EmailFullDetail({
  item,
  detail,
  loading,
}: {
  item?: EmailPecRow
  detail: EmailDetailData | null
  loading: boolean
}) {
  if (!item) return null
  if (loading) {
    return <div className="iu-mail-full-detail"><strong>Caricamento messaggio completo...</strong></div>
  }
  if (!detail?.item) return null
  const bodyText = detail.bodyText || detail.item.preview
  return (
    <div className="iu-mail-full-detail" aria-label="Messaggio completo">
      <header>
        <strong>Messaggio completo</strong>
        <span>{detail.attachments.length} allegati</span>
      </header>
      {detail.bodyHtml ? (
        <iframe
          title="Corpo HTML email"
          sandbox=""
          srcDoc={detail.bodyHtml}
        />
      ) : (
        <pre>{bodyText || 'Nessun testo disponibile per questo messaggio.'}</pre>
      )}
      {detail.attachments.length ? (
        <div className="iu-mail-attachments">
          {detail.attachments.map((attachment) => (
            <article key={`${detail.item?.id}-${attachment.index}`}>
              <Paperclip size={16} />
              <div>
                <strong>{attachment.name}</strong>
                <span>{attachment.mime || 'file'} {attachment.sizeLabel ? `- ${attachment.sizeLabel}` : ''}</span>
              </div>
              {attachment.previewHref ? <a href={attachment.previewHref}>Apri</a> : null}
              {attachment.viewHref ? <a href={attachment.viewHref} target="_blank" rel="noreferrer">Visualizza</a> : null}
              {attachment.downloadHref ? <a href={attachment.downloadHref}>Scarica</a> : null}
            </article>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function EmailPreview({
  item,
  detail,
  detailLoading,
  onAction,
  copy,
}: {
  item?: EmailPecRow
  detail: EmailDetailData | null
  detailLoading: boolean
  onAction: (url: string, label: string) => void
  copy: MailboxCopy
}) {
  if (!item) {
    return (
      <section className="iu-mail-preview-card iu-mail-preview-empty">
        <Mail size={38} />
        <h2>{copy.previewEmptyTitle}</h2>
        <p>{copy.previewEmptyText}</p>
      </section>
    )
  }
  const person = rowPerson(item)
  const hasTelematicBanner = copy.includeTelematic && (item.pctStatus || item.isPst)
  return (
    <section className="iu-mail-preview-card">
      <header>
        <div>
          <span className="iu-mail-preview-eyebrow">{folderIcon(item.folder)} {folderLabel(item.folder)} · {item.origin || copy.sourceFallback}</span>
          <h2>{item.subject || '(nessun oggetto)'}</h2>
        </div>
        <div className="iu-mail-preview-status">
          {item.unread ? <Badge tone="primary">Non letta</Badge> : <Badge tone="success">Letta</Badge>}
          {copy.includeTelematic && item.isPst ? <Badge tone="primary"><ShieldCheck size={12} /> PST</Badge> : null}
        </div>
      </header>
      <div className="iu-mail-meta">
        <div><span>{item.folder === 'INVIATI' ? 'A' : 'Da'}</span><strong>{person}</strong></div>
        <div><span>{item.folder === 'INVIATI' ? 'Mittente' : 'Destinatari'}</span><strong>{item.folder === 'INVIATI' ? (item.sender || '-') : (item.recipients || '-')}</strong></div>
        <div><span>Data</span><strong>{item.timeLabel || item.timestamp || '-'}</strong></div>
        <div><span>Allegati</span><strong>{item.attachmentCount || 0}</strong></div>
      </div>
      {hasTelematicBanner ? (
        <div className="iu-mail-pct-banner">
          <ShieldCheck size={18} />
          <div>
            <strong>{item.pctStatus ? `Esito telematico rilevato: ${item.pctStatus}` : 'Comunicazione PST rilevata'}</strong>
            <span>Lex può aiutarti a collegare questa PEC a fascicolo, deposito, comunicazione cancelleria o prossima azione.</span>
          </div>
        </div>
      ) : null}
      <p className="iu-mail-body-preview">{item.preview || 'Nessuna anteprima testuale disponibile. Apri la vista completa per leggere HTML e allegati.'}</p>
      <footer>
        <Button variant="primary" href={item.detailHref}><Eye size={15} /> Apri</Button>
        {item.folder !== 'CESTINO' ? <Button href={item.replyHref}><Reply size={15} /> Rispondi</Button> : null}
        {item.folder !== 'CESTINO'
          ? <button type="button" onClick={() => onAction(item.trashHref, 'Sposta nel cestino')}><Trash2 size={15} /> Cestino</button>
          : <button type="button" onClick={() => onAction(item.restoreHref, 'Ripristina')}><Undo2 size={15} /> Ripristina</button>}
        {item.unread
          ? <button type="button" onClick={() => onAction(item.markReadHref, 'Segna letta')}><MailCheck size={15} /> Letta</button>
          : <button type="button" onClick={() => onAction(item.markUnreadHref, 'Segna non letta')}><Mail size={15} /> Non letta</button>}
      </footer>
      <EmailFullDetail item={item} detail={detail} loading={detailLoading} />
    </section>
  )
}

function PecInspector({ data, rows }: { data: EmailPecPageData; rows: EmailPecRow[] }) {
  const pstWaiting = rows.filter((item) => item.isPst && !item.pctStatus).slice(0, 4)
  const pctAlerts = rows.filter((item) => item.pctStatus && (item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') || item.pctStatus.includes('WARN'))).slice(0, 4)
  return (
    <aside className="iu-mail-inspector">
      <Panel title="Cabina PEC" subtitle="Controlli utili per studio legale" icon={<ShieldCheck size={17} />}>
        <div className="iu-mail-briefing">
          <article>
            <span>PEC/PST riconosciute</span>
            <strong>{data.summary.pst}</strong>
            <small>Messaggi con valore operativo telematico nella casella.</small>
          </article>
          <article>
            <span>Auto-collegate</span>
            <strong>{data.summary.autoLinked}</strong>
            <small>Esiti o comunicazioni già registrati nei fascicoli.</small>
          </article>
        </div>
      </Panel>
      <Panel title="Esiti da presidiare" icon={<AlertTriangle size={17} />} count={pctAlerts.length}>
        {pctAlerts.length ? (
          <div className="iu-mail-alerts">
            {pctAlerts.map((item) => (
              <a href={item.detailHref} key={item.id}>
                <Badge tone="danger">{item.pctStatus}</Badge>
                <strong>{item.subject}</strong>
                <span>{rowPerson(item)}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessun esito critico nella cartella visibile.</p>}
      </Panel>
      <Panel title="PST in attesa" icon={<FileCheck2 size={17} />} count={pstWaiting.length}>
        {pstWaiting.length ? (
          <div className="iu-mail-alerts">
            {pstWaiting.map((item) => (
              <a href={item.detailHref} key={item.id}>
                <Badge tone="warning">da collegare</Badge>
                <strong>{item.subject}</strong>
                <span>{item.timeLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna PEC PST in attesa nella vista corrente.</p>}
      </Panel>
      <Panel title="Azioni rapide" icon={<Sparkles size={17} />}>
        <div className="iu-mail-quick-actions">
          <a href={data.actions.compose}><Send size={15} /> Nuova PEC</a>
          <a href={data.actions.legalNotice}><FileSignature size={15} /> Notifica ex L. 53</a>
          <a href={data.actions.settings}><Settings2 size={15} /> Parametri PEC</a>
          <a href={data.actions.localPecTest}><Wrench size={15} /> Test SMTP dal PC</a>
        </div>
      </Panel>
    </aside>
  )
}

function OrdinaryInspector({ data, rows }: { data: EmailPecPageData; rows: EmailPecRow[] }) {
  const unread = rows.filter((item) => item.unread).slice(0, 4)
  const withAttachments = rows.filter((item) => item.attachmentCount > 0).slice(0, 4)
  return (
    <aside className="iu-mail-inspector">
      <Panel title="Cabina email" subtitle="Posta ordinaria separata dalla PEC" icon={<Mail size={17} />}>
        <div className="iu-mail-briefing">
          <article>
            <span>Da leggere</span>
            <strong>{data.summary.unread}</strong>
            <small>Messaggi ordinari non ancora lavorati.</small>
          </article>
          <article>
            <span>Allegati</span>
            <strong>{data.summary.attachments}</strong>
            <small>File recuperati dalla casella ordinaria.</small>
          </article>
        </div>
      </Panel>
      <Panel title="Email da leggere" icon={<MailCheck size={17} />} count={unread.length}>
        {unread.length ? (
          <div className="iu-mail-alerts">
            {unread.map((item) => (
              <a href={item.detailHref} key={item.id}>
                <Badge tone="primary">non letta</Badge>
                <strong>{item.subject}</strong>
                <span>{rowPerson(item)}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna email ordinaria non letta nella vista corrente.</p>}
      </Panel>
      <Panel title="Allegati recenti" icon={<Paperclip size={17} />} count={withAttachments.length}>
        {withAttachments.length ? (
          <div className="iu-mail-alerts">
            {withAttachments.map((item) => (
              <a href={item.detailHref} key={item.id}>
                <Badge tone="orange">{item.attachmentCount} allegati</Badge>
                <strong>{item.subject}</strong>
                <span>{item.timeLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessun allegato nella vista corrente.</p>}
      </Panel>
      <Panel title="Azioni rapide" icon={<Sparkles size={17} />}>
        <div className="iu-mail-quick-actions">
          <a href={data.actions.compose}><Send size={15} /> Nuova email</a>
          <a href={data.actions.settings}><Settings2 size={15} /> Parametri SMTP/IMAP</a>
          <a href={data.actions.sync}><RefreshCw size={15} /> Aggiorna casella</a>
        </div>
      </Panel>
    </aside>
  )
}

function MailboxStats({ data, mode }: { data: EmailPecPageData; mode: MailboxMode }) {
  if (mode === 'ordinaria') {
    return (
      <section className="iu-mail-stats" aria-label={mailboxCopy.ordinaria.statsAria}>
        <StatCard icon={<Mail size={19} />} label="Totali" value={data.summary.total} note="email ordinarie archiviate" tone="primary" />
        <StatCard icon={<Inbox size={19} />} label="In arrivo" value={data.summary.inbox} note="ricevute via IMAP" tone="info" />
        <StatCard icon={<MailCheck size={19} />} label="Non lette" value={data.summary.unread} note="da lavorare" tone={data.summary.unread ? 'warning' : 'success'} />
        <StatCard icon={<Send size={19} />} label="Inviate" value={data.summary.sent} note="email inviate dallo studio" tone="success" />
        <StatCard icon={<Trash2 size={19} />} label="Cestino" value={data.summary.trash} note="spostate localmente" tone="neutral" />
        <StatCard icon={<Paperclip size={19} />} label="Allegati" value={data.summary.attachments} note="file recuperati" tone="orange" />
      </section>
    )
  }
  return (
    <section className="iu-mail-stats" aria-label={mailboxCopy.pec.statsAria}>
      <StatCard icon={<Mail size={19} />} label="Totali" value={data.summary.total} note="messaggi archiviati" tone="primary" />
      <StatCard icon={<Inbox size={19} />} label="In arrivo" value={data.summary.inbox} note="ricevute in casella" tone="info" />
      <StatCard icon={<MailCheck size={19} />} label="Non lette" value={data.summary.unread} note="da lavorare" tone={data.summary.unread ? 'warning' : 'success'} />
      <StatCard icon={<Send size={19} />} label="Inviate" value={data.summary.sent} note="PEC inviate dallo studio" tone="success" />
      <StatCard icon={<Trash2 size={19} />} label="Cestino" value={data.summary.trash} note="spostate localmente" tone="neutral" />
      <StatCard icon={<ShieldCheck size={19} />} label="PST/PCT" value={data.summary.pst} note="messaggi telematici" tone="purple" />
      <StatCard icon={<Paperclip size={19} />} label="Allegati" value={data.summary.attachments} note="file recuperati" tone="orange" />
      <StatCard icon={<CheckCircle2 size={19} />} label="Collegate" value={data.summary.autoLinked} note="auto-esiti registrati" tone="success" />
    </section>
  )
}

function EmailMailboxPage({ mode }: { mode: MailboxMode }) {
  const copy = mailboxCopy[mode]
  const [data, setData] = useState<EmailPecPageData>(copy.emptyData)
  const [loading, setLoading] = useState(true)
  const [folder, setFolder] = useState<EmailFolder>('INBOX')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<EmailStatus>('tutti')
  const [sort, setSort] = useState<SortKey>('recenti')
  const [onlyPst, setOnlyPst] = useState(false)
  const [onlyAttachments, setOnlyAttachments] = useState(false)
  const [pctStatus, setPctStatus] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selectedId, setSelectedId] = useState(routeEmailId(mode))
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<EmailDetailData | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [statusLine, setStatusLine] = useState('')
  const [bulkWorking, setBulkWorking] = useState(false)

  const fetchPage = mode === 'ordinaria' ? getEmailOrdinariaPage : getEmailPecPage
  const fetchParams = {
    folder,
    q: query,
    stato: status,
    pst: copy.includeTelematic ? onlyPst : false,
    conAllegati: onlyAttachments,
    statoPct: copy.includeTelematic ? pctStatus : '',
  }

  const load = () => {
    setLoading(true)
    fetchPage(fetchParams)
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchPage(fetchParams)
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [folder, status, onlyPst, onlyAttachments, pctStatus])

  const visible = useMemo(() => sortRows(data.items.filter((item) => isInsideQuery(item, query)), sort), [data.items, query, sort])
  const selected = detail?.item && detail.item.id === selectedId ? detail.item : visible.find((item) => item.id === selectedId) || visible[0]
  const visibleIds = useMemo(() => visible.map((item) => item.id), [visible])
  const selectedVisibleCount = useMemo(() => visibleIds.filter((id) => selectedIds.has(id)).length, [selectedIds, visibleIds])
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id))
  const bulkActionKind = folder === 'CESTINO' ? 'delete' : 'trash'
  const bulkActionLabel = folder === 'CESTINO' ? 'Elimina selezione' : 'Sposta nel cestino'

  useEffect(() => {
    setSelectedIds((current) => {
      const validIds = new Set(data.items.map((item) => item.id))
      const next = new Set<string>()
      current.forEach((id) => {
        if (validIds.has(id)) next.add(id)
      })
      if (next.size === current.size) return current
      return next
    })
  }, [data.items])

  useEffect(() => {
    const routeId = routeEmailId(mode)
    if (routeId) {
      if (selectedId !== routeId) setSelectedId(routeId)
      return
    }
    if (!visible.length) {
      setSelectedId('')
      return
    }
    if (!visible.some((item) => item.id === selectedId)) setSelectedId(visible[0].id)
  }, [mode, selectedId, visible])

  useEffect(() => {
    const id = selectedId || routeEmailId(mode)
    if (!id) {
      setDetail(null)
      return
    }
    let active = true
    setDetailLoading(true)
    const loader = mode === 'ordinaria' ? getEmailOrdinariaDetail : getEmailPecDetail
    loader(id)
      .then((payload) => {
        if (active) setDetail(payload.item ? payload : null)
      })
      .finally(() => {
        if (active) setDetailLoading(false)
      })
    return () => { active = false }
  }, [mode, selectedId])

  const runAction = (url: string, label: string) => {
    setStatusLine(`${label} in corso...`)
    postMailAction(url, label)
      .then((message) => {
        setStatusLine(message)
        load()
      })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : `${label}: errore operativo`))
  }

  const toggleSelection = (id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAllVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (allVisibleSelected) {
        visibleIds.forEach((id) => next.delete(id))
      } else {
        visibleIds.forEach((id) => next.add(id))
      }
      return next
    })
  }

  const runBulkAction = () => {
    const ids = visibleIds.filter((id) => selectedIds.has(id))
    if (!ids.length) {
      setStatusLine('Seleziona almeno un messaggio.')
      return
    }
    setBulkWorking(true)
    setStatusLine(`${bulkActionLabel} in corso...`)
    submitEmailBulkAction(data.actions.bulkAction, ids, bulkActionKind)
      .then((message) => {
        setStatusLine(message)
        setSelectedIds((current) => {
          const next = new Set(current)
          ids.forEach((id) => next.delete(id))
          return next
        })
        load()
      })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : `${bulkActionLabel}: errore operativo`))
      .finally(() => setBulkWorking(false))
  }

  const runSync = () => runAction(data.actions.sync, copy.syncLabel)
  const runAutoEsiti = () => {
    if (data.actions.autoEsiti) runAction(data.actions.autoEsiti, 'Auto-esiti')
  }
  const sortOptions = (copy.includeTelematic ? Object.keys(sortLabels) : ['recenti', 'mittente', 'oggetto']) as SortKey[]

  return (
    <main className="iu-content iu-email-page">
      <section className="iu-mail-hero">
        <div>
          <span className="iu-mail-eyebrow">{copy.includeTelematic ? <ShieldCheck size={16} /> : <Mail size={16} />} {copy.eyebrow}</span>
          <h1>{copy.heroTitle}</h1>
          <p>{copy.heroText}</p>
        </div>
        <div className="iu-mail-hero__actions">
          <Button href={data.actions.operationalInbox}><Archive size={15} /> {copy.openLabel}</Button>
          <Button href={data.actions.settings}><Settings2 size={15} /> Impostazioni</Button>
          {data.actions.autoEsiti ? <button type="button" onClick={runAutoEsiti}><Sparkles size={15} /> Auto-esiti</button> : null}
          <button type="button" onClick={runSync}><RefreshCw size={15} /> Aggiorna</button>
          <Button variant="primary" href={data.actions.compose}><Send size={16} /> {copy.composeLabel}</Button>
        </div>
      </section>

      <MailboxStats data={data} mode={mode} />

      <section className="iu-mail-toolbar" aria-label={copy.filtersAria}>
        <FolderTabs data={data} folder={folder} onChange={setFolder} ariaLabel={copy.folderAria} />
        <label className="iu-mail-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') load() }} placeholder="Cerca mittente, destinatario, oggetto, riferimento..." /></label>
        <button className="iu-mail-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><SlidersHorizontal size={16} /> Filtri</button>
        <button className="iu-mail-icon-btn" type="button" onClick={load} aria-label="Aggiorna vista"><RefreshCw size={17} /></button>
      </section>

      {advancedOpen ? (
        <section className="iu-mail-advanced" aria-label={`Filtri avanzati ${copy.title}`}>
          <label><span>Stato lettura</span><select value={status} onChange={(event) => setStatus(event.target.value as EmailStatus)}>{data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}</select></label>
          {copy.includeTelematic ? <label><span>Esito PCT</span><select value={pctStatus} onChange={(event) => setPctStatus(event.target.value)}>{data.facets.pctStatuses.map((facet) => <option value={facet.value} key={facet.value || 'all'}>{facet.label} ({facet.count})</option>)}</select></label> : null}
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{sortOptions.map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          {copy.includeTelematic ? <label className="iu-mail-check"><input type="checkbox" checked={onlyPst} onChange={(event) => setOnlyPst(event.target.checked)} /><span>Solo PEC/PST</span></label> : null}
          <label className="iu-mail-check"><input type="checkbox" checked={onlyAttachments} onChange={(event) => setOnlyAttachments(event.target.checked)} /><span>Solo con allegati</span></label>
          <button type="button" onClick={() => { setStatus('tutti'); setOnlyPst(false); setOnlyAttachments(false); setPctStatus(''); setQuery('') }}>Reset</button>
        </section>
      ) : null}

      <section className="iu-mail-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? copy.syncingLabel : copy.updatedLabel}</span>
        <small><Clock3 size={14} /> Le azioni sono tracciate e separate tra PEC ed email ordinaria.</small>
        {selectedVisibleCount ? <small>{selectedVisibleCount} messaggi selezionati nella vista corrente.</small> : null}
        {statusLine ? <small className="iu-mail-operation-status">{statusLine}</small> : null}
      </section>

      <section className="iu-mail-layout">
        <div className="iu-mail-list-card">
          <header>
            <div><strong>{visible.length} messaggi</strong><span>{folderLabel(folder)} · {sourceLabel(data.source, copy.sourceFallback)}</span></div>
            <a href={`${data.actions.operationalInbox}?cartella=${folder}`}><Download size={15} /> Apri cartella</a>
          </header>
          {visible.length ? (
            <div className="iu-mail-list-select-all">
              <label>
                <input type="checkbox" checked={allVisibleSelected} onChange={toggleAllVisible} />
                <span>Seleziona tutti i messaggi visibili</span>
              </label>
            </div>
          ) : null}
          {selectedVisibleCount ? (
            <div className="iu-mail-bulkbar">
              <strong>{selectedVisibleCount} selezionati</strong>
              <span>{folder === 'CESTINO' ? "Nel cestino puoi eliminare definitivamente piu' messaggi insieme." : "Puoi spostare nel cestino piu' messaggi della vista corrente."}</span>
              <button type="button" onClick={runBulkAction} disabled={bulkWorking}>
                <Trash2 size={15} /> {bulkWorking ? `${bulkActionLabel}...` : bulkActionLabel}
              </button>
            </div>
          ) : null}
          <div className="iu-mail-list">
            {visible.map((item) => (
              <EmailListRow
                item={item}
                selected={selected?.id === item.id}
                checked={selectedIds.has(item.id)}
                onSelect={() => setSelectedId(item.id)}
                onToggleChecked={() => toggleSelection(item.id)}
                includeTelematic={copy.includeTelematic}
                fallbackInitials={mode === 'pec' ? 'PEC' : 'EM'}
                key={item.id}
              />
            ))}
            {!visible.length ? (
              <div className="iu-mail-empty">
                <Mail size={34} />
                <strong>{copy.emptyTitle}</strong>
                <span>{copy.emptyText}</span>
              </div>
            ) : null}
          </div>
        </div>
        <EmailPreview item={selected} detail={detail} detailLoading={detailLoading} onAction={runAction} copy={copy} />
        {mode === 'pec' ? <PecInspector data={data} rows={visible} /> : <OrdinaryInspector data={data} rows={visible} />}
      </section>

      <section className="iu-mail-lower-grid">
        <Panel title={mode === 'pec' ? 'Qualità PEC' : 'Qualità email'} subtitle={mode === 'pec' ? 'Controlli prima di deposito, cancelleria e fascicolo' : 'Controlli su casella ordinaria, allegati e risposte'} icon={<ShieldCheck size={17} />}>
          <div className="iu-mail-checklist">
            <span><CheckCircle2 size={16} /> In arrivo, inviate e cestino restano visibili come cartelle distinte.</span>
            <span><FileCheck2 size={16} /> {mode === 'pec' ? 'PEC/PST ed esiti PCT sono evidenziati senza aprire ogni messaggio.' : 'La posta ordinaria resta separata dalla PEC e dalla telematica.'}</span>
            <span><Paperclip size={16} /> Allegati e anteprima restano accessibili dalla vista rapida.</span>
          </div>
        </Panel>
        <Panel title="Integrazioni operative" subtitle="Fascicoli e comunicazioni" icon={<Sparkles size={17} />}>
          <div className="iu-mail-integrations">
            <a href="/fascicoli">Fascicoli</a>
            <a href={mode === 'pec' ? '/telematico' : '/messaggi'}>{mode === 'pec' ? 'Servizi telematici' : 'Messaggi'}</a>
            <a href={mode === 'pec' ? '/deposito/checklist' : '/clienti'}>{mode === 'pec' ? 'Checklist deposito' : 'Clienti'}</a>
          </div>
        </Panel>
      </section>

      <FloatingLex
        context={copy.lexContext}
        title={copy.lexTitle}
        body={copy.lexBody}
        primaryHref={data.actions.lex}
        primaryLabel={copy.lexPrimaryLabel}
        secondaryHref="/fascicoli"
        secondaryLabel="Vai ai fascicoli"
      />
    </main>
  )
}

export function EmailPecPage() {
  return <EmailMailboxPage mode="pec" />
}

export function EmailOrdinariaPage() {
  return <EmailMailboxPage mode="ordinaria" />
}

export function EmailComposePage({ mode }: { mode: MailboxMode }) {
  const copy = mailboxCopy[mode]
  const params = new URLSearchParams(window.location.search)
  const isOrdinary = mode === 'ordinaria'
  const action = isOrdinary ? '/email-ordinaria/scrivi' : '/email/scrivi'
  const backHref = isOrdinary ? '/email-ordinaria/?cartella=INBOX' : '/email/?cartella=INBOX'
  const settingsHref = isOrdinary ? '/impostazioni?tab=smtp' : '/impostazioni?tab=pec'
  const [recipient, setRecipient] = useState(params.get('a') || '')
  const [subject, setSubject] = useState(params.get('oggetto') || '')
  const [body, setBody] = useState('')

  return (
    <main className="iu-content iu-mail-compose-page">
      <section className="iu-mail-compose-hero">
        <div>
          <span className="iu-mail-eyebrow">{isOrdinary ? <Mail size={16} /> : <ShieldCheck size={16} />} {copy.eyebrow}</span>
          <h1>{isOrdinary ? 'Componi email ordinaria' : 'Componi PEC'}</h1>
          <p>
            {isOrdinary
              ? 'Invia un messaggio tramite la configurazione SMTP ordinaria dello studio, mantenendolo separato dalla PEC.'
              : 'Prepara un messaggio PEC usando il canale certificato configurato nello studio.'}
          </p>
        </div>
        <div className="iu-mail-compose-hero__actions">
          <Button href={backHref}><Archive size={15} /> Torna alla casella</Button>
          <Button href={settingsHref}><Settings2 size={15} /> Impostazioni</Button>
        </div>
      </section>

      <section className="iu-mail-compose-grid">
        <JsonPostForm className="iu-mail-compose-form" action={action}>
          <label>
            <span>Destinatario</span>
            <input
              type="email"
              name="a"
              value={recipient}
              onChange={(event) => setRecipient(event.target.value)}
              placeholder="cliente@example.it"
              autoComplete="email"
              required
            />
          </label>
          <input type="hidden" name="id_cliente" value="" />
          <label>
            <span>Oggetto</span>
            <input
              type="text"
              name="oggetto"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="Oggetto del messaggio"
              required
            />
          </label>
          <label>
            <span>Messaggio</span>
            <textarea
              name="corpo"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={14}
              placeholder="Scrivi il messaggio..."
            />
          </label>
          <footer>
            <button type="submit"><Send size={16} /> Invia</button>
            <a href={backHref}>Annulla</a>
          </footer>
        </JsonPostForm>

        <aside className="iu-mail-compose-side">
          <Panel title={isOrdinary ? 'Canale ordinario' : 'Canale PEC'} subtitle="Controllo operativo" icon={isOrdinary ? <Mail size={17} /> : <ShieldCheck size={17} />}>
            <div className="iu-mail-compose-checks">
              <span><CheckCircle2 size={16} /> Invio collegato alla casella selezionata.</span>
              <span><CheckCircle2 size={16} /> Rientro automatico in <strong>{isOrdinary ? 'Email ordinaria' : 'Email PEC'}</strong>.</span>
              <span><Settings2 size={16} /> Configurazione da <a href={settingsHref}>{isOrdinary ? 'SMTP/IMAP ordinario' : 'PEC'}</a>.</span>
            </div>
          </Panel>
          <Panel title="Anteprima rapida" subtitle="Controllo prima dell'invio" icon={<Eye size={17} />}>
            <div className="iu-mail-compose-preview">
              <span>A</span>
              <strong>{recipient || 'Destinatario non indicato'}</strong>
              <span>Oggetto</span>
              <strong>{subject || 'Oggetto non indicato'}</strong>
              <p>{body || 'Il testo comparirà qui mentre componi il messaggio.'}</p>
            </div>
          </Panel>
        </aside>
      </section>

      <FloatingLex
        context={copy.lexContext}
        title={copy.lexTitle}
        body={copy.lexBody}
        primaryHref="#lex"
        primaryLabel={copy.lexPrimaryLabel}
        secondaryHref={backHref}
        secondaryLabel={copy.title}
      />
    </main>
  )
}
