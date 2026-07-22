export type LocalAiLocalResult = {
  ok: boolean
  status: 'ready' | 'missing' | 'warning'
  message: string
  payload?: Record<string, unknown>
}

export type MobileAiInstallPlan = {
  isPortable: boolean
  deviceLabel: string
  resourceLabel: string
  modelLabel: string
  pathLabel: string
  canPrepareOnThisDevice: boolean
  missingSignals: boolean
}

type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'loopback' }

const DEFAULT_AI_BASE_URL = 'http://127.0.0.1:11434/api'
const START_WAIT_STEPS = [500, 900, 1400, 2000, 2600]

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function bool(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  const normalized = text(value).toLowerCase()
  if (['1', 'true', 'yes', 'on'].includes(normalized)) return true
  if (['0', 'false', 'no', 'off'].includes(normalized)) return false
  return fallback
}

function numericText(value: unknown): string {
  const raw = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(raw) || raw <= 0) return ''
  return raw >= 10 ? String(Math.round(raw)) : raw.toFixed(1)
}

function modelValue(value: unknown): string {
  const normalized = text(value)
  return normalized === '__auto__' ? '' : normalized
}

export function localAiModelLabel(value: unknown): string {
  const normalized = text(value).toLowerCase()
  if (!normalized) return 'automatico'
  if (normalized === 'embeddinggemma' || normalized === 'embeddinggemma:latest') return 'EmbeddingGemma'
  if (normalized === 'embeddinggemma:300m') return 'EmbeddingGemma 300M'
  if (normalized === 'gemini-embedding-001') return 'Gemini Embedding'
  if (normalized === 'gemini-embedding-2') return 'Gemini Embedding 2'
  if (normalized === 'qwen3.5:0.8b') return 'Qwen 3.5 minimo'
  if (normalized === 'qwen3.5:2b') return 'Qwen 3.5 leggero'
  if (normalized === 'qwen3.5:9b') return 'Qwen 3.5 avanzato'
  if (normalized === 'gemma3:1b') return 'Gemma 3 veloce'
  if (normalized === 'gemma3:4b') return 'Gemma 3 completo'
  if (normalized === 'qwen2.5:0.5b') return 'Qwen leggero'
  if (normalized === 'nomic-embed-text') return 'Nomic Embed'
  return text(value)
}

function aiSettings(values: Record<string, unknown>, force = false): Record<string, unknown> {
  return {
    enabled: bool(values.enabled, true),
    base_url: text(values.base_url) || DEFAULT_AI_BASE_URL,
    auto_bootstrap: bool(values.auto_bootstrap, true),
    chat_model: modelValue(values.chat_model),
    embed_model: modelValue(values.embed_model),
    keep_alive: text(values.keep_alive) || '10m',
    auto_index_documents: bool(values.auto_index_documents, true),
    force,
  }
}

