import type { LucideIcon } from 'lucide-react'
import {
  AlertTriangle,
  Bell,
  Bot,
  BriefcaseBusiness,
  Calculator,
  CalendarDays,
  CheckCircle2,
  Clock,
  Contact,
  Euro,
  FileSignature,
  FileText,
  Files,
  Fingerprint,
  FolderOpen,
  Gavel,
  Info,
  Landmark,
  LockKeyhole,
  MessageCircle,
  ReceiptText,
  Scale,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UserRound,
  UsersRound,
} from 'lucide-react'

export type IusLegalArea =
  | 'agenda'
  | 'alert'
  | 'clienti'
  | 'conformita'
  | 'documenti'
  | 'fascicoli'
  | 'lex'
  | 'privacy'
  | 'ricerca'
  | 'sicurezza'
  | 'soggetti'
  | 'tariffario'
  | 'telematico'

export type IusTone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'gold' | 'info'

export const iusLegalIcons: Record<IusLegalArea, LucideIcon> = {
  agenda: CalendarDays,
  alert: AlertTriangle,
  clienti: UserRound,
  conformita: CheckCircle2,
  documenti: FileText,
  fascicoli: FolderOpen,
  lex: Bot,
  privacy: Fingerprint,
  ricerca: Search,
  sicurezza: ShieldCheck,
  soggetti: UsersRound,
  tariffario: Calculator,
  telematico: Landmark,
}

export const iusIconCatalog = {
  agenda: { CalendarDays, Clock, Bell },
  alert: { AlertTriangle, CheckCircle2, Info },
  clienti: { UserRound, UsersRound, Contact },
  documenti: { FileText, Files, FileSignature },
  fascicoli: { FolderOpen, FileText, BriefcaseBusiness },
  lex: { Bot, Sparkles, MessageCircle },
  privacy: { LockKeyhole, ShieldCheck, Fingerprint },
  ricerca: { Search },
  tariffario: { Calculator, ReceiptText, Euro },
  telematico: { Landmark, Send, UploadCloud, ShieldCheck, Gavel, Scale },
} as const

export const iusToneClass: Record<IusTone, string> = {
  neutral: 'ius-tone-neutral',
  primary: 'ius-tone-primary',
  success: 'ius-tone-success',
  warning: 'ius-tone-warning',
  danger: 'ius-tone-danger',
  gold: 'ius-tone-gold',
  info: 'ius-tone-info',
}
