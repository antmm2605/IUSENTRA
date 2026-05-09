import { Component, Suspense, lazy, useEffect, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  Banknote,
  BookOpen,
  BriefcaseBusiness,
  Building2,
  CalendarCheck,
  CalendarDays,
  CalendarPlus,
  CalendarSync,
  ChartColumn,
  ChevronDown,
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
import { DashboardData, Row, Tone, emptyDashboard, getDashboard, syncDashboardMailboxes } from './data'
import { Badge, DossierCard, KpiCard, Panel, SourceCard } from './components/dashboard'
import { FloatingLex } from './components/FloatingLex'
import { IusAppSidebar } from './components/iusentra'
import { TopBar } from './components/layout/TopBar'
import { findStudioModule, isStudioModuleRoute } from './studioModuleData'
import './index.css'
import './components/layout/TopBar.css'

const AgendaPage = lazy(() => import('./components/AgendaPage').then((module) => ({ default: module.AgendaPage })))
const NuovoAppuntamentoPage = lazy(() => import('./components/NuovoAppuntamentoPage').then((module) => ({ default: module.NuovoAppuntamentoPage })))
const RicercaStudioPage = lazy(() => import('./components/RicercaStudioPage').then((module) => ({ default: module.RicercaStudioPage })))
const FascicoliPage = lazy(() => import('./components/FascicoliPage').then((module) => ({ default: module.FascicoliPage })))
const DocumentEditorPage = lazy(() => import('./components/DocumentEditorPage').then((module) => ({ default: module.DocumentEditorPage })))
const AnagraficaClientiPage = lazy(() => import('./components/AnagraficaClientiPage').then((module) => ({ default: module.AnagraficaClientiPage })))
const CartellaClientePage = lazy(() => import('./components/CartellaClientePage').then((module) => ({ default: module.CartellaClientePage })))
const NuovoClientePage = lazy(() => import('./components/NuovoClientePage').then((module) => ({ default: module.NuovoClientePage })))
const SoggettiPage = lazy(() => import('./components/SoggettiPage').then((module) => ({ default: module.SoggettiPage })))
const EmailPecPage = lazy(() => import('./components/EmailPecPage').then((module) => ({ default: module.EmailPecPage })))
const EmailOrdinariaPage = lazy(() => import('./components/EmailPecPage').then((module) => ({ default: module.EmailOrdinariaPage })))
const EmailComposePage = lazy(() => import('./components/EmailPecPage').then((module) => ({ default: module.EmailComposePage })))
const MessaggiPage = lazy(() => import('./components/MessaggiPage').then((module) => ({ default: module.MessaggiPage })))
const NuovoMessaggioPage = lazy(() => import('./components/MessaggiPage').then((module) => ({ default: module.NuovoMessaggioPage })))
const ScadenziarioPage = lazy(() => import('./components/ScadenziarioPage').then((module) => ({ default: module.ScadenziarioPage })))
const NuovaScadenzaPage = lazy(() => import('./components/NuovaScadenzaPage').then((module) => ({ default: module.NuovaScadenzaPage })))
const WizardProPage = lazy(() => import('./components/WizardProPage').then((module) => ({ default: module.WizardProPage })))
const WizardProStepPage = lazy(() => import('./components/WizardProStepPage').then((module) => ({ default: module.WizardProStepPage })))
const WizardProCompletePage = lazy(() => import('./components/WizardProCompletePage').then((module) => ({ default: module.WizardProCompletePage })))
const TimesheetPage = lazy(() => import('./components/TimesheetPage').then((module) => ({ default: module.TimesheetPage })))
const CartelleCondivisePage = lazy(() => import('./components/CartelleCondivisePage').then((module) => ({ default: module.CartelleCondivisePage })))
const TelematicoPage = lazy(() => import('./components/TelematicoPage').then((module) => ({ default: module.TelematicoPage })))
const TelematicoSurfacePage = lazy(() => import('./components/TelematicoSurfacePage').then((module) => ({ default: module.TelematicoSurfacePage })))
const StudioModulePage = lazy(() => import('./components/StudioModulePage').then((module) => ({ default: module.StudioModulePage })))
const PrivacyRegistroPage = lazy(() => import('./components/PrivacyRegistroPage').then((module) => ({ default: module.PrivacyRegistroPage })))
const AdminDatabasePage = lazy(() => import('./components/AdminDatabasePage').then((module) => ({ default: module.AdminDatabasePage })))
const StatistichePage = lazy(() => import('./components/StatistichePage').then((module) => ({ default: module.StatistichePage })))
const ImpostazioniPage = lazy(() => import('./components/ImpostazioniPage').then((module) => ({ default: module.ImpostazioniPage })))
const AuditPage = lazy(() => import('./components/AuditPage').then((module) => ({ default: module.AuditPage })))
const UtentiPage = lazy(() => import('./components/UtentiPage').then((module) => ({ default: module.UtentiPage })))
const ProfiliPage = lazy(() => import('./components/ProfiliPage').then((module) => ({ default: module.ProfiliPage })))
const BackupPage = lazy(() => import('./components/BackupPage').then((module) => ({ default: module.BackupPage })))
const SitoStudioPage = lazy(() => import('./components/SitoStudioPage').then((module) => ({ default: module.SitoStudioPage })))
const StudioPage = lazy(() => import('./components/StudioPage').then((module) => ({ default: module.StudioPage })))
const AmministrazionePage = lazy(() => import('./components/AmministrazionePage').then((module) => ({ default: module.AmministrazionePage })))
const FatturazionePage = lazy(() => import('./components/FatturazionePage').then((module) => ({ default: module.FatturazionePage })))
const IncassiPagamentiPage = lazy(() => import('./components/IncassiPagamentiPage').then((module) => ({ default: module.IncassiPagamentiPage })))
const PreventiviPage = lazy(() => import('./components/PreventiviPage').then((module) => ({ default: module.PreventiviPage })))
const PreventivoWizardPage = lazy(() => import('./components/PreventivoWizardPage').then((module) => ({ default: module.PreventivoWizardPage })))
const CompensiForensiPage = lazy(() => import('./components/CompensiForensiPage').then((module) => ({ default: module.CompensiForensiPage })))
const TariffarioPage = lazy(() => import('./components/TariffarioPage').then((module) => ({ default: module.TariffarioPage })))
const TemplateAttiPage = lazy(() => import('./components/TemplateAttiPage').then((module) => ({ default: module.TemplateAttiPage })))
const RedazioneAttiPage = lazy(() => import('./components/RedazioneAttiPage').then((module) => ({ default: module.RedazioneAttiPage })))
const GiurisprudenzaPage = lazy(() => import('./components/GiurisprudenzaPage').then((module) => ({ default: module.GiurisprudenzaPage })))
const LegalIntelligencePage = lazy(() => import('./components/LegalIntelligencePage').then((module) => ({ default: module.LegalIntelligencePage })))

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

type ShellUserProfile = {
  id: string
  username: string
  displayName: string
  role: string
  initials: string
}

type ShellBootstrap = {
  user: ShellUserProfile | null
  actions: {
    profile?: string
    logout?: string
  }
}

const emptyShellBootstrap: ShellBootstrap = { user: null, actions: {} }

function textFromRecord(record: Record<string, unknown>, key: string): string {
  return typeof record[key] === 'string' ? record[key].trim() : ''
}

function readShellBootstrap(): ShellBootstrap {
  const element = document.getElementById('iusentra-react-bootstrap')
  if (!element?.textContent) return emptyShellBootstrap
  try {
    const parsed = JSON.parse(element.textContent) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return emptyShellBootstrap
    const root = parsed as Record<string, unknown>
    const userPayload = root.user && typeof root.user === 'object' && !Array.isArray(root.user)
      ? root.user as Record<string, unknown>
      : null
    const actionsPayload = root.actions && typeof root.actions === 'object' && !Array.isArray(root.actions)
      ? root.actions as Record<string, unknown>
      : {}
    const displayName = userPayload ? textFromRecord(userPayload, 'displayName') : ''
    const username = userPayload ? textFromRecord(userPayload, 'username') : ''
    const user = userPayload && (displayName || username)
      ? {
        id: textFromRecord(userPayload, 'id'),
        username,
        displayName: displayName || username,
        role: textFromRecord(userPayload, 'role'),
        initials: textFromRecord(userPayload, 'initials'),
      }
      : null
    return {
      user,
      actions: {
        profile: textFromRecord(actionsPayload, 'profile'),
        logout: textFromRecord(actionsPayload, 'logout'),
      },
    }
  } catch {
    return emptyShellBootstrap
  }
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
    items: []
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
      { label: 'Email ordinaria', icon: Mail, href: '/email-ordinaria/', badge: 'SMTP' },
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
      { label: 'PolisWeb / PST', icon: CloudUpload, href: '/polisWeb' },
      { label: 'Panoramica PST', icon: FileText, href: '/polisWeb' },
      { label: 'SIGP - Giudice di Pace', icon: Landmark, href: '/sigp/' },
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
      { label: 'Studio', icon: Building2, href: '/studio' },
      { label: 'Parcelle e Fatture', icon: FileText, href: '/fatturazione/' },
      { label: 'Preventivi e Incarichi', icon: FileText, href: '/preventivi/' },
      { label: 'Compensi Forensi', icon: Banknote, href: '/compensi-forensi' },
      { label: 'Redazione Atti', icon: FilePenLine, href: '/redazione-atti' },
      { label: 'Statistiche', icon: ChartColumn, href: '/statistiche/' },
      { label: 'Ricerca Legale', icon: Building2, href: '/ricerca-legale' },
      { label: 'Archivio Giurisprudenza', icon: Landmark, href: '/giurisprudenza/' },
      { label: 'Strumenti Forensi', icon: Wrench, href: '/strumenti-legali/' },
      { label: 'Strumenti Operativi', icon: Table, href: '/strumenti-operativi' },
      { label: 'Sito Studio', icon: Earth, href: '/sito-studio/' },
    ]
  },
  {
    id: 'impostazioni',
    label: 'Impostazioni',
    icon: Settings2,
    items: [
      { label: 'Impostazioni Studio', icon: Settings2, href: '/impostazioni' },
      { label: 'Notifiche', icon: MessageCircle, href: '/impostazioni?tab=notifiche' },
      { label: 'Pagamenti', icon: CreditCard, href: '/impostazioni?tab=pagamenti' },
      { label: 'Backup', icon: CloudUpload, href: '/impostazioni?tab=backup' },
      { label: 'Sincronizzazione Calendari', icon: CalendarSync, href: '/impostazioni/calendario' }
    ]
  },
  {
    id: 'amministrazione',
    label: 'Amministrazione',
    icon: ShieldCheck,
    tone: 'admin',
    items: [
      { label: 'Amministrazione', icon: ShieldCheck, href: '/amministrazione' },
      { label: 'Utenti', icon: UsersRound, href: '/utenti' },
      { label: 'Profili e Permessi', icon: Table, href: '/profili' },
      { label: 'Registro Attività', icon: ClipboardList, href: '/audit' },
      { label: 'Database', icon: Database, href: '/admin/database' },
      { label: 'Registro GDPR', icon: FileText, href: '/privacy/registro' }
    ]
  }
]

