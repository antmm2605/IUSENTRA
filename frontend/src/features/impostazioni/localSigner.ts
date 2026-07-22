export type LocalSignerCheck = {
  ok: boolean
  status: 'ready' | 'missing' | 'unsupported' | 'warning'
  message: string
  certificate?: LocalSignerCertificate
}

export type LocalSignerCertificate = {
  thumbprint: string
  soggetto: string
  codice_fiscale: string
  emittente: string
  scadenza: string
  scadenza_it: string
  giorni_scadenza?: number
}

type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'loopback' }

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
    const requestOptions: LocalNetworkRequestInit = {
      ...init,
      signal: controller.signal,
      mode: 'cors',
      targetAddressSpace: 'loopback',
      headers: buildHeaders(init.headers),
    }
    const response = await fetch(url, requestOptions)
    return await response.json() as Record<string, unknown>
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}

function canRequestProtocolStart(): boolean {
  if (!isDesktopHost()) return false
  const activation = (window.navigator as Navigator & { userActivation?: { isActive?: boolean } }).userActivation
  return activation?.isActive !== false
}

function requestStart(protocol: string): boolean {
  if (!canRequestProtocolStart()) return false
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = protocol
  document.body.appendChild(iframe)
  window.setTimeout(() => iframe.remove(), 2500)
  return true
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

function formatItalianDate(value: string): string {
  const raw = text(value)
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (match) return `${match[3]}/${match[2]}/${match[1]}`
  const italian = raw.match(/^(\d{2})[/-](\d{2})[/-](\d{4})/)
  return italian ? `${italian[1]}/${italian[2]}/${italian[3]}` : ''
}

function daysUntilDate(value: string): number | undefined {
  const raw = text(value)
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return undefined
  const target = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = target.getTime() - today.getTime()
  if (!Number.isFinite(diff)) return undefined
  return Math.round(diff / 86400000)
}

function parseCertificate(payload: Record<string, unknown> | null): LocalSignerCertificate | undefined {
  const source = objectValue(payload?.certificato_windows_selezionato)
  const scadenza = text(source.scadenza || source.expires_at || source.not_after)
  if (!scadenza) return undefined
  return {
    thumbprint: text(source.thumbprint),
    soggetto: text(source.soggetto || source.subject),
    codice_fiscale: text(source.codice_fiscale).toUpperCase(),
    emittente: text(source.emittente || source.issuer),
    scadenza: scadenza.slice(0, 10),
    scadenza_it: formatItalianDate(scadenza),
    giorni_scadenza: daysUntilDate(scadenza),
  }
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
  const certificate = parseCertificate(full)
  if (tokens.length || fresh.length) {
    const certificateText = certificate?.scadenza_it ? ` Certificato valido fino al ${certificate.scadenza_it}.` : ''
    return { ok: true, status: 'ready', message: `Local Signer attivo: dispositivo di firma disponibile.${certificateText}`, certificate }
  }
  const note = String(full?.errore_token || full?.errore_libreria || full?.nota_riavvio_signer || '')
  return {
    ok: true,
    status: 'warning',
    message: note || 'Local Signer attivo, ma nessun dispositivo di firma risulta ancora disponibile.',
    certificate,
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
    username: text(values.username, text(values.indirizzo)),
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
        username: payload.username,
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
      username: text(payload.username, text(savedPayload.username, text(payload.indirizzo, text(savedPayload.indirizzo)))),
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
