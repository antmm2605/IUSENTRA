import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  FileCheck2,
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
import {
  emptyEmailPecPage,
  folderLabel,
  getEmailPecPage,
  type EmailFolder,
  type EmailPecPageData,
  type EmailPecRow,
  type EmailStatus,
} from '../emailData'
import './EmailPecPage.css'

type SortKey = 'recenti' | 'mittente' | 'oggetto' | 'pct'

const sortLabels: Record<SortKey, string> = {
  recenti: 'Più recenti',
  mittente: 'Mittente / destinatario',
  oggetto: 'Oggetto',
  pct: 'Esito PCT',
}

function sourceLabel(source: string): string {
  if (source === 'repository_reali') return 'dati applicativi'
  if (source === 'errore_controllato') return 'dati parziali'
  return source || 'casella PEC'
}

function StatCard({ icon, label, value, note, tone = 'primary' }:{ icon:ReactNode; label:string; value:number|string; note:string; tone?:EmailPecRow['tone'] }) {
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
  if (folder === 'INVIATI') return <Send size={15}/>
  if (folder === 'CESTINO') return <Trash2 size={15}/>
  return <Inbox size={15}/>
}

function rowPerson(item: EmailPecRow): string {
  if (item.folder === 'INVIATI') return item.recipients || 'Destinatario non indicato'
  return item.senderName || item.sender || 'Mittente non indicato'
}

function initials(value: string): string {
  const parts = value.replace(/[<>@.]/g, ' ').split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'PEC'
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
  if (label === 'Sincronizzazione PEC') {
    const nuove = Number(payload.nuove || 0)
    const allegati = Number(payload.allegati_salvati || 0)
    if (nuove || allegati) return `Sincronizzazione PEC completata: ${nuove} nuove PEC, ${allegati} allegati recuperati.`
  }
  return payload.messaggio || `${label}: operazione eseguita.`
}

function routeEmailId(): string {
  const match = window.location.pathname.match(/^\/(?:app-v2\/)?email\/messaggio\/([^/]+)/i)
  return match ? decodeURIComponent(match[1]) : ''
}

