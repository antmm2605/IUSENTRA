import { Component, Suspense, lazy, useEffect, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  Banknote,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  Building2,
  CalendarCheck,
  CalendarDays,
  CalendarPlus,
  CalendarSync,
  ChartColumn,
  ChevronDown,
  CircleHelp,
  CirclePlus,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  CloudUpload,
  CreditCard,
  Database,
  Earth,
  FilePenLine,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  Home,
  Landmark,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Mail,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Table,
  UserPlus,
  UserRound,
  UsersRound,
  Wrench,
  type LucideIcon
} from 'lucide-react'
import { DashboardData, Row, Tone, emptyDashboard, getDashboard } from './data'
import { Badge, DossierCard, KpiCard, Panel, SourceCard } from './components/dashboard'
import { FloatingLex } from './components/FloatingLex'
import './index.css'

const AgendaPage = lazy(() => import('./components/AgendaPage').then((module) => ({ default: module.AgendaPage })))
const NuovoAppuntamentoPage = lazy(() => import('./components/NuovoAppuntamentoPage').then((module) => ({ default: module.NuovoAppuntamentoPage })))
const RicercaStudioPage = lazy(() => import('./components/RicercaStudioPage').then((module) => ({ default: module.RicercaStudioPage })))
const FascicoliPage = lazy(() => import('./components/FascicoliPage').then((module) => ({ default: module.FascicoliPage })))
const AnagraficaClientiPage = lazy(() => import('./components/AnagraficaClientiPage').then((module) => ({ default: module.AnagraficaClientiPage })))
const CartellaClientePage = lazy(() => import('./components/CartellaClientePage').then((module) => ({ default: module.CartellaClientePage })))
const NuovoClientePage = lazy(() => import('./components/NuovoClientePage').then((module) => ({ default: module.NuovoClientePage })))
const SoggettiPage = lazy(() => import('./components/SoggettiPage').then((module) => ({ default: module.SoggettiPage })))
const EmailPecPage = lazy(() => import('./components/EmailPecPage').then((module) => ({ default: module.EmailPecPage })))
const MessaggiPage = lazy(() => import('./components/MessaggiPage').then((module) => ({ default: module.MessaggiPage })))
const NuovoMessaggioPage = lazy(() => import('./components/MessaggiPage').then((module) => ({ default: module.NuovoMessaggioPage })))
const ScadenziarioPage = lazy(() => import('./components/ScadenziarioPage').then((module) => ({ default: module.ScadenziarioPage })))
const NuovaScadenzaPage = lazy(() => import('./components/NuovaScadenzaPage').then((module) => ({ default: module.NuovaScadenzaPage })))
const WizardProPage = lazy(() => import('./components/WizardProPage').then((module) => ({ default: module.WizardProPage })))
const TelematicoPage = lazy(() => import('./components/TelematicoPage').then((module) => ({ default: module.TelematicoPage })))
const TelematicoSurfacePage = lazy(() => import('./components/TelematicoSurfacePage').then((module) => ({ default: module.TelematicoSurfacePage })))

const toneColor: Record<Tone,string> = { danger:'var(--iu-danger-500)', warning:'var(--iu-warning-500)', primary:'var(--iu-blue-600)', success:'var(--iu-success-500)', info:'var(--iu-sky-500)', purple:'var(--iu-purple-500)', orange:'var(--iu-warning-500)', neutral:'var(--iu-slate-300)' }
const metricIcon = { danger: AlertTriangle, primary: Mail, success: MessageCircle, purple: Clock3, orange: UsersRound, warning: AlertTriangle, info: Mail, neutral: Clock3 }

class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: unknown) {
    console.error('Errore React shell IUSENTRA', error)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <main className="iu-content iu-react-error" role="alert">
        <div>
          <AlertTriangle size={24}/>
          <h1>Pagina temporaneamente non disponibile</h1>
          <p>La shell React ha intercettato un errore di interfaccia. Ricarica la pagina o apri il modulo operativo dal menu senza perdere i dati dello studio.</p>
          <a href="/agenda">Apri agenda operativa</a>
          <button type="button" onClick={() => window.location.reload()}>Ricarica</button>
        </div>
      </main>
    )
  }
}

function Avatar({ label }:{label:string}) {
  const initials = label.split(' ').map(x=>x[0]).join('').slice(0,2).toUpperCase()
  return <span className="iu-avatar">{initials}</span>
}

function Logo() {
  return <svg width="46" height="46" viewBox="0 0 64 64" fill="none"><rect width="64" height="64" rx="16" fill="url(#g)"/><path d="M23.5 18.5h13.8c5 0 8.7 3.8 8.7 8.7v17.3H18V24c0-3 2.5-5.5 5.5-5.5Z" fill="url(#f)"/><rect x="29.2" y="26" width="5.8" height="15.5" rx="2.2" fill="#071329" opacity=".85"/><circle cx="48.2" cy="18.4" r="3.2" fill="#2F80ED"/><defs><linearGradient id="g" x1="8" x2="57" y1="4" y2="60"><stop stopColor="#F4B21B"/><stop offset="1" stopColor="#D49205"/></linearGradient><linearGradient id="f" x1="18" x2="47" y1="18" y2="45"><stop stopColor="#FCE7A3"/><stop offset="1" stopColor="#D4A017"/></linearGradient></defs></svg>
}

type NavItem = {
  label: string
  href: string
  icon: LucideIcon
  badge?: string
  active?: boolean
}

type NavSection = {
  id: string
  label?: string
  icon?: LucideIcon
  items: NavItem[]
  tone?: 'admin'
}

