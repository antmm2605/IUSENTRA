import { useEffect, useMemo, useState, type MouseEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FolderOpen,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyTelematicoPage,
  getTelematicoPage,
  type TelematicoCase,
  type TelematicoChannel,
  type TelematicoChannelId,
  type TelematicoControlItem,
  type TelematicoEvent,
  type TelematicoPageData,
} from '../telematicoData'
import type { Tone } from '../data'
import './TelematicoPage.css'

const portalIcon: Record<TelematicoChannelId, ReactNode> = {
  pst: <Building2 size={21}/>,
  pdp: <ShieldCheck size={21}/>,
  pat: <FileCheck2 size={21}/>,
  ptt: <FileText size={21}/>,
}

const portalToneLabel: Record<TelematicoChannelId | 'altro', string> = {
  pst: 'PST',
  pdp: 'PDP',
  pat: 'PAT',
  ptt: 'PTT',
  altro: 'TEL',
}

function StatCard({ icon, label, value, note, tone = 'primary' }:{ icon:ReactNode; label:string; value:number|string; note:string; tone?:Tone }) {
  return (
    <article className={`iu-tel-stat iu-tel-stat--${tone}`}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function portalBadge(portal: TelematicoChannelId | 'altro') {
  if (portal === 'altro') return <Badge tone="neutral">TEL</Badge>
  return <Badge tone={portal === 'pdp' ? 'danger' : portal === 'pat' ? 'success' : portal === 'ptt' ? 'warning' : 'primary'}>{portalToneLabel[portal]}</Badge>
}

function sourceLabel(source: string): string {
  return source === 'repository_reali' ? 'dati applicativi' : 'servizio applicativo'
}

function sameTelematicoPage(href: string): boolean {
  try {
    const url = new URL(href, window.location.origin)
    if (url.origin !== window.location.origin) return false
    const path = url.pathname.replace(/\/+$/, '').toLowerCase() || '/'
    return path === '/telematico' || path === '/app-v2/telematico'
  } catch {
    return false
  }
}

function ChannelCard({
  channel,
  selected,
  onSelect,
  onAction,
}:{
  channel:TelematicoChannel
  selected:boolean
  onSelect:(channel:TelematicoChannel)=>void
  onAction:(event:MouseEvent<HTMLAnchorElement>, channel:TelematicoChannel, actionIndex:number)=>void
}) {
  const attention = channel.attentionNeeded > 0
  return (
    <article
      className={`iu-tel-channel iu-tel-channel--${channel.tone} ${selected ? 'is-selected' : ''}`}
      tabIndex={0}
      onClick={(event) => {
        if ((event.target as HTMLElement).closest('a,button')) return
        onSelect(channel)
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect(channel)
        }
      }}
    >
      <header>
        <div className="iu-tel-channel__icon">{portalIcon[channel.id]}</div>
        <div>
          <span>{channel.label}</span>
          <h2>{channel.title}</h2>
        </div>
        <Badge tone={attention ? 'warning' : channel.cases ? 'success' : 'neutral'}>{channel.statusText}</Badge>
      </header>
      <p>{channel.description}</p>
      <div className="iu-tel-channel__badges">
        {channel.badges.map((badge) => <Badge tone={channel.demoMode ? 'warning' : channel.pkcs11Mode ? 'success' : 'primary'} key={badge}>{badge}</Badge>)}
      </div>
      <dl>
        <div><dt>Casi</dt><dd>{channel.cases}</dd></div>
        <div><dt>Import completi</dt><dd>{channel.importCompleted}</dd></div>
        <div><dt>Da presidiare</dt><dd>{channel.attentionNeeded}</dd></div>
      </dl>
      <small className="iu-tel-channel__sync">{channel.lastSyncAt ? `Ultimo allineamento: ${channel.lastSyncAt}` : channel.environmentLabel || 'Nessun allineamento ancora registrato.'}</small>
      <footer>
        {channel.quickActions.slice(0, 3).map((action, index) => (
          <a className={index === 1 ? 'is-primary' : ''} href={action.href} onClick={(event) => onAction(event, channel, index)} key={`${channel.id}-${action.label}`}>
            {index === 0 ? <ExternalLink size={15}/> : index === 1 ? <UploadCloud size={15}/> : <FolderOpen size={15}/>} {action.label}
          </a>
        ))}
      </footer>
    </article>
  )
}

function ActiveChannelPanel({
  channel,
  actionIndex,
}:{
  channel:TelematicoChannel
  actionIndex:number
}) {
  const action = channel.quickActions[actionIndex] || channel.quickActions[0]
  const importAction = channel.quickActions[1] || action
  const checkAction = channel.quickActions[2] || action
  return (
    <section id="canale-attivo" className={`iu-tel-active-channel iu-tel-active-channel--${channel.tone}`}>
      <div className="iu-tel-active-channel__icon">{portalIcon[channel.id]}</div>
      <div className="iu-tel-active-channel__copy">
        <span>Canale pronto</span>
        <h2>{action?.label || channel.title}</h2>
        <p>{channel.description}</p>
        <dl>
          <div><dt>Canale</dt><dd>{channel.title}</dd></div>
          <div><dt>Stato</dt><dd>{channel.statusText}</dd></div>
          <div><dt>Pratiche</dt><dd>{channel.cases}</dd></div>
        </dl>
      </div>
      <div className="iu-tel-active-channel__actions">
        <a href={importAction.href}>Importa pratica</a>
        <a href={channel.homeHref}>Apri superficie</a>
        <a href={checkAction.href}>Controlli</a>
      </div>
    </section>
  )
}

function ControlList({ title, items, empty, icon }:{title:string; items:TelematicoControlItem[]; empty:string; icon:ReactNode}) {
  return (
    <Panel title={title} icon={icon} count={items.length}>
      {items.length ? (
        <div className="iu-tel-control-list">
          {items.slice(0, 5).map((item) => (
            <a href={item.href} key={item.id}>
              {portalBadge(item.portal)}
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
              </div>
              <Badge tone={item.tone}>{item.badge}</Badge>
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">{empty}</p>}
    </Panel>
  )
}

function CaseRow({ item }:{item:TelematicoCase}) {
  return (
    <a className={`iu-tel-case iu-tel-case--${item.tone}`} href={item.href}>
      <span className="iu-tel-case__portal">{portalBadge(item.portal)}</span>
      <span className="iu-tel-case__main">
        <strong>{item.title}</strong>
        <small>{item.subtitle}</small>
        <em>{item.subject || 'Oggetto non indicato'}</em>
      </span>
      <span className="iu-tel-case__meta">
        <b>{item.documentsCount}</b>
        <small>documenti</small>
      </span>
      <span className="iu-tel-case__meta">
        <b>{item.openTasks}</b>
        <small>task</small>
      </span>
      <Badge tone={item.tone}>{item.statusText}</Badge>
    </a>
  )
}

function EventCard({ item }:{item:TelematicoEvent}) {
  return (
    <a className="iu-tel-event" href={item.href}>
      <span>{portalBadge(item.portal)}</span>
      <div>
        <strong>{item.title}</strong>
        <small>{item.subtitle}</small>
        <time>{item.timestamp}</time>
      </div>
      {item.badge ? <Badge tone={item.tone}>{item.badge}</Badge> : <ArrowRight size={15}/>}
    </a>
  )
}

function QualityGrid({ data }:{data:TelematicoPageData}) {
  const checks = [
    { icon: <ShieldCheck size={17}/>, label: 'Canali autorizzati', text: 'PST, PDP, PAT e PTT restano su portali ufficiali, Local Signer o import file/payload autorizzati.' },
    { icon: <Database size={17}/>, label: 'Repository unico', text: 'Documenti, eventi, udienze, comunicazioni e istanze finiscono nel fascicolo interno.' },
    { icon: <ClipboardCheck size={17}/>, label: 'Predisposto deposito', text: `${data.summary.blocked} blocchi e ${data.summary.warnings} warning vengono esposti prima della firma.` },
    { icon: <Sparkles size={17}/>, label: 'Lex contestuale', text: 'Lex legge contesto telematico, RG, portale, esiti, documenti censiti e prossima azione.' },
  ]
  return (
    <div className="iu-tel-quality-grid">
      {checks.map((item) => (
        <article key={item.label}>
          <div>{item.icon}</div>
          <strong>{item.label}</strong>
          <span>{item.text}</span>
        </article>
      ))}
    </div>
  )
}

function normaliseSearch(value: string) {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

export function TelematicoPage() {
  const [data, setData] = useState<TelematicoPageData>(emptyTelematicoPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [activeChannel, setActiveChannel] = useState<{ id:TelematicoChannelId; actionIndex:number }>({ id: 'pst', actionIndex: 0 })

  const load = () => {
    setLoading(true)
    getTelematicoPage()
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getTelematicoPage()
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const filteredCases = useMemo(() => {
    const needle = normaliseSearch(query.trim())
    if (!needle) return data.recentCases
    return data.recentCases.filter((item) => normaliseSearch([
      item.title,
      item.subtitle,
      item.subject,
      item.portalLabel,
      item.statusText,
    ].join(' ')).includes(needle))
  }, [data.recentCases, query])

  const priorityItems = [
    ...data.controlTower.blockedCases,
    ...data.controlTower.pendingOutcomes,
    ...data.controlTower.incompleteImports,
    ...data.controlTower.warnings,
  ].slice(0, 6)
  const selectedChannel = data.channels.find((channel) => channel.id === activeChannel.id) || data.channels[0]

  const selectChannel = (channel: TelematicoChannel, actionIndex = 0) => {
    setActiveChannel({ id: channel.id, actionIndex })
    window.requestAnimationFrame(() => {
      document.getElementById('canale-attivo')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  const handleChannelAction = (event: MouseEvent<HTMLAnchorElement>, channel: TelematicoChannel, actionIndex: number) => {
    const action = channel.quickActions[actionIndex]
    if (!action || !sameTelematicoPage(action.href)) return
    event.preventDefault()
    selectChannel(channel, actionIndex)
    const url = new URL(action.href, window.location.origin)
    const nextUrl = `${url.pathname}${url.search}${url.hash}`
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
    if (nextUrl !== currentUrl) {
      window.history.pushState({ telematicoChannel: channel.id, action: actionIndex }, '', nextUrl)
    }
  }

  return (
    <main className="iu-content iu-telematico-page">
      <section className="iu-tel-hero">
        <div>
          <span className="iu-tel-eyebrow"><ShieldCheck size={16}/> Un presidio unico per i portali telematici</span>
          <h1>Centro Servizi Telematici</h1>
          <p>PST/PolisWeb, SIGP, PDP Penale, PAT/SIGA e PTT/SIGIT in una regia operativa: accessi, acquisizioni, fascicoli importati, controlli e prossime attività.</p>
          <div className="iu-tel-hero__chips">
            <Badge tone="primary">no scraping</Badge>
            <Badge tone="success">Local Signer</Badge>
            <Badge tone="warning">import autorizzati</Badge>
            <Badge tone="purple">Lex AI</Badge>
          </div>
        </div>
        <div className="iu-tel-hero__actions">
          <Button href={data.actions.checklistHref}><ClipboardCheck size={16}/> Checklist deposito</Button>
          <Button href={data.actions.firmaDigitaleHref}><FileCheck2 size={16}/> Firma digitale</Button>
          <button type="button" onClick={load}><RefreshCw size={16}/> Aggiorna</button>
        </div>
      </section>

      {data.notices.length ? (
        <section className="iu-tel-notices" aria-label="Avvisi telematici">
          {data.notices.map((notice) => (
            <article className={`iu-tel-notice iu-tel-notice--${notice.tone}`} key={`${notice.title}-${notice.body}`}>
              <AlertTriangle size={18}/>
              <div><strong>{notice.title}</strong><span>{notice.body}</span></div>
            </article>
          ))}
        </section>
      ) : null}

      <section className="iu-tel-stats" aria-label="Indicatori telematici">
        <StatCard icon={<FolderOpen size={19}/>} label="Pratiche telematiche" value={data.summary.total} note="fascicoli sincronizzati o importati" tone="primary"/>
        <StatCard icon={<Building2 size={19}/>} label="PST / PDP" value={data.summary.pst + data.summary.pdp} note="ministero giustizia" tone="info"/>
        <StatCard icon={<FileCheck2 size={19}/>} label="PAT / SIGA" value={data.summary.pat} note="amministrativo" tone="success"/>
        <StatCard icon={<FileText size={19}/>} label="PTT / SIGIT" value={data.summary.ptt} note="tributario" tone="warning"/>
        <StatCard icon={<AlertTriangle size={19}/>} label="Da presidiare" value={data.summary.attentionNeeded + data.summary.blocked} note="warning, blocchi e import" tone={data.summary.attentionNeeded || data.summary.blocked ? 'danger' : 'success'}/>
      </section>

      <section className="iu-tel-section-head">
        <div>
          <span>Canali ufficiali</span>
          <h2>Accesso ai portali</h2>
        </div>
        <small>{loading ? 'Sincronizzazione dati telematici...' : `Dati aggiornati · ${sourceLabel(data.source)}`}</small>
      </section>

      <section className="iu-tel-channel-grid">
        {data.channels.map((channel) => (
          <ChannelCard
            channel={channel}
            selected={selectedChannel?.id === channel.id}
            onSelect={selectChannel}
            onAction={handleChannelAction}
            key={channel.id}
          />
        )) }
      </section>

      {selectedChannel ? <ActiveChannelPanel channel={selectedChannel} actionIndex={activeChannel.actionIndex}/> : null}

      <section className="iu-tel-command-grid">
        <div className="iu-tel-command-main">
          <Panel title="Regia telematica operativa" subtitle="Esiti, import incompleti, warning e predeposito" icon={<ShieldCheck size={17}/>} count={priorityItems.length}>
            {priorityItems.length ? (
              <div className="iu-tel-priority-list">
                {priorityItems.map((item) => (
                  <a href={item.href} key={item.id}>
                    {portalBadge(item.portal)}
                    <div><strong>{item.title}</strong><span>{item.subtitle}</span></div>
                    <Badge tone={item.tone}>{item.badge}</Badge>
                  </a>
                ))}
              </div>
            ) : <p className="iu-empty">Nessuna criticità telematica aperta: i canali risultano presidiati.</p>}
          </Panel>
        </div>
        <ControlList title="Esiti in attesa" icon={<Clock3 size={17}/>} items={data.controlTower.pendingOutcomes} empty="Nessun esito in attesa."/>
        <ControlList title="Import incompleti" icon={<Download size={17}/>} items={data.controlTower.incompleteImports} empty="Nessun import incompleto."/>
        <ControlList title="Controlli predeposito" icon={<ClipboardCheck size={17}/>} items={[...data.controlTower.predeposito, ...data.controlTower.blockedCases]} empty="Nessun blocco predeposito."/>
      </section>

      <section className="iu-tel-workspace">
        <div className="iu-tel-cases-card">
          <header>
            <div>
              <span>Pratiche recenti</span>
              <h2>Fascicoli telematici</h2>
            </div>
            <label className="iu-tel-search"><Search size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca RG, soggetto, portale, stato..."/></label>
          </header>
          <div className="iu-tel-case-list">
            {filteredCases.map((item) => <CaseRow item={item} key={item.id}/>) }
            {!filteredCases.length ? (
              <div className="iu-tel-empty">
                <FolderOpen size={34}/>
                <strong>Nessuna pratica nella vista corrente</strong>
                <span>Apri un portale o importa un payload autorizzato per alimentare la regia telematica.</span>
              </div>
            ) : null}
          </div>
        </div>
        <aside className="iu-tel-timeline">
          <Panel title="Cronologia recente" subtitle="Import, sincronizzazioni ed esiti" icon={<Clock3 size={17}/>} count={data.recentEvents.length}>
            {data.recentEvents.length ? <div className="iu-tel-event-list">{data.recentEvents.slice(0, 8).map((item) => <EventCard item={item} key={item.id}/>)}</div> : <p className="iu-empty">Nessun evento telematico recente.</p>}
          </Panel>
          <Panel title="Azioni rapide" icon={<Sparkles size={17}/>}>
            <div className="iu-tel-quick-links">
              <a href={data.actions.connectionStatusHref}><RefreshCw size={15}/> Stato connessioni</a>
              <a href={data.actions.localSignerHref}><ShieldCheck size={15}/> Local Signer</a>
              <a href={data.actions.emailHref}><FileText size={15}/> PEC ed esiti</a>
              <a href={data.actions.lexHref}><Sparkles size={15}/> Lex telematico</a>
            </div>
          </Panel>
        </aside>
      </section>

      <section className="iu-tel-lower-grid">
        <Panel title="Qualità telematica" subtitle="Cosa viene controllato prima di deposito e import" icon={<CheckCircle2 size={17}/>}>
          <QualityGrid data={data}/>
        </Panel>
        <Panel title="Suggerimenti Lex AI" subtitle="Prossime mosse operative" icon={<Sparkles size={17}/>} count={data.lexSuggestions.length}>
          {data.lexSuggestions.length ? (
            <div className="iu-tel-lex-suggestions">
              {data.lexSuggestions.map((item) => <span key={item}><Sparkles size={15}/>{item}</span>)}
            </div>
          ) : <p className="iu-empty">Lex non segnala priorità telematiche ulteriori.</p>}
        </Panel>
      </section>

      <FloatingLex
        context="telematico"
        title="Lex AI Telematico"
        body="Posso aiutarti a leggere esiti, RG, documenti importati, warning predeposito e prossima azione sui canali PST, PDP, PAT e PTT."
        primaryHref={data.actions.lexHref}
        primaryLabel="Apri Lex telematico"
        secondaryHref={data.actions.checklistHref}
        secondaryLabel="Checklist deposito"
      />
    </main>
  )
}
