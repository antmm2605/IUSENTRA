import type { LucideIcon } from 'lucide-react'
import { Scale } from 'lucide-react'
import { iusIconCatalog as sharedIconCatalog, iusIcons } from './icons'

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
  agenda: iusIcons.agenda,
  alert: iusIcons.alert,
  clienti: iusIcons.clienti,
  conformita: iusIcons.conformita,
  documenti: iusIcons.documenti,
  fascicoli: iusIcons.fascicoli,
  lex: iusIcons.lex,
  privacy: iusIcons.privacy,
  ricerca: iusIcons.ricerca,
  sicurezza: iusIcons.sicurezza,
  soggetti: iusIcons.soggetti,
  tariffario: iusIcons.tariffario,
  telematico: iusIcons.telematico,
}

export const iusIconCatalog = {
  ...sharedIconCatalog,
  telematico: { ...sharedIconCatalog.telematico, Scale },
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