function query(values: Record<string, unknown>): string {
  const params = new URLSearchParams()
  const settings = aiSettings(values)
  Object.entries(settings).forEach(([key, value]) => {
    if (key === 'force') return
    params.set(key, String(value))
  })
  return params.toString()
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function isDesktopHost(): boolean {
  const host = window.location.hostname
  return ['127.0.0.1', 'localhost', '::1'].includes(host) || host.endsWith('.local')
}

function gbLabel(value: number | undefined, suffix: string): string {
  if (!Number.isFinite(value) || !value || value <= 0) return ''
  return `${value >= 10 ? Math.round(value) : Number(value.toFixed(1))} ${suffix}`
}

function mobileDeviceLabel(userAgent: string, platform: string, isPortable: boolean): string {
  const source = `${userAgent} ${platform}`.toLowerCase()
  if (/iphone|ipad|ipod|ios/.test(source)) return /ipad/.test(source) ? 'iPad rilevato' : 'iPhone rilevato'
  if (/android/.test(source)) return /tablet/.test(source) ? 'Tablet Android rilevato' : 'Telefono Android rilevato'
  if (isPortable) return 'Dispositivo touch rilevato'
  return 'PC dello studio rilevato'
}

function mobileModelLabel(memoryGb: number | undefined, freeGb: number | undefined, isPortable: boolean): string {
  if (!isPortable) return 'Scelta automatica sul PC'
  void memoryGb
  void freeGb
  return 'Motore AI di produzione'
}

export async function detectMobileAiInstallPlan(): Promise<MobileAiInstallPlan> {
  const nav = window.navigator as Navigator & {
    deviceMemory?: number
    userAgentData?: { mobile?: boolean; platform?: string }
  }
  const userAgent = nav.userAgent || ''
  const platform = nav.userAgentData?.platform || nav.platform || ''
  const uaMobile = /android|iphone|ipad|ipod|mobile|tablet/i.test(`${userAgent} ${platform}`)
  const touch = (nav.maxTouchPoints || 0) > 1
  const compactScreen = Math.min(window.screen.width || window.innerWidth, window.screen.height || window.innerHeight) <= 820
  const ipadDesktopMode = /mac/i.test(platform) && touch
  const isPortable = Boolean(nav.userAgentData?.mobile || uaMobile || ipadDesktopMode || (touch && compactScreen))
  const memoryGb = typeof nav.deviceMemory === 'number' ? nav.deviceMemory : undefined
  const cores = typeof nav.hardwareConcurrency === 'number' ? nav.hardwareConcurrency : undefined
  let freeGb: number | undefined

  try {
    if (navigator.storage?.estimate) {
      const estimate = await navigator.storage.estimate()
      if (typeof estimate.quota === 'number' && typeof estimate.usage === 'number') {
        freeGb = Math.max(0, (estimate.quota - estimate.usage) / 1024 / 1024 / 1024)
      }
    }
  } catch {
    freeGb = undefined
  }

  const resourceParts = [
    gbLabel(memoryGb, 'GB RAM'),
    cores ? `${cores} core` : '',
    gbLabel(freeGb, 'GB liberi'),
  ].filter(Boolean)
  const resourceLabel = resourceParts.length > 0 ? resourceParts.join(', ') : 'Risorse non dichiarate dal dispositivo'
  const modelLabel = mobileModelLabel(memoryGb, freeGb, isPortable)
  const canPrepareOnThisDevice = !isPortable
  return {
    isPortable,
    deviceLabel: mobileDeviceLabel(userAgent, platform, isPortable),
    resourceLabel,
    modelLabel,
    canPrepareOnThisDevice,
    missingSignals: resourceParts.length === 0,
    pathLabel: isPortable
      ? "Su telefono e tablet non si installa Ollama: Lex usa il motore AI nell'ambiente di produzione IUSENTRA."
      : 'Da questo PC IUSENTRA può preparare Ollama e scaricare il modello.',
  }
}

async function fetchJson(url: string, init?: RequestInit, timeoutMs = 4000): Promise<Record<string, unknown>> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const requestOptions: LocalNetworkRequestInit = {
      ...init,
      signal: controller.signal,
      mode: 'cors',
      targetAddressSpace: 'loopback',
    }
    const response = await fetch(url, requestOptions)
    const payload = await response.json().catch(() => ({}))
    return record(payload)
  } finally {
    window.clearTimeout(timeout)
  }
}

async function requestLocalSignerStart(protocolUrl: string): Promise<void> {
  if (!protocolUrl || !isDesktopHost()) return
  const frame = document.createElement('iframe')
  frame.style.display = 'none'
  frame.src = protocolUrl
  document.body.appendChild(frame)
  window.setTimeout(() => frame.remove(), 1500)
}

async function ensureLocalSigner(baseUrl: string, protocolUrl: string): Promise<boolean> {
  try {
    const ping = await fetchJson(`${baseUrl}/ping`, undefined, 1400)
    if (ping.ok !== false) return true
  } catch {
    await requestLocalSignerStart(protocolUrl)
  }
  for (const wait of START_WAIT_STEPS) {
    await sleep(wait)
    try {
      const ping = await fetchJson(`${baseUrl}/ping`, undefined, 1400)
      if (ping.ok !== false) return true
    } catch {
      // Continue polling while the local service starts.
    }
  }
  return false
}

