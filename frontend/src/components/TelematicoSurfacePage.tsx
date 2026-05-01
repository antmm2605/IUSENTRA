import { useEffect, useMemo, useState, type MouseEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  Copy,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FolderOpen,
  Mail,
  MonitorCheck,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  type LucideIcon,
} from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyTelematicoSurface,
  getTelematicoSurfacePage,
  type ChecklistGroup,
  type OfficeRow,
  type SurfaceAction,
  type SurfaceCard,
  type TelematicoSurfaceData,
  type TelematicoSurfaceId,
} from '../telematicoSurfacesData'
import type { Tone } from '../data'
import './TelematicoSurfacePage.css'

const iconMap: Record<string, LucideIcon> = {
  monitor: MonitorCheck,
  download: Download,
  external: ExternalLink,
  shield: ShieldCheck,
  folder: FolderOpen,
  mail: Mail,
  search: Search,
  refresh: RefreshCw,
  workflow: ClipboardCheck,
}

const surfaceFallbacks: Record<TelematicoSurfaceId, { title: string; context: string }> = {
  polisweb: { title: 'PolisWeb / PST', context: 'telematico-polisweb' },
  pdp: { title: 'PDP Penale', context: 'telematico-pdp' },
  pat: { title: 'PAT Amministrativo', context: 'telematico-pat' },
  ptt: { title: 'PTT Tributario', context: 'telematico-ptt' },
  tribunali: { title: 'Tribunali / PEC', context: 'telematico-tribunali' },
  checklist: { title: 'Checklist deposito', context: 'telematico-checklist' },
  firma: { title: 'Guida firma digitale', context: 'telematico-firma' },
}

const surfaceAppPaths: Record<TelematicoSurfaceId, string> = {
  polisweb: '/app-v2/polisweb',
  pdp: '/app-v2/pdp',
  pat: '/app-v2/pat',
  ptt: '/app-v2/ptt',
  tribunali: '/app-v2/tribunali',
  checklist: '/app-v2/deposito/checklist',
  firma: '/app-v2/guida/firma-digitale',
}

function surfaceFromCurrentPath(): TelematicoSurfaceId {
  const raw = window.location.pathname.replace(/\/+$/, '') || '/'
  const route = raw.toLowerCase().startsWith('/app-v2/') ? raw.slice('/app-v2'.length).toLowerCase() : raw.toLowerCase()
  if (route.startsWith('/pdp') || route.startsWith('/portali/pdp')) return 'pdp'
  if (route.startsWith('/pat') || route.startsWith('/portali/pat')) return 'pat'
  if (route.startsWith('/ptt') || route.startsWith('/sigit') || route.startsWith('/portali/ptt') || route.startsWith('/portali/sigit')) return 'ptt'
  if (route.startsWith('/tribunali')) return 'tribunali'
  if (route.startsWith('/deposito/checklist')) return 'checklist'
  if (route.startsWith('/guida/firma-digitale')) return 'firma'
  if (
    route.startsWith('/polisweb') ||
    route.startsWith('/pst') ||
    route.startsWith('/sigp') ||
    route.startsWith('/sigp-sync') ||
    route.startsWith('/portali/pst')
  ) return 'polisweb'
  return 'polisweb'
}