function normaliseRoutePath(path: string): string {
  const clean = (path || '/').split('?')[0].replace(/\/+$/, '') || '/'
  if (clean === '/app-v2') return '/'
  return clean.startsWith('/app-v2/') ? clean.slice('/app-v2'.length) || '/' : clean
}

function isActiveHref(href: string, activePath: string): boolean {
  const cleanPath = normaliseRoutePath(activePath).toLowerCase()
  const cleanHref = normaliseRoutePath(href).toLowerCase()
  if (cleanHref === '/') return cleanPath === '/'
  return cleanPath === cleanHref || cleanPath.startsWith(`${cleanHref}/`)
}

function isTelematicoSurfaceRoute(path: string): boolean {
  const route = normaliseRoutePath(path).toLowerCase()
  return (
    route === '/polisweb' ||
    route === '/pst' ||
    route.startsWith('/polisweb/') ||
    route.startsWith('/pst/') ||
    route === '/sigp' ||
    route.startsWith('/sigp/') ||
    route === '/sigp-sync' ||
    route.startsWith('/sigp-sync/') ||
    route === '/pdp' ||
    route.startsWith('/pdp/') ||
    route === '/pat' ||
    route.startsWith('/pat/') ||
    route === '/ptt' ||
    route.startsWith('/ptt/') ||
    route === '/sigit' ||
    route.startsWith('/sigit/') ||
    route === '/tribunali' ||
    route.startsWith('/tribunali/') ||
    route === '/deposito/checklist' ||
    route.startsWith('/deposito/checklist/') ||
    route === '/guida/firma-digitale' ||
    route.startsWith('/guida/firma-digitale/') ||
    route.startsWith('/portali/pst') ||
    route.startsWith('/portali/pdp') ||
    route.startsWith('/portali/pat') ||
    route.startsWith('/portali/ptt') ||
    route.startsWith('/portali/sigit')
  )
}

