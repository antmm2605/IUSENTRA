import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import { AlertTriangle, CheckCircle2, Filter, Search, X } from 'lucide-react'
import {
  IusActionCard,
  IusEmptyState,
  IusSectionHeader,
  IusStatusBadge,
} from '@/components/iusentra'
import { Badge, type BadgeTone } from './Badge'
import { Button, ButtonLink, type ButtonTone } from './Button'
import './ui.css'

export type CommonProps = {
  children?: ReactNode
  className?: string
}

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

export function Card({ children, className = '' }: CommonProps) {
  return <article className={cx('iu-card', className)}>{children}</article>
}

export function ActionCard({
  title,
  description,
  actionLabel,
  href,
  tone = 'primary',
  children,
}: {
  title: string
  description?: string
  actionLabel: string
  href: string
  tone?: ButtonTone
  children?: ReactNode
}) {
  return (
    <IusActionCard
      title={title}
      description={description}
      actionLabel={actionLabel}
      href={href}
      tone={tone === 'neutral' ? 'neutral' : tone === 'danger' ? 'danger' : tone === 'warning' ? 'warning' : tone === 'success' ? 'success' : 'primary'}
    >
      {children}
    </IusActionCard>
  )
}

export function CompactCard({ title, meta, children, actions }: {
  title: string
  meta?: string
  children?: ReactNode
  actions?: ReactNode
}) {
  return (
    <article className="iu-compact-card">
      <div>
        <h3>{title}</h3>
        {meta ? <p>{meta}</p> : null}
        {children}
      </div>
      {actions ? <div className="iu-compact-card__actions">{actions}</div> : null}
    </article>
  )
}

export function IconButton({
  label,
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button className={cx('iu-icon-button', className)} aria-label={label} title={label} {...props}>
      {children}
    </button>
  )
}

export function Workspace({ children, className = '' }: CommonProps) {
  return <section className={cx('iu-workspace', className)}>{children}</section>
}

export function WorkspaceHeader({ title, description, actions }: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <IusSectionHeader title={title} description={description} actions={actions} level={1} />
  )
}

export function WorkspaceGrid({ children, columns = 3 }: CommonProps & { columns?: 2 | 3 | 4 }) {
  return <div className={`iu-workspace-grid iu-workspace-grid--${columns}`}>{children}</div>
}

export function ResponsiveGrid({ children, columns = 3 }: CommonProps & { columns?: 2 | 3 | 4 }) {
  return <WorkspaceGrid columns={columns}>{children}</WorkspaceGrid>
}

export function SplitLayout({ left, children, right }: { left?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="iu-split-layout">
      {left ? <aside>{left}</aside> : null}
      <section>{children}</section>
      {right ? <aside>{right}</aside> : null}
    </div>
  )
}

export function SplitView({ left, children, right }: { left?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return <SplitLayout left={left} right={right}>{children}</SplitLayout>
}

export function ThreeColumnLayout({ left, center, right }: { left: ReactNode; center: ReactNode; right: ReactNode }) {
  return <SplitLayout left={left} right={right}>{center}</SplitLayout>
}

export function FourColumnLayout({ first, second, third, fourth }: {
  first: ReactNode
  second: ReactNode
  third: ReactNode
  fourth: ReactNode
}) {
  return (
    <div className="iu-four-column-layout">
      <aside>{first}</aside>
      <section>{second}</section>
      <section>{third}</section>
      <aside>{fourth}</aside>
    </div>
  )
}

export function Drawer({ title, open, children, onClose }: {
  title: string
  open: boolean
  children: ReactNode
  onClose: () => void
}) {
  if (!open) return null
  return (
    <div className="iu-drawer" role="dialog" aria-modal="true" aria-labelledby="iu-drawer-title">
      <div className="iu-drawer__panel">
        <header>
          <h2 id="iu-drawer-title">{title}</h2>
          <IconButton label="Chiudi" onClick={onClose}><X size={18} /></IconButton>
        </header>
        <div>{children}</div>
      </div>
    </div>
  )
}

export function Modal({ title, open, children, onClose }: {
  title: string
  open: boolean
  children: ReactNode
  onClose: () => void
}) {
  if (!open) return null
  return (
    <div className="iu-modal" role="dialog" aria-modal="true" aria-labelledby="iu-modal-title">
      <section className="iu-modal__panel">
        <header>
          <h2 id="iu-modal-title">{title}</h2>
          <IconButton label="Chiudi" onClick={onClose}><X size={18} /></IconButton>
        </header>
        {children}
      </section>
    </div>
  )
}

export function Accordion({ title, children, defaultOpen = false }: {
  title: string
  children: ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details className="iu-accordion" open={defaultOpen}>
      <summary>{title}</summary>
      <div>{children}</div>
    </details>
  )
}

export function SearchInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="iu-search-input">
      <Search size={16} aria-hidden="true" />
      <input type="search" {...props} />
    </label>
  )
}

