import { Component, Suspense, lazy, useEffect, useState, type ComponentType, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  Banknote,
  BookOpen,
  BookOpenCheck,
  Bot,
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
  RefreshCw,
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
import { IusAppSidebar, IusentraRoutePresetFrame } from './components/iusentra'
import { JsonPostForm } from './components/JsonPostForm'
import { TopBar } from './components/layout/TopBar'
import { sanitizeDisplayText } from './displayText'
import { appV2FeatureFlagForPath, isFeatureFlagEnabledSync, type FeatureFlagKey } from './lib/featureFlags'
import { findStudioModule, isStudioModuleRoute } from './studioModuleData'
import './index.css'
import './components/layout/TopBar.css'

const CHUNK_RELOAD_GUARD_WINDOW_MS = 30_000

// Dopo un deploy gli hash dei chunk cambiano: un tab aperto col bundle
// precedente fallirebbe l'import dinamico mostrando l'error boundary.
// Qui la pagina si ricarica da sola una volta così il browser riprende il
// bundle aggiornato dal server; la guardia anti-loop vive in history.state
// (sopravvive al reload senza usare storage di tab, vietato dalla governance).
function lazyPage<T extends ComponentType<any>>(loader: () => Promise<{ default: T }>) {
  return lazy(() =>
    loader().catch((error: unknown) => {
      try {
        const state = (window.history.state || {}) as { iuChunkReloadAt?: number }
        const last = Number(state.iuChunkReloadAt || 0)
        if (Date.now() - last > CHUNK_RELOAD_GUARD_WINDOW_MS) {
          window.history.replaceState({ ...state, iuChunkReloadAt: Date.now() }, '')
          window.location.reload()
          return new Promise<{ default: T }>(() => {})
        }
      } catch {
        // history non disponibile: si lascia all'error boundary.
      }
      throw error
    }),
  )
}

const AgendaPage = lazyPage(() => import('./components/AgendaPage').then((module) => ({ default: module.AgendaPage })))
const AgendaImportPage = lazyPage(() => import('./components/AgendaImportPage').then((module) => ({ default: module.AgendaImportPage })))
const NuovoAppuntamentoPage = lazyPage(() => import('./components/NuovoAppuntamentoPage').then((module) => ({ default: module.NuovoAppuntamentoPage })))
const RicercaStudioPage = lazyPage(() => import('./components/RicercaStudioPage').then((module) => ({ default: module.RicercaStudioPage })))
const FascicoliPage = lazyPage(() => import('./components/FascicoliPage').then((module) => ({ default: module.FascicoliPage })))
const DocumentEditorPage = lazyPage(() => import('./components/DocumentEditorPage').then((module) => ({ default: module.DocumentEditorPage })))
const AnagraficaClientiPage = lazyPage(() => import('./components/AnagraficaClientiPage').then((module) => ({ default: module.AnagraficaClientiPage })))
const CartellaClientePage = lazyPage(() => import('./components/CartellaClientePage').then((module) => ({ default: module.CartellaClientePage })))
const NuovoClientePage = lazyPage(() => import('./components/NuovoClientePage').then((module) => ({ default: module.NuovoClientePage })))
const SoggettiPage = lazyPage(() => import('./components/SoggettiPage').then((module) => ({ default: module.SoggettiPage })))
const EmailPecPage = lazyPage(() => import('./components/EmailPecPage').then((module) => ({ default: module.EmailPecPage })))
const EmailOrdinariaPage = lazyPage(() => import('./components/EmailPecPage').then((module) => ({ default: module.EmailOrdinariaPage })))
const EmailComposePage = lazyPage(() => import('./components/EmailPecPage').then((module) => ({ default: module.EmailComposePage })))
const NotificheLegaliPage = lazyPage(() => import('./components/NotificheLegaliPage').then((module) => ({ default: module.NotificheLegaliPage })))
const MessaggiPage = lazyPage(() => import('./components/MessaggiPage').then((module) => ({ default: module.MessaggiPage })))
const NuovoMessaggioPage = lazyPage(() => import('./components/MessaggiPage').then((module) => ({ default: module.NuovoMessaggioPage })))
const ScadenziarioPage = lazyPage(() => import('./components/ScadenziarioPage').then((module) => ({ default: module.ScadenziarioPage })))
const NuovaScadenzaPage = lazyPage(() => import('./components/NuovaScadenzaPage').then((module) => ({ default: module.NuovaScadenzaPage })))
const WizardProPage = lazyPage(() => import('./components/WizardProPage').then((module) => ({ default: module.WizardProPage })))
const WizardProStepPage = lazyPage(() => import('./components/WizardProStepPage').then((module) => ({ default: module.WizardProStepPage })))
const WizardProCompletePage = lazyPage(() => import('./components/WizardProCompletePage').then((module) => ({ default: module.WizardProCompletePage })))
const TimesheetPage = lazyPage(() => import('./components/TimesheetPage').then((module) => ({ default: module.TimesheetPage })))
const CartelleCondivisePage = lazyPage(() => import('./components/CartelleCondivisePage').then((module) => ({ default: module.CartelleCondivisePage })))
const TelematicoPage = lazyPage(() => import('./components/TelematicoPage').then((module) => ({ default: module.TelematicoPage })))
const TelematicoSurfacePage = lazyPage(() => import('./components/TelematicoSurfacePage').then((module) => ({ default: module.TelematicoSurfacePage })))
const StudioModulePage = lazyPage(() => import('./components/StudioModulePage').then((module) => ({ default: module.StudioModulePage })))
const PrivacyRegistroPage = lazyPage(() => import('./components/PrivacyRegistroPage').then((module) => ({ default: module.PrivacyRegistroPage })))
const AdminDatabasePage = lazyPage(() => import('./components/AdminDatabasePage').then((module) => ({ default: module.AdminDatabasePage })))
const QuickOrganizerImportPage = lazyPage(() => import('./components/QuickOrganizerImportPage').then((module) => ({ default: module.QuickOrganizerImportPage })))
const StatistichePage = lazyPage(() => import('./components/StatistichePage').then((module) => ({ default: module.StatistichePage })))
const ImpostazioniPage = lazyPage(() => import('./components/ImpostazioniPage').then((module) => ({ default: module.ImpostazioniPage })))
const AuditPage = lazyPage(() => import('./components/AuditPage').then((module) => ({ default: module.AuditPage })))
const UtentiPage = lazyPage(() => import('./components/UtentiPage').then((module) => ({ default: module.UtentiPage })))
const ProfiliPage = lazyPage(() => import('./components/ProfiliPage').then((module) => ({ default: module.ProfiliPage })))
const ProfiloPage = lazyPage(() => import('./components/ProfiloPage').then((module) => ({ default: module.ProfiloPage })))
const BackupPage = lazyPage(() => import('./components/BackupPage').then((module) => ({ default: module.BackupPage })))
const SitoStudioBuilderPage = lazyPage(() => import('./components/SitoStudioBuilderPage').then((module) => ({ default: module.SitoStudioBuilderPage })))
const SitoStudioRedazioneAiPage = lazyPage(() => import('./components/SitoStudioRedazioneAiPage').then((module) => ({ default: module.SitoStudioRedazioneAiPage })))
const SitoStudioPage = lazyPage(() => import('./components/SitoStudioPage').then((module) => ({ default: module.SitoStudioPage })))
const StudioPage = lazyPage(() => import('./components/StudioPage').then((module) => ({ default: module.StudioPage })))
const EditorProfessionalePage = lazyPage(() => import('./components/EditorProfessionalePage').then((module) => ({ default: module.EditorProfessionalePage })))
const AmministrazionePage = lazyPage(() => import('./components/AmministrazionePage').then((module) => ({ default: module.AmministrazionePage })))
const FatturazionePage = lazyPage(() => import('./components/FatturazionePage').then((module) => ({ default: module.FatturazionePage })))
const IncassiPagamentiPage = lazyPage(() => import('./components/IncassiPagamentiPage').then((module) => ({ default: module.IncassiPagamentiPage })))
const PreventiviPage = lazyPage(() => import('./components/PreventiviPage').then((module) => ({ default: module.PreventiviPage })))
const PreventivoWizardPage = lazyPage(() => import('./components/PreventivoWizardPage').then((module) => ({ default: module.PreventivoWizardPage })))
const CompensiForensiPage = lazyPage(() => import('./components/CompensiForensiPage').then((module) => ({ default: module.CompensiForensiPage })))
const TariffarioPage = lazyPage(() => import('./components/TariffarioPage').then((module) => ({ default: module.TariffarioPage })))
const TemplateAttiPage = lazyPage(() => import('./components/TemplateAttiPage').then((module) => ({ default: module.TemplateAttiPage })))
const RedazioneAttiPage = lazyPage(() => import('./components/RedazioneAttiPage').then((module) => ({ default: module.RedazioneAttiPage })))
const GiurisprudenzaPage = lazyPage(() => import('./components/GiurisprudenzaPage').then((module) => ({ default: module.GiurisprudenzaPage })))
const LegalIntelligencePage = lazyPage(() => import('./components/LegalIntelligencePage').then((module) => ({ default: module.LegalIntelligencePage })))
const LegalSkillsCatalogPage = lazyPage(() => import('./features/legal-skills/pages/LegalSkillsCatalogPage').then((module) => ({ default: module.LegalSkillsCatalogPage })))
const PracticeProfilePage = lazyPage(() => import('./features/legal-skills/pages/PracticeProfilePage').then((module) => ({ default: module.PracticeProfilePage })))
const ColdStartInterviewPage = lazyPage(() => import('./features/legal-skills/pages/ColdStartInterviewPage').then((module) => ({ default: module.ColdStartInterviewPage })))
const LegalSkillRunPage = lazyPage(() => import('./features/legal-skills/pages/LegalSkillRunPage').then((module) => ({ default: module.LegalSkillRunPage })))
const SkillRunDetailPage = lazyPage(() => import('./features/legal-skills/pages/SkillRunDetailPage').then((module) => ({ default: module.SkillRunDetailPage })))
const ReviewerQueuePage = lazyPage(() => import('./features/legal-skills/pages/ReviewerQueuePage').then((module) => ({ default: module.ReviewerQueuePage })))
const WorkflowAgentsHome = lazyPage(() => import('./pages/workflow-agents/WorkflowAgentsHome').then((module) => ({ default: module.WorkflowAgentsHome })))
const AgentApprovalQueue = lazyPage(() => import('./pages/workflow-agents/AgentApprovalQueue').then((module) => ({ default: module.AgentApprovalQueue })))
const AgentRunDetail = lazyPage(() => import('./pages/workflow-agents/AgentRunDetail').then((module) => ({ default: module.AgentRunDetail })))
const ClientPortalPage = lazyPage(() => import('./components/ClientPortalPage').then((module) => ({ default: module.ClientPortalPage })))

const toneColor: Record<Tone,string> = { danger:'var(--iu-danger-500)', warning:'var(--iu-warning-500)', primary:'var(--iu-blue-600)', success:'var(--iu-success-500)', info:'var(--iu-sky-500)', purple:'var(--iu-purple-500)', orange:'var(--iu-warning-500)', neutral:'var(--iu-slate-300)' }
const metricIcon = { danger: AlertTriangle, primary: Mail, success: MessageCircle, purple: Clock3, orange: UsersRound, warning: AlertTriangle, info: Mail, neutral: Clock3 }
const TEXT_SANITIZER_SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'PRE', 'CODE', 'KBD', 'SAMP'])
const ATTRIBUTE_SANITIZER_SKIP = new Set(['SCRIPT', 'STYLE', 'PRE', 'CODE', 'KBD', 'SAMP'])

