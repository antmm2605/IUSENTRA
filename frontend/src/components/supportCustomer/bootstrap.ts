import type { SupportCustomerBootstrap, SupportCustomerSession } from './types'

/**
 * Lettura del bootstrap della stanza cliente.
 *
 * Il template `support/customer_room_react.html` imposta `window.SUPPORT_BOOTSTRAP`
 * con uno script che porta il nonce CSP della richiesta e replica gli stessi dati
 * in un blocco JSON non eseguibile (`#support-customer-bootstrap`), usato come
 * riserva se lo script con nonce non è stato eseguito.
 */

export const CUSTOMER_BOOTSTRAP_SCRIPT_ID = 'support-customer-bootstrap'
export const CUSTOMER_SESSION_SCRIPT_ID = 'support-customer-session'

const DEFAULT_LOCAL_SIGNER_BASE = 'http://127.0.0.1:27272'
const DEFAULT_LOCAL_CONTROL_BASE = 'http://127.0.0.1:27273'

type SupportGlobals = {
  SUPPORT_BOOTSTRAP?: unknown
  SUPPORT_SESSION?: unknown
}

function supportGlobals(): SupportGlobals {
  return window as unknown as SupportGlobals
}

function readJsonScript(id: string): unknown {
  const element = document.getElementById(id)
  if (!element?.textContent) return null
  try {
    return JSON.parse(element.textContent) as unknown
  } catch {
    return null
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function text(value: unknown, fallback = ''): string {
  if (value === undefined || value === null) return fallback
  if (typeof value === 'object') return fallback
  const normalized = String(value).trim()
  return normalized || fallback
}

export function normalizeCustomerBootstrap(raw: unknown): SupportCustomerBootstrap {
  const source = asRecord(raw)
  const status = text(source.status)
  return {
    publicId: text(source.publicId),
    role: 'client',
    authToken: text(source.authToken),
    apiPrefix: text(source.apiPrefix).replace(/\/+$/, ''),
    wsBase: text(source.wsBase, '/support/ws').replace(/\/+$/, ''),
    localControlBase: text(source.localControlBase, DEFAULT_LOCAL_CONTROL_BASE),
    localSignerBase: text(source.localSignerBase, DEFAULT_LOCAL_SIGNER_BASE),
    localSignerLatestVersion: text(source.localSignerLatestVersion),
    customerName: text(source.customerName),
    status,
    closed: source.closed === true || status === 'closed',
  }
}

export function normalizeCustomerSession(raw: unknown): SupportCustomerSession {
  const source = asRecord(raw)
  const presence = asRecord(source.presence)
  return {
    public_id: text(source.public_id),
    status: text(source.status),
    status_label: text(source.status_label),
    customer_name: text(source.customer_name),
    practice_label: text(source.practice_label),
    presence: { client: presence.client === true, operator: presence.operator === true },
    advanced_control_requested: source.advanced_control_requested === true,
    advanced_control_approved: source.advanced_control_approved === true,
  }
}

export function readCustomerBootstrap(): SupportCustomerBootstrap {
  const globals = supportGlobals()
  return normalizeCustomerBootstrap(globals.SUPPORT_BOOTSTRAP ?? readJsonScript(CUSTOMER_BOOTSTRAP_SCRIPT_ID))
}

export function readCustomerSession(): SupportCustomerSession {
  const globals = supportGlobals()
  return normalizeCustomerSession(globals.SUPPORT_SESSION ?? readJsonScript(CUSTOMER_SESSION_SCRIPT_ID))
}

/** Il bootstrap è utilizzabile solo se identifica sessione, token e API. */
export function isCustomerBootstrapUsable(boot: SupportCustomerBootstrap): boolean {
  return Boolean(boot.publicId && boot.authToken && boot.apiPrefix)
}