function FolderTabs({ data, folder, onChange }:{data:EmailPecPageData; folder:EmailFolder; onChange:(folder:EmailFolder)=>void}) {
  return (
    <div className="iu-mail-folders" role="tablist" aria-label="Cartelle PEC">
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

function EmailListRow({ item, selected, onSelect }:{item:EmailPecRow; selected:boolean; onSelect:()=>void}) {
  const person = rowPerson(item)
  return (
    <button className={`iu-mail-row ${selected ? 'is-selected' : ''} ${item.unread ? 'is-unread' : ''}`} type="button" onClick={onSelect}>
      <span className="iu-mail-avatar">{initials(person)}</span>
      <span className="iu-mail-main">
        <span className="iu-mail-row__top">
          <strong>{person}</strong>
          <time>{item.timeLabel}</time>
        </span>
        <span className="iu-mail-subject">{item.subject || '(nessun oggetto)'}</span>
        <span className="iu-mail-preview">{item.preview || 'Nessuna anteprima disponibile.'}</span>
        <span className="iu-mail-tags">
          {item.isPst ? <Badge tone="primary"><ShieldCheck size={12}/> PST</Badge> : null}
          {item.pctStatus ? <Badge tone={item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') ? 'danger' : 'warning'}>{item.pctStatus}</Badge> : null}
          {item.attachmentCount ? <em><Paperclip size={12}/> {item.attachmentCount}</em> : null}
        </span>
      </span>
    </button>
  )
}

function EmailPreview({ item, onAction }:{item?:EmailPecRow; onAction:(url:string,label:string)=>void}) {
  if (!item) {
    return (
      <section className="iu-mail-preview-card iu-mail-preview-empty">
        <Mail size={38}/>
        <h2>Seleziona una PEC</h2>
        <p>La lettura rapida comparirà qui, con esiti PCT, allegati e azioni operative.</p>
      </section>
    )
  }
  const person = rowPerson(item)
  return (
    <section className="iu-mail-preview-card">
      <header>
        <div>
          <span className="iu-mail-preview-eyebrow">{folderIcon(item.folder)} {folderLabel(item.folder)} · {item.origin || 'casella PEC'}</span>
          <h2>{item.subject || '(nessun oggetto)'}</h2>
        </div>
        <div className="iu-mail-preview-status">
          {item.unread ? <Badge tone="primary">Non letta</Badge> : <Badge tone="success">Letta</Badge>}
          {item.isPst ? <Badge tone="primary"><ShieldCheck size={12}/> PST</Badge> : null}
        </div>
      </header>
      <div className="iu-mail-meta">
        <div><span>{item.folder === 'INVIATI' ? 'A' : 'Da'}</span><strong>{person}</strong></div>
        <div><span>{item.folder === 'INVIATI' ? 'Mittente' : 'Destinatari'}</span><strong>{item.folder === 'INVIATI' ? (item.sender || '-') : (item.recipients || '-')}</strong></div>
        <div><span>Data</span><strong>{item.timeLabel || item.timestamp || '-'}</strong></div>
        <div><span>Allegati</span><strong>{item.attachmentCount || 0}</strong></div>
      </div>
      {item.pctStatus ? (
        <div className="iu-mail-pct-banner">
          <ShieldCheck size={18}/>
          <div>
            <strong>Esito telematico rilevato: {item.pctStatus}</strong>
            <span>Lex può aiutarti a collegare questa PEC a fascicolo, deposito, comunicazione cancelleria o prossima azione.</span>
          </div>
        </div>
      ) : null}
      <p className="iu-mail-body-preview">{item.preview || 'Nessuna anteprima testuale disponibile. Apri la vista completa per leggere HTML e allegati.'}</p>
      <footer>
        <Button variant="primary" href={item.detailHref}><Eye size={15}/> Apri</Button>
        {item.folder !== 'CESTINO' ? <Button href={item.replyHref}><Reply size={15}/> Rispondi</Button> : null}
        {item.folder !== 'CESTINO'
          ? <button type="button" onClick={() => onAction(item.trashHref, 'Sposta nel cestino')}><Trash2 size={15}/> Cestino</button>
          : <button type="button" onClick={() => onAction(item.restoreHref, 'Ripristina')}><Undo2 size={15}/> Ripristina</button>}
        {item.unread
          ? <button type="button" onClick={() => onAction(item.markReadHref, 'Segna letta')}><MailCheck size={15}/> Letta</button>
          : <button type="button" onClick={() => onAction(item.markUnreadHref, 'Segna non letta')}><Mail size={15}/> Non letta</button>}
      </footer>
    </section>
  )
}

function Inspector({ data, rows }:{data:EmailPecPageData; rows:EmailPecRow[]}) {
  const pstWaiting = rows.filter((item) => item.isPst && !item.pctStatus).slice(0, 4)
  const pctAlerts = rows.filter((item) => item.pctStatus && (item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') || item.pctStatus.includes('WARN'))).slice(0, 4)
  return (
    <aside className="iu-mail-inspector">
      <Panel title="Cabina PEC" subtitle="Controlli utili per studio legale" icon={<ShieldCheck size={17}/>}>
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
      <Panel title="Esiti da presidiare" icon={<AlertTriangle size={17}/>} count={pctAlerts.length}>
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
      <Panel title="PST in attesa" icon={<FileCheck2 size={17}/>} count={pstWaiting.length}>
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
      <Panel title="Azioni rapide" icon={<Sparkles size={17}/>}>
        <div className="iu-mail-quick-actions">
          <a href={data.actions.compose}><Send size={15}/> Nuova PEC</a>
          <a href={data.actions.settings}><Settings2 size={15}/> Parametri PEC</a>
          <a href={data.actions.localPecTest}><Wrench size={15}/> Test SMTP dal PC</a>
          <a href={data.actions.lex}><Sparkles size={15}/> Chiedi a Lex</a>
        </div>
      </Panel>
    </aside>
  )
}

export function EmailPecPage() {
  const [data, setData] = useState<EmailPecPageData>(emptyEmailPecPage)
  const [loading, setLoading] = useState(true)
  const [folder, setFolder] = useState<EmailFolder>('INBOX')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<EmailStatus>('tutti')
  const [sort, setSort] = useState<SortKey>('recenti')
  const [onlyPst, setOnlyPst] = useState(false)
  const [onlyAttachments, setOnlyAttachments] = useState(false)
  const [pctStatus, setPctStatus] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selectedId, setSelectedId] = useState(routeEmailId())
  const [statusLine, setStatusLine] = useState('')

  const load = () => {
    setLoading(true)
    getEmailPecPage({ folder, q: query, stato: status, pst: onlyPst, conAllegati: onlyAttachments, statoPct: pctStatus })
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getEmailPecPage({ folder, q: query, stato: status, pst: onlyPst, conAllegati: onlyAttachments, statoPct: pctStatus })
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [folder, status, onlyPst, onlyAttachments, pctStatus])

  const visible = useMemo(() => sortRows(data.items.filter((item) => isInsideQuery(item, query)), sort), [data.items, query, sort])
  const selected = visible.find((item) => item.id === selectedId) || visible[0]

  useEffect(() => {
    if (!visible.length) {
      setSelectedId('')
      return
    }
    const routeId = routeEmailId()
    if (routeId && visible.some((item) => item.id === routeId)) {
      setSelectedId(routeId)
      return
    }
    if (!visible.some((item) => item.id === selectedId)) setSelectedId(visible[0].id)
  }, [selectedId, visible])

  const runAction = (url: string, label: string) => {
    setStatusLine(`${label} in corso...`)
    postMailAction(url, label)
      .then((message) => {
        setStatusLine(message)
        load()
      })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : `${label}: errore operativo`))
  }

  const runSync = () => runAction(data.actions.sync, 'Sincronizzazione PEC')
  const runAutoEsiti = () => runAction(data.actions.autoEsiti, 'Auto-esiti')

  return (
    <main className="iu-content iu-email-page">
      <section className="iu-mail-hero">
        <div>
          <span className="iu-mail-eyebrow"><ShieldCheck size={16}/> Email PEC</span>
          <h1>Casella PEC dello studio</h1>
          <p>Posta certificata, messaggi PST, allegati, esiti PCT e comunicazioni di cancelleria in una vista professionale unica.</p>
        </div>
        <div className="iu-mail-hero__actions">
          <Button href={data.actions.operationalInbox}><Archive size={15}/> Apri casella</Button>
          <Button href={data.actions.settings}><Settings2 size={15}/> Impostazioni</Button>
          <button type="button" onClick={runAutoEsiti}><Sparkles size={15}/> Auto-esiti</button>
          <button type="button" onClick={runSync}><RefreshCw size={15}/> Aggiorna</button>
          <Button variant="primary" href={data.actions.compose}><Send size={16}/> Componi PEC</Button>
        </div>
      </section>

      <section className="iu-mail-stats" aria-label="Indicatori email PEC">
        <StatCard icon={<Mail size={19}/>} label="Totali" value={data.summary.total} note="messaggi archiviati" tone="primary"/>
        <StatCard icon={<Inbox size={19}/>} label="In arrivo" value={data.summary.inbox} note="ricevute in casella" tone="info"/>
        <StatCard icon={<MailCheck size={19}/>} label="Non lette" value={data.summary.unread} note="da lavorare" tone={data.summary.unread ? 'warning' : 'success'}/>
        <StatCard icon={<Send size={19}/>} label="Inviate" value={data.summary.sent} note="PEC inviate dallo studio" tone="success"/>
        <StatCard icon={<Trash2 size={19}/>} label="Cestino" value={data.summary.trash} note="spostate localmente" tone="neutral"/>
        <StatCard icon={<ShieldCheck size={19}/>} label="PST/PCT" value={data.summary.pst} note="messaggi telematici" tone="purple"/>
        <StatCard icon={<Paperclip size={19}/>} label="Allegati" value={data.summary.attachments} note="file recuperati" tone="orange"/>
        <StatCard icon={<CheckCircle2 size={19}/>} label="Collegate" value={data.summary.autoLinked} note="auto-esiti registrati" tone="success"/>
      </section>

      <section className="iu-mail-toolbar" aria-label="Filtri casella PEC">
        <FolderTabs data={data} folder={folder} onChange={setFolder}/>
        <label className="iu-mail-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') load() }} placeholder="Cerca mittente, destinatario, oggetto, RG, esito..."/></label>
        <button className="iu-mail-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><SlidersHorizontal size={16}/> Filtri</button>
        <button className="iu-mail-icon-btn" type="button" onClick={load} aria-label="Aggiorna vista"><RefreshCw size={17}/></button>
      </section>

      {advancedOpen ? (
        <section className="iu-mail-advanced" aria-label="Filtri avanzati email PEC">
          <label><span>Stato lettura</span><select value={status} onChange={(event) => setStatus(event.target.value as EmailStatus)}>{data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}</select></label>
          <label><span>Esito PCT</span><select value={pctStatus} onChange={(event) => setPctStatus(event.target.value)}>{data.facets.pctStatuses.map((facet) => <option value={facet.value} key={facet.value || 'all'}>{facet.label} ({facet.count})</option>)}</select></label>
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          <label className="iu-mail-check"><input type="checkbox" checked={onlyPst} onChange={(event) => setOnlyPst(event.target.checked)}/><span>Solo PEC/PST</span></label>
          <label className="iu-mail-check"><input type="checkbox" checked={onlyAttachments} onChange={(event) => setOnlyAttachments(event.target.checked)}/><span>Solo con allegati</span></label>
          <button type="button" onClick={() => { setStatus('tutti'); setOnlyPst(false); setOnlyAttachments(false); setPctStatus(''); setQuery('') }}>Reset</button>
        </section>
      ) : null}

      <section className="iu-mail-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione vista PEC...' : 'Dati PEC aggiornati'}</span>
        <small><Clock3 size={14}/> Le azioni di invio, sincronizzazione e fascicolazione restano sui servizi backend già auditati.</small>
        {statusLine ? <small className="iu-mail-operation-status">{statusLine}</small> : null}
      </section>

      <section className="iu-mail-layout">
        <div className="iu-mail-list-card">
          <header>
            <div><strong>{visible.length} messaggi</strong><span>{folderLabel(folder)} · {sourceLabel(data.source)}</span></div>
            <a href={`/email/?cartella=${folder}`}><Download size={15}/> Apri cartella</a>
          </header>
          <div className="iu-mail-list">
            {visible.map((item) => <EmailListRow item={item} selected={selected?.id === item.id} onSelect={() => setSelectedId(item.id)} key={item.id}/>) }
            {!visible.length ? (
              <div className="iu-mail-empty">
                <Mail size={34}/>
                <strong>Nessuna PEC nella vista corrente</strong>
                <span>Prova ad aggiornare IMAP, cambiare cartella o rimuovere i filtri.</span>
              </div>
            ) : null}
          </div>
        </div>
        <EmailPreview item={selected} onAction={runAction}/>
        <Inspector data={data} rows={visible}/>
      </section>

      <section className="iu-mail-lower-grid">
        <Panel title="Qualità PEC" subtitle="Controlli prima di deposito, cancelleria e fascicolo" icon={<ShieldCheck size={17}/>}>
          <div className="iu-mail-checklist">
            <span><CheckCircle2 size={16}/> In arrivo, inviate e cestino restano visibili come cartelle distinte.</span>
            <span><FileCheck2 size={16}/> PEC/PST ed esiti PCT sono evidenziati senza aprire ogni messaggio.</span>
            <span><Paperclip size={16}/> Allegati e anteprima restano accessibili dalla vista rapida.</span>
          </div>
        </Panel>
        <Panel title="Integrazioni operative" subtitle="Fascicoli, comunicazioni e Lex" icon={<Sparkles size={17}/>}>
          <div className="iu-mail-integrations">
            <a href="/fascicoli">Fascicoli</a>
            <a href="/telematico">Servizi telematici</a>
            <a href="/deposito/checklist">Checklist deposito</a>
            <a href="/lex?context=email-pec">Lex su PEC</a>
          </div>
        </Panel>
      </section>

      <FloatingLex
        context="email-pec"
        title="Lex AI PEC"
        body="Posso leggere il contesto della PEC selezionata, preparare risposta, estrarre RG, suggerire fascicolo e verificare esito PCT o comunicazione di cancelleria."
        primaryHref="/lex?context=email-pec"
        primaryLabel="Apri Lex sulla PEC"
        secondaryHref="/fascicoli"
        secondaryLabel="Vai ai fascicoli"
      />
    </main>
  )
}
