import type { LucideIcon } from 'lucide-react'
import {
  BookOpen,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  FileText,
  FolderOpen,
  Landmark,
  Mail,
  Settings2,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from 'lucide-react'

export type AppRouteFamily =
  | 'regia'
  | 'fascicoli'
  | 'anagrafiche'
  | 'agenda'
  | 'mandato'
  | 'documenti'
  | 'telematico'
  | 'comunicazioni'
  | 'lex'
  | 'amministrazione'
  | 'impostazioni'

export type AppRouteDefinition = {
  path: string
  label: string
  family: AppRouteFamily
  icon: LucideIcon
  api?: string
}

export const APP_ROUTES: AppRouteDefinition[] = [
  { path: '/app', label: 'Regia', family: 'regia', icon: Sparkles, api: '/api/v1/ui/dashboard' },
  { path: '/app/regia', label: 'Regia', family: 'regia', icon: Sparkles, api: '/api/v1/ui/dashboard' },
  { path: '/app/fascicoli', label: 'Fascicoli', family: 'fascicoli', icon: FolderOpen, api: '/api/v1/ui/fascicoli' },
  { path: '/app/fascicoli/:id', label: 'Dettaglio fascicolo', family: 'fascicoli', icon: FolderOpen, api: '/api/v1/ui/fascicoli/:id' },
  { path: '/app/anagrafiche', label: 'Clienti', family: 'anagrafiche', icon: UsersRound, api: '/api/v1/ui/clienti' },
  { path: '/app/agenda', label: 'Agenda', family: 'agenda', icon: CalendarDays, api: '/api/v1/ui/agenda' },
  { path: '/app/mandato', label: 'Mandato', family: 'mandato', icon: BriefcaseBusiness, api: '/api/v1/ui/preventivi' },
  { path: '/app/documenti', label: 'Documenti', family: 'documenti', icon: FileText, api: '/api/v1/ui/template-atti' },
  { path: '/app/telematico', label: 'Telematico', family: 'telematico', icon: Landmark, api: '/api/v1/ui/telematico' },
  { path: '/app/comunicazioni', label: 'Comunicazioni', family: 'comunicazioni', icon: Mail, api: '/api/v1/ui/messaggi' },
  { path: '/app/lex', label: 'Lex', family: 'lex', icon: BookOpen, api: '/api/v1/ui/legal-intelligence' },
  { path: '/app/amministrazione', label: 'Amministrazione', family: 'amministrazione', icon: ShieldCheck, api: '/api/v1/ui/amministrazione' },
  { path: '/app/impostazioni', label: 'Impostazioni', family: 'impostazioni', icon: Settings2 },
]

export const MAIN_NAV_ROUTES = APP_ROUTES.filter((route) => !route.path.includes('/:id') && route.path !== '/app')

export const LEGACY_ROUTE_TARGETS: Record<string, string> = {
  '/workspace-intelligente': '/app/regia',
  '/regia-operativa': '/app/regia',
  '/fascicoli': '/app/fascicoli',
  '/fascicoli/nuovo': '/app/fascicoli?drawer=nuovo',
  '/agenda': '/app/agenda',
  '/agenda/nuovo': '/app/agenda?drawer=evento',
  '/scadenziario': '/app/agenda?tab=scadenze',
  '/preventivi': '/app/mandato?tab=preventivi',
  '/preventivi/nuovo': '/app/mandato?tab=nuovo-preventivo',
  '/preventivi/wizard': '/app/mandato?tab=wizard',
  '/tariffario': '/app/mandato?tab=tariffario',
  '/compensi-forensi': '/app/mandato?tab=compensi',
  '/fatturazione': '/app/mandato?tab=fatturazione',
  '/incassi-pagamenti': '/app/mandato?tab=incassi',
  '/clienti': '/app/anagrafiche?tab=clienti',
  '/soggetti': '/app/anagrafiche?tab=soggetti',
  '/template-atti': '/app/documenti?tab=template',
  '/redazione-atti': '/app/documenti?tab=redazione',
  '/telematico': '/app/telematico',
  '/messaggi': '/app/comunicazioni?tab=messaggi',
  '/email': '/app/comunicazioni?tab=email',
  '/utenti': '/app/amministrazione?tab=utenti',
  '/profili': '/app/amministrazione?tab=profili',
  '/backup': '/app/impostazioni?tab=backup',
  '/sincronizzazione-calendari': '/app/impostazioni?tab=calendari',
  '/impostazioni/calendario': '/app/impostazioni?tab=calendari',
  '/audit': '/app/amministrazione?tab=audit',
  '/registro-attivita': '/app/amministrazione?tab=registro',
  '/impostazioni': '/app/impostazioni',
  '/impostazioni-studio': '/app/impostazioni',
}

export const APP_ROUTE_ICONS = {
  Building2,
}
