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

async function fetchJsonWithTimeout(url: string, timeoutMs: number): Promise<Record<string, unknown> | null> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, { signal: controller.signal, headers: { 'X-Requested-With': 'XMLHttpRequest' } })
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

export async function checkLocalSigner(baseUrl: string, restartProtocol: string): Promise<LocalSignerCheck> {
  if (!isDesktopHost()) {
    return { ok: false, status: 'unsupported', message: 'Il controllo Local Signer richiede un PC desktop.' }
  }
  const pingUrl = `${baseUrl.replace(/\/+$/, '')}/ping`
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