const legacyOperationalPrefixes = [
  '/servizi-telematici',
  '/telematico',
  '/telematici',
  '/polisweb',
  '/pst',
  '/sigp',
  '/sigp-sync',
  '/pdp',
  '/pat',
  '/ptt',
  '/sigit',
  '/tribunali',
  '/deposito/checklist',
  '/guida/firma-digitale',
]

function legacyOperationalRedirectHref(activePath: string): string | null {
  const raw = activePath || '/'
  const lowerRaw = raw.toLowerCase()
  if (lowerRaw !== '/app-v2' && !lowerRaw.startsWith('/app-v2/')) return null
  const route = normaliseRoutePath(raw)
  const routeLower = route.toLowerCase()
  const mustLeaveReact = legacyOperationalPrefixes.some((prefix) => routeLower === prefix || routeLower.startsWith(`${prefix}/`))
  if (!mustLeaveReact) return null
  return `${route}${window.location.search || ''}${window.location.hash || ''}`
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

const OPEN_LEX_WIDGET_HREF = '#lex'

function resolveLexPageContext(routePath: string): GlobalLexConfig {
  const route = normaliseRoutePath(routePath).toLowerCase()
  if (route === '/global-search' || route === '/ricerca-studio' || route === '/cerca') {
    return {
      context: 'ricerca-studio',
      title: 'Lex AI ricerca',
      body: 'Legge il contesto della ricerca e collega fascicoli, clienti, scadenze, PEC e documenti pertinenti.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex ricerca',
      secondaryHref: '/global-search',
      secondaryLabel: 'Ricerca Studio',
    }
  }
  if (route === '/workspace-intelligente' || route === '/regia-operativa' || route.startsWith('/regia-operativa/')) {
    return {
      context: 'regia-operativa',
      title: 'Lex AI regia',
      body: 'Legge priorità, PEC, scadenze e fascicoli da presidiare per suggerire il prossimo passo operativo.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex regia',
      secondaryHref: '/workspace-intelligente',
      secondaryLabel: 'Regia operativa',
    }
  }
  if (route === '/agenda/nuovo' || route.startsWith('/agenda/nuovo/') || /^\/agenda\/[^/]+\/modifica$/.test(route)) {
    return {
      context: 'agenda-appuntamento',
      title: 'Lex AI appuntamento',
      body: 'Legge cliente, fascicolo, orario e note per aiutarti a preparare agenda, promemoria e attività collegate.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
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
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex termini',
      secondaryHref: '/scadenziario',
      secondaryLabel: 'Scadenziario',
    }
  }
  if (/^\/fascicoli\/[^/]+\/documenti\/[^/]+\/editor$/.test(route)) {
    return {
      context: 'editor-documento',
      title: 'Lex AI editor',
      body: 'Legge il documento aperto, il fascicolo collegato e gli avvisi di conversione per aiutare nella revisione professionale.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex editor',
      secondaryHref: '/global-search?tipo=documenti',
      secondaryLabel: 'Cerca documenti',
    }
  }
  if (route.startsWith('/fascicoli')) {
    return {
      context: 'fascicoli',
      title: 'Lex AI fascicoli',
      body: 'Legge il contesto del fascicolo, documenti, attività, scadenze e canali telematici collegati.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex fascicoli',
      secondaryHref: '/global-search?tipo=fascicoli',
      secondaryLabel: 'Cerca fascicoli',
    }
  }
  if (route.startsWith('/clienti') || route.startsWith('/soggetti')) {
    return {
      context: 'anagrafiche',
      title: 'Lex AI anagrafiche',
      body: 'Legge anagrafiche, parti, recapiti, fascicoli collegati e dati mancanti da completare.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex anagrafiche',
      secondaryHref: '/clienti',
      secondaryLabel: 'Clienti',
    }
  }
  if (route === '/email' || route === '/email-ordinaria' || route.startsWith('/messaggi')) {
    return {
      context: 'comunicazioni',
      title: 'Lex AI comunicazioni',
      body: 'Legge PEC, email ordinarie, messaggi, mittenti, allegati ed esiti per aiutarti a collegare comunicazioni e fascicoli.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex comunicazioni',
      secondaryHref: route === '/email-ordinaria' ? '/email-ordinaria/' : '/email/',
      secondaryLabel: route === '/email-ordinaria' ? 'Email ordinaria' : 'Casella PEC',
    }
  }
  if (route.startsWith('/scadenziario')) {
    return {
      context: 'scadenziario',
      title: 'Lex AI scadenziario',
      body: 'Legge scadenze, termini, urgenze e blocchi operativi per presidiare il calendario processuale.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex termini',
      secondaryHref: '/scadenziario',
      secondaryLabel: 'Scadenziario',
    }
  }
  const wizardStepMatch = route.match(/^\/wizard-pro\/[^/]+\/step\/([1-5])$/)
  if (wizardStepMatch) {
    const contexts: Record<string,string> = {
      '1': 'preparazione-udienza-briefing',
      '2': 'preparazione-udienza-documenti',
      '3': 'preparazione-udienza-strategia',
      '4': 'preparazione-udienza-precheck',
      '5': 'preparazione-udienza-esito',
    }
    return {
      context: contexts[wizardStepMatch[1]] || 'preparazione-udienza',
      title: 'Lex AI udienza',
      body: 'Legge lo step corrente della preparazione udienza e collega fascicolo, documenti, strategia ed esito.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex udienza',
      secondaryHref: '/wizard-pro/',
      secondaryLabel: 'Wizard udienza',
    }
  }
  if (/^\/wizard-pro\/[^/]+\/completo$/.test(route)) {
    return {
      context: 'preparazione-udienza-riepilogo',
      title: 'Lex AI riepilogo',
      body: 'Legge esito, azioni successive e checklist della preparazione udienza.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex riepilogo',
      secondaryHref: '/wizard-pro/',
      secondaryLabel: 'Wizard udienza',
    }
  }
  if (route.startsWith('/wizard-pro')) {
    return {
      context: 'preparazione-udienza',
      title: 'Lex AI udienza',
      body: 'Legge attività, documenti, parti e udienza per preparare checklist, note e prossime azioni.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex udienza',
      secondaryHref: '/wizard-pro/',
      secondaryLabel: 'Wizard udienza',
    }
  }
  if (route === '/timesheet') {
    return {
      context: 'timesheet',
      title: 'Lex AI timesheet',
      body: 'Legge voci, stati, clienti e fascicoli per aiutarti a presidiare tempi e fatturazione.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex timesheet',
      secondaryHref: '/fatturazione/',
      secondaryLabel: 'Fatturazione',
    }
  }
  if (route === '/cartelle-condivise') {
    return {
      context: 'cartelle-condivise',
      title: 'Lex AI condivisioni',
      body: 'Legge accessi, ruoli, scadenze e presidi privacy delle cartelle condivise.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex condivisioni',
      secondaryHref: '/privacy/registro',
      secondaryLabel: 'Registro GDPR',
    }
  }
  if (route === '/telematico' || route === '/telematici' || route === '/servizi-telematici' || isTelematicoSurfaceRoute(route)) {
    return {
      context: 'telematico',
      title: 'Lex AI telematico',
      body: 'Legge canale, uffici, checklist, ricevute, import e stato del deposito nella pagina telematica aperta.',
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex telematico',
      secondaryHref: '/telematico',
      secondaryLabel: 'Centro telematico',
    }
  }
  const studioModule = findStudioModule(route)
  if (studioModule) {
    return {
      context: studioModule.lexContext,
      title: `Lex AI ${studioModule.title}`,
      body: studioModule.lexLabel,
      primaryHref: OPEN_LEX_WIDGET_HREF,
      primaryLabel: 'Apri Lex',
      secondaryHref: studioModule.routes[0],
      secondaryLabel: studioModule.title,
    }
  }
  return {
    context: 'panoramica',
    title: 'Lex AI',
    body: 'Legge il contesto della pagina e collega dati di studio, scadenze, fascicoli e comunicazioni.',
    primaryHref: OPEN_LEX_WIDGET_HREF,
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
  if (route === '/email' || route === '/email-ordinaria' || route.startsWith('/messaggi')) return true
  if (route.startsWith('/scadenziario') && !isNewDeadline && !isDeadlineEdit) return true
  if (route.startsWith('/wizard-pro')) return true
  if (route === '/timesheet' || route === '/cartelle-condivise') return true
  if (route.startsWith('/privacy/registro') || route === '/registro-gdpr') return true
  if (route === '/admin/database') return true
  return route === '/telematico' || route === '/telematici' || isTelematicoSurfaceRoute(route)
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

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

function SidebarUser({ bootstrap }: { bootstrap: ShellBootstrap }) {
  const profile = bootstrap.user
  if (!profile) return null
  const initials = profile.initials || profile.username.slice(0, 2).toUpperCase()
  const logoutAction = bootstrap.actions.logout || ''
  return (
    <div className="iu-sidebar__user">
      <span>{initials}</span>
      <div>
        <strong>{profile.displayName}</strong>
        {profile.role ? <small>{profile.role}</small> : null}
      </div>
      {bootstrap.actions.profile ? <a href={bootstrap.actions.profile} aria-label="Profilo" title="Profilo"><UserRound size={16}/></a> : null}
      {logoutAction ? (
        <form method="post" action={logoutAction}>
          <input type="hidden" name="_csrf_token" value={csrfToken()}/>
          <button type="submit" aria-label="Esci" title="Esci"><LogOut size={16}/></button>
        </form>
      ) : null}
    </div>
  )
}

function Sidebar({ collapsed, mobileOpen, activePath, onToggle, onCloseMobile, bootstrap }:{collapsed:boolean; mobileOpen:boolean; activePath:string; onToggle:()=>void; onCloseMobile:()=>void; bootstrap:ShellBootstrap}) {
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
    <IusAppSidebar collapsed={collapsed} className={mobileOpen ? 'iu-sidebar--mobile-open' : ''}>
      <div className="iu-sidebar__brand">
        <Logo/>
        <div><strong>IUSENTRA</strong><span>Lo studio legale, in un unico sistema</span></div>
        <button className="iu-sidebar__toggle" type="button" onClick={handleToggle} aria-label={toggleLabel} title={toggleLabel}><ToggleIcon size={18}/></button>
      </div>
      <nav className="iu-sidebar__nav" aria-label="Navigazione principale">
        <div className="iu-nav-primary">
          {primaryNav.map(item=><NavLink key={item.label} item={item} collapsed={collapsed} activePath={activePath} onNavigate={onCloseMobile}/>)}
        </div>
        {navSections.filter(section=>section.items.length > 0).map(section=>{
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
      <SidebarUser bootstrap={bootstrap}/>
    </IusAppSidebar>
  )
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
  return <Panel title="Suggerimenti Lex AI" icon={<Sparkles size={17}/>} count={data.lex.length}>{data.lex.length?<div className="iu-lex">{data.lex.map(s=><div key={s}><Sparkles size={15}/><span>{s}</span></div>)}</div>:<Empty>Nessun suggerimento prioritario.</Empty>}<a className="iu-link" href={OPEN_LEX_WIDGET_HREF} data-lex-open data-lex-context="panoramica">Apri Lex AI -&gt;</a></Panel>
}

function Dossiers({ data }:{data:DashboardData}) {
  return <Panel title="Fascicoli da presidiare" subtitle="Fascicoli reali ad alta priorità da seguire nel quadro operativo." icon={<BriefcaseBusiness size={17}/>} count={data.dossiers.length}>{data.dossiers.length?<div className="iu-dossier-grid">{data.dossiers.map(dossier=><DossierCard dossier={dossier} key={dossier.id}/>)}</div>:<Empty>Nessun fascicolo prioritario nell'orizzonte operativo.</Empty>}<a className="iu-link" href="/fascicoli">Apri tutti i fascicoli -&gt;</a></Panel>
}

function Sources({ data }:{data:DashboardData}) {
  return <Panel title="Fonti operative collegate" subtitle="Fonti applicative alimentate dai conteggi reali dello studio." icon={<BookOpen size={17}/>} count={data.sources.length}>{data.sources.length?<div className="iu-source-grid">{data.sources.map(source=><SourceCard source={source} key={source.id}/>)}</div>:<Empty>Nessuna fonte operativa disponibile.</Empty>}</Panel>
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

function DashboardPage({ data, loading, mailSyncing = false }:{data:DashboardData; loading:boolean; mailSyncing?:boolean}) {
  return (
    <main className="iu-content">
      <div className="iu-page-heading">
        <div>
          <h1>Panoramica</h1>
          <p>Centro operativo dello studio</p>
        </div>
        <span className={`iu-sync ${loading || mailSyncing?'':'ok'}`}>{loading?'Sincronizzazione dati...':mailSyncing?'Sincronizzazione comunicazioni...':'Dati aggiornati'}</span>
      </div>
      <section className="iu-metrics">{data.metrics.map(m=><KpiCard item={m} icon={metricIcon[m.tone] || AlertTriangle} key={m.id}/>)}</section>
      <section className="iu-grid">
        <div className="span3"><Panel title="Ultime PEC ricevute" icon={<Mail size={17}/>} count={data.pec.length}><List rows={data.pec} href="/email/"/><a className="iu-link" href="/email/">Vai alla casella PEC -&gt;</a></Panel></div>
        <div className="span3"><Panel title="Email recenti" icon={<Mail size={17}/>} count={data.emails.length}><List rows={data.emails} href="/email-ordinaria/"/><a className="iu-link" href="/email-ordinaria/">Vai alle email ordinarie -&gt;</a></Panel></div>
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
  const forcedLegacyHref = legacyOperationalRedirectHref(activePath)
  if (forcedLegacyHref) {
    window.location.replace(forcedLegacyHref)
    return <PageLoading/>
  }
  const isSearchPage = routeKey === '/global-search' || routeKey === '/ricerca-studio' || routeKey === '/cerca'
  const isNewAppointmentPage = routeKey === '/agenda/nuovo' || routeKey.startsWith('/agenda/nuovo/')
  const isAppointmentEditPage = /^\/agenda\/[^/]+\/modifica$/.test(routeKey)
  const isAgendaPage = !isNewAppointmentPage && !isAppointmentEditPage && (routeKey === '/agenda' || routeKey.startsWith('/agenda/'))
  const isRegiaPage = routeKey === '/workspace-intelligente' || routeKey === '/regia-operativa' || routeKey.startsWith('/regia-operativa/')
  const isDocumentEditorPage = /^\/fascicoli\/[^/]+\/documenti\/[^/]+\/editor$/.test(routeKey)
  const isFascicoliPage = !isDocumentEditorPage && (routeKey === '/fascicoli' || routeKey.startsWith('/fascicoli/'))
  const isNewClientPage = routeKey === '/clienti/nuovo'
  const isNewSubjectPage = routeKey === '/soggetti/nuovo'
  const isClientEditPage = /^\/clienti\/[^/]+\/modifica$/.test(routeKey)
  const isSubjectEditPage = /^\/soggetti\/[^/]+\/modifica$/.test(routeKey)
  const isClientFolderPage = /^\/clienti\/[^/]+(\/(cartella|faldone|portale))?$/.test(routeKey)
  const isClientiPage = !isNewClientPage && !isClientFolderPage && routeKey === '/clienti'
  const isSoggettiPage = !isNewSubjectPage && !isSubjectEditPage && (routeKey === '/soggetti' || routeKey.startsWith('/soggetti/'))
  const isEmailComposePage = routeKey === '/email/scrivi'
  const isEmailOrdinariaComposePage = routeKey === '/email-ordinaria/scrivi'
  const isEmailPage = !isEmailComposePage && (routeKey === '/email' || routeKey.startsWith('/email/'))
  const isEmailOrdinariaPage = !isEmailOrdinariaComposePage && (routeKey === '/email-ordinaria' || routeKey.startsWith('/email-ordinaria/'))
  const isNewMessagePage = routeKey === '/messaggi/nuovo'
  const isMessagesPage = !isNewMessagePage && (routeKey === '/messaggi' || routeKey.startsWith('/messaggi/'))
  const isNewDeadlinePage = routeKey === '/scadenziario/nuova'
  const isDeadlineEditPage = /^\/scadenziario\/[^/]+\/modifica$/.test(routeKey)
  const isScadenziarioPage = !isNewDeadlinePage && !isDeadlineEditPage && (routeKey === '/scadenziario' || routeKey.startsWith('/scadenziario/'))
  const isTimesheetPage = routeKey === '/timesheet'
  const isCartelleCondivisePage = routeKey === '/cartelle-condivise'
  const isWizardProDashboard = routeKey === '/wizard-pro' || routeKey === '/wizard-pro/nuovo'
  const isWizardProStep = /^\/wizard-pro\/[^/]+\/step\/[1-5]$/.test(routeKey)
  const isWizardProComplete = /^\/wizard-pro\/[^/]+\/completo$/.test(routeKey)
  const isWizardProPage = isWizardProDashboard || isWizardProStep || isWizardProComplete
  const isTelematicoPage = routeKey === '/telematico' || routeKey === '/telematici' || routeKey === '/servizi-telematici'
  const isTelematicoSurfacePage = isTelematicoSurfaceRoute(routeKey)
  const isPrivacyRegistroPage = routeKey === '/privacy/registro' || routeKey === '/privacy/registro/nuovo' || routeKey === '/registro-gdpr'
  const isAdminDatabasePage = routeKey === '/admin/database'
  const isStatistichePage = routeKey === '/statistiche'
  const isImpostazioniPage = routeKey === '/impostazioni' || routeKey === '/impostazioni-studio' || routeKey === '/impostazioni/pagamenti' || routeKey === '/notifiche' || routeKey === '/notifiche-whatsapp' || routeKey === '/backup' || routeKey === '/impostazioni/calendario' || routeKey === '/sincronizzazione-calendari'
  const isAuditPage = routeKey === '/audit'
  const isRegistroAttivitaPage = routeKey === '/registro-attivita'
  const isUtentiPage = routeKey === '/utenti' || routeKey === '/utenti/nuovo'
  const isProfiliPage = routeKey === '/profili'
  const isBackupPage = routeKey === '/backup'
  const isSitoStudioPage = routeKey === '/sito-studio' || routeKey === '/sito-studio/contatti'
  const isStudioPage = routeKey === '/studio'
  const isAmministrazionePage = routeKey === '/amministrazione'
  const isFatturazionePage = routeKey === '/fatturazione' || routeKey === '/fatturazione/nuova'
  const isIncassiPagamentiPage = routeKey === '/incassi-pagamenti'
  const isPreventivoWizardPage = routeKey === '/preventivi/wizard'
  const isPreventiviPage =
    routeKey === '/preventivi' ||
    routeKey === '/preventivi/nuovo' ||
    routeKey === '/preventivi/conferimento/nuovo'
  const isCompensiForensiPage = routeKey === '/compensi-forensi'
  const isTariffarioPage = routeKey === '/tariffario'
  const isTemplateAttiPage =
    routeKey === '/template-atti' ||
    routeKey === '/template-atti/catalogo'
  const isRedazioneAttiPage = routeKey === '/redazione-atti'
  const isGiurisprudenzaPage = routeKey === '/giurisprudenza'
  const isLegalIntelligencePage =
    routeKey === '/legal-intelligence' ||
    routeKey === '/legal-intelligence/news' ||
    routeKey === '/legal-intelligence/mediazione' ||
    routeKey === '/ricerca-legale'
  const isStudioModulePage = !isStudioPage && !isAmministrazionePage && !isFatturazionePage && !isIncassiPagamentiPage && !isPreventivoWizardPage && !isPreventiviPage && !isCompensiForensiPage && !isTariffarioPage && !isTemplateAttiPage && !isRedazioneAttiPage && !isGiurisprudenzaPage && !isLegalIntelligencePage && !isAdminDatabasePage && !isStatistichePage && !isImpostazioniPage && !isAuditPage && !isRegistroAttivitaPage && !isUtentiPage && !isProfiliPage && !isBackupPage && !isSitoStudioPage && !isTimesheetPage && !isCartelleCondivisePage && !isWizardProPage && isStudioModuleRoute(routeKey)
  const isDashboardPage = !isSearchPage && !isAgendaPage && !isNewAppointmentPage && !isAppointmentEditPage && !isRegiaPage && !isDocumentEditorPage && !isFascicoliPage && !isClientiPage && !isClientFolderPage && !isClientEditPage && !isNewClientPage && !isSoggettiPage && !isNewSubjectPage && !isSubjectEditPage && !isEmailComposePage && !isEmailOrdinariaComposePage && !isEmailPage && !isEmailOrdinariaPage && !isMessagesPage && !isNewMessagePage && !isScadenziarioPage && !isNewDeadlinePage && !isDeadlineEditPage && !isTimesheetPage && !isCartelleCondivisePage && !isWizardProPage && !isTelematicoPage && !isTelematicoSurfacePage && !isPrivacyRegistroPage && !isAdminDatabasePage && !isStatistichePage && !isImpostazioniPage && !isAuditPage && !isRegistroAttivitaPage && !isUtentiPage && !isProfiliPage && !isBackupPage && !isSitoStudioPage && !isStudioPage && !isAmministrazionePage && !isFatturazionePage && !isIncassiPagamentiPage && !isPreventivoWizardPage && !isPreventiviPage && !isCompensiForensiPage && !isTariffarioPage && !isTemplateAttiPage && !isRedazioneAttiPage && !isGiurisprudenzaPage && !isLegalIntelligencePage && !isStudioModulePage
  const isStandalonePage = isSearchPage || isAgendaPage || isNewAppointmentPage || isAppointmentEditPage || isDocumentEditorPage || isFascicoliPage || isClientiPage || isClientFolderPage || isClientEditPage || isNewClientPage || isSoggettiPage || isNewSubjectPage || isSubjectEditPage || isEmailComposePage || isEmailOrdinariaComposePage || isEmailPage || isEmailOrdinariaPage || isMessagesPage || isNewMessagePage || isScadenziarioPage || isNewDeadlinePage || isDeadlineEditPage || isTimesheetPage || isCartelleCondivisePage || isWizardProPage || isTelematicoPage || isTelematicoSurfacePage || isPrivacyRegistroPage || isAdminDatabasePage || isStatistichePage || isImpostazioniPage || isAuditPage || isRegistroAttivitaPage || isUtentiPage || isProfiliPage || isBackupPage || isSitoStudioPage || isStudioPage || isAmministrazionePage || isFatturazionePage || isIncassiPagamentiPage || isPreventivoWizardPage || isPreventiviPage || isCompensiForensiPage || isTariffarioPage || isTemplateAttiPage || isRedazioneAttiPage || isGiurisprudenzaPage || isLegalIntelligencePage || isStudioModulePage
  const initialSearchQuery = new URLSearchParams(window.location.search).get('q') ?? ''
  const lexConfig = resolveLexPageContext(routeKey)
  const needsShellLexContext = !routePublishesLexContext(routeKey)
  const shellBootstrap = readShellBootstrap()
  const [data,setData]=useState<DashboardData>(emptyDashboard)
  const [loading,setLoading]=useState(!isStandalonePage)
  const [mailSyncing,setMailSyncing]=useState(false)
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false)
  const [mobileMenuOpen,setMobileMenuOpen]=useState(false)
  const [mobileNavCollapsed,setMobileNavCollapsed]=useState(false)
  useEffect(()=>{
    if(isStandalonePage)return
    let ok=true
    getDashboard()
      .then(d=>{
        if(ok)setData(d)
        if(ok && isDashboardPage){
          window.setTimeout(()=>{
            if(!ok)return
            setMailSyncing(true)
            syncDashboardMailboxes()
              .then(()=>getDashboard({refresh:true}))
              .then((fresh)=>{if(ok)setData(fresh)})
              .finally(()=>{if(ok)setMailSyncing(false)})
          },0)
        }
      })
      .finally(()=>{if(ok)setLoading(false)})
    return()=>{ok=false}
  },[isDashboardPage,isStandalonePage])
  return (
    <AppErrorBoundary>
      <div className={`iu-shell ${sidebarCollapsed?'iu-shell--collapsed':''}`}>
        <Sidebar collapsed={sidebarCollapsed} mobileOpen={mobileMenuOpen} activePath={activePath} onToggle={()=>setSidebarCollapsed(v=>!v)} onCloseMobile={()=>setMobileMenuOpen(false)} bootstrap={shellBootstrap}/>
        {mobileMenuOpen?<button className="iu-sidebar-scrim" type="button" aria-label="Chiudi menu" onClick={()=>setMobileMenuOpen(false)}/>:null}
        <div className="iu-main">
          <TopBar onOpenMenu={()=>setMobileMenuOpen(true)} activePath={routeKey}/>
          <Suspense fallback={<PageLoading/>}>
            {isSearchPage?<RicercaStudioPage initialQuery={initialSearchQuery}/>:isNewAppointmentPage||isAppointmentEditPage?<NuovoAppuntamentoPage/>:isAgendaPage?<AgendaPage/>:isRegiaPage?<RegiaOperativaPage data={data} loading={loading}/>:isDocumentEditorPage?<DocumentEditorPage/>:isFascicoliPage?<FascicoliPage/>:isNewClientPage||isNewSubjectPage||isClientEditPage||isSubjectEditPage?<NuovoClientePage/>:isClientFolderPage?<CartellaClientePage/>:isClientiPage?<AnagraficaClientiPage/>:isSoggettiPage?<SoggettiPage/>:isEmailOrdinariaComposePage?<EmailComposePage mode="ordinaria"/>:isEmailComposePage?<EmailComposePage mode="pec"/>:isEmailOrdinariaPage?<EmailOrdinariaPage/>:isEmailPage?<EmailPecPage/>:isNewMessagePage?<NuovoMessaggioPage/>:isMessagesPage?<MessaggiPage/>:isNewDeadlinePage||isDeadlineEditPage?<NuovaScadenzaPage/>:isScadenziarioPage?<ScadenziarioPage/>:isTimesheetPage?<TimesheetPage/>:isCartelleCondivisePage?<CartelleCondivisePage/>:isWizardProStep?<WizardProStepPage/>:isWizardProComplete?<WizardProCompletePage/>:isWizardProDashboard?<WizardProPage/>:isTelematicoPage?<TelematicoPage/>:isTelematicoSurfacePage?<TelematicoSurfacePage/>:isPrivacyRegistroPage?<PrivacyRegistroPage/>:isAdminDatabasePage?<AdminDatabasePage/>:isStatistichePage?<StatistichePage/>:isImpostazioniPage?<ImpostazioniPage/>:isAuditPage||isRegistroAttivitaPage?<AuditPage/>:isUtentiPage?<UtentiPage/>:isProfiliPage?<ProfiliPage/>:isBackupPage?<BackupPage/>:isSitoStudioPage?<SitoStudioPage/>:isStudioPage?<StudioPage/>:isAmministrazionePage?<AmministrazionePage/>:isFatturazionePage?<FatturazionePage/>:isIncassiPagamentiPage?<IncassiPagamentiPage/>:isPreventivoWizardPage?<PreventivoWizardPage/>:isPreventiviPage?<PreventiviPage/>:isCompensiForensiPage?<CompensiForensiPage/>:isTariffarioPage?<TariffarioPage/>:isTemplateAttiPage?<TemplateAttiPage/>:isRedazioneAttiPage?<RedazioneAttiPage/>:isGiurisprudenzaPage?<GiurisprudenzaPage/>:isLegalIntelligencePage?<LegalIntelligencePage/>:isStudioModulePage?<StudioModulePage/>:<DashboardPage data={data} loading={loading} mailSyncing={mailSyncing}/>}
          </Suspense>
        </div>
        <nav className={`iu-mobile ${mobileNavCollapsed?'is-collapsed':''}`} aria-label="Navigazione mobile">
          <div id="iu-mobile-links" className="iu-mobile__rail" hidden={mobileNavCollapsed}>
            <a className={isDashboardPage?'active':''} href="/"><LayoutDashboard size={18}/>Panoramica</a>
            <a className={isSearchPage?'active':''} href="/global-search"><Search size={18}/>Ricerca</a>
            <a className={isFascicoliPage?'active':''} href="/fascicoli"><BriefcaseBusiness size={18}/>Fascicoli</a>
            <a className={isClientiPage||isClientFolderPage||isClientEditPage||isNewClientPage||isCartelleCondivisePage||isSoggettiPage||isNewSubjectPage||isSubjectEditPage?'active':''} href="/clienti"><UsersRound size={18}/>Clienti</a>
            <a className={isEmailPage||isEmailOrdinariaPage||isMessagesPage||isNewMessagePage?'active':''} href="/email/"><Mail size={18}/>Posta</a>
            <a className={isAgendaPage||isNewAppointmentPage||isAppointmentEditPage||isTimesheetPage||isScadenziarioPage||isNewDeadlinePage||isDeadlineEditPage||isWizardProPage?'active':''} href="/agenda"><CalendarDays size={18}/>Agenda</a>
            <a className={isRegiaPage||isPrivacyRegistroPage||isAdminDatabasePage?'active':''} href="/workspace-intelligente"><Sparkles size={18}/>Regia</a>
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
