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
import './StudioModulePage.css'

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

function ModuleCard({ card }: { card: StudioModuleCard }) {
  const Icon = iconFor(card.icon)
  return (
    <a className={`iu-sm-card iu-sm-card--${card.tone}`} href={card.href}>
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

export function StudioModulePage() {
  const module = currentModule()
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
              <p>Ogni card apre una funzione reale già collegata nel gestionale.</p>
            </div>
            <span>React UI</span>
          </div>
          <div className="iu-sm-cards">
            {module.cards.map((card) => <ModuleCard card={card} key={`${module.id}-${card.title}`}/>)}
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
