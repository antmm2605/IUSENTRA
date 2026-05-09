export type LocalSignerCheck = {
  ok: boolean
  status: 'ready' | 'missing' | 'unsupported' | 'warning'
  message: string
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function isDesktopHost(): boolean {
  const userAgent = String(window.navigator.userAgent || '').toLowerCase()
  const platformName = String(window.navigator.platform || '').toLowerCase()
  const mobile = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(userAgent)
  const ipadDesktopMode = platformName.includes('mac') && Number(window.navigator.maxTouchPoints || 0) > 1
  return !mobile && !ipadDesktopMode
}

function buildHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers)
  if (!merged.has('X-Requested-With')) merged.set('X-Requested-With', 'XMLHttpRequest')
  return merged
}

async function fetchJsonWithTimeout(
  url: string,
  timeoutMs: number,
  init: RequestInit = {},
): Promise<Record<string, unknown> | null> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: buildHeaders(init.headers),
    })
    return await response.json() as Record<string, unknown>
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}

function requestStart(protocol: string) {
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = protocol
  document.body.appendChild(iframe)
  window.setTimeout(() => iframe.remove(), 2500)
}

function text(value: unknown, fallback = ''): string {
  if (value === undefined || value === null || value === '') return String(fallback || '').trim()
  if (typeof value === 'object') return String(fallback || '').trim()
  return String(value).trim()
}

function booleanValue(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  const normalized = text(value).toLowerCase()
  if (['1', 'true', 'si', 'yes', 'on'].includes(normalized)) return true
  if (['0', 'false', 'no', 'off'].includes(normalized)) return false
  return fallback
}

function integerValue(value: unknown, fallback: number): number {
  const parsed = Number.parseInt(text(value), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function hasSavedSecret(value: unknown): boolean {
  const secret = objectValue(value)
  return Boolean(secret.present)
}

function localBaseUrl(baseUrl: string): string {
  return text(baseUrl, 'http://127.0.0.1:27272').replace(/\/+$/, '')
}

async function ensureLocalSignerService(baseUrl: string, restartProtocol: string): Promise<LocalSignerCheck | null> {
  if (!isDesktopHost()) {
    return { ok: false, status: 'unsupported', message: 'Il controllo invio PEC richiede il PC dello studio.' }
  }

  const pingUrl = `${localBaseUrl(baseUrl)}/ping?light=1`
  let payload = await fetchJsonWithTimeout(pingUrl, 2500)
  if (!payload?.ok) {
    requestStart(restartProtocol)
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await sleep(900)
      payload = await fetchJsonWithTimeout(pingUrl, 2500)
      if (payload?.ok) break
    }
  }

  if (!payload?.ok) {
    return { ok: false, status: 'missing', message: 'Local Signer non rilevato. Avvia IUSENTRA Local Signer sul PC in uso e riprova.' }
  }

  return null
}

export async function checkLocalSigner(baseUrl: string, restartProtocol: string): Promise<LocalSignerCheck> {
  if (!isDesktopHost()) {
    return { ok: false, status: 'unsupported', message: 'Il controllo Local Signer richiede un PC desktop.' }
  }
  const pingUrl = `${localBaseUrl(baseUrl)}/ping`
  let payload = await fetchJsonWithTimeout(`${pingUrl}?light=1`, 2500)
  if (!payload?.ok) {
    requestStart(restartProtocol)
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await sleep(900)
      payload = await fetchJsonWithTimeout(`${pingUrl}?light=1`, 2500)
      if (payload?.ok) break
    }
  }
  if (!payload?.ok) {
    return { ok: false, status: 'missing', message: 'Local Signer non rilevato. Installa o avvia il servizio locale e riprova.' }
  }
  const full = await fetchJsonWithTimeout(pingUrl, 4000)
  const tokens = Array.isArray(full?.token) ? full.token : []
  const fresh = Array.isArray(full?.token_probe_fresh) ? full.token_probe_fresh : []
  if (tokens.length || fresh.length) {
    return { ok: true, status: 'ready', message: 'Local Signer attivo: dispositivo di firma disponibile.' }
  }
  const note = String(full?.errore_token || full?.errore_libreria || full?.nota_riavvio_signer || '')
  return {
    ok: true,
    status: 'warning',
    message: note || 'Local Signer attivo, ma nessun dispositivo di firma risulta ancora disponibile.',
  }
}

export async function testPecSmtpViaLocalSigner(
  baseUrl: string,
  restartProtocol: string,
  values: Record<string, unknown>,
  savedPasswordState: unknown,
): Promise<LocalSignerCheck> {
  const serviceError = await ensureLocalSignerService(baseUrl, restartProtocol)
  if (serviceError) return serviceError

  let payload: Record<string, unknown> = {
    indirizzo: text(values.indirizzo),
    username: text(values.indirizzo),
    password: text(values.password),
    smtp_host: text(values.smtp_host),
    smtp_port: integerValue(values.smtp_port, 465),
    use_ssl: booleanValue(values.use_ssl, true),
  }

  if (!text(payload.password) && hasSavedSecret(savedPasswordState)) {
    const saved = await fetchJsonWithTimeout('/impostazioni/pec/local-smtp-payload', 10000, {
      method: 'POST',
      credentials: 'same-origin',
      headers: new Headers({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      body: JSON.stringify({
        indirizzo: payload.indirizzo,
        smtp_host: payload.smtp_host,
        smtp_port: payload.smtp_port,
        use_ssl: payload.use_ssl,
      }),
    })
    const savedPayload = objectValue(saved?.payload)
    if (!saved?.ok || !Object.keys(savedPayload).length) {
      return {
        ok: false,
        status: 'warning',
        message: text(saved?.errore, 'Password PEC non disponibile. Inseriscila nel campo Password PEC, poi ripeti la verifica. La password viene inviata solo al Local Signer sul PC in uso.'),
      }
    }
    payload = {
      ...payload,
      ...savedPayload,
      indirizzo: text(payload.indirizzo, text(savedPayload.indirizzo)),
      username: text(payload.indirizzo, text(savedPayload.username, text(savedPayload.indirizzo))),
      password: text(savedPayload.password),
      smtp_host: text(payload.smtp_host, text(savedPayload.smtp_host)),
      smtp_port: integerValue(payload.smtp_port, integerValue(savedPayload.smtp_port, 465)),
      use_ssl: booleanValue(payload.use_ssl, booleanValue(savedPayload.use_ssl, true)),
    }
  }

  if (!text(payload.password)) {
    return {
      ok: false,
      status: 'warning',
      message: 'Password PEC non disponibile. Inseriscila nel campo Password PEC, poi ripeti la verifica. La password viene inviata solo al Local Signer sul PC in uso.',
    }
  }

  const result = await fetchJsonWithTimeout(`${localBaseUrl(baseUrl)}/pec/smtp/test`, 35000, {
    method: 'POST',
    headers: new Headers({ 'Content-Type': 'application/json', Accept: 'application/json' }),
    body: JSON.stringify(payload),
  })

  if (!result) {
    return { ok: false, status: 'missing', message: 'Local Signer non rilevato. Avvia IUSENTRA Local Signer sul PC in uso e riprova.' }
  }

  const ok = Boolean(result.ok)
  return {
    ok,
    status: ok ? 'ready' : 'warning',
    message: text(result.messaggio, text(result.message, ok ? 'Connessione SMTP PEC riuscita.' : 'Verifica invio PEC non completata.')),
  }
}