const primaryNav: NavItem[] = [
  { label: 'Panoramica', icon: LayoutDashboard, href: '/' },
  { label: 'Regia Operativa', icon: Sparkles, href: '/workspace-intelligente' },
  { label: 'Ricerca Studio', icon: Search, href: '/global-search' }
]

const navSections: NavSection[] = [
  {
    id: 'recenti',
    label: 'Recenti',
    icon: FolderOpen,
    items: [
      { label: '2026/004 - N.RG 139/2023 - ...', icon: FolderOpen, href: '/fascicoli' }
    ]
  },
  {
    id: 'agenda',
    label: 'Agenda',
    icon: CalendarCheck,
    items: [
      { label: 'Calendario', icon: CalendarDays, href: '/agenda' },
      { label: 'Nuovo Appuntamento', icon: CirclePlus, href: '/agenda/nuovo' },
      { label: 'Timesheet', icon: Clock3, href: '/timesheet' }
    ]
  },
  {
    id: 'fascicoli',
    label: 'Fascicoli',
    icon: Folder,
    items: [
      { label: 'Tutti i Fascicoli', icon: FolderOpen, href: '/fascicoli' },
      { label: 'Nuovo Fascicolo', icon: FolderPlus, href: '/fascicoli/nuovo' },
      { label: 'Archivio', icon: Archive, href: '/fascicoli/archivio' }
    ]
  },
  {
    id: 'clienti',
    label: 'Clienti e Anagrafiche',
    icon: UsersRound,
    items: [
      { label: 'Anagrafica', icon: UsersRound, href: '/clienti' },
      { label: 'Nuovo Cliente', icon: UserPlus, href: '/clienti/nuovo' },
      { label: 'Cartelle Condivise', icon: FolderPlus, href: '/cartelle-condivise' }
    ]
  },
  {
    id: 'soggetti',
    label: 'Soggetti e Parti',
    icon: FileText,
    items: [
      { label: 'Anagrafica', icon: UsersRound, href: '/soggetti' },
      { label: 'Nuovo Soggetto', icon: UserPlus, href: '/soggetti/nuovo' }
    ]
  },
  {
    id: 'comunicazioni',
    label: 'Comunicazioni',
    icon: MessageCircle,
    items: [
      { label: 'Email PEC', icon: Mail, href: '/email/', badge: 'PEC' },
      { label: 'Messaggi', icon: MessageCircle, href: '/messaggi' },
      { label: 'Nuovo SMS/WA', icon: Send, href: '/messaggi/nuovo' }
    ]
  },
  {
    id: 'scadenze',
    label: 'Scadenze e Termini',
    icon: Clock3,
    items: [
      { label: 'Scadenziario', icon: CalendarDays, href: '/scadenziario' },
      { label: 'Nuova Scadenza', icon: CalendarPlus, href: '/scadenziario/nuova' },
      { label: 'Preparazione Udienza Guidata', icon: Building2, href: '/wizard-pro/' },
      { label: 'Controlli Atti', icon: ClipboardCheck, href: '/deposito/checklist' }
    ]
  },
  {
    id: 'telematici',
    label: 'Servizi Telematici',
    icon: Send,
    items: [
      { label: 'Centro Servizi Telematici', icon: BriefcaseBusiness, href: '/telematico' },
      { label: 'PolisWeb / PST', icon: CloudUpload, href: '/portali/pst/acquisizione' },
      { label: 'Panoramica PST', icon: FileText, href: '/polisWeb' },
      { label: 'SIGP - Giudice di Pace', icon: Landmark, href: '/polisWeb' },
      { label: 'PDP Penale', icon: ShieldCheck, href: '/pdp' },
      { label: 'PAT Amministrativo', icon: FileText, href: '/pat' },
      { label: 'PTT Tributario', icon: FileText, href: '/sigit' },
      { label: 'Tribunali / PEC', icon: Landmark, href: '/tribunali' },
      { label: 'Checklist deposito', icon: ListChecks, href: '/deposito/checklist' },
      { label: 'Guida firma digitale', icon: BookOpen, href: '/guida/firma-digitale' }
    ]
  },
  {
    id: 'studio',
    label: 'Studio',
    icon: ChartColumn,
    items: [
      { label: 'Parcelle e Fatture', icon: FileText, href: '/fatturazione/' },
      { label: 'Preventivi e Incarichi', icon: FileText, href: '/preventivi/' },
      { label: 'Compensi Forensi', icon: Banknote, href: '/compensi-forensi' },
      { label: 'Redazione Atti', icon: FilePenLine, href: '/redazione-atti' },
      { label: 'Statistiche', icon: ChartColumn, href: '/statistiche/' },
      { label: 'Ricerca Legale', icon: Building2, href: '/ricerca-studio' },
      { label: 'Archivio Giurisprudenza', icon: Landmark, href: '/giurisprudenza/' },
      { label: 'Strumenti Forensi', icon: Wrench, href: '/strumenti-legali/' },
      { label: 'Strumenti Operativi', icon: Table, href: '/strumenti-operativi' },
      { label: 'Sito Studio', icon: Earth, href: '/sito-studio/' },
      { label: 'Notifiche WhatsApp', icon: MessageCircle, href: '/impostazioni/test/whatsapp' },
      { label: 'Incassi e Pagamenti', icon: CreditCard, href: '/impostazioni/pagamenti' },
      { label: 'Backup', icon: CloudUpload, href: '/backup' },
      { label: 'Impostazioni Studio', icon: Settings2, href: '/impostazioni' },
      { label: 'Sincronizzazione Calendari', icon: CalendarSync, href: '/impostazioni/calendario' }
    ]
  },
  {
    id: 'amministrazione',
    label: 'Amministrazione',
    icon: ShieldCheck,
    tone: 'admin',
    items: [
      { label: 'Utenti', icon: UsersRound, href: '/utenti' },
      { label: 'Profili e Permessi', icon: Table, href: '/profili' },
      { label: 'Registro Attività', icon: ClipboardList, href: '/admin/osservabilita' },
      { label: 'Database', icon: Database, href: '/admin/database' },
      { label: 'Registro GDPR', icon: FileText, href: '/privacy/registro' }
    ]
  }
]

