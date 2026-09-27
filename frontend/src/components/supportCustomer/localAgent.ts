/**
 * Agente locale sul PC del cliente: agente dedicato «IUSENTRA Assistenza»
 * (porta 27273) oppure modulo `/support` di Local Signer (porta 27272).
 *
 * Porta 1:1 le funzioni loopback di web/static/js/support_customer_room.js:
 * basi candidate, confronto versioni, aggiornamento automatico di Local Signer,
 * probe in ordine con passaggio alla base successiva solo per errori di rete.
 */

type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'loopback' }

export const LOCAL_AGENT_DEDICATED_BASE = 'http://127.0.0.1:27273'
export const LOCAL_SIGNER_SUPPORT_BASE = 'http://127.0.0.1:27272/support'
export const LOCAL_SIGNER_DEFAULT_BASE = 'http://127.0.0.1:27272'
export const LOCAL_SIGNER_FALLBACK_LATEST_VERSION = '1.6.72'
const LOCAL_SIGNER_UPDATE_PROTOCOL = 'iusentra-local-signer://update'
const LOOPBACK_TIMEOUT_MS = 4500
const SUPPORT_READY_ATTEMPTS = 60

export class LoopbackError extends Error {
  status?: number
  payload?: Record<string, unknown>
  base?: string
  path?: string

  constructor(message: string, details: { status?: number; payload?: Record<string, unknown>; base?: string; path?: string } = {}) {
    super(message)
    this.name = 'LoopbackError'
    this.status = details.status
    this.payload = details.payload
    this.base = details.base
    this.path = details.path
  }
}

function trimBase(value: string): string {
  return String(value || '').replace(/\/+$/, '')
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export function versionParts(value: unknown): number[] {
  return String(value || '')
    .replace(/^v/i, '')
    .split(/[^\d]+/)
    .filter(Boolean)
    .map((part) => Number.parseInt(part, 10) || 0)
}

export function compareVersions(a: unknown, b: unknown): number {
  const left = versionParts(a)
  const right = versionParts(b)
  const max = Math.max(left.length, right.length)
  for (let index = 0; index < max; index += 1) {
    const av = left[index] || 0
    const bv = right[index] || 0
    if (av > bv) return 1
    if (av < bv) return -1
  }
  return 0
}

/**
 * Basi candidate in ordine di preferenza:
 * 1) override esplicito dal server (SUPPORT_LOCAL_CONTROL_BASE);
 * 2) agente dedicato 27273, se lo studio lo usa ancora;
 * 3) Local Signer 27272/support, già presente su molti PC per firma/PEC/PST.
 */
export function agentBaseCandidates(localControlBase: string): string[] {
  const bases = [localControlBase ? trimBase(localControlBase) : '', LOCAL_AGENT_DEDICATED_BASE, LOCAL_SIGNER_SUPPORT_BASE]
  return bases.filter((base, index) => Boolean(base) && bases.indexOf(base) === index)
}

export function isAgentNetworkError(error: unknown): boolean {
  const candidate = error as { name?: string; message?: string } | null
  if (candidate?.name === 'AbortError' || candidate?.name === 'TypeError') return true
  return /failed to fetch|networkerror|load failed/i.test(String(candidate?.message || ''))
}

function isNotFound(error: unknown): boolean {
  const candidate = error as { status?: number; message?: string } | null
  return candidate?.status === 404 || /not found/i.test(String(candidate?.message || ''))
}

export async function fetchLoopbackJson(
  url: string,
  init: RequestInit = {},
  timeoutMs = LOOPBACK_TIMEOUT_MS,
  details: { base?: string; path?: string } = {},
): Promise<Record<string, unknown>> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const request: LocalNetworkRequestInit = {
      ...init,
      headers: { Accept: 'application/json', ...(init.headers as Record<string, string> | undefined) },
      signal: controller.signal,
      targetAddressSpace: 'loopback',
    }
    const response = await fetch(url, request)
    const rawText = await response.text()
    let payload: Record<string, unknown> = {}
    try {
      payload = rawText ? JSON.parse(rawText) as Record<string, unknown> : {}
    } catch {
      payload = {}
    }
    if (!response.ok || payload.ok === false) {
      const message = [payload.error, payload.description, payload.errore]
        .map((value) => (typeof value === 'string' ? value : ''))
        .find(Boolean) || rawText || `HTTP ${response.status}`
      throw new LoopbackError(message, { status: response.status, payload, ...details })
    }
    return payload
  } finally {
    window.clearTimeout(timeout)
  }
}

/** Chiede al sistema operativo di avviare l'aggiornamento di Local Signer (protocollo registrato). */
export function requestLocalSignerProtocolUpdate(): void {
  try {
    const iframe = document.createElement('iframe')
    iframe.hidden = true
    iframe.setAttribute('aria-hidden', 'true')
    iframe.tabIndex = -1
    iframe.src = LOCAL_SIGNER_UPDATE_PROTOCOL
    document.body.appendChild(iframe)
    window.setTimeout(() => iframe.remove(), 2500)
  } catch {
    // Il protocollo può non essere registrato: resta il percorso via browser.
  }
}

type LocalSupportAgentOptions = {
  localControlBase: string
  localSignerBase: string
  localSignerLatestVersion: string
  onStatus: (text: string) => void
}

