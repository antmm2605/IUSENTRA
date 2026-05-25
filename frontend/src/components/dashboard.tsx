import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight } from 'lucide-react'
import type { Dossier, Metric, Source, Tone } from '../data'
import { IusMetricCard, IusStatusBadge } from './iusentra'
import type { IusTone } from '../design/iusentraTokens'

type ButtonProps = {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost'
  full?: boolean
  href?: string
  className?: string
  title?: string
  disabled?: boolean
}

export function Button({ children, variant = 'secondary', full = false, href, className = '', title, disabled = false }: ButtonProps) {
  const classes = `iu-button iu-button--${variant} ${full ? 'iu-button--full' : ''} ${disabled ? 'is-disabled' : ''} ${className}`.trim()
  if (href && !disabled) return <a className={classes} href={href} title={title}>{children}</a>
  return <button className={classes} type="button" title={title} disabled={disabled} aria-disabled={disabled}>{children}</button>
}

export function Badge({ tone = 'neutral', children }:{tone?:Tone; children:ReactNode}) {
  return <IusStatusBadge tone={toIusTone(tone)}>{children}</IusStatusBadge>
}

function toIusTone(tone: Tone): IusTone {
  if (tone === 'orange' || tone === 'purple') return 'gold'
  if (tone === 'info') return 'info'
  return tone
}

export function Panel({
  title,
  subtitle,
  icon,
  count,
  action,
  children,
  className = '',
}:{
  title:string
  subtitle?:string
  icon?:ReactNode
  count?:number|string
  action?:ReactNode
  children:ReactNode
  className?:string
}) {
  return (
    <section className={`iu-panel ${className}`.trim()}>
      <header>
        <div>
          {icon}
          <span>
            <strong>{title}</strong>
            {subtitle ? <small>{subtitle}</small> : null}
          </span>
        </div>
        {action ? <div className="iu-panel__action">{action}</div> : count!==undefined ? <span>{count}</span> : null}
      </header>
      <div className="iu-panel__body">{children}</div>
    </section>
  )
}

export function KpiCard({ item, icon: Icon }:{item:Metric; icon:LucideIcon}) {
  return (
    <IusMetricCard
      label={item.label}
      value={item.value}
      badge={item.tag}
      href={item.href}
      icon={Icon}
      tone={toIusTone(item.tone)}
      actionLabel={item.actionLabel || 'Apri'}
      className={`iu-metric iu-metric--${item.tone}`}
    />
  )
}

export function DossierCard({ dossier }:{dossier:Dossier}) {
  return (
    <article className="iu-dossier-card">
      <div className="iu-dossier-card__topline">
        <Badge tone={dossier.tone}>{dossier.area}</Badge>
        <strong>{dossier.score}</strong>
      </div>
      <a className="iu-dossier-card__title" href={dossier.href}>{dossier.title}</a>
      <p>{dossier.meta}</p>
      <h3>Prossime mosse</h3>
      <ul>
        {dossier.moves.map((move)=><li key={move}>{move}</li>)}
      </ul>
      <div className="iu-dossier-card__actions">
        <Button variant="primary" href={dossier.href}>Apri fascicolo</Button>
        <Button href="/giurisprudenza/">Ricerca sentenze</Button>
      </div>
    </article>
  )
}

export function SourceCard({ source }:{source:Source}) {
  return (
    <article className="iu-source-card">
      <div className="iu-source-card__head">
        <h3>{source.title}</h3>
        {source.badge?<Badge tone={source.tone}>{source.badge}</Badge>:null}
      </div>
      <p>{source.description}</p>
      <a href={source.href}>Fonte operativa <ArrowRight size={14}/></a>
    </article>
  )
}