function normaliseRoutePath(path: string): string {
  const clean = (path || '/').replace(/\/+$/, '') || '/'
  if (clean === '/app-v2') return '/'
  return clean.startsWith('/app-v2/') ? clean.slice('/app-v2'.length) || '/' : clean
}

function isActiveHref(href: string, activePath: string): boolean {
  const cleanPath = normaliseRoutePath(activePath).toLowerCase()
  const cleanHref = normaliseRoutePath(href).toLowerCase()
  if (cleanHref === '/') return cleanPath === '/'
  return cleanPath === cleanHref || cleanPath.startsWith(`${cleanHref}/`)
}

type GlobalLexConfig = {
  context: string
  title: string
  body: string
  primaryHref: string
  primaryLabel: string
  secondaryHref: string
  secondaryLabel: string
}

function resolveLexPageContext(routePath: string): GlobalLexConfig {
  const route = normaliseRoutePath(routePath).toLowerCase()
  if (route === '/global-search' || route === '/ricerca-studio') {
    return {
      context: 'ricerca-studio',
      title: 'Lex AI ricerca',
      body: 'Legge il contesto della ricerca e collega fascicoli, clienti, scadenze, PEC e documenti pertinenti.',
      primaryHref: '/lex?context=ricerca-studio',
      primaryLabel: 'Apri Lex ricerca',
      secondaryHref: '/global-search',
      secondaryLabel: 'Ricerca Studio',
    }
  }
  if (route === '/workspace-intelligente' || route === '/regia-operativa' || route.startsWith('/regia-operativa/')) {
    return {
      context: 'regia-operativa',
      title: 'Lex AI regia',
      body: 'Legge priorita, PEC, scadenze e fascicoli da presidiare per suggerire il prossimo passo operativo.',
      primaryHref: '/lex?context=regia-operativa',
      primaryLabel: 'Apri Lex regia',
      secondaryHref: '/workspace-intelligente',
      secondaryLabel: 'Regia operativa',
    }
  }
  if (route === '/agenda/nuovo' || route.startsWith('/agenda/nuovo/') || /^\/agenda\/[^/]+\/modifica$/.test(route)) {
    return {
      context: 'agenda-appuntamento',
      title: 'Lex AI appuntamento',
      body: 'Legge cliente, fascicolo, orario e note per aiutarti a preparare agenda, promemoria e attivita collegate.',
      primaryHref: '/lex?context=agenda-appuntamento',
      primaryLabel: 'Apri Lex agenda',
      secondaryHref: '/agenda',
      secondaryLabel: 'Agenda',
    }
  }
  if (route === '/scadenziario/nuova' || /^\/scadenziario\/[^/]+\/modifica$/.test(route)) {
    return {
      context: 'scadenza-form',
      title: 'Lex AI scadenza',
      body: 'Legge materia, fascicolo e termine indicato per aiutarti a controllare decorrenza, avvisi e prossima azione.',
      primaryHref: '/lex?context=scadenza-form',
      primaryLabel: 'Apri Lex termini',
      secondaryHref: '/scadenziario',
      secondaryLabel: 'Scadenziario',
    }
  }
  if (route.startsWith('/fascicoli')) {
    return {
      context: 'fascicoli',
      title: 'Lex AI fascicoli',
      body: 'Legge il contesto del fascicolo, documenti, attivita, scadenze e canali telematici collegati.',
      primaryHref: '/lex?context=fascicoli',
      primaryLabel: 'Apri Lex fascicoli',
      secondaryHref: '/fascicoli',
      secondaryLabel: 'Fascicoli',
    }
  }
  if (route.startsWith('/clienti') || route.startsWith('/soggetti')) {
    return {
      context: 'anagrafiche',
      title: 'Lex AI anagrafiche',
      body: 'Legge anagrafiche, parti, recapiti, fascicoli collegati e dati mancanti da completare.',
      primaryHref: '/lex?context=anagrafiche',
      primaryLabel: 'Apri Lex anagrafiche',
      secondaryHref: '/clienti',
      secondaryLabel: 'Clienti',
    }
  }
  if (route === '/email' || route.startsWith('/messaggi')) {
    return {
      context: 'comunicazioni',
      title: 'Lex AI comunicazioni',
      body: 'Legge PEC, messaggi, mittenti, allegati ed esiti per aiutarti a collegare comunicazioni e fascicoli.',
      primaryHref: '/lex?context=comunicazioni',
      primaryLabel: 'Apri Lex PEC',
      secondaryHref: '/email/',
      secondaryLabel: 'Casella PEC',
    }
  }
  if (route.startsWith('/scadenziario')) {
    return {
      context: 'scadenziario',
      title: 'Lex AI scadenziario',
      body: 'Legge scadenze, termini, urgenze e blocchi operativi per presidiare il calendario processuale.',
      primaryHref: '/lex?context=scadenziario',
      primaryLabel: 'Apri Lex termini',
      secondaryHref: '/scadenziario',
      secondaryLabel: 'Scadenziario',
    }
  }
  if (route.startsWith('/wizard-pro')) {
    return {
      context: 'preparazione-udienza',
      title: 'Lex AI udienza',
      body: 'Legge attivita, documenti, parti e udienza per preparare checklist, note e prossime azioni.',
      primaryHref: '/lex?context=preparazione-udienza',
      primaryLabel: 'Apri Lex udienza',
      secondaryHref: '/wizard-pro/',
      secondaryLabel: 'Wizard udienza',
    }
  }
  if (route === '/telematico' || route === '/telematici' || route === '/polisweb' || route === '/pdp' || route === '/pat' || route === '/sigit' || route === '/sigit/ricerca' || route === '/ptt' || route === '/tribunali' || route === '/deposito/checklist' || route === '/guida/firma-digitale') {
    return {
      context: 'telematico',
      title: 'Lex AI telematico',
      body: 'Legge canale, uffici, checklist, ricevute, import e stato del deposito nella pagina telematica aperta.',
      primaryHref: '/lex?context=telematico',
      primaryLabel: 'Apri Lex telematico',
      secondaryHref: '/telematico',
      secondaryLabel: 'Centro telematico',
    }
  }
  return {
    context: 'panoramica',
    title: 'Lex AI',
    body: 'Legge il contesto della pagina e collega dati di studio, scadenze, fascicoli e comunicazioni.',
    primaryHref: '/lex?context=panoramica',
    primaryLabel: 'Apri Lex',
    secondaryHref: '/workspace-intelligente',
    secondaryLabel: 'Regia operativa',
  }
}