class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: unknown) {
    console.error('Errore interfaccia IUSENTRA', error)
    // Primo errore di pagina: un reload riprende bundle e dati freschi e
    // guarisce i casi "tab rimasto sul deploy precedente". La guardia in
    // history.state evita loop: al secondo errore resta la schermata di cortesia.
    try {
      const state = (window.history.state || {}) as { iuBoundaryReloadAt?: number }
      const last = Number(state.iuBoundaryReloadAt || 0)
      if (Date.now() - last > CHUNK_RELOAD_GUARD_WINDOW_MS) {
        window.history.replaceState({ ...state, iuBoundaryReloadAt: Date.now() }, '')
        window.location.reload()
      }
    } catch {
      // history non disponibile: si mostra la schermata di cortesia.
    }
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <main className="iu-content iu-react-error" role="alert">
        <div>
          <AlertTriangle size={24}/>
          <h1>Pagina temporaneamente non disponibile</h1>
          <p>La pagina ha intercettato un errore di interfaccia. Ricarica o apri il modulo operativo dal menu senza perdere i dati dello studio.</p>
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
  featureFlag?: FeatureFlagKey
  requiresAnyPermission?: string[]
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
  email: string
  role: string
  initials: string
}

type ShellBootstrap = {
  user: ShellUserProfile | null
  tenant: {
    slug: string
    name: string
  } | null
  permissions: string[]
  actions: {
    profile?: string
    logout?: string
  }
}

function shouldSanitizeTextNode(node: Node): boolean {
  let current = node.parentElement
  while (current) {
    if (TEXT_SANITIZER_SKIP.has(current.tagName)) return false
    if (current.getAttribute('data-allow-technical-text') === 'true') return false
    current = current.parentElement
  }
  return true
}

