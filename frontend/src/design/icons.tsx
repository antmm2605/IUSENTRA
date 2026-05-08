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
  FileSpreadsheet,
  FileSignature,
  FileText,
  Files,
  Fingerprint,
  FolderOpen,
  Gavel,
  Info,
  Landmark,
  LayoutDashboard,
  LockKeyhole,
  MailCheck,
  MessageCircle,
  MessageSquare,
  ReceiptText,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Timer,
  UploadCloud,
  UserRound,
  UsersRound,
  XCircle,
} from 'lucide-react'

export type IusIconKey =
  | 'regia'
  | 'fascicoli'
  | 'fascicoloQuadro'
  | 'clienti'
  | 'soggetti'
  | 'agenda'
  | 'scadenziario'
  | 'documenti'
  | 'files'
  | 'telematico'
  | 'deposito'
  | 'upload'
  | 'conformita'
  | 'emailPec'
  | 'messaggi'
  | 'tariffario'
  | 'preventivi'
  | 'timesheet'
  | 'fatture'
  | 'sicurezza'
  | 'privacy'
  | 'lex'
  | 'sparkles'
  | 'ricerca'
  | 'alert'
  | 'info'
  | 'success'
  | 'danger'
  | 'gavel'

export const iusIcons: Record<IusIconKey, LucideIcon> = {
  regia: LayoutDashboard,
  fascicoli: FolderOpen,
  fascicoloQuadro: BriefcaseBusiness,
  clienti: UserRound,
  soggetti: UsersRound,
  agenda: CalendarDays,
  scadenziario: Clock,
  documenti: FileText,
  files: Files,
  telematico: Landmark,
  deposito: Send,
  upload: UploadCloud,
  conformita: ShieldCheck,
  emailPec: MailCheck,
  messaggi: MessageSquare,
  tariffario: Calculator,
  preventivi: ReceiptText,
  timesheet: Timer,
  fatture: FileSpreadsheet,
  sicurezza: ShieldCheck,
  privacy: Fingerprint,
  lex: Bot,
  sparkles: Sparkles,
  ricerca: Search,
  alert: AlertTriangle,
  info: Info,
  success: CheckCircle2,
  danger: XCircle,
  gavel: Gavel,
}

export const iusIconCatalog = {
  regia: { LayoutDashboard },
  fascicoli: { FolderOpen, FileText, BriefcaseBusiness },
  clienti: { UserRound, UsersRound, Contact },
  agenda: { CalendarDays, Clock, Bell },
  documenti: { FileText, Files, FileSignature },
  telematico: { Landmark, Send, UploadCloud, ShieldCheck, Gavel },
  comunicazioni: { MailCheck, MessageSquare, MessageCircle },
  tariffario: { Calculator, ReceiptText, Euro },
  sicurezza: { ShieldCheck, LockKeyhole, Fingerprint },
  lex: { Bot, Sparkles, MessageCircle },
  ricerca: { Search },
  alert: { AlertTriangle, Info, CheckCircle2, XCircle },
} as const