function routePublishesLexContext(routePath: string): boolean {
  const route = normaliseRoutePath(routePath).toLowerCase()
  const isNewAppointment = route === '/agenda/nuovo' || route.startsWith('/agenda/nuovo/')
  const isAppointmentEdit = /^\/agenda\/[^/]+\/modifica$/.test(route)
  const isNewDeadline = route === '/scadenziario/nuova'
  const isDeadlineEdit = /^\/scadenziario\/[^/]+\/modifica$/.test(route)
  if (route === '/agenda' || (route.startsWith('/agenda/') && !isNewAppointment && !isAppointmentEdit)) return true
  if (route.startsWith('/fascicoli')) return true
  if (route.startsWith('/clienti') || route.startsWith('/soggetti')) return true
  if (route === '/email' || route.startsWith('/messaggi')) return true
  if (route.startsWith('/scadenziario') && !isNewDeadline && !isDeadlineEdit) return true
  if (route.startsWith('/wizard-pro')) return true
  return route === '/telematico' || route === '/telematici' || route === '/polisweb' || route === '/pdp' || route === '/pat' || route === '/sigit' || route === '/sigit/ricerca' || route === '/ptt' || route === '/tribunali' || route === '/deposito/checklist' || route === '/guida/firma-digitale'
}

function NavLink({ item, collapsed, activePath, onNavigate }:{item:NavItem; collapsed:boolean; activePath:string; onNavigate?:()=>void}) {
  const Icon = item.icon
  const active = item.active || isActiveHref(item.href, activePath)
  return (
    <a className={`iu-nav-link ${active?'is-active':''}`} href={item.href} title={collapsed?item.label:undefined} onClick={onNavigate}>
      <Icon size={17}/>
      <span>{item.label}</span>
      {item.badge?<b className="iu-nav-badge">{item.badge}</b>:null}
    </a>
  )
}

function Sidebar({ collapsed, mobileOpen, activePath, onToggle, onCloseMobile }:{collapsed:boolean; mobileOpen:boolean; activePath:string; onToggle:()=>void; onCloseMobile:()=>void}) {
  const [openSections,setOpenSections]=useState<Record<string,boolean>>({})
  const toggleSection=(id:string)=>setOpenSections(current=>({...current,[id]:!current[id]}))
  const ToggleIcon = mobileOpen ? PanelLeftClose : collapsed ? PanelLeftOpen : PanelLeftClose
  const toggleLabel = mobileOpen ? 'Chiudi menu' : collapsed ? 'Espandi menu' : 'Comprimi menu'
  const handleToggle = () => {
    if (mobileOpen) {
      onCloseMobile()
      return
    }
    onToggle()
  }
  return (
    <aside className={`iu-sidebar ${collapsed?'iu-sidebar--collapsed':''} ${mobileOpen?'iu-sidebar--mobile-open':''}`}>
      <div className="iu-sidebar__brand">
        <Logo/>
        <div><strong>IUSENTRA</strong><span>Lo studio legale, in un unico sistema</span></div>
        <button className="iu-sidebar__toggle" type="button" onClick={handleToggle} aria-label={toggleLabel} title={toggleLabel}><ToggleIcon size={18}/></button>
      </div>
      <nav className="iu-sidebar__nav" aria-label="Navigazione principale">
        <div className="iu-nav-primary">
          {primaryNav.map(item=><NavLink key={item.label} item={item} collapsed={collapsed} activePath={activePath} onNavigate={onCloseMobile}/>)}
        </div>
        {navSections.map(section=>{
          const SectionIcon = section.icon || Folder
          const open = openSections[section.id] === true
          return (
            <section className={`iu-nav-section ${section.tone==='admin'?'iu-nav-section--admin':''}`} key={section.id}>
              <button className="iu-nav-section__head" type="button" onClick={()=>toggleSection(section.id)} aria-expanded={open}>
                <span><SectionIcon size={14}/>{section.label}</span>
                <ChevronDown size={13}/>
              </button>
              {open?<div className="iu-nav-section__items">{section.items.map(item=><NavLink key={`${section.id}-${item.label}`} item={item} collapsed={collapsed} activePath={activePath} onNavigate={onCloseMobile}/>)}</div>:null}
            </section>
          )
        })}
      </nav>
      <div className="iu-sidebar__user"><span>R</span><div><strong>Avv. Roberto Rossi</strong><small>AMMINISTRATORE</small></div><a href="/profilo" aria-label="Profilo" title="Profilo"><UserRound size={16}/></a><a href="/logout" aria-label="Esci" title="Esci"><LogOut size={16}/></a></div>
    </aside>
  )
}

