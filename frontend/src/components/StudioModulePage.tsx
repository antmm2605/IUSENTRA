import { useEffect, useState, type MouseEvent } from 'react'
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
  CreditCard,
  Database,
  Download,
  Earth,
  FileText,
  FolderOpen,
  Landmark,
  Mail,
  MessageCircle,
  Plus,
  Send,
  Settings2,
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
  operationIdFromTitle,
  type StudioModuleRuntime,
  type StudioRuntimeField,
  type StudioRuntimeOperation,
} from '../studioModuleRuntime'
import './StudioModulePage.css'

function runtimeSourceLabel(source: string): string {
  return source === 'repository_reali' ? 'Dati applicativi' : 'Caricamento'
}

const toneLabel: Record<StudioModuleTone, string> = {
  primary: 'Primario',
  success: 'Operativo',
  warning: 'Da verificare',
  danger: 'Critico',
  purple: 'AI / analisi',
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
      title: `Lex AI ${module.title}`,
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
    return <input name={field.name} type="hidden" defaultValue={field.value}/>
  }
  if (field.type === 'checkbox') {
    const checkedValues = new Set(['1', 'true', 'si', 'sì', 'yes', 'on'])
    return (
      <input
        name={field.name}
        type="checkbox"
        value="1"
        defaultChecked={checkedValues.has(field.value.toLowerCase())}
        required={field.required}
      />
    )
  }
  if (field.type === 'file') {
    return <input name={field.name} type="file" required={field.required}/>
  }
  if (field.type === 'textarea') {
    return <textarea name={field.name} required={field.required} defaultValue={field.value} rows={3}/>
  }
  if (field.type === 'select') {
    return (
      <select name={field.name} required={field.required} defaultValue={field.value}>
        <option value="">Seleziona</option>
        {field.options.map((option) => <option value={option.value} key={`${field.name}-${option.value}`}>{option.label}</option>)}
      </select>
    )
  }
  return <input name={field.name} required={field.required} defaultValue={field.value} type={field.type}/>
}

function ActiveFunctionPanel({
  module,
  card,
  operation,
  runtime,
  loading,
}: {
  module: StudioModuleConfig
  card: StudioModuleCard
  operation?: StudioRuntimeOperation
  runtime: StudioModuleRuntime
  loading: boolean
}) {
  const Icon = iconFor(card.icon)
  const actions = operation?.actions?.length ? operation.actions : [{ label: card.action, href: card.href, method: 'GET' as const, tone: card.tone }]
  const metrics = operation?.metrics?.length ? operation.metrics : runtime.metrics
  return (
    <section id="funzione-operativa" className={`iu-sm-focus iu-sm-focus--${card.tone}`}>
      <div className="iu-sm-focus__icon"><Icon size={22}/></div>
      <div className="iu-sm-focus__copy">
        <span>{loading ? 'Caricamento dati reali' : 'Operazione pronta'}</span>
        <h2>{operation?.title || card.title}</h2>
        <p>{operation?.body || card.body}</p>
        <dl>
          <div><dt>Area</dt><dd>{module.title}</dd></div>
          <div><dt>Fonte</dt><dd>{runtimeSourceLabel(runtime.source)}</dd></div>
          <div><dt>Scritture</dt><dd>{runtime.contracts.writes === 'operational_routes' ? 'Route operative auditate' : runtime.contracts.writes}</dd></div>
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
            {operation.records.slice(0, 12).map((record) => (
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
          >
            {operation.form.fields.map((field) => (
              <label className={field.type === 'hidden' ? 'iu-sm-field--hidden' : ''} key={`${operation.id}-${field.name}`}>
                {field.type !== 'hidden' ? <span>{field.label}{field.required ? ' *' : ''}</span> : null}
                <RuntimeField field={field}/>
              </label>
            ))}
            <button type="submit">{operation.form.submitLabel}</button>
          </form>
        ) : null}
      </div>
      <div className="iu-sm-focus__actions">
        {actions.map((action) => action.method === 'POST' ? (
          <form action={action.href} method="post" key={`${card.title}-${action.label}`}>
            <button type="submit">{action.label}</button>
          </form>
        ) : (
          <a href={action.href} key={`${card.title}-${action.label}`}>{action.label}</a>
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
  const selectedCard = module.cards.find((card) => card.title === selectedCardTitle) || initialCard || module.cards[0]
  const selectedOperation = selectedCard ? operationForCard(runtime, selectedCard) : undefined

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
          <strong>Lex AI contestuale</strong>
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
              <p>Ogni card apre una funzione collegata a dati, form o azioni reali del gestionale.</p>
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