function normaliseSearch(value: string) {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function formatGeneratedAt(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function linkKindLabel(kind: string) {
  const labels: Record<string, string> = {
    react: 'Operativo',
    operativo: 'Modulo',
    esterno: 'Esterno',
    download: 'Download',
    api: 'Servizio',
    link: 'Link',
  }
  return labels[kind] || 'Link'
}

function sameOriginUrl(href: string): URL | null {
  try {
    const url = new URL(href, window.location.origin)
    return url.origin === window.location.origin ? url : null
  } catch {
    return null
  }
}

function normalizeAppPath(pathname: string): string {
  const clean = pathname.replace(/\/+$/, '').toLowerCase() || '/'
  return clean.startsWith('/app-v2/') ? clean.slice('/app-v2'.length) || '/' : clean
}

function isSameSurfaceAction(surfaceId: TelematicoSurfaceId, action: SurfaceAction): boolean {
  if (action.method === 'POST' || action.external) return false
  const url = sameOriginUrl(action.href)
  if (!url) return false
  const actionPath = normalizeAppPath(url.pathname)
  const currentSurfacePath = normalizeAppPath(surfaceAppPaths[surfaceId])
  const aliases: Partial<Record<TelematicoSurfaceId, string[]>> = {
    polisweb: ['/polisweb', '/pst', '/portali/pst', '/portali/pst/acquisizione'],
    pdp: ['/pdp', '/portali/pdp', '/portali/pdp/acquisizione'],
    pat: ['/pat', '/portali/pat', '/portali/pat/acquisizione'],
    ptt: ['/ptt', '/sigit', '/portali/ptt', '/portali/sigit', '/portali/ptt/acquisizione'],
  }
  return actionPath === currentSurfacePath || Boolean(aliases[surfaceId]?.some((alias) => actionPath === alias || actionPath.startsWith(`${alias}/`)))
}

function statToneClass(tone: Tone) {
  return `iu-tel-surface-stat iu-tel-surface-stat--${tone}`
}

function Stat({ label, value, tone = 'primary', icon }:{ label:string; value:number|string; tone?:Tone; icon:ReactNode }) {
  return (
    <article className={statToneClass(tone)}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function ActionLink({
  action,
  onPost,
  onNavigate,
}:{
  action:SurfaceAction
  onPost:(action:SurfaceAction)=>void
  onNavigate:(event: MouseEvent<HTMLAnchorElement>, action:SurfaceAction)=>void
}) {
  if (action.method === 'POST') {
    return (
      <button type="button" onClick={() => onPost(action)}>
        <RefreshCw size={15}/> {action.label}
      </button>
    )
  }
  return (
    <a href={action.href} onClick={(event) => onNavigate(event, action)} target={action.external ? '_blank' : undefined} rel={action.external ? 'noreferrer' : undefined}>
      {action.external ? <ExternalLink size={15}/> : <ArrowRight size={15}/>} {action.label}
    </a>
  )
}

function OperationCard({
  card,
  selected,
  onPost,
  onNavigate,
}:{
  card:SurfaceCard
  selected:boolean
  onPost:(action:SurfaceAction)=>void
  onNavigate:(event: MouseEvent<HTMLAnchorElement>, card:SurfaceCard, action:SurfaceAction)=>void
}) {
  const Icon = iconMap[card.icon] || ClipboardCheck
  return (
    <article className={`iu-tel-op-card iu-tel-op-card--${card.tone} ${selected ? 'is-selected' : ''}`}>
      <header>
        <div><Icon size={20}/></div>
        <span>{card.title}</span>
      </header>
      <p>{card.body}</p>
      {card.metrics.length ? (
        <dl>
          {card.metrics.map((metric) => (
            <div key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {card.actions.length ? (
        <footer>
          {card.actions.map((action) => (
            <ActionLink
              action={action}
              onPost={onPost}
              onNavigate={(event, selectedAction) => onNavigate(event, card, selectedAction)}
              key={action.id}
            />
          ))}
        </footer>
      ) : null}
    </article>
  )
}

function ActiveOperationPanel({
  surfaceId,
  title,
  card,
  action,
  onLex,
}:{
  surfaceId: TelematicoSurfaceId
  title:string
  card:SurfaceCard
  action:SurfaceAction
  onLex:()=>void
}) {
  const Icon = iconMap[card.icon] || ClipboardCheck
  const checklistHref = surfaceId === 'checklist' ? surfaceAppPaths.checklist : `${surfaceAppPaths[surfaceId]}#checklist-operativa`
  return (
    <section id="operazione-attiva" className={`iu-tel-active-op iu-tel-active-op--${card.tone}`}>
      <div className="iu-tel-active-op__icon"><Icon size={23}/></div>
      <div className="iu-tel-active-op__copy">
        <span>Operazione pronta</span>
        <h2>{action.label || card.title}</h2>
        <p>{card.body}</p>
        <dl>
          <div><dt>Superficie</dt><dd>{title}</dd></div>
          <div><dt>Modalità</dt><dd>React operativa</dd></div>
          <div><dt>Canale</dt><dd>{surfaceId === 'polisweb' ? 'PST / PolisWeb' : surfaceId.toUpperCase()}</dd></div>
        </dl>
      </div>
      <div className="iu-tel-active-op__actions">
        <a href="/app-v2/fascicoli">Scegli fascicolo</a>
        <a href={checklistHref}>Controlli</a>
        <button type="button" onClick={onLex}>Chiedi a Lex</button>
      </div>
    </section>
  )
}

function ChecklistPanel({
  groups,
  surfaceId,
}:{
  groups: ChecklistGroup[]
  surfaceId: TelematicoSurfaceId
}) {
  const storagePrefix = `iusentra.telematico.${surfaceId}.check.`
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const next: Record<string, boolean> = {}
    groups.forEach((group) => {
      group.items.forEach((item) => {
        next[item.id] = window.localStorage.getItem(`${storagePrefix}${item.id}`) === '1'
      })
    })
    setChecked(next)
  }, [groups, storagePrefix])

  const total = groups.reduce((sum, group) => sum + group.items.length, 0)
  const done = Object.values(checked).filter(Boolean).length
  if (!groups.length) return null

  return (
    <section id="checklist-operativa" className="iu-tel-anchor-target">
      <Panel title="Checklist operativa" subtitle="Le spunte restano salvate sul browser della postazione" icon={<ClipboardCheck size={17}/>} count={`${done}/${total}`}>
        <div className="iu-tel-checklist">
          {groups.map((group) => (
            <section key={group.id}>
              <h3>{group.title}</h3>
              {group.items.map((item) => {
                const itemId = `${surfaceId}-${group.id}-${item.id}`
                return (
                  <label className="iu-tel-check-item" htmlFor={itemId} key={item.id}>
                    <input
                      id={itemId}
                      type="checkbox"
                      checked={Boolean(checked[item.id])}
                      onChange={(event) => {
                        const value = event.currentTarget.checked
                        setChecked((current) => ({ ...current, [item.id]: value }))
                        window.localStorage.setItem(`${storagePrefix}${item.id}`, value ? '1' : '0')
                      }}
                    />
                    <span>
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </span>
                    {item.critical ? <Badge tone="danger">Critico</Badge> : null}
                  </label>
                )
              })}
            </section>
          ))}
        </div>
      </Panel>
    </section>
  )
}

function ControlList({ title, items, empty }:{ title:string; items:TelematicoSurfaceData['controlTower']['warnings']; empty:string }) {
  return (
    <Panel title={title} icon={<ShieldCheck size={17}/>} count={items.length}>
      {items.length ? (
        <div className="iu-tel-surface-list">
          {items.map((item) => (
            <a href={item.href} key={item.id}>
              <Badge tone={item.tone}>{item.badge}</Badge>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
              </div>
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">{empty}</p>}
    </Panel>
  )
}

function CasesPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Pratiche collegate" subtitle="Fascicoli e import del canale" icon={<FolderOpen size={17}/>} count={data.recentCases.length}>
      {data.recentCases.length ? (
        <div className="iu-tel-surface-cases">
          {data.recentCases.map((item) => (
            <a href={item.href} key={item.id}>
              <Badge tone={item.tone}>{item.portalLabel}</Badge>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
                <small>{item.subject || 'Oggetto non indicato'}</small>
              </div>
              <em>{item.documentsCount} documenti</em>
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">Nessuna pratica collegata a questa superficie.</p>}
    </Panel>
  )
}

function EventsPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Cronologia" subtitle="Import, esiti e azioni recenti" icon={<RefreshCw size={17}/>} count={data.recentEvents.length}>
      {data.recentEvents.length ? (
        <div className="iu-tel-surface-events">
          {data.recentEvents.map((item) => (
            <a href={item.href} key={item.id}>
              <Badge tone={item.tone}>{item.badge || 'Evento'}</Badge>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
                <time>{item.timestamp}</time>
              </div>
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">Nessun evento telematico recente.</p>}
    </Panel>
  )
}

function OfficeDirectory({ data }:{ data:TelematicoSurfaceData }) {
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('tutti')
  const [copied, setCopied] = useState('')
  const types = useMemo(() => ['tutti', ...Object.keys(data.officeSummary.perType || {}).sort()], [data.officeSummary.perType])
  const offices = useMemo(() => {
    const needle = normaliseSearch(query)
    return data.offices.filter((office) => {
      const haystack = normaliseSearch([
        office.nome,
        office.codice,
        office.pec,
        office.tipo,
        office.distretto,
        office.comune,
        office.provincia,
      ].join(' '))
      const typeOk = typeFilter === 'tutti' || office.tipo === typeFilter
      return typeOk && (!needle || haystack.includes(needle))
    }).slice(0, 80)
  }, [data.offices, query, typeFilter])

  const copyPec = async (office: OfficeRow) => {
    if (!office.pec) return
    try {
      await navigator.clipboard.writeText(office.pec)
      setCopied(office.id)
      window.setTimeout(() => setCopied(''), 1400)
    } catch {
      setCopied('')
    }
  }

  return (
    <section className="iu-tel-offices">
      <header>
        <div>
          <span>Elenco uffici</span>
          <h2>Tribunali e indirizzi PEC</h2>
        </div>
        <label><Search size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca ufficio, PEC, distretto, codice..."/></label>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filtra tipo ufficio">
          {types.map((type) => <option value={type} key={type}>{type === 'tutti' ? 'Tutti i tipi' : type}</option>)}
        </select>
      </header>
      <div className="iu-tel-office-list">
        {offices.map((office) => (
          <article key={office.id}>
            <div>
              <Badge tone="primary">{office.tipo || 'Ufficio'}</Badge>
              <strong>{office.nome}</strong>
              <span>{[office.codice, office.distretto, office.comune || office.provincia].filter(Boolean).join(' - ')}</span>
            </div>
            <button type="button" onClick={() => copyPec(office)} disabled={!office.pec}>
              <Copy size={15}/> {office.pec ? (copied === office.id ? 'Copiata' : office.pec) : 'PEC assente'}
            </button>
          </article>
        ))}
      </div>
    </section>
  )
}

function LinksPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Collegamenti rapidi" icon={<ExternalLink size={17}/>} count={data.links.length}>
      <div className="iu-tel-surface-links">
        {data.links.map((link) => (
          <a href={link.href} key={`${link.kind}-${link.href}`}>
            <span>{linkKindLabel(link.kind)}</span>
            <strong>{link.label}</strong>
            <ArrowRight size={15}/>
          </a>
        ))}
      </div>
    </Panel>
  )
}

function SurfaceSidePanels({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <>
      <ControlList title="Esiti in attesa" items={data.controlTower.pendingOutcomes} empty="Nessun esito in attesa."/>
      <ControlList title="Import incompleti" items={data.controlTower.incompleteImports} empty="Nessun import incompleto."/>
      <ControlList title="Controlli predeposito" items={[...data.controlTower.blockedCases, ...data.controlTower.predeposito]} empty="Nessun blocco predeposito."/>
      <LinksPanel data={data}/>
    </>
  )
}

function LexPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Suggerimenti Lex AI" icon={<Sparkles size={17}/>} count={data.lexSuggestions.length}>
      {data.lexSuggestions.length ? (
        <div className="iu-tel-surface-lex">
          {data.lexSuggestions.map((item) => <span key={item}><Sparkles size={15}/>{item}</span>)}
        </div>
      ) : <p className="iu-empty">Lex non segnala ulteriori priorita su questa superficie.</p>}
    </Panel>
  )
}

export function TelematicoSurfacePage() {
  const surfaceId = surfaceFromCurrentPath()
  const [data, setData] = useState<TelematicoSurfaceData>(emptyTelematicoSurface)
  const [loading, setLoading] = useState(true)
  const [actionMessage, setActionMessage] = useState('')
  const [activeOperation, setActiveOperation] = useState<{ cardId:string; actionId:string } | null>(null)

  useEffect(() => {
    let active = true
    setActiveOperation(null)
    setLoading(true)
    getTelematicoSurfacePage(surfaceId)
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [surfaceId])

  useEffect(() => {
    if (loading || !window.location.hash) return
    const targetId = decodeURIComponent(window.location.hash.slice(1))
    window.requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [data.surface.id, loading])

  useEffect(() => {
    if (!data.operationCards.length) return
    const hash = window.location.hash
    const card = hash
      ? data.operationCards.find((item) => item.actions.some((action) => action.href.includes(hash))) || data.operationCards[0]
      : data.operationCards[0]
    const action = card.actions.find((item) => hash && item.href.includes(hash)) || card.actions[0]
    if (card && action) {
      setActiveOperation((current) => current || { cardId: card.id, actionId: action.id })
    }
  }, [data.operationCards])

  const postAction = async (action: SurfaceAction) => {
    setActionMessage(`Esecuzione: ${action.label}...`)
    try {
      const response = await fetch(action.href, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'react_surface' }),
      })
      const payload = await response.json().catch(() => ({}))
      const message = typeof payload.messaggio === 'string'
        ? payload.messaggio
        : typeof payload.errore === 'string'
          ? payload.errore
          : response.ok ? 'Operazione completata.' : 'Operazione non completata.'
      setActionMessage(message)
    } catch {
      setActionMessage('Operazione non disponibile in questo momento.')
    }
  }

  const title = data.surface.title || surfaceFallbacks[surfaceId].title
  const tone = data.surface.tone || 'primary'
  const generatedAt = formatGeneratedAt(data.generatedAt)
  const selectedCard = data.operationCards.find((card) => card.id === activeOperation?.cardId) || data.operationCards[0]
  const selectedAction = selectedCard?.actions.find((action) => action.id === activeOperation?.actionId) || selectedCard?.actions[0]

  const openSurfaceLex = () => {
    window.dispatchEvent(new CustomEvent('iusentra:lex-context', {
      detail: {
        context: surfaceFallbacks[data.surface.id]?.context || surfaceFallbacks[surfaceId].context,
        title: `Lex AI - ${title}`,
        body: selectedCard?.body || 'Contesto telematico operativo',
        page_path: window.location.pathname,
        context_label: title,
      },
    }))
    window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex'))
  }

  const navigateAction = (event: MouseEvent<HTMLAnchorElement>, card: SurfaceCard, action: SurfaceAction) => {
    if (!isSameSurfaceAction(surfaceId, action)) return
    event.preventDefault()
    setActiveOperation({ cardId: card.id, actionId: action.id })
    const url = sameOriginUrl(action.href)
    if (url) {
      const nextUrl = `${url.pathname}${url.search}${url.hash}`
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
      if (nextUrl !== currentUrl) {
        window.history.pushState({ telematicoSurface: surfaceId, card: card.id, action: action.id }, '', nextUrl)
      }
    }
    window.requestAnimationFrame(() => {
      document.getElementById('operazione-attiva')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  return (
    <main className={`iu-content iu-tel-surface-page iu-tel-surface-page--${data.surface.id}`}>
      <section className={`iu-tel-surface-hero iu-tel-surface-hero--${tone}`}>
        <div>
          <span className="iu-tel-surface-hero__eyebrow"><ShieldCheck size={16}/> {data.surface.eyebrow}</span>
          <h1>{title}</h1>
          <p>{data.surface.subtitle}</p>
          <div className="iu-tel-surface-hero__badges">
            <Badge tone="primary">Superficie operativa</Badge>
            <Badge tone="success">Dati aggiornati</Badge>
            <Badge tone="warning">Import autorizzato</Badge>
            <Badge tone="purple">Lex AI</Badge>
          </div>
        </div>
        <aside className="iu-tel-surface-hero__meta">
          <strong>{loading ? 'Sincronizzazione...' : 'Dati aggiornati'}</strong>
          <small>{generatedAt || 'Aggiornamento in corso'}</small>
          {data.surface.officialHref ? <a href={data.surface.officialHref} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Portale ufficiale</a> : null}
        </aside>
      </section>

      {data.notices.length || actionMessage ? (
        <section className="iu-tel-surface-notices">
          {actionMessage ? <article><CheckCircle2 size={18}/><div><strong>Esito azione</strong><span>{actionMessage}</span></div></article> : null}
          {data.notices.map((notice) => (
            <article key={`${notice.title}-${notice.body}`}>
              <AlertTriangle size={18}/>
              <div><strong>{notice.title}</strong><span>{notice.body}</span></div>
            </article>
          ))}
        </section>
      ) : null}

      <section className="iu-tel-surface-stats">
        <Stat label="Pratiche" value={data.summary.total} tone="primary" icon={<FolderOpen size={19}/>}/>
        <Stat label={data.surface.id === 'tribunali' ? 'PEC censite' : 'Import'} value={data.summary.imports} tone="success" icon={<UploadCloud size={19}/>}/>
        <Stat label="Da presidiare" value={data.summary.attention} tone={data.summary.attention ? 'warning' : 'success'} icon={<BadgeCheck size={19}/>}/>
        <Stat label="Blocchi" value={data.summary.blocked} tone={data.summary.blocked ? 'danger' : 'neutral'} icon={<AlertTriangle size={19}/>}/>
        <Stat label="Avvisi" value={data.summary.warnings} tone={data.summary.warnings ? 'warning' : 'neutral'} icon={<FileCheck2 size={19}/>}/>
      </section>

      <section id="acquisizione-portale" className="iu-tel-op-grid iu-tel-anchor-target">
        {data.operationCards.map((card) => (
          <OperationCard
            card={card}
            selected={selectedCard?.id === card.id}
            onPost={postAction}
            onNavigate={navigateAction}
            key={card.id}
          />
        ))}
      </section>

      {selectedCard && selectedAction ? (
        <ActiveOperationPanel
          surfaceId={data.surface.id}
          title={title}
          card={selectedCard}
          action={selectedAction}
          onLex={openSurfaceLex}
        />
      ) : null}

      {data.surface.id === 'tribunali' ? (
        <section className="iu-tel-tribunali-workspace">
          <OfficeDirectory data={data}/>
          <aside className="iu-tel-tribunali-side">
            <SurfaceSidePanels data={data}/>
          </aside>
        </section>
      ) : (
        <section className="iu-tel-surface-grid">
          <div className="iu-tel-surface-main">
            <ChecklistPanel groups={data.checklistGroups} surfaceId={data.surface.id}/>
            <CasesPanel data={data}/>
          </div>
          <aside>
            <SurfaceSidePanels data={data}/>
          </aside>
        </section>
      )}

      <section className="iu-tel-surface-bottom">
        <EventsPanel data={data}/>
        <LexPanel data={data}/>
      </section>

      <FloatingLex
        context={surfaceFallbacks[data.surface.id]?.context || surfaceFallbacks[surfaceId].context}
        title={`Lex AI - ${title}`}
        body="Posso aiutarti a leggere stato canale, checklist, uffici, documenti, ricevute e prossima azione senza uscire dalla nuova UI."
        primaryHref="/lex?context=telematico"
        primaryLabel="Apri Lex"
        secondaryHref="/app-v2/telematico"
        secondaryLabel="Centro telematico"
      />
    </main>
  )
}
