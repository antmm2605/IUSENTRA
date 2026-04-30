import { useEffect } from 'react'

type FloatingLexProps = {
  context?: string
  title?: string
  body?: string
  primaryHref?: string
  primaryLabel?: string
  secondaryHref?: string
  secondaryLabel?: string
}

type GlobalLexWindow = Window & {
  IUSENTRA_LEX_CONTEXT?: FloatingLexProps & { pagePath?: string }
}

function publishLexContext(config: FloatingLexProps) {
  if (typeof window === 'undefined') return
  const detail = {
    ...config,
    pagePath: window.location.pathname,
  }
  const target = window as GlobalLexWindow
  target.IUSENTRA_LEX_CONTEXT = detail
  window.dispatchEvent(new CustomEvent('iusentra:lex-context', { detail }))
}

export function FloatingLex(config: FloatingLexProps = {}) {
  useEffect(() => {
    publishLexContext(config)
  }, [
    config.context,
    config.title,
    config.body,
    config.primaryHref,
    config.primaryLabel,
    config.secondaryHref,
    config.secondaryLabel,
  ])

  return null
}
