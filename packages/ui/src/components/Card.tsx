import type { HTMLAttributes, ReactNode } from 'react'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  body?: ReactNode
  eyebrow?: string
  footer?: ReactNode
  title: string
  description?: string
}

const joinClassNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(' ')

export function Card({
  body,
  children,
  className,
  description,
  eyebrow,
  footer,
  title,
  ...props
}: CardProps) {
  return (
    <section className={joinClassNames('iusentra-card', className)} {...props}>
      <header className="iusentra-card__header">
        {eyebrow ? <span className="iusentra-card__eyebrow">{eyebrow}</span> : null}
        <h3 className="iusentra-card__title">{title}</h3>
        {description ? <p className="iusentra-card__description">{description}</p> : null}
      </header>
      {body || children ? <div className="iusentra-card__body">{body ?? children}</div> : null}
      {footer ? <footer className="iusentra-card__footer">{footer}</footer> : null}
    </section>
  )
}
