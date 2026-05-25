import { useEffect, useState, type FormEvent, type MouseEvent } from 'react'
import {
  Archive,
  Banknote,
  BookOpen,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Clock3,
  CloudUpload,
  Copy,
  CreditCard,
  Database,
  Download,
  Earth,
  ExternalLink,
  FileText,
  FolderOpen,
  Landmark,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Plus,
  Send,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Table,
  UsersRound,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { findStudioModule, type StudioModuleCard, type StudioModuleConfig, type StudioModuleTone } from '../studioModuleData'
import {
  emptyStudioModuleRuntime,
  getStudioModuleRuntime,
  normaliseStudioRuntimeResult,
  operationIdFromTitle,
  type StudioModuleRuntime,
  type StudioRuntimeField,
  type StudioRuntimeOffice,
  type StudioRuntimeOperation,
  type StudioRuntimeResult,
} from '../studioModuleRuntime'
import { displayWritesLabel } from '../displayText'
import { csrfToken } from '../formSubmit'
import './StudioModulePage.css'

type ToolResultState = {
  loading: boolean
  result?: StudioRuntimeResult
  error?: string
}

function runtimeSourceLabel(source: string): string {
  return source === 'repository_reali' ? 'Dati dello studio' : 'Caricamento'
}

const toneLabel: Record<StudioModuleTone, string> = {
  primary: 'Primario',
  success: 'Operativo',
  warning: 'Da verificare',
  danger: 'Critico',
  purple: 'Analisi',
  orange: 'Economico',
  neutral: 'Supporto',
}

const iconMap: Record<string, LucideIcon> = {
  archive: Archive,
  backup: CloudUpload,
  banknote: Banknote,
  book: BookOpen,
  briefcase: BriefcaseBusiness,
  building: Building2,
  calendar: CalendarDays,
  card: CreditCard,
  chart: Table,
  check: CheckCircle2,
  clipboard: ClipboardList,
  clock: Clock3,
  database: Database,
  download: Download,
  earth: Earth,
  file: FileText,
  folder: FolderOpen,
  landmark: Landmark,
  mail: Mail,
  'map-pin': MapPin,
  message: MessageCircle,
  plus: Plus,
  send: Send,
  settings: Settings2,
  shield: ShieldCheck,
  spark: Sparkles,
  table: Table,
  upload: CloudUpload,
  users: UsersRound,
  wrench: Wrench,
}

function iconFor(name: string): LucideIcon {
  return iconMap[name] || Sparkles
}

function currentModule(): StudioModuleConfig {
  return findStudioModule(window.location.pathname) || findStudioModule('/studio')!
}

function openLexContext(module: StudioModuleConfig) {
  window.dispatchEvent(new CustomEvent('iusentra:lex-context', {
    detail: {
      context: module.lexContext,
      title: `Lex ${module.title}`,
      body: module.lexLabel,
      page_path: window.location.pathname,
      context_label: module.section,
    },
  }))
  window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex'))
}

function anchorForCard(card: StudioModuleCard): string {
  return card.title
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function normalizeRoute(path: string): string {
  const clean = (path || '/').split('?')[0].split('#')[0].replace(/\/+$/, '') || '/'
  return clean.startsWith('/app-v2/') ? clean.slice('/app-v2'.length) || '/' : clean
}

function localUrl(href: string): URL | null {
  try {
    const url = new URL(href, window.location.origin)
    return url.origin === window.location.origin ? url : null
  } catch {
    return null
  }
}

function isSameModuleHref(module: StudioModuleConfig, href: string): boolean {
  const url = localUrl(href)
  if (!url) return false
  return findStudioModule(url.pathname)?.id === module.id
}

function resolveSelectedCard(module: StudioModuleConfig): StudioModuleCard | undefined {
  const currentPath = normalizeRoute(window.location.pathname)
  const currentSearch = window.location.search
  const currentHash = window.location.hash
  return module.cards.find((card) => {
    const url = localUrl(card.href)
    if (!url) return false
    const cardPath = normalizeRoute(url.pathname)
    const samePath = cardPath === currentPath || currentPath.startsWith(`${cardPath}/`)
    if (!samePath) return false
    if (url.hash && currentHash) return url.hash === currentHash
    if (url.search && currentSearch) return url.search === currentSearch
    return true
  }) || module.cards[0]
}

function operationForCard(runtime: StudioModuleRuntime, card: StudioModuleCard): StudioRuntimeOperation | undefined {
  const cardId = anchorForCard(card)
  return runtime.operations.find((operation) =>
    operation.id === cardId ||
    operationIdFromTitle(operation.title) === cardId ||
    operation.title.toLowerCase() === card.title.toLowerCase(),
  )
}

function operationForCurrentRoute(runtime: StudioModuleRuntime, card?: StudioModuleCard): StudioRuntimeOperation | undefined {
  const params = new URLSearchParams(window.location.search)
  const appId = params.get('app') || ''
  const toolId = params.get('tool') || ''
  if (appId) {
    const byApp = runtime.operations.find((operation) => operation.tool?.appId === appId)
    if (byApp) return byApp
  }
  if (toolId) {
    const byTool = runtime.operations.find((operation) => operation.tool?.toolId === toolId)
    if (byTool) return byTool
  }
  return card ? operationForCard(runtime, card) : runtime.operations[0]
}

function fieldValue(field: StudioRuntimeField): string {
  return Array.isArray(field.value) ? field.value[0] || '' : field.value
}

function ModuleCard({
  card,
  selected,
  onActivate,
}: {
  card: StudioModuleCard
  selected: boolean
  onActivate: (event: MouseEvent<HTMLAnchorElement>, card: StudioModuleCard) => void
}) {
  const Icon = iconFor(card.icon)
  return (
    <a
      id={anchorForCard(card)}
      className={`iu-sm-card iu-sm-card--${card.tone} ${selected ? 'is-selected' : ''}`}
      href={card.href}
      onClick={(event) => onActivate(event, card)}
      aria-current={selected ? 'true' : undefined}
    >
      <span className="iu-sm-card__icon"><Icon size={20}/></span>
      <span className="iu-sm-card__copy">
        <span className="iu-sm-card__meta">{card.meta || toneLabel[card.tone]}</span>
        <strong>{card.title}</strong>
        <span>{card.body}</span>
      </span>
      <span className="iu-sm-card__action">{card.action}</span>
    </a>
  )
}

function RuntimeField({ field }: { field: StudioRuntimeField }) {
  if (field.type === 'hidden') {
    return <input name={field.name} type="hidden" defaultValue={fieldValue(field)}/>
  }
  if (field.type === 'checkbox') {
    const checkedValues = new Set(['1', 'true', 'si', 'sì', 'yes', 'on'])
    return (
      <input
        name={field.name}
        type="checkbox"
        value="1"
        defaultChecked={checkedValues.has(fieldValue(field).toLowerCase())}
        required={field.required}
      />
    )
  }
  if (field.type === 'file') {
    return <input name={field.name} type="file" required={field.required}/>
  }
  if (field.type === 'multiselect') {
    const values = new Set(Array.isArray(field.value) ? field.value : fieldValue(field).split(',').map((value) => value.trim()).filter(Boolean))
    return (
      <span className="iu-sm-check-grid">
        {field.options.map((option) => (
          <span className="iu-sm-check-option" key={`${field.name}-${option.value}`}>
            <input
              name={field.name}
              type="checkbox"
              value={option.value}
              defaultChecked={values.has(option.value)}
            />
            <span>{option.label}</span>
          </span>
        ))}
      </span>
    )
  }
  if (field.type === 'textarea') {
    return <textarea name={field.name} required={field.required} defaultValue={fieldValue(field)} rows={3}/>
  }
  if (field.type === 'select') {
    return (
      <select name={field.name} required={field.required} defaultValue={fieldValue(field)}>
        <option value="">Seleziona</option>
        {field.options.map((option) => <option value={option.value} key={`${field.name}-${option.value}`}>{option.label}</option>)}
      </select>
    )
  }
  return (
    <input
      name={field.name}
      required={field.required}
      defaultValue={fieldValue(field)}
      type={field.type}
      step={field.step || undefined}
      min={field.min || undefined}
      max={field.max || undefined}
    />
  )
}

function officeDetailLabel(key: string): string {
  const labels: Record<string, string> = {
    avviso: 'Avviso',
    email: 'Email',
    fax: 'Fax',
    note: 'Note',
    orari: 'Orari',
    pec: 'PEC',
    ricevimento: 'Ricevimento',
    telefono: 'Telefono',
  }
  return labels[key] || key.replace(/_/g, ' ')
}

function officeSiteHref(site: string): string {
  if (!site) return '#'
  return /^https?:\/\//i.test(site) ? site : `https://${site}`
}

function OfficeContactRow({
  icon: Icon,
  label,
  value,
  href,
  onCopy,
}: {
  icon: LucideIcon
  label: string
  value: string
  href?: string
  onCopy: (value: string, label: string) => void
}) {
  if (!value) return null
  const content = href ? <a href={href}>{value}</a> : <span>{value}</span>
  return (
    <div className="iu-sm-office-contact">
      <Icon size={15}/>
      <strong>{label}</strong>
      {content}
      <button type="button" onClick={() => onCopy(value, label)} title={`Copia ${label}`}>
        <Copy size={14}/>
      </button>
    </div>
  )
}

function OfficeDetailBlock({ title, details }: { title: string; details: Record<string, string> }) {
  const entries = Object.entries(details).filter(([, value]) => value)
  if (!entries.length) return null
  return (
    <section className="iu-sm-office-detail">
      <strong>{title}</strong>
      {entries.slice(0, 5).map(([key, value]) => (
        <p key={`${title}-${key}`}>
          <span>{officeDetailLabel(key)}</span>
          <em>{value}</em>
        </p>
      ))}
    </section>
  )
}

function OfficeResultCards({ offices }: { offices: StudioRuntimeOffice[] }) {
  const [copied, setCopied] = useState('')
  if (!offices.length) return null
  const copyValue = (value: string, label: string) => {
    if (!value) return
    if (navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(value)
    }
    setCopied(`${label} copiato`)
    window.setTimeout(() => setCopied(''), 1600)
  }
  return (
    <div className="iu-sm-office-results">
      <div className="iu-sm-office-results__head">
        <strong>Uffici trovati</strong>
        {copied ? <span>{copied}</span> : null}
      </div>
      {offices.map((office) => (
        <article className={`iu-sm-office-card ${office.primary ? 'is-primary' : ''}`} key={office.id}>
          <header>
            <span><Landmark size={15}/>{office.typeLabel}</span>
            <strong>{office.name}</strong>
            <p>
              <MapPin size={15}/>
              {[office.address, office.cap, office.city].filter(Boolean).join(' - ') || 'Sede non indicata'}
            </p>
          </header>
          <div className="iu-sm-office-card__contacts">
            <OfficeContactRow icon={Phone} label="Telefono" value={office.phone} onCopy={copyValue}/>
            <OfficeContactRow icon={Mail} label="Email" value={office.email} href={`mailto:${office.email}`} onCopy={copyValue}/>
            <OfficeContactRow icon={ShieldAlert} label="PEC" value={office.pec} href={`mailto:${office.pec}`} onCopy={copyValue}/>
            {office.site ? (
              <a className="iu-sm-office-site" href={officeSiteHref(office.site)} target="_blank" rel="noreferrer">
                <ExternalLink size={14}/> Sito ufficiale
              </a>
            ) : null}
          </div>
          <OfficeDetailBlock title="Assistenza depositi telematici" details={office.assistenzaPct}/>
          <OfficeDetailBlock title="Casellario" details={office.casellario}/>
          {office.notes ? <p className="iu-sm-office-card__note">{office.notes}</p> : null}
          {office.actions.length ? (
            <div className="iu-sm-office-card__actions">
              {office.actions.slice(0, 3).map((action) => (
                <a href={action.href} key={`${office.id}-${action.label}`}>{action.label}</a>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  )
}

function ToolResultView({ state }: { state?: ToolResultState }) {
  if (!state) return null
  if (state.loading) {
    return <div className="iu-sm-result" role="status">Calcolo in corso...</div>
  }
  if (state.error) {
    return <div className="iu-sm-result iu-sm-result--error" role="alert">{state.error}</div>
  }
  const result = state.result
  if (!result) return null
  return (
    <div className="iu-sm-result" role="status">
      <header>
        <span>{result.message}</span>
        <strong>{result.title}</strong>
      </header>
      {result.metrics.length ? (
        <div className="iu-sm-result__metrics">
          {result.metrics.map((metric) => (
            <article key={`${result.toolId}-${metric.label}`}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              {metric.note ? <small>{metric.note}</small> : null}
            </article>
          ))}
        </div>
      ) : null}
      <OfficeResultCards offices={result.offices}/>
      {result.tables.map((table) => (
        <div className="iu-sm-result__table" key={`${result.toolId}-${table.title}`}>
          <strong>{table.title}</strong>
          <div>
            <table>
              <thead>
                <tr>{table.headers.map((header) => <th key={header}>{header}</th>)}</tr>
              </thead>
              <tbody>
                {table.rows.map((row, rowIndex) => (
                  <tr key={`${table.title}-${rowIndex}`}>
                    {row.map((cell, cellIndex) => <td key={`${table.title}-${rowIndex}-${cellIndex}`}>{cell}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {result.previewText ? <pre>{result.previewText}</pre> : null}
      {result.warnings.length || result.notes.length ? (
        <div className="iu-sm-result__notes">
          {[...result.warnings, ...result.notes].slice(0, 6).map((note) => <span key={note}>{note}</span>)}
        </div>
      ) : null}
      {result.sources.length ? (
        <div className="iu-sm-result__sources">
          {result.sources.slice(0, 5).map((source) => (
            <a href={source.url || '#'} key={`${source.title}-${source.url}`} target="_blank" rel="noreferrer">{source.title}</a>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function ActiveFunctionPanel({
  module,
  card,
  operation,
  runtime,
  loading,
  resultState,
  onSubmitOperation,
}: {
  module: StudioModuleConfig
  card: StudioModuleCard
  operation?: StudioRuntimeOperation
  runtime: StudioModuleRuntime
  loading: boolean
  resultState?: ToolResultState
  onSubmitOperation: (event: FormEvent<HTMLFormElement>, operation: StudioRuntimeOperation) => void
}) {
  const Icon = iconFor(card.icon)
  const actions = operation?.actions?.length ? operation.actions : [{ label: card.action, href: card.href, method: 'GET' as const, tone: card.tone }]
  const metrics = operation?.metrics?.length ? operation.metrics : runtime.metrics
  const recordLimit = module.id === 'strumenti-forensi' ? 90 : 12
  return (
    <section id="funzione-operativa" className={`iu-sm-focus iu-sm-focus--${card.tone}`}>
      <div className="iu-sm-focus__icon"><Icon size={22}/></div>
      <div className="iu-sm-focus__copy">
        <span>{loading ? 'Caricamento dati reali' : 'Operazione pronta'}</span>
        <h2>{operation?.title || card.title}</h2>
        <p>{operation?.body || card.body}</p>
        <dl>
          <div><dt>Area</dt><dd>{module.title}</dd></div>
          <div><dt>Dati</dt><dd>{runtimeSourceLabel(runtime.source)}</dd></div>
          <div><dt>Comandi</dt><dd>{displayWritesLabel(runtime.contracts.writes)}</dd></div>
        </dl>
        {metrics.length ? (
          <div className="iu-sm-focus__metrics">
            {metrics.slice(0, 6).map((metric) => (
              <article key={`${card.title}-${metric.label}`}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                {metric.note ? <small>{metric.note}</small> : null}
              </article>
            ))}
          </div>
        ) : null}
        {operation?.warnings?.length ? (
          <div className="iu-sm-focus__warnings">
            {operation.warnings.map((warning) => <span key={warning}>{warning}</span>)}
          </div>
        ) : null}
        {operation?.records?.length ? (
          <div className="iu-sm-focus__records">
            {operation.records.slice(0, recordLimit).map((record) => (
              <a href={record.href || card.href} key={record.id}>
                <div>
                  <strong>{record.title}</strong>
                  <span>{record.subtitle || 'Dato operativo collegato'}</span>
                </div>
                {record.badge ? <b>{record.badge}</b> : null}
                {record.meta ? <em>{record.meta}</em> : null}
              </a>
            ))}
          </div>
        ) : null}
        {operation?.form ? (
          <form
            className="iu-sm-focus__form"
            action={operation.form.action}
            method={operation.form.method.toLowerCase()}
            encType={operation.form.enctype || undefined}
            onSubmit={operation.tool ? (event) => onSubmitOperation(event, operation) : undefined}
          >
            {operation.form.fields.map((field) => (
              <label className={field.type === 'hidden' ? 'iu-sm-field--hidden' : field.type === 'multiselect' ? 'iu-sm-field--wide' : ''} key={`${operation.id}-${field.name}`}>
                {field.type !== 'hidden' ? <span>{field.label}{field.required ? ' *' : ''}</span> : null}
                <RuntimeField field={field}/>
              </label>
            ))}
            <button type="submit" disabled={resultState?.loading}>{resultState?.loading ? 'Calcolo in corso...' : operation.form.submitLabel}</button>
          </form>
        ) : null}
        <ToolResultView state={resultState}/>
      </div>
      <div className="iu-sm-focus__actions">
        {actions.map((action) => (
          <a
            href={action.href}
            key={`${card.title}-${action.label}`}
            data-method={action.method !== 'GET' ? action.method : undefined}
          >
            {action.label}
          </a>
        ))}
        <button type="button" onClick={() => openLexContext(module)}>Chiedi a Lex</button>
      </div>
    </section>
  )
}

export function StudioModulePage() {
  const module = currentModule()
  const initialCard = resolveSelectedCard(module)
  const [selectedCardTitle, setSelectedCardTitle] = useState(initialCard?.title || '')
  const [runtime, setRuntime] = useState<StudioModuleRuntime>(emptyStudioModuleRuntime)
  const [runtimeLoading, setRuntimeLoading] = useState(true)
  const [toolResults, setToolResults] = useState<Record<string, ToolResultState>>({})
  const selectedCard = module.cards.find((card) => card.title === selectedCardTitle) || initialCard || module.cards[0]
  const selectedOperation = operationForCurrentRoute(runtime, selectedCard)
  const selectedResultKey = selectedOperation?.tool?.toolId || selectedOperation?.id || ''
  const selectedResultState = selectedResultKey ? toolResults[selectedResultKey] : undefined

  useEffect(() => {
    const updateFromLocation = () => setSelectedCardTitle(resolveSelectedCard(module)?.title || module.cards[0]?.title || '')
    updateFromLocation()
    window.addEventListener('popstate', updateFromLocation)
    return () => window.removeEventListener('popstate', updateFromLocation)
  }, [module.id])

  useEffect(() => {
    let active = true
    setRuntimeLoading(true)
    getStudioModuleRuntime(module.id)
      .then((payload) => { if (active) setRuntime(payload) })
      .finally(() => { if (active) setRuntimeLoading(false) })
    return () => { active = false }
  }, [module.id])

  useEffect(() => {
    if (!window.location.hash) return
    window.requestAnimationFrame(() => {
      document.getElementById('funzione-operativa')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }, [module.id, selectedCardTitle])

  const handleActivateCard = (event: MouseEvent<HTMLAnchorElement>, card: StudioModuleCard) => {
    if (!isSameModuleHref(module, card.href)) return
    event.preventDefault()
    const url = localUrl(card.href)
    setSelectedCardTitle(card.title)
    if (url) {
      const nextUrl = `${url.pathname}${url.search}${url.hash}`
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
      if (nextUrl !== currentUrl) {
        window.history.pushState({ studioModule: module.id, card: card.title }, '', nextUrl)
      }
    }
    window.requestAnimationFrame(() => {
      document.getElementById('funzione-operativa')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  const handleOperationSubmit = async (event: FormEvent<HTMLFormElement>, operation: StudioRuntimeOperation) => {
    if (!operation.form || !operation.tool) return
    event.preventDefault()
    const key = operation.tool.toolId || operation.id
    setToolResults((current) => ({ ...current, [key]: { loading: true } }))
    try {
      const token = csrfToken()
      const response = await fetch(operation.form.action, {
        method: operation.form.method,
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body: new FormData(event.currentTarget),
      })
      const result = normaliseStudioRuntimeResult(await response.json().catch(() => ({})))
      if (!response.ok || !result.ok) {
        throw new Error(result.message || 'Verifica non riuscita. Controlla i campi e riprova.')
      }
      setToolResults((current) => ({ ...current, [key]: { loading: false, result } }))
    } catch (error) {
      setToolResults((current) => ({
        ...current,
        [key]: {
          loading: false,
          error: error instanceof Error ? error.message : 'Verifica non riuscita. Controlla i campi e riprova.',
        },
      }))
    }
  }

  return (
    <main className="iu-content iu-studio-module">
      <section className={`iu-sm-hero iu-sm-hero--${module.kpis[0]?.tone || 'primary'}`}>
        <div>
          <p>{module.section}</p>
          <h1>{module.title}</h1>
          <span>{module.subtitle}</span>
        </div>
        <aside>
          <Sparkles size={20}/>
          <strong>Lex contestuale</strong>
          <span>{module.lexLabel}</span>
          <button type="button" onClick={() => openLexContext(module)}>Apri Lex</button>
        </aside>
      </section>

      <section className="iu-sm-kpis" aria-label={`Indicatori ${module.title}`}>
        {module.kpis.map((item) => (
          <article className={`iu-sm-kpi iu-sm-kpi--${item.tone}`} key={`${module.id}-${item.label}`}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <p>{item.note}</p>
          </article>
        ))}
      </section>

      <section className="iu-sm-layout">
        <div className="iu-sm-main">
          <div className="iu-sm-section-head">
            <div>
              <h2>Funzioni operative</h2>
              <p>Ogni scheda apre una funzione collegata a dati, moduli o azioni reali del gestionale.</p>
            </div>
            <span>Operativo</span>
          </div>
          {selectedCard ? (
            <ActiveFunctionPanel
              module={module}
              card={selectedCard}
              operation={selectedOperation}
              runtime={runtime}
              loading={runtimeLoading}
              resultState={selectedResultState}
              onSubmitOperation={handleOperationSubmit}
            />
          ) : null}
          <div className="iu-sm-cards">
            {module.cards.map((card) => (
              <ModuleCard
                card={card}
                selected={selectedCard?.title === card.title}
                onActivate={handleActivateCard}
                key={`${module.id}-${card.title}`}
              />
            ))}
          </div>
        </div>

        <aside className="iu-sm-side">
          <section className="iu-sm-panel">
            <h2>Flusso consigliato</h2>
            <ol>
              {module.workflow.map((step) => <li key={`${module.id}-${step}`}>{step}</li>)}
            </ol>
          </section>
          <section className="iu-sm-panel">
            <h2>Collegamenti rapidi</h2>
            <div className="iu-sm-links">
              {module.links.map((link) => <a href={link.href} key={`${module.id}-${link.label}`}>{link.label}</a>)}
            </div>
          </section>
        </aside>
      </section>
    </main>
  )
}

export default StudioModulePage