function Topbar({ onOpenMenu }:{onOpenMenu:()=>void}) {
  const today = new Date().toLocaleDateString('it-IT')
  return <header className="iu-topbar"><button className="iu-icon iu-menu-mobile" type="button" onClick={onOpenMenu} aria-label="Apri menu"><PanelLeftOpen size={18}/></button><label className="iu-search"><Search size={18}/><input placeholder="Cerca fascicolo, cliente, pratica, scadenza..." onKeyDown={(event)=>{if(event.key==='Enter'){const value=event.currentTarget.value.trim(); window.location.href=value?`/global-search?q=${encodeURIComponent(value)}`:'/global-search'}}}/></label><div className="iu-topbar__actions"><button className="iu-date">{today} <CalendarDays size={16}/></button><button className="iu-icon notify"><Bell size={18}/><span>8</span></button><button className="iu-icon"><Settings2 size={18}/></button><button className="iu-icon"><CircleHelp size={18}/></button><button className="iu-new"><Plus size={16}/>Nuovo</button></div></header>
}

function Empty({ children='Nessun elemento da presidiare.' }:{children?:string}) {
  return <p className="iu-empty">{children}</p>
}

function PageLoading() {
  return (
    <main className="iu-content">
      <div className="iu-page-heading">
        <div>
          <h1>Caricamento modulo</h1>
          <p>Preparazione della superficie React operativa.</p>
        </div>
        <span className="iu-sync">Sincronizzazione...</span>
      </div>
    </main>
  )
}

function List({ rows, avatar=false, href='/' }:{rows:Row[]; avatar?:boolean; href?:string}) {
  if (!rows.length) return <Empty/>
  return <div className="iu-list">{rows.map(r=><a className="iu-row" href={r.href||href} key={r.id}>{avatar?<Avatar label={r.avatar||r.title}/>:<i className={r.unread?'is-on':''}/>}<div><strong>{r.title}</strong><span>{r.subtitle}</span></div><time>{r.time}</time>{r.badge&&!avatar?<b className="iu-red-dot">{r.badge}</b>:null}</a>)}</div>
}

function italianDay(offset:number) {
  const d = new Date()
  d.setDate(d.getDate()+offset)
  const label = d.toLocaleDateString('it-IT', {weekday:'long', day:'numeric', month:'long', year:'numeric'})
  return `${offset===0?'Oggi':'Domani'} - ${label.charAt(0).toUpperCase()}${label.slice(1)}`
}

function Agenda({ data }:{data:DashboardData}) {
  const todayRows = data.agenda.filter(a=>a.badge==='OGGI')
  const tomorrowRows = data.agenda.filter(a=>a.badge==='DOMANI')
  const otherRows = data.agenda.filter(a=>a.badge!=='OGGI' && a.badge!=='DOMANI')
  return <Panel title="Agenda e udienze" icon={<CalendarDays size={17}/>} count={data.agenda.length}><div className="iu-agenda"><p>{italianDay(0)}</p>{todayRows.length?todayRows.map(a=><a className="iu-agenda-row" href={a.href||'/agenda'} key={a.id}><time>{a.time}</time><div><strong>{a.title}</strong><span>{a.subtitle}</span></div>{a.badge?<Badge tone="warning">{a.badge}</Badge>:null}</a>):<Empty>Nessun impegno per oggi.</Empty>}<p className="next">{italianDay(1)}</p>{[...tomorrowRows,...otherRows].length?[...tomorrowRows,...otherRows].map(a=><a className="iu-agenda-row" href={a.href||'/agenda'} key={a.id}><time>{a.time}</time><div><strong>{a.title}</strong><span>{a.subtitle}</span></div>{a.badge?<Badge tone="primary">{a.badge}</Badge>:null}</a>):<Empty>Nessun impegno programmato.</Empty>}</div><a className="iu-link" href="/agenda">Vai all'agenda completa -&gt;</a></Panel>
}

function Completion({ data }:{data:DashboardData}) {
  const c=data.completion
  return <Panel title="Anagrafiche ancora da completare" icon={<Home size={17}/>} count={c.totalMissing}><div className="iu-completion"><div className="iu-ring" style={{background:`conic-gradient(var(--iu-blue-600) ${c.percent}%, var(--iu-slate-100) 0)`}}><div><strong>{c.percent}%</strong><span>Completate</span></div></div><div className="iu-legend"><strong>Da completare: {c.totalMissing}</strong>{c.items.map(x=><span key={x.label}><i/>{x.label}<b>{x.count}</b></span>)}</div></div><a className="iu-link" href="/clienti">Vai alle anagrafiche -&gt;</a></Panel>
}

function Compact({ title, icon, count, rows, href }:{title:string; icon:ReactNode; count:number; rows:Row[]; href:string}) {
  return <Panel title={title} icon={icon} count={count}>{rows.length?<div className="iu-compact">{rows.map(r=><a className="iu-compact-row" href={r.href||href} key={r.id}><div><strong>{r.title}</strong><span>{r.subtitle}</span></div>{r.badge?<Badge tone={r.tone||'neutral'}>{r.badge}</Badge>:null}</a>)}</div>:<Empty/>}<a className="iu-link" href={href}>Vai -&gt;</a></Panel>
}

