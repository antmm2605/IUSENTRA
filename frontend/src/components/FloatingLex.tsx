import { useEffect } from 'react'

type FloatingLexProps = {
  context?: string
  title?: string
  body?: string
  primaryHref?: string
  primaryLabel?: string
  secondaryHref?: string
  secondaryLabel?: string
  activeContext?: LexActiveContext
  contextType?: string
  caseId?: string
  clientId?: string
  pecId?: string
  documentId?: string
  modelCode?: string
  linkedCaseId?: string
  linkedClientId?: string
  userId?: string
  permissionsScope?: string[]
}

type LexActiveContext = {
  context_type?: string
  contextType?: string
  case_id?: string
  caseId?: string
  client_id?: string
  clientId?: string
  pec_id?: string
  pecId?: string
  document_id?: string
  documentId?: string
  model_code?: string
  modelCode?: string
  linked_case_id?: string
  linkedCaseId?: string
  linked_client_id?: string
  linkedClientId?: string
  user_id?: string
  userId?: string
  permissions_scope?: string[]
  permissionsScope?: string[]
}

type GlobalLexWindow = Window & {
  IUSENTRA_LEX_CONTEXT?: FloatingLexProps & { pagePath?: string; active_context?: LexActiveContext }
}

function publishLexContext(config: FloatingLexProps) {
  if (typeof window === 'undefined') return
  const detail = {
    ...config,
    contextType: config.contextType,
    caseId: config.caseId,
    clientId: config.clientId,
    pecId: config.pecId,
    documentId: config.documentId,
    modelCode: config.modelCode,
    linkedCaseId: config.linkedCaseId,
    linkedClientId: config.linkedClientId,
    userId: config.userId,
    permissionsScope: config.permissionsScope,
    active_context: config.activeContext,
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
    config.activeContext,
    config.contextType,
    config.caseId,
    config.clientId,
    config.pecId,
    config.documentId,
    config.modelCode,
    config.linkedCaseId,
    config.linkedClientId,
    config.userId,
    config.permissionsScope,
  ])

  return null
}