function shouldSanitizeElement(element: Element): boolean {
  let current: Element | null = element
  while (current) {
    if (ATTRIBUTE_SANITIZER_SKIP.has(current.tagName)) return false
    if (current.getAttribute('data-allow-technical-text') === 'true') return false
    current = current.parentElement
  }
  return true
}

function sanitizeVisibleAttributes(root: HTMLElement) {
  const attributes = ['title', 'aria-label', 'aria-description', 'placeholder', 'alt']
  for (const element of Array.from(root.querySelectorAll(attributes.map((name) => `[${name}]`).join(',')))) {
    if (!shouldSanitizeElement(element)) continue
    for (const attribute of attributes) {
      const original = element.getAttribute(attribute)
      if (!original) continue
      const cleaned = sanitizeDisplayText(original)
      if (cleaned !== original) element.setAttribute(attribute, cleaned)
    }
  }
}

function sanitizeVisibleText(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const nodes: Text[] = []
  let current = walker.nextNode()
  while (current) {
    if (current.textContent && shouldSanitizeTextNode(current)) nodes.push(current as Text)
    current = walker.nextNode()
  }
  for (const node of nodes) {
    const original = node.textContent || ''
    const cleaned = sanitizeDisplayText(original)
    if (cleaned !== original) node.textContent = cleaned
  }
  sanitizeVisibleAttributes(root)
  const cleanedTitle = sanitizeDisplayText(document.title)
  if (cleanedTitle !== document.title) document.title = cleanedTitle
}

function useVisibleTextGuard() {
  useEffect(() => {
    const root = document.getElementById('root') || document.body
    let frame = 0
    const schedule = () => {
      if (frame) return
      frame = window.requestAnimationFrame(() => {
        frame = 0
        sanitizeVisibleText(root)
      })
    }
    schedule()
    const observer = new MutationObserver(schedule)
    observer.observe(root, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['title', 'aria-label', 'aria-description', 'placeholder', 'alt'] })
    return () => {
      observer.disconnect()
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])
}

const emptyShellBootstrap: ShellBootstrap = { user: null, tenant: null, permissions: [], actions: {} }