function Donut({ data }:{data:DashboardData}) {
  let cur=0
  const parts=data.deadlines.filter(d=>d.percent>0).map(d=>{const s=cur; cur+=d.percent; return `${toneColor[d.tone]} ${s}% ${cur}%`})
  const total=data.deadlines.reduce((a,b)=>a+b.count,0)
  const chart=parts.length?`conic-gradient(${parts.join(',')})`:'conic-gradient(var(--iu-slate-100) 0 100%)'
  return <Panel title="Scadenze per priorità" icon={<Sparkles size={17}/>} count={total}><div className="iu-deadlines"><div className="iu-donut" style={{background:chart}}><div><strong>{total}</strong><span>Totali</span></div></div><div className="iu-deadlines__legend">{data.deadlines.map(d=><span key={d.label}><i style={{background:toneColor[d.tone]}}/>{d.label}<b>{d.percent}%</b></span>)}</div></div><a className="iu-link" href="/scadenziario">Vai a Scadenze e Termini -&gt;</a></Panel>
}

function Economic({ data }:{data:DashboardData}) {
  return <Panel title="Economico rapido" icon={<UsersRound size={17}/>}><div className="iu-economy">{data.economic.map(e=><div className="iu-money" key={e.label}><span>{e.label}</span><strong>{e.value}</strong><small>{e.note}{e.delta?<b>{e.delta}</b>:null}</small></div>)}</div><a className="iu-link" href="/fatturazione">Vai al controllo economico -&gt;</a></Panel>
}

function Lex({ data }:{data:DashboardData}) {
  return <Panel title="Suggerimenti Lex AI" icon={<Sparkles size={17}/>} count={data.lex.length}>{data.lex.length?<div className="iu-lex">{data.lex.map(s=><div key={s}><Sparkles size={15}/><span>{s}</span></div>)}</div>:<Empty>Nessun suggerimento prioritario.</Empty>}<a className="iu-link" href="/lex">Apri Lex AI -&gt;</a></Panel>
}