function profileLabel(value: unknown): string {
  const profile = text(value).toLowerCase()
  if (profile === 'strong') return 'PC adatto a modelli completi'
  if (profile === 'medium') return 'PC adatto a modelli medi'
  if (profile === 'weak') return 'PC da usare con modelli leggeri'
  return 'PC da verificare'
}

function firstModelName(rows: unknown, kind: string): string {
  if (!Array.isArray(rows)) return ''
  for (const row of rows) {
    const item = record(row)
    if (text(item.kind) === kind) {
      return text(item.name)
    }
  }
  return ''
}

export function describeLocalAiStatus(rawPayload: unknown): LocalAiLocalResult {
  const payload = record(rawPayload)
  const runtime = record(payload.runtime)
  const models = record(payload.resolved_models)
  const status = text(runtime.status).toLowerCase()
  const runtimeOnline = payload.runtime_online === true || ['ready', 'ok', 'running', 'available'].includes(status)
  const missingRuntime = ['missing', 'unavailable'].includes(status)
  const chatModel = localAiModelLabel(text(models.chat) || firstModelName(payload.models, 'chat') || 'automatico')
  const embedModel = localAiModelLabel(text(models.embed) || firstModelName(payload.models, 'embed') || 'automatico')
  const ram = numericText(runtime.ram_gb)
  const disk = numericText(runtime.disk_free_gb)
  const pc = [profileLabel(runtime.hardware_profile), ram ? `${ram} GB RAM` : '', disk ? `${disk} GB liberi` : '']
    .filter(Boolean)
    .join(', ')

  if (runtimeOnline) {
    return {
      ok: true,
      status: 'ready',
      message: `AI locale pronta. Risposte: ${chatModel}. Ricerca documenti: ${embedModel}. ${pc}`,
      payload,
    }
  }

  if (missingRuntime) {
    return {
      ok: false,
      status: 'missing',
      message: `Ollama non risulta pronto su questo PC. Premi Prepara AI locale: IUSENTRA controlla il computer, installa quanto manca e sceglie i modelli adatti. ${pc}`,
      payload,
    }
  }

  return {
    ok: false,
    status: 'warning',
    message: `AI locale da completare. Premi Prepara AI locale per controllare il PC e preparare i modelli. ${pc}`,
    payload,
  }
}

export async function checkLocalAiViaLocalSigner(
  baseUrl: string,
  protocolUrl: string,
  values: Record<string, unknown>,
): Promise<LocalAiLocalResult> {
  const ready = await ensureLocalSigner(baseUrl, protocolUrl)
  if (!ready) {
    return {
      ok: false,
      status: 'missing',
      message: 'IUSENTRA Local Signer non risponde su questo PC. Avvialo o installalo dalla sezione Firma Digitale, poi riprova.',
    }
  }
  try {
    const payload = await fetchJson(`${baseUrl}/ai/status?${query(values)}`, undefined, 9000)
    return describeLocalAiStatus(payload)
  } catch {
    return {
      ok: false,
      status: 'warning',
      message: 'Controllo AI locale non completato. Avvia IUSENTRA Local Signer e riprova.',
    }
  }
}

export async function prepareLocalAiViaLocalSigner(
  baseUrl: string,
  protocolUrl: string,
  values: Record<string, unknown>,
  force = false,
): Promise<LocalAiLocalResult> {
  const ready = await ensureLocalSigner(baseUrl, protocolUrl)
  if (!ready) {
    return {
      ok: false,
      status: 'missing',
      message: 'IUSENTRA Local Signer non risponde su questo PC. Avvialo o installalo dalla sezione Firma Digitale, poi riprova.',
    }
  }
  try {
    const payload = await fetchJson(
      `${baseUrl}/ai/bootstrap`,
      {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify(aiSettings(values, force)),
      },
      120000,
    )
    const statusPayload = payload.status_payload || payload.result || payload
    return describeLocalAiStatus(statusPayload)
  } catch {
    return {
      ok: false,
      status: 'warning',
      message: 'Preparazione AI locale non completata. Controlla che il PC resti acceso e riprova.',
    }
  }
}