export class LocalSupportAgent {
  private readonly bases: string[]
  private readonly localSignerBase: string
  private readonly supportLocalSignerBase: string
  private readonly latestVersion: string
  private readonly onStatus: (text: string) => void
  private activeBase: string | null = null
  private updatePromise: Promise<Record<string, unknown>> | null = null

  constructor(options: LocalSupportAgentOptions) {
    this.bases = agentBaseCandidates(options.localControlBase)
    this.localSignerBase = trimBase(options.localSignerBase || LOCAL_SIGNER_DEFAULT_BASE)
    this.supportLocalSignerBase = `${this.localSignerBase}/support`
    this.latestVersion = String(options.localSignerLatestVersion || LOCAL_SIGNER_FALLBACK_LATEST_VERSION).trim()
    this.onStatus = options.onStatus
  }

  get candidates(): string[] {
    return [...this.bases]
  }

  isLocalSignerSupportBase(base: string): boolean {
    const normalized = trimBase(base)
    return normalized === this.supportLocalSignerBase || /:27272\/support$/.test(normalized)
  }

  fetchLocalSigner(path: string, init: RequestInit = {}, timeoutMs = LOOPBACK_TIMEOUT_MS) {
    return fetchLoopbackJson(`${this.localSignerBase}${path}`, init, timeoutMs)
  }

  private isOutdated(ping: Record<string, unknown>): boolean {
    const installed = String(ping.versione || ping.version || '')
    return Boolean(this.latestVersion) && compareVersions(installed, this.latestVersion) < 0
  }

  async waitForLocalSignerSupportReady(): Promise<Record<string, unknown> | null> {
    for (let attempt = 0; attempt < SUPPORT_READY_ATTEMPTS; attempt += 1) {
      await sleep(1000)
      try {
        const ping = await this.fetchLocalSigner('/ping?light=1', {}, 2500)
        if (this.isOutdated(ping)) continue
        const status = await this.fetchLocalSigner('/support/status', {}, 2500)
        if (status && status.ok) return status
      } catch {
        // Il servizio può riavviarsi durante l'aggiornamento.
      }
    }
    return null
  }

  updateLocalSignerForSupport(reason: 'outdated' | 'missing-support'): Promise<Record<string, unknown>> {
    if (this.updatePromise) return this.updatePromise
    this.updatePromise = (async () => {
      this.onStatus('Aggiorno Local Signer per il controllo PC')
      try {
        await this.fetchLocalSigner('/update', {}, 8000)
      } catch {
        requestLocalSignerProtocolUpdate()
      }
      const ready = await this.waitForLocalSignerSupportReady()
      if (!ready) {
        throw new Error(
          reason === 'missing-support'
            ? "Local Signer trovato ma il modulo assistenza non risponde ancora. Attendi l'aggiornamento e riprova."
            : 'Aggiornamento Local Signer non completato. Attendi qualche secondo e riprova.',
        )
      }
      this.onStatus('Local Signer pronto per il controllo PC')
      return ready
    })().finally(() => {
      this.updatePromise = null
    })
    return this.updatePromise
  }

  /** All'apertura della stanza: aggiorna Local Signer se vecchio o senza modulo assistenza. */
  async autoPrepareLocalSignerForSupport(): Promise<void> {
    try {
      const ping = await this.fetchLocalSigner('/ping?light=1', {}, 2500)
      if (this.isOutdated(ping)) {
        await this.updateLocalSignerForSupport('outdated')
        return
      }
      try {
        await this.fetchLocalSigner('/support/status', {}, 2500)
      } catch (error) {
        if (isNotFound(error)) await this.updateLocalSignerForSupport('missing-support')
      }
    } catch {
      // Nessun Local Signer in esecuzione: la condivisione schermo via browser resta disponibile.
    }
  }

  fetchAgentAt(base: string, path: string, body: Record<string, unknown> | null = null) {
    return fetchLoopbackJson(
      `${base}${path}`,
      {
        method: body ? 'POST' : 'GET',
        headers: body ? { 'Content-Type': 'application/json' } : { Accept: 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      },
      LOOPBACK_TIMEOUT_MS,
      { base, path },
    )
  }

  /**
   * Base già individuata in questa sessione: usata direttamente. Altrimenti probe
   * in ordine; si passa alla base successiva SOLO per errori di rete (porta chiusa,
   * timeout): un errore applicativo (es. token non valido) si propaga subito.
   */
  async fetchAgent(path: string, body: Record<string, unknown> | null = null): Promise<Record<string, unknown>> {
    if (this.activeBase) return this.fetchAgentAt(this.activeBase, path, body)
    let lastError: unknown = null
    for (const base of this.bases) {
      try {
        const payload = await this.fetchAgentAt(base, path, body)
        this.activeBase = base
        return payload
      } catch (error) {
        lastError = error
        if (this.isLocalSignerSupportBase(base) && path === '/status' && isNotFound(error)) {
          await this.updateLocalSignerForSupport('missing-support')
          const payload = await this.fetchAgentAt(base, path, body)
          this.activeBase = base
          return payload
        }
        if (!isAgentNetworkError(error)) {
          this.activeBase = base
          throw error
        }
      }
    }
    throw lastError instanceof Error ? lastError : new Error('Agente locale non raggiungibile.')
  }
}