function Dossiers({ data }:{data:DashboardData}) {
  return <Panel title="Fascicoli da presidiare" subtitle="Array dossier derivato dai fascicoli reali ad alta priorità." icon={<BriefcaseBusiness size={17}/>} count={data.dossiers.length}>{data.dossiers.length?<div className="iu-dossier-grid">{data.dossiers.map(dossier=><DossierCard dossier={dossier} key={dossier.id}/>)}</div>:<Empty>Nessun fascicolo prioritario nell'orizzonte operativo.</Empty>}<a className="iu-link" href="/fascicoli">Apri tutti i fascicoli -&gt;</a></Panel>
}

function Sources({ data }:{data:DashboardData}) {
  return <Panel title="Fonti operative collegate" subtitle="Array fonti pronto per API/store e alimentato dai conteggi reali." icon={<BookOpen size={17}/>} count={data.sources.length}>{data.sources.length?<div className="iu-source-grid">{data.sources.map(source=><SourceCard source={source} key={source.id}/>)}</div>:<Empty>Nessuna fonte operativa disponibile.</Empty>}</Panel>
}

function RegiaOperativaPage({ data, loading }:{data:DashboardData; loading:boolean}) {
  const priorityMetrics = data.metrics.filter((metric)=>['urgent','pec','messages'].includes(metric.id))
  const agendaRows = data.agenda.slice(0,5)
  const matterRows = data.matters.slice(0,5)
  return (
    <main className="iu-content iu-regia-page">
      <div className="iu-page-heading">
        <div>
          <h1>Regia Operativa</h1>
          <p>Azioni, comunicazioni e priorità da lavorare fuori dalla Panoramica.</p>
        </div>
        <a className={`iu-sync ${loading?'':'ok'}`} href="/workspace-intelligente">{loading?'Sincronizzazione dati...':'Apri versione completa'}</a>
      </div>
      <section className="iu-metrics">{priorityMetrics.map(m=><KpiCard item={m} icon={metricIcon[m.tone] || Sparkles} key={m.id}/>)}</section>
      <section className="iu-grid">
        <div className="span4"><Panel title="Azioni operative" icon={<Sparkles size={17}/>} count={data.operations.length}>{data.operations.length?<div className="iu-compact">{data.operations.map(action=><a className="iu-compact-row" href={action.href||'/workspace-intelligente'} key={action.id}><div><strong>{action.title}</strong><span>{action.subtitle}</span></div>{action.badge?<Badge tone={action.tone||'neutral'}>{action.badge}</Badge>:null}</a>)}</div>:<Empty>Nessuna azione operativa urgente.</Empty>}<a className="iu-link" href="/workspace-intelligente">Vai alla regia completa -&gt;</a></Panel></div>
        <div className="span4"><Panel title="Agenda da presidiare" icon={<CalendarDays size={17}/>} count={agendaRows.length}><List rows={agendaRows} href="/agenda"/><a className="iu-link" href="/agenda">Apri agenda -&gt;</a></Panel></div>
        <div className="span4"><Panel title="Fascicoli prioritari" icon={<BriefcaseBusiness size={17}/>} count={matterRows.length}>{matterRows.length?<div className="iu-compact">{matterRows.map(row=><a className="iu-compact-row" href={row.href||'/fascicoli'} key={row.id}><div><strong>{row.title}</strong><span>{row.subtitle}</span></div>{row.badge?<Badge tone={row.tone||'neutral'}>{row.badge}</Badge>:null}</a>)}</div>:<Empty>Nessun fascicolo ad alta priorità.</Empty>}<a className="iu-link" href="/fascicoli">Vai ai fascicoli -&gt;</a></Panel></div>
        <div className="span6"><Panel title="Comunicazioni recenti" icon={<MessageCircle size={17}/>} count={data.messages.length}><List rows={data.messages} avatar href="/messaggi"/><a className="iu-link" href="/messaggi">Vai ai messaggi -&gt;</a></Panel></div>
        <div className="span6"><Lex data={data}/></div>
      </section>
    </main>
  )
}

function DashboardPage({ data, loading }:{data:DashboardData; loading:boolean}) {
  return (
    <main className="iu-content">
      <div className="iu-page-heading">
        <div>
          <h1>Panoramica</h1>
          <p>Centro operativo dello studio</p>
        </div>
        <span className={`iu-sync ${loading?'':'ok'}`}>{loading?'Sincronizzazione dati...':'Dati aggiornati'}</span>
      </div>
      <section className="iu-metrics">{data.metrics.map(m=><KpiCard item={m} icon={metricIcon[m.tone] || AlertTriangle} key={m.id}/>)}</section>
      <section className="iu-grid">
        <div className="span3"><Panel title="Ultime PEC ricevute" icon={<Mail size={17}/>} count={data.pec.length}><List rows={data.pec} href="/email/"/><a className="iu-link" href="/email/">Vai alla casella PEC -&gt;</a></Panel></div>
        <div className="span3"><Panel title="Email recenti" icon={<Mail size={17}/>} count={data.emails.length}><List rows={data.emails} avatar href="/email/"/><a className="iu-link" href="/email/">Vai alla posta -&gt;</a></Panel></div>
        <div className="span3"><Panel title="Messaggi recenti dai clienti" icon={<MessageCircle size={17}/>} count={data.messages.length}><List rows={data.messages} avatar href="/messaggi"/><a className="iu-link" href="/messaggi">Vai ai messaggi -&gt;</a></Panel></div>
        <div className="span3"><Agenda data={data}/></div>
        <div className="span3"><Completion data={data}/></div>
        <div className="span3"><Compact title="Conferimenti incarico mancanti" icon={<UsersRound size={17}/>} count={data.engagements.length} rows={data.engagements} href="/preventivi"/></div>
        <div className="span2"><Compact title="Fascicoli con priorità alta" icon={<BriefcaseBusiness size={17}/>} count={data.matters.length} rows={data.matters} href="/fascicoli"/></div>
        <div className="span4"><Donut data={data}/></div>
        <div className="span5"><Economic data={data}/></div>
        <div className="span3"><Lex data={data}/></div>
        <div className="span6"><Dossiers data={data}/></div>
        <div className="span6"><Sources data={data}/></div>
      </section>
    </main>
  )
}

export default function App() {
  const activePath = window.location.pathname.replace(/\/+$/, '') || '/'
  const routePath = normaliseRoutePath(activePath)
  const routeKey = routePath.toLowerCase()
  const isSearchPage = routeKey === '/global-search' || routeKey === '/ricerca-studio'
  const isNewAppointmentPage = routeKey === '/agenda/nuovo' || routeKey.startsWith('/agenda/nuovo/')
  const isAppointmentEditPage = /^\/agenda\/[^/]+\/modifica$/.test(routeKey)
  const isAgendaPage = !isNewAppointmentPage && !isAppointmentEditPage && (routeKey === '/agenda' || routeKey.startsWith('/agenda/'))
  const isRegiaPage = routeKey === '/workspace-intelligente' || routeKey === '/regia-operativa' || routeKey.startsWith('/regia-operativa/')
  const isFascicoliPage = routeKey === '/fascicoli' || routeKey.startsWith('/fascicoli/')
  const isNewClientPage = routeKey === '/clienti/nuovo'
  const isNewSubjectPage = routeKey === '/soggetti/nuovo'
  const isClientEditPage = /^\/clienti\/[^/]+\/modifica$/.test(routeKey)
  const isSubjectEditPage = /^\/soggetti\/[^/]+\/modifica$/.test(routeKey)
  const isClientFolderPage = /^\/clienti\/[^/]+(\/cartella)?$/.test(routeKey)
  const isClientiPage = !isNewClientPage && !isClientFolderPage && routeKey === '/clienti'
  const isSoggettiPage = !isNewSubjectPage && !isSubjectEditPage && (routeKey === '/soggetti' || routeKey.startsWith('/soggetti/'))
  const isEmailPage = routeKey === '/email'
  const isNewMessagePage = routeKey === '/messaggi/nuovo'
  const isMessagesPage = !isNewMessagePage && (routeKey === '/messaggi' || routeKey.startsWith('/messaggi/'))
  const isNewDeadlinePage = routeKey === '/scadenziario/nuova'
  const isDeadlineEditPage = /^\/scadenziario\/[^/]+\/modifica$/.test(routeKey)
  const isScadenziarioPage = !isNewDeadlinePage && !isDeadlineEditPage && (routeKey === '/scadenziario' || routeKey.startsWith('/scadenziario/'))
  const isWizardProPage = routeKey === '/wizard-pro' || routeKey.startsWith('/wizard-pro/')
  const isTelematicoPage = routeKey === '/telematico' || routeKey === '/telematici'
  const isTelematicoSurfacePage = routeKey === '/polisweb' || routeKey === '/pdp' || routeKey === '/pat' || routeKey === '/sigit' || routeKey === '/sigit/ricerca' || routeKey === '/ptt' || routeKey === '/tribunali' || routeKey === '/deposito/checklist' || routeKey === '/guida/firma-digitale'
  const isDashboardPage = !isSearchPage && !isAgendaPage && !isNewAppointmentPage && !isAppointmentEditPage && !isRegiaPage && !isFascicoliPage && !isClientiPage && !isClientFolderPage && !isClientEditPage && !isNewClientPage && !isSoggettiPage && !isNewSubjectPage && !isSubjectEditPage && !isEmailPage && !isMessagesPage && !isNewMessagePage && !isScadenziarioPage && !isNewDeadlinePage && !isDeadlineEditPage && !isWizardProPage && !isTelematicoPage && !isTelematicoSurfacePage
  const isStandalonePage = isSearchPage || isAgendaPage || isNewAppointmentPage || isAppointmentEditPage || isFascicoliPage || isClientiPage || isClientFolderPage || isClientEditPage || isNewClientPage || isSoggettiPage || isNewSubjectPage || isSubjectEditPage || isEmailPage || isMessagesPage || isNewMessagePage || isScadenziarioPage || isNewDeadlinePage || isDeadlineEditPage || isWizardProPage || isTelematicoPage || isTelematicoSurfacePage
  const initialSearchQuery = new URLSearchParams(window.location.search).get('q') ?? ''
  const lexConfig = resolveLexPageContext(routeKey)
  const needsShellLexContext = !routePublishesLexContext(routeKey)
  const [data,setData]=useState<DashboardData>(emptyDashboard)
  const [loading,setLoading]=useState(!isStandalonePage)
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false)
  const [mobileMenuOpen,setMobileMenuOpen]=useState(false)
  const [mobileNavCollapsed,setMobileNavCollapsed]=useState(false)
  useEffect(()=>{if(isStandalonePage)return; let ok=true; getDashboard().then(d=>{if(ok)setData(d)}).finally(()=>{if(ok)setLoading(false)}); return()=>{ok=false}},[isStandalonePage])
  return (
    <AppErrorBoundary>
      <div className={`iu-shell ${sidebarCollapsed?'iu-shell--collapsed':''}`}>
        <Sidebar collapsed={sidebarCollapsed} mobileOpen={mobileMenuOpen} activePath={activePath} onToggle={()=>setSidebarCollapsed(v=>!v)} onCloseMobile={()=>setMobileMenuOpen(false)}/>
        {mobileMenuOpen?<button className="iu-sidebar-scrim" type="button" aria-label="Chiudi menu" onClick={()=>setMobileMenuOpen(false)}/>:null}
        <div className="iu-main">
          <Topbar onOpenMenu={()=>setMobileMenuOpen(true)}/>
          <Suspense fallback={<PageLoading/>}>
            {isSearchPage?<RicercaStudioPage initialQuery={initialSearchQuery}/>:isNewAppointmentPage||isAppointmentEditPage?<NuovoAppuntamentoPage/>:isAgendaPage?<AgendaPage/>:isRegiaPage?<RegiaOperativaPage data={data} loading={loading}/>:isFascicoliPage?<FascicoliPage/>:isNewClientPage||isNewSubjectPage||isClientEditPage||isSubjectEditPage?<NuovoClientePage/>:isClientFolderPage?<CartellaClientePage/>:isClientiPage?<AnagraficaClientiPage/>:isSoggettiPage?<SoggettiPage/>:isEmailPage?<EmailPecPage/>:isNewMessagePage?<NuovoMessaggioPage/>:isMessagesPage?<MessaggiPage/>:isNewDeadlinePage||isDeadlineEditPage?<NuovaScadenzaPage/>:isScadenziarioPage?<ScadenziarioPage/>:isWizardProPage?<WizardProPage/>:isTelematicoPage?<TelematicoPage/>:isTelematicoSurfacePage?<TelematicoSurfacePage/>:<DashboardPage data={data} loading={loading}/>}
          </Suspense>
        </div>
        <nav className={`iu-mobile ${mobileNavCollapsed?'is-collapsed':''}`} aria-label="Navigazione mobile">
          <div id="iu-mobile-links" className="iu-mobile__rail" hidden={mobileNavCollapsed}>
            <a className={isDashboardPage?'active':''} href="/"><LayoutDashboard size={18}/>Panoramica</a>
            <a className={isSearchPage?'active':''} href="/global-search"><Search size={18}/>Ricerca</a>
            <a className={isFascicoliPage?'active':''} href="/fascicoli"><BriefcaseBusiness size={18}/>Fascicoli</a>
            <a className={isClientiPage||isClientFolderPage||isClientEditPage||isNewClientPage||isSoggettiPage||isNewSubjectPage||isSubjectEditPage?'active':''} href="/clienti"><UsersRound size={18}/>Clienti</a>
            <a className={isEmailPage||isMessagesPage||isNewMessagePage?'active':''} href="/email/"><Mail size={18}/>PEC</a>
            <a className={isAgendaPage||isNewAppointmentPage||isAppointmentEditPage||isScadenziarioPage||isNewDeadlinePage||isDeadlineEditPage||isWizardProPage?'active':''} href="/agenda"><CalendarDays size={18}/>Agenda</a>
            <a className={isRegiaPage?'active':''} href="/workspace-intelligente"><Sparkles size={18}/>Regia</a>
          </div>
          <button
            type="button"
            className="iu-mobile__toggle"
            aria-controls="iu-mobile-links"
            aria-expanded={!mobileNavCollapsed}
            aria-label={mobileNavCollapsed?'Apri navigazione mobile':'Chiudi navigazione mobile'}
            onClick={()=>setMobileNavCollapsed(v=>!v)}
          >
            <ChevronDown size={17}/>
            <span>{mobileNavCollapsed?'Menu':'Chiudi'}</span>
          </button>
        </nav>
        {needsShellLexContext ? <FloatingLex {...lexConfig} /> : null}
      </div>
    </AppErrorBoundary>
  )
}