export function Select({ label, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <label className="iu-field">
      <span>{label}</span>
      <select {...props} />
    </label>
  )
}

export function TextField({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="iu-field">
      <span>{label}</span>
      <input {...props} />
    </label>
  )
}

export function DateField(props: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <TextField type="date" {...props} />
}

export function TextArea({ label, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return (
    <label className="iu-field">
      <span>{label}</span>
      <textarea {...props} />
    </label>
  )
}

export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: BadgeTone }) {
  return <IusStatusBadge tone={tone === 'info' ? 'info' : tone}>{children}</IusStatusBadge>
}

export function LegalStatusBadge({ status }: { status: string }) {
  const tone: BadgeTone = /scad|errore|rifiut/i.test(status)
    ? 'danger'
    : /attesa|verifica|bozza/i.test(status)
      ? 'warning'
      : /chius|pagat|accett/i.test(status)
        ? 'success'
        : 'neutral'
  return <StatusBadge tone={tone}>{status}</StatusBadge>
}

export function FilterBar({ children, activeCount = 0 }: CommonProps & { activeCount?: number }) {
  return (
    <section className="iu-filter-bar">
      <Filter size={16} aria-hidden="true" />
      <div>{children}</div>
      <Badge tone={activeCount ? 'primary' : 'neutral'}>{activeCount ? `${activeCount} filtri` : 'Nessun filtro'}</Badge>
    </section>
  )
}

export function AdvancedFilters({ title = 'Filtri avanzati', children }: { title?: string; children: ReactNode }) {
  return <Accordion title={title}>{children}</Accordion>
}

export function ResponsiveTable({ children }: CommonProps) {
  return <div className="iu-responsive-table">{children}</div>
}

export function Timeline({ children }: CommonProps) {
  return <ol className="iu-timeline">{children}</ol>
}

export function PermissionDeniedState() {
  return (
    <IusEmptyState
      title="Non hai i permessi per questa operazione"
      message="Richiedi l'abilitazione all'amministratore dello studio."
      icon={AlertTriangle}
      tone="warning"
    />
  )
}

export function ErrorState({ title = 'Si e verificato un problema', message = 'Non e stato possibile caricare i dati. Riprova tra qualche istante.' }: {
  title?: string
  message?: string
}) {
  return (
    <IusEmptyState title={title} message={message} icon={AlertTriangle} tone="danger" />
  )
}

export function InlineAlert({ children, tone = 'warning' }: { children: ReactNode; tone?: BadgeTone }) {
  return <div className={`iu-inline-alert iu-inline-alert--${tone}`} role="status">{children}</div>
}

export function SectionHeader({ title, description, actions }: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <IusSectionHeader title={title} description={description} actions={actions} level={2} />
  )
}

export function Toast({ children, tone = 'success' }: { children: ReactNode; tone?: BadgeTone }) {
  return <div className={`iu-toast iu-toast--${tone}`} role="status">{children}</div>
}

export function ConfirmDialog({ title, message, open, onCancel, onConfirm }: {
  title: string
  message: string
  open: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <Modal title={title} open={open} onClose={onCancel}>
      <p>{message}</p>
      <div className="iu-modal__actions">
        <Button tone="neutral" type="button" onClick={onCancel}>Annulla</Button>
        <Button type="button" onClick={onConfirm}>Conferma</Button>
      </div>
    </Modal>
  )
}

export function StickyActionBar({ children }: CommonProps) {
  return <div className="iu-sticky-action-bar">{children}</div>
}

export function QuickActionBar({ children }: CommonProps) {
  return <div className="iu-quick-action-bar">{children}</div>
}

export function DetailPanel({ title, children }: { title: string; children: ReactNode }) {
  return <PanelBlock title={title} className="iu-detail-panel">{children}</PanelBlock>
}

export function SummaryPanel({ title, children }: { title: string; children: ReactNode }) {
  return <PanelBlock title={title} className="iu-summary-panel">{children}</PanelBlock>
}

export function NextActionPanel({ title, children }: { title: string; children: ReactNode }) {
  return <PanelBlock title={title} className="iu-next-action-panel">{children}</PanelBlock>
}

function PanelBlock({ title, children, className }: { title: string; children: ReactNode; className: string }) {
  return (
    <aside className={cx('iu-panel-block', className)}>
      <header>
        <CheckCircle2 size={17} aria-hidden="true" />
        <h2>{title}</h2>
      </header>
      {children}
    </aside>
  )
}

export { Button, ButtonLink }
