import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight } from 'lucide-react'
import type { Dossier, Metric, Source, Tone } from '../data'

type ButtonProps = {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost'
  full?: boolean
  href?: string
  className?: string
}

export function Button({ children, variant = 'secondary', full = false, href, className = '' }: ButtonProps) {
  const classes = `iu-button iu-button--${variant} ${full ? 'iu-button--full' : ''} ${className}`.trim()
  if (href) return <a className={classes} href={href}>{children}</a>
  return <button className={classes} type="button">{children}</button>
}

export function Badge({ tone = 'neutral', children }:{tone?:Tone; children:ReactNode}) {
  return <span className={`iu-badge iu-badge--${tone}`}>{children}</span>
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
  const content = (
    <>
      <div className="iu-metric__icon"><Icon size={25}/></div>
      <div className="iu-metric__content">
        <div className="iu-metric__top">
          <strong>{item.value}</strong>
          {item.tag?<Badge tone={item.tone}>{item.tag}</Badge>:null}
        </div>
        <div className="iu-metric__label">{item.label}</div>
        <span className="iu-link">{item.actionLabel || 'Apri'} <ArrowRight size={14}/></span>
      </div>
    </>
  )
  if (!item.href) {
    return <article className={`iu-metric iu-metric--${item.tone}`} aria-label={item.label}>{content}</article>
  }
  return (
    <a href={item.href} className={`iu-metric iu-metric--${item.tone}`}>
      {content}
    </a>
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
