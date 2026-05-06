import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'
import './ui.css'

export type ButtonTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning'

export function Button({
  children,
  tone = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: ButtonTone; children: ReactNode }) {
  const classes = ['iu-btn', `iu-btn--${tone}`, className].filter(Boolean).join(' ')
  return (
    <button className={classes} {...props}>
      {children}
    </button>
  )
}

export function ButtonLink({
  children,
  tone = 'primary',
  className = '',
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { tone?: ButtonTone; children: ReactNode }) {
  const classes = ['iu-btn', `iu-btn--${tone}`, className].filter(Boolean).join(' ')
  return (
    <a className={classes} {...props}>
      {children}
    </a>
  )
}