function textFromRecord(record: Record<string, unknown>, key: string): string {
  return typeof record[key] === 'string' ? record[key].trim() : ''
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item || '').trim()).filter(Boolean)
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
    const tenantPayload = root.tenant && typeof root.tenant === 'object' && !Array.isArray(root.tenant)
      ? root.tenant as Record<string, unknown>
      : null
    const displayName = userPayload ? textFromRecord(userPayload, 'displayName') : ''
    const username = userPayload ? textFromRecord(userPayload, 'username') : ''
    const user = userPayload && (displayName || username)
      ? {
        id: textFromRecord(userPayload, 'id'),
        username,
        displayName: displayName || username,
        email: textFromRecord(userPayload, 'email'),
        role: textFromRecord(userPayload, 'role'),
        initials: textFromRecord(userPayload, 'initials'),
      }
      : null
    const tenantSlug = tenantPayload ? textFromRecord(tenantPayload, 'slug') : ''
    const tenantName = tenantPayload ? textFromRecord(tenantPayload, 'name') : ''
    return {
      user,
      tenant: tenantSlug || tenantName ? { slug: tenantSlug, name: tenantName } : null,
      permissions: stringList(root.permissions),
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
      { label: 'Cartelle Condivise', icon: FolderPlus, href: '/cartelle-condivise' },
      { label: 'Portale Clienti', icon: MessageCircle, href: '/app/portale-clienti', featureFlag: 'routes.appV2.clientPortal.enabled' }
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
      { label: 'Notifiche legali', icon: ShieldCheck, href: '/notifiche-legali', badge: 'L.53' },
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
      { label: 'Documenti', icon: FileText, href: '/documenti' },
      { label: 'Editor professionale', icon: FilePenLine, href: '/editor-professionale' },
      { label: 'Redazione Atti', icon: FilePenLine, href: '/redazione-atti' },
      { label: 'Statistiche', icon: ChartColumn, href: '/statistiche/' },
      { label: 'Ricerca Legale', icon: Building2, href: '/ricerca-legale' },
      { label: 'Legal Skills', icon: BookOpenCheck, href: '/legal-skills', featureFlag: 'routes.appV2.legalSkills.catalog', requiresAnyPermission: ['legal_skills.leggi'] },
      { label: 'Regia Agentica', icon: Bot, href: '/workflow-agents', featureFlag: 'routes.appV2.workflowAgents.home', requiresAnyPermission: ['ai.usa', 'legal_skills.leggi'] },
      { label: 'Archivio Giurisprudenza', icon: Landmark, href: '/giurisprudenza/' },
      { label: 'Strumenti Forensi', icon: Wrench, href: '/strumenti-legali/' },
      { label: 'Strumenti Operativi', icon: Table, href: '/strumenti-operativi' },
    ]
  },
  {
    id: 'sito-studio',
    label: 'Sito Studio',
    icon: Earth,
    items: [
      { label: 'Sito Studio', icon: Earth, href: '/sito-studio/' },
      { label: 'Builder Sito', icon: FilePenLine, href: '/sito-studio/builder' },
      { label: 'Redazione AI Sito', icon: Bot, href: '/sito-studio/redazione-ai' },
      { label: 'Contatti Sito', icon: Mail, href: '/sito-studio/contatti' },
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
      { label: 'Canali SdI', icon: Send, href: '/impostazioni/sdi' },
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
      { label: 'Importa pratiche da Studio Telematico', icon: CloudUpload, href: '/importa-pratiche-studio-telematico' },
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

function appV2NavigationActive(path: string): boolean {
  const clean = (path || '/').toLowerCase()
  return clean === '/app-v2' || clean.startsWith('/app-v2/') || clean === '/app' || clean.startsWith('/app/')
}

function hasAnyPermission(bootstrap: ShellBootstrap, permissions: string[]): boolean {
  if (!permissions.length) return true
  const available = new Set(bootstrap.permissions)
  return permissions.some((permission) => available.has(permission))
}

function requiredPermissionsForHref(href: string): string[] {
  const route = normaliseRoutePath(href).toLowerCase()
  if (route === '/' || route.startsWith('/workspace-intelligente') || route.startsWith('/regia-operativa')) return []
  if (route.startsWith('/global-search') || route.startsWith('/ricerca-studio') || route.startsWith('/cerca')) return []
  if (route.startsWith('/agenda/nuovo') || /^\/agenda\/[^/]+\/modifica$/.test(route)) return ['agenda.scrivi']
  if (route.startsWith('/agenda') || route.startsWith('/timesheet')) return ['agenda.leggi']
  if (route.startsWith('/fascicoli/nuovo')) return ['fascicoli.scrivi']
  if (route.startsWith('/fascicoli') || route.startsWith('/cartelle-condivise')) return ['fascicoli.leggi']
  if (route.startsWith('/clienti/nuovo') || route.startsWith('/soggetti/nuovo')) return ['clienti.scrivi']
  if (route.startsWith('/app/portale-clienti')) return ['clienti.leggi']
  if (route.startsWith('/clienti') || route.startsWith('/soggetti')) return ['clienti.leggi']
  if (route.startsWith('/email') || route.startsWith('/notifiche-legali') || route.startsWith('/messaggi')) return ['messaggi.leggi']
  if (route.startsWith('/scadenziario/nuova')) return ['scadenziario.scrivi']
  if (route.startsWith('/scadenziario') || route.startsWith('/wizard-pro')) return ['scadenziario.leggi']
  if (route.startsWith('/deposito/checklist')) return ['telematico.leggi', 'fascicoli.leggi']
  if (route.startsWith('/telematico') || route.startsWith('/servizi-telematici') || route.startsWith('/polisweb') || route.startsWith('/pst') || route.startsWith('/pdp') || route.startsWith('/pat') || route.startsWith('/ptt') || route.startsWith('/sigit') || route.startsWith('/tribunali') || route.startsWith('/guida/firma-digitale') || route.startsWith('/portali')) return ['telematico.leggi']
  if (route.startsWith('/fatturazione') || route.startsWith('/preventivi') || route.startsWith('/compensi-forensi') || route.startsWith('/tariffario') || route.startsWith('/incassi-pagamenti')) return ['fatturazione.leggi']
  if (route.startsWith('/documenti') || route.startsWith('/editor-professionale') || route.startsWith('/template-atti') || route.startsWith('/redazione-atti') || route.startsWith('/giurisprudenza') || route.startsWith('/legal-intelligence') || route.startsWith('/ricerca-legale')) return ['ai.usa', 'fascicoli.leggi']
  if (route.startsWith('/workflow-agents') || route.startsWith('/regia-agentica')) return ['ai.usa', 'legal_skills.leggi']
  if (route.startsWith('/legal-skills')) return ['legal_skills.leggi']
  if (route.startsWith('/sito-studio') || route.startsWith('/studio') || route.startsWith('/statistiche') || route.startsWith('/strumenti-legali') || route.startsWith('/strumenti-operativi') || route.startsWith('/applicazioni')) return ['admin.leggi', 'fascicoli.leggi']
  if (route.startsWith('/impostazioni') || route.startsWith('/notifiche') || route.startsWith('/backup') || route.startsWith('/sincronizzazione-calendari')) return ['admin.configura', 'backup.leggi']
  if (route.startsWith('/utenti/nuovo')) return ['utenti.scrivi']
  if (route.startsWith('/importa-pratiche-studio-telematico') || route.startsWith('/import/quickorganizer')) return ['admin.configura', 'fascicoli.scrivi', 'clienti.scrivi']
  if (route.startsWith('/utenti') || route.startsWith('/profili') || route.startsWith('/admin/database') || route.startsWith('/database') || route.startsWith('/amministrazione') || route.startsWith('/privacy/registro') || route.startsWith('/registro-gdpr')) return ['utenti.leggi', 'admin.leggi']
  if (route.startsWith('/audit') || route.startsWith('/registro-attivita')) return ['audit.leggi']
  return []
}

function shouldShowNavItem(item: NavItem, bootstrap: ShellBootstrap, appV2Navigation: boolean): boolean {
  if (!appV2Navigation) return true
  const flag = item.featureFlag || appV2FeatureFlagForPath(item.href)
  if (flag && !isFeatureFlagEnabledSync(flag)) return false
  const permissions = item.requiresAnyPermission || requiredPermissionsForHref(item.href)
  return hasAnyPermission(bootstrap, permissions)
}

function visibleNavItems(items: NavItem[], bootstrap: ShellBootstrap, appV2Navigation: boolean): NavItem[] {
  return items.filter((item) => shouldShowNavItem(item, bootstrap, appV2Navigation))
}

function visibleNavSections(sections: NavSection[], bootstrap: ShellBootstrap, appV2Navigation: boolean): NavSection[] {
  return sections
    .map((section) => ({ ...section, items: visibleNavItems(section.items, bootstrap, appV2Navigation) }))
    .filter((section) => section.items.length > 0)
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
  '/portali/pst/acquisizione',
  '/portali/pdp/acquisizione',
  '/portali/pat/acquisizione',
  '/portali/ptt/acquisizione',
  '/portali/sigit/acquisizione',
  '/pst',
  '/pdp',
  '/pat',
  '/ptt',
  '/sigit',
  '/tribunali',
  '/guida/firma-digitale',
]

const reactTelematicoGraphicalRoutes = new Set([
  '/guida/firma-digitale',
  '/pat',
  '/pdp',
  '/polisweb',
  '/pst',
  '/servizi-telematici',
  '/sigit',
  '/telematico',
  '/telematici',
  '/tribunali',
  '/portali/pst/acquisizione',
  '/portali/pdp/acquisizione',
  '/portali/pat/acquisizione',
  '/portali/ptt/acquisizione',
  '/portali/sigit/acquisizione',
])

function legacyOperationalRedirectHref(activePath: string): string | null {
  const raw = activePath || '/'
  const lowerRaw = raw.toLowerCase()
  if (lowerRaw !== '/app-v2' && !lowerRaw.startsWith('/app-v2/')) return null
  const route = normaliseRoutePath(raw)
  const routeLower = route.toLowerCase()
  if (reactTelematicoGraphicalRoutes.has(routeLower)) return null
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
  if (route === '/editor-professionale') {
    return {
      context: 'editor-professionale',
      title: 'Lex AI editor',
      body: 'Legge redazione, documenti, fascicoli, PEC e formati firmati per aiutarti a scrivere, controllare e cercare nello studio.',
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
  if (route === '/email' || route === '/email-ordinaria' || route === '/notifiche-legali' || route.startsWith('/messaggi')) return true
  if (route.startsWith('/scadenziario') && !isNewDeadline && !isDeadlineEdit) return true
  if (route.startsWith('/wizard-pro')) return true
  if (route === '/timesheet' || route === '/cartelle-condivise') return true
  if (route.startsWith('/privacy/registro') || route === '/registro-gdpr') return true
  if (route.startsWith('/workflow-agents') || route === '/regia-agentica') return true
  if (route.startsWith('/legal-skills')) return true
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
        <JsonPostForm action={logoutAction}>
          <input type="hidden" name="_csrf_token" value={csrfToken()}/>
          <button type="submit" aria-label="Esci" title="Esci"><LogOut size={16}/></button>
        </JsonPostForm>
      ) : null}
    </div>
  )
}

function Sidebar({ collapsed, mobileOpen, activePath, onToggle, onCloseMobile, bootstrap, appV2Navigation }:{collapsed:boolean; mobileOpen:boolean; activePath:string; onToggle:()=>void; onCloseMobile:()=>void; bootstrap:ShellBootstrap; appV2Navigation:boolean}) {
  const primaryItems = visibleNavItems(primaryNav, bootstrap, appV2Navigation)
  const sectionItems = visibleNavSections(navSections, bootstrap, appV2Navigation)
  const activeSectionId = sectionItems.find(section => section.items.some(item => isActiveHref(item.href, activePath)))?.id || null
  const [openSectionId,setOpenSectionId]=useState<string | null>(activeSectionId)
  useEffect(()=>{
    if(activeSectionId){
      setOpenSectionId(activeSectionId)
    }
  },[activeSectionId])
  const toggleSection=(id:string)=>setOpenSectionId(current=>current===id?null:id)
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
          {primaryItems.map(item=><NavLink key={item.label} item={item} collapsed={collapsed} activePath={activePath} onNavigate={onCloseMobile}/>)}
        </div>
        {sectionItems.map(section=>{
          const SectionIcon = section.icon || Folder
          const open = openSectionId === section.id
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
          <p>Preparazione della pagina operativa.</p>
        </div>
        <span className="iu-sync">Sincronizzazione...</span>
      </div>
    </main>
  )
}

function FeatureUnavailablePage() {
  return (
    <main className="iu-content" role="status">
      <div className="iu-page-heading">
        <div>
          <h1>Modulo non attivo per questo studio</h1>
          <p>L'accesso a questa area e' stato sospeso nelle impostazioni dello studio. I dati restano invariati.</p>
        </div>
        <ShieldCheck size={24}/>
      </div>
      <section className="iu-panel">
        <div className="iu-panel__title">
          <span><Settings2 size={17}/> Attivazione richiesta</span>
          <Badge tone="warning">Da attivare</Badge>
        </div>
        <p className="iu-empty">Chiedi a un profilo abilitato di attivare il modulo dalle impostazioni. Fino ad allora non vengono caricate informazioni riservate.</p>
        <div className="iu-actions">
          <a className="iu-btn primary" href="/impostazioni">Apri impostazioni</a>
          <a className="iu-btn" href="/">Torna alla panoramica</a>
        </div>
      </section>
    </main>
  )
}

function AppV2NotFoundPage() {
  return (
    <main className="iu-content" role="status">
      <div className="iu-page-heading">
        <div>
          <h1>Pagina App V2 non disponibile</h1>
          <p>Il collegamento non corrisponde a una pagina attiva dello studio. Nessun dato riservato e' stato caricato.</p>
        </div>
        <AlertTriangle size={24}/>
      </div>
      <section className="iu-panel">
        <div className="iu-panel__title">
          <span><ShieldCheck size={17}/> Percorso controllato</span>
          <Badge tone="warning">404</Badge>
        </div>
        <p className="iu-empty">Apri una voce del menu oppure torna alla panoramica operativa.</p>
        <div className="iu-actions">
          <a className="iu-btn primary" href="/">Torna alla panoramica</a>
          <a className="iu-btn" href="/global-search">Cerca nello studio</a>
        </div>
      </section>
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

function DashboardPage({
  data,
  loading,
  mailSyncing = false,
  onRefresh,
  onSyncMailboxes,
}:{
  data: DashboardData
  loading: boolean
  mailSyncing?: boolean
  onRefresh: () => void
  onSyncMailboxes: () => void
}) {
  return (
    <main className="iu-content">
      <div className="iu-page-heading">
        <div>
          <h1>Panoramica</h1>
          <p>Centro operativo dello studio</p>
        </div>
        <div className="iu-page-heading__actions">
          <span className={`iu-sync ${loading || mailSyncing?'':'ok'}`}>{loading?'Caricamento dati...':mailSyncing?'Sincronizzazione comunicazioni...':'Dati aggiornati'}</span>
          <button className="iu-button iu-button--ghost iu-button--compact" type="button" onClick={onRefresh} disabled={loading || mailSyncing}>
            <RefreshCw size={15}/> Aggiorna
          </button>
          <button className="iu-button iu-button--primary iu-button--compact" type="button" onClick={onSyncMailboxes} disabled={loading || mailSyncing}>
            <Mail size={15}/> Sincronizza comunicazioni
          </button>
        </div>
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
  useVisibleTextGuard()
  const [, refreshRoute] = useState(0)
  useEffect(() => {
    const handleRouteChange = () => refreshRoute((value) => value + 1)
    window.addEventListener('popstate', handleRouteChange)
    return () => window.removeEventListener('popstate', handleRouteChange)
  }, [])
  const activePath = window.location.pathname.replace(/\/+$/, '') || '/'
  const routePath = normaliseRoutePath(activePath)
  const routeKey = routePath.toLowerCase()
  const appV2FlagProtectedPath = appV2NavigationActive(activePath)
  const appV2RequiredFlag = appV2FlagProtectedPath ? appV2FeatureFlagForPath(routeKey) : null
  const appV2UnknownRoute = appV2FlagProtectedPath && !appV2RequiredFlag
  const appV2FlagDenied = appV2RequiredFlag ? !isFeatureFlagEnabledSync(appV2RequiredFlag) : false
  const forcedLegacyHref = legacyOperationalRedirectHref(activePath)
  if (forcedLegacyHref) {
    window.location.replace(forcedLegacyHref)
    return <PageLoading/>
  }
  const isClientPortalPublicPage = routeKey === '/portale-cliente' || routeKey.startsWith('/portale-cliente/')
  if (isClientPortalPublicPage) {
    return (
      <AppErrorBoundary>
        <Suspense fallback={<PageLoading/>}>
          <ClientPortalPage mode="client"/>
        </Suspense>
      </AppErrorBoundary>
    )
  }
  const isSearchPage = routeKey === '/global-search' || routeKey === '/ricerca-studio' || routeKey === '/cerca'
  const isNewAppointmentPage = routeKey === '/agenda/nuovo' || routeKey.startsWith('/agenda/nuovo/')
  const isAppointmentEditPage = /^\/agenda\/[^/]+\/modifica$/.test(routeKey)
  const isAgendaImportPage = routeKey === '/agenda/importa'
  const isAgendaPage = !isNewAppointmentPage && !isAppointmentEditPage && !isAgendaImportPage && (routeKey === '/agenda' || routeKey.startsWith('/agenda/'))
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
  const isNotificheLegaliPage = routeKey === '/notifiche-legali'
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
  const isQuickOrganizerImportPage = routeKey === '/importa-pratiche-studio-telematico' || routeKey === '/import/quickorganizer'
  const isStatistichePage = routeKey === '/statistiche'
  const isImpostazioniPage = routeKey === '/impostazioni' || routeKey === '/impostazioni-studio' || routeKey === '/impostazioni/sdi' || routeKey === '/impostazioni/canali-sdi' || routeKey === '/impostazioni/pagamenti' || routeKey === '/notifiche' || routeKey === '/notifiche-whatsapp' || routeKey === '/backup' || routeKey === '/impostazioni/calendario' || routeKey === '/sincronizzazione-calendari'
  const isAuditPage = routeKey === '/audit'
  const isRegistroAttivitaPage = routeKey === '/registro-attivita'
  const isUtentiPage = routeKey === '/utenti' || routeKey === '/utenti/nuovo'
  const isProfiliPage = routeKey === '/profili'
  const isProfiloPage = routeKey === '/profilo'
  const isBackupPage = routeKey === '/backup'
  const isSitoStudioBuilderPage = routeKey === '/sito-studio/builder'
  const isFascicoloDetailViewPage = /^\/fascicoli\/(?!nuovo$|archivio$|importa$)[^/]+$/.test(routeKey)
  const isPresetExcludedPage = isSitoStudioBuilderPage || isFascicoloDetailViewPage
  const isSitoStudioRedazioneAiPage = routeKey === '/sito-studio/redazione-ai'
  const isSitoStudioArticleEditPage = /^\/sito-studio\/articoli\/\d+\/modifica$/.test(routeKey)
  const isSitoStudioPage = routeKey === '/sito-studio' || routeKey === '/sito-studio/contatti' || isSitoStudioArticleEditPage
  const isStudioPage = routeKey === '/studio'
  const isEditorProfessionalePage = routeKey === '/editor-professionale'
  const isAmministrazionePage = routeKey === '/amministrazione'
  const isFatturazionePage = routeKey === '/fatturazione' || routeKey === '/fatturazione/nuova'
  const isIncassiPagamentiPage = routeKey === '/incassi-pagamenti'
  const isPreventivoWizardPage = routeKey === '/preventivi/wizard'
  const isPreventiviPage =
    routeKey === '/preventivi' ||
    routeKey === '/preventivi/nuovo' ||
    routeKey === '/preventivi/conferimento/nuovo' ||
    /^\/preventivi\/conferimento\/[^/]+$/.test(routeKey)
  const isCompensiForensiPage = routeKey === '/compensi-forensi'
  const isTariffarioPage = routeKey === '/tariffario'
  const isTemplateAttiPage =
    routeKey === '/template-atti' ||
    routeKey.startsWith('/template-atti/')
  const isRedazioneAttiPage = routeKey === '/redazione-atti' || routeKey.startsWith('/redazione-atti/')
  const isGiurisprudenzaPage = routeKey === '/giurisprudenza' || routeKey.startsWith('/giurisprudenza/')
  const isLegalIntelligencePage =
    routeKey === '/ricerca-legale' ||
    routeKey.startsWith('/ricerca-legale/') ||
    // alias storico: i path /legal-intelligence/* vengono ridiretti 301 a /ricerca-legale/*
    // dal hook server-side, ma manteniamo il riconoscimento client lato App.tsx
    // per gestire eventuali bookmark vecchi durante il TTL del browser.
    routeKey === '/legal-intelligence' ||
    routeKey.startsWith('/legal-intelligence/')
  const isLegalSkillsCatalogPage = routeKey === '/legal-skills' || routeKey === '/app/legal-skills' || /^\/legal-skills\/packs\/[^/]+\/skills$/.test(routeKey)
  const isLegalSkillsProfilePage = routeKey === '/legal-skills/profile'
  const isColdStartInterviewPage = routeKey === '/legal-skills/profile/cold-start'
  const isLegalSkillsRunPage = routeKey === '/legal-skills/run' || /^\/legal-skills\/packs\/[^/]+\/skills\/[^/]+\/run$/.test(routeKey)
  const isLegalSkillsReviewQueuePage = routeKey === '/legal-skills/review' || routeKey === '/legal-skills/review-queue'
  const isLegalSkillsRunDetailPage = /^\/legal-skills\/runs\/[^/]+$/.test(routeKey)
  const isLegalSkillsReviewPage = isLegalSkillsReviewQueuePage || isLegalSkillsRunDetailPage
  const isLegalSkillsPage = isLegalSkillsCatalogPage || isLegalSkillsProfilePage || isColdStartInterviewPage || isLegalSkillsRunPage || isLegalSkillsReviewPage
  const isWorkflowAgentsHomePage = routeKey === '/workflow-agents' || routeKey === '/regia-agentica'
  const isWorkflowAgentsApprovalPage = routeKey === '/workflow-agents/approvals'
  const isWorkflowAgentsRunPage = /^\/workflow-agents\/runs\/[^/]+$/.test(routeKey)
  const isWorkflowAgentsPage = isWorkflowAgentsHomePage || isWorkflowAgentsApprovalPage || isWorkflowAgentsRunPage
  const isClientPortalStudioPage = routeKey === '/app/portale-clienti' || routeKey === '/app/portale-clienti/impostazioni'
  const isStudioModulePage = !isClientPortalStudioPage && !isStudioPage && !isEditorProfessionalePage && !isAmministrazionePage && !isFatturazionePage && !isIncassiPagamentiPage && !isPreventivoWizardPage && !isPreventiviPage && !isCompensiForensiPage && !isTariffarioPage && !isTemplateAttiPage && !isRedazioneAttiPage && !isGiurisprudenzaPage && !isLegalIntelligencePage && !isLegalSkillsPage && !isWorkflowAgentsPage && !isAdminDatabasePage && !isQuickOrganizerImportPage && !isStatistichePage && !isImpostazioniPage && !isAuditPage && !isRegistroAttivitaPage && !isUtentiPage && !isProfiliPage && !isBackupPage && !isSitoStudioBuilderPage && !isSitoStudioRedazioneAiPage && !isSitoStudioPage && !isTimesheetPage && !isCartelleCondivisePage && !isWizardProPage && isStudioModuleRoute(routeKey)
  const isDashboardPage = !isClientPortalStudioPage && !isSearchPage && !isAgendaImportPage && !isAgendaPage && !isNewAppointmentPage && !isAppointmentEditPage && !isRegiaPage && !isDocumentEditorPage && !isFascicoliPage && !isClientiPage && !isClientFolderPage && !isClientEditPage && !isNewClientPage && !isSoggettiPage && !isNewSubjectPage && !isSubjectEditPage && !isEmailComposePage && !isEmailOrdinariaComposePage && !isNotificheLegaliPage && !isEmailPage && !isEmailOrdinariaPage && !isMessagesPage && !isNewMessagePage && !isScadenziarioPage && !isNewDeadlinePage && !isDeadlineEditPage && !isTimesheetPage && !isCartelleCondivisePage && !isWizardProPage && !isTelematicoPage && !isTelematicoSurfacePage && !isPrivacyRegistroPage && !isAdminDatabasePage && !isQuickOrganizerImportPage && !isStatistichePage && !isImpostazioniPage && !isAuditPage && !isRegistroAttivitaPage && !isUtentiPage && !isProfiliPage && !isProfiloPage && !isBackupPage && !isSitoStudioBuilderPage && !isSitoStudioRedazioneAiPage && !isSitoStudioPage && !isStudioPage && !isEditorProfessionalePage && !isAmministrazionePage && !isFatturazionePage && !isIncassiPagamentiPage && !isPreventivoWizardPage && !isPreventiviPage && !isCompensiForensiPage && !isTariffarioPage && !isTemplateAttiPage && !isRedazioneAttiPage && !isGiurisprudenzaPage && !isLegalIntelligencePage && !isLegalSkillsPage && !isWorkflowAgentsPage && !isStudioModulePage
  const isStandalonePage = isClientPortalStudioPage || isSearchPage || isAgendaImportPage || isAgendaPage || isNewAppointmentPage || isAppointmentEditPage || isDocumentEditorPage || isFascicoliPage || isClientiPage || isClientFolderPage || isClientEditPage || isNewClientPage || isSoggettiPage || isNewSubjectPage || isSubjectEditPage || isEmailComposePage || isEmailOrdinariaComposePage || isNotificheLegaliPage || isEmailPage || isEmailOrdinariaPage || isMessagesPage || isNewMessagePage || isScadenziarioPage || isNewDeadlinePage || isDeadlineEditPage || isTimesheetPage || isCartelleCondivisePage || isWizardProPage || isTelematicoPage || isTelematicoSurfacePage || isPrivacyRegistroPage || isAdminDatabasePage || isQuickOrganizerImportPage || isStatistichePage || isImpostazioniPage || isAuditPage || isRegistroAttivitaPage || isUtentiPage || isProfiliPage || isProfiloPage || isBackupPage || isSitoStudioBuilderPage || isSitoStudioRedazioneAiPage || isSitoStudioPage || isStudioPage || isEditorProfessionalePage || isAmministrazionePage || isFatturazionePage || isIncassiPagamentiPage || isPreventivoWizardPage || isPreventiviPage || isCompensiForensiPage || isTariffarioPage || isTemplateAttiPage || isRedazioneAttiPage || isGiurisprudenzaPage || isLegalIntelligencePage || isLegalSkillsPage || isWorkflowAgentsPage || isStudioModulePage
  const effectiveStandalonePage = isStandalonePage || appV2FlagDenied || appV2UnknownRoute
  const initialSearchQuery = new URLSearchParams(window.location.search).get('q') ?? ''
  const lexConfig = resolveLexPageContext(routeKey)
  const needsShellLexContext = !routePublishesLexContext(routeKey)
  const shellBootstrap = readShellBootstrap()
  const [data,setData]=useState<DashboardData>(emptyDashboard)
  const [loading,setLoading]=useState(!effectiveStandalonePage)
  const [mailSyncing,setMailSyncing]=useState(false)
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false)
  const [guidePanelExpanded,setGuidePanelExpanded]=useState(false)
  const [mobileMenuOpen,setMobileMenuOpen]=useState(false)
  const [mobileNavCollapsed,setMobileNavCollapsed]=useState(false)
  useEffect(()=>{
    const onGuidePanel = (event: Event) => {
      const detail = (event as CustomEvent<{ expanded?: boolean }>).detail
      setGuidePanelExpanded(Boolean(detail?.expanded))
    }
    window.addEventListener('iusentra:guida-pratica-panel', onGuidePanel)
    return()=>window.removeEventListener('iusentra:guida-pratica-panel', onGuidePanel)
  },[])
  useEffect(()=>{
    if(!isFascicoliPage){
      setGuidePanelExpanded(false)
      return
    }
    if(guidePanelExpanded){
      setSidebarCollapsed(true)
    } else {
      setSidebarCollapsed(false)
    }
  },[guidePanelExpanded,isFascicoliPage])
  const refreshDashboard = (refresh = false) => {
    setLoading(true)
    getDashboard({ refresh })
      .then(setData)
      .finally(() => setLoading(false))
  }
  const syncMailboxesNow = () => {
    setMailSyncing(true)
    syncDashboardMailboxes()
      .then(() => getDashboard({refresh:true}))
      .then(setData)
      .finally(() => setMailSyncing(false))
  }
  useEffect(()=>{
    if(effectiveStandalonePage){
      setLoading(false)
      return
    }
    let ok=true
    setLoading(true)
    getDashboard()
      .then(d=>{ if(ok)setData(d) })
      .finally(()=>{if(ok)setLoading(false)})
    return()=>{ok=false}
  },[effectiveStandalonePage])
  const openMobileLex = () => {
    const detail = {
      ...lexConfig,
      context: lexConfig.context || 'mobile',
      title: lexConfig.title || 'Lex AI mobile',
      body: lexConfig.body || 'Posso aiutarti da telefono o tablet con fascicoli, scadenze, posta, ricerca legale e prossima azione operativa.',
      pagePath: window.location.pathname,
      mobileFullscreen: true,
    }
    window.dispatchEvent(new CustomEvent('iusentra:lex-context', { detail }))
    window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex', { detail }))
  }
  return (
    <AppErrorBoundary>
      <div className={`iu-shell ${sidebarCollapsed?'iu-shell--collapsed':''} ${guidePanelExpanded && isFascicoliPage?'iu-shell--guide-open':''} ${isPresetExcludedPage?'iusentra-preset-excluded':'iusentra-preset-active'}`} data-iusentra-preset-root={isPresetExcludedPage?'excluded':'active'}>
        <Sidebar collapsed={sidebarCollapsed} mobileOpen={mobileMenuOpen} activePath={activePath} onToggle={()=>setSidebarCollapsed(v=>!v)} onCloseMobile={()=>setMobileMenuOpen(false)} bootstrap={shellBootstrap} appV2Navigation={appV2FlagProtectedPath}/>
        {mobileMenuOpen?<button className="iu-sidebar-scrim" type="button" aria-label="Chiudi menu" onClick={()=>setMobileMenuOpen(false)}/>:null}
        <div className="iu-main">
          <TopBar onOpenMenu={()=>setMobileMenuOpen(true)} activePath={routeKey} supportEnabled={Boolean(shellBootstrap.user)} bootstrap={shellBootstrap}/>
          <Suspense fallback={<PageLoading/>}>
            <IusentraRoutePresetFrame routeKey={routeKey} enabled={!isPresetExcludedPage} key={routeKey}>
              {appV2UnknownRoute?<AppV2NotFoundPage/>:appV2FlagDenied?<FeatureUnavailablePage/>:isClientPortalStudioPage?<ClientPortalPage mode="studio"/>:isSearchPage?<RicercaStudioPage initialQuery={initialSearchQuery}/>:isAgendaImportPage?<AgendaImportPage/>:isNewAppointmentPage||isAppointmentEditPage?<NuovoAppuntamentoPage/>:isAgendaPage?<AgendaPage/>:isRegiaPage?<RegiaOperativaPage data={data} loading={loading}/>:isDocumentEditorPage?<DocumentEditorPage/>:isFascicoliPage?<FascicoliPage/>:isNewClientPage||isNewSubjectPage||isClientEditPage||isSubjectEditPage?<NuovoClientePage/>:isClientFolderPage?<CartellaClientePage/>:isClientiPage?<AnagraficaClientiPage/>:isSoggettiPage?<SoggettiPage/>:isNotificheLegaliPage?<NotificheLegaliPage/>:isEmailOrdinariaComposePage?<EmailComposePage mode="ordinaria"/>:isEmailComposePage?<EmailComposePage mode="pec"/>:isEmailOrdinariaPage?<EmailOrdinariaPage/>:isEmailPage?<EmailPecPage/>:isNewMessagePage?<NuovoMessaggioPage/>:isMessagesPage?<MessaggiPage/>:isNewDeadlinePage||isDeadlineEditPage?<NuovaScadenzaPage/>:isScadenziarioPage?<ScadenziarioPage/>:isTimesheetPage?<TimesheetPage/>:isCartelleCondivisePage?<CartelleCondivisePage/>:isWizardProStep?<WizardProStepPage/>:isWizardProComplete?<WizardProCompletePage/>:isWizardProDashboard?<WizardProPage/>:isTelematicoPage?<TelematicoPage/>:isTelematicoSurfacePage?<TelematicoSurfacePage/>:isPrivacyRegistroPage?<PrivacyRegistroPage/>:isAdminDatabasePage?<AdminDatabasePage/>:isQuickOrganizerImportPage?<QuickOrganizerImportPage/>:isStatistichePage?<StatistichePage/>:isImpostazioniPage?<ImpostazioniPage/>:isAuditPage||isRegistroAttivitaPage?<AuditPage/>:isUtentiPage?<UtentiPage/>:isProfiliPage?<ProfiliPage/>:isProfiloPage?<ProfiloPage/>:isBackupPage?<BackupPage/>:isSitoStudioRedazioneAiPage?<SitoStudioRedazioneAiPage/>:isSitoStudioBuilderPage?<SitoStudioBuilderPage/>:isSitoStudioPage?<SitoStudioPage/>:isStudioPage?<StudioPage/>:isEditorProfessionalePage?<EditorProfessionalePage/>:isAmministrazionePage?<AmministrazionePage/>:isFatturazionePage?<FatturazionePage/>:isIncassiPagamentiPage?<IncassiPagamentiPage/>:isPreventivoWizardPage?<PreventivoWizardPage/>:isPreventiviPage?<PreventiviPage/>:isCompensiForensiPage?<CompensiForensiPage/>:isTariffarioPage?<TariffarioPage/>:isTemplateAttiPage?<TemplateAttiPage/>:isRedazioneAttiPage?<RedazioneAttiPage/>:isGiurisprudenzaPage?<GiurisprudenzaPage/>:isLegalIntelligencePage?<LegalIntelligencePage/>:isWorkflowAgentsRunPage?<AgentRunDetail/>:isWorkflowAgentsApprovalPage?<AgentApprovalQueue/>:isWorkflowAgentsHomePage?<WorkflowAgentsHome/>:isColdStartInterviewPage?<ColdStartInterviewPage/>:isLegalSkillsProfilePage?<PracticeProfilePage/>:isLegalSkillsRunPage?<LegalSkillRunPage/>:isLegalSkillsRunDetailPage?<SkillRunDetailPage/>:isLegalSkillsReviewQueuePage?<ReviewerQueuePage/>:isLegalSkillsCatalogPage?<LegalSkillsCatalogPage/>:isStudioModulePage?<StudioModulePage/>:<DashboardPage data={data} loading={loading} mailSyncing={mailSyncing} onRefresh={()=>refreshDashboard(true)} onSyncMailboxes={syncMailboxesNow}/>}
            </IusentraRoutePresetFrame>
          </Suspense>
        </div>
        <nav className={`iu-mobile ${mobileNavCollapsed?'is-collapsed':''}`} aria-label="Navigazione mobile">
          <div id="iu-mobile-links" className="iu-mobile__rail" hidden={mobileNavCollapsed}>
            <a className={isDashboardPage?'active':''} href="/"><LayoutDashboard size={18}/>Panoramica</a>
            <a className={isSearchPage?'active':''} href="/global-search"><Search size={18}/>Ricerca</a>
            <button type="button" className="iu-mobile__lex" onClick={openMobileLex} aria-label="Apri Lex AI"><Bot size={18}/>Lex AI</button>
            <a className={isFascicoliPage?'active':''} href="/fascicoli"><BriefcaseBusiness size={18}/>Fascicoli</a>
            <a className={isClientiPage||isClientFolderPage||isClientEditPage||isNewClientPage||isCartelleCondivisePage||isSoggettiPage||isNewSubjectPage||isSubjectEditPage?'active':''} href="/clienti"><UsersRound size={18}/>Clienti</a>
            <a className={isEmailPage||isEmailOrdinariaPage||isNotificheLegaliPage||isMessagesPage||isNewMessagePage?'active':''} href="/email/"><Mail size={18}/>Posta</a>
            <a className={isAgendaImportPage||isAgendaPage||isNewAppointmentPage||isAppointmentEditPage||isTimesheetPage||isScadenziarioPage||isNewDeadlinePage||isDeadlineEditPage||isWizardProPage?'active':''} href="/agenda"><CalendarDays size={18}/>Agenda</a>
            <a className={isRegiaPage||isPrivacyRegistroPage||isAdminDatabasePage||isQuickOrganizerImportPage?'active':''} href="/workspace-intelligente"><Sparkles size={18}/>Regia</a>
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
