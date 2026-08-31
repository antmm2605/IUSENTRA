export type LocalSignerForegroundGrant = {
  required: boolean
  nonce: string
  dispatched: boolean
}

type LocalSignerRequest = (
  path: string,
  body?: Record<string, unknown>,
  timeoutMs?: number,
) => Promise<Record<string, unknown>>

function windowsDesktop(): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false
  const userAgent = String(navigator.userAgent || '').toLowerCase()
  const platform = String(navigator.platform || '').toLowerCase()
  return /windows|win32|win64/.test(`${userAgent} ${platform}`)
}

function foregroundNonce(): string {
  const randomUuid = globalThis.crypto?.randomUUID?.()
  if (randomUuid) return randomUuid.replaceAll('-', '')
  const bytes = new Uint8Array(24)
  globalThis.crypto.getRandomValues(bytes)
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
}

export function beginLocalSignerForegroundGrant(): LocalSignerForegroundGrant {
  if (!windowsDesktop()) return { required: false, nonce: '', dispatched: false }
  if (navigator.userActivation && !navigator.userActivation.isActive) {
    throw new Error('Premi direttamente il comando in IUSENTRA per aprire la richiesta PIN in primo piano.')
  }
  const nonce = foregroundNonce()
  const link = document.createElement('a')
  link.href = `iusentra-local-signer://foreground?nonce=${encodeURIComponent(nonce)}`
  link.hidden = true
  link.setAttribute('aria-hidden', 'true')
  document.body.appendChild(link)
  link.click()
  link.remove()
  return { required: true, nonce, dispatched: true }
}

export async function waitLocalSignerForegroundGrant(
  request: LocalSignerRequest,
  grant: LocalSignerForegroundGrant,
  timeoutMs = 5_000,
): Promise<string> {
  if (!grant.required) return ''
  if (!grant.dispatched || !grant.nonce) {
    throw new Error('Attivazione Windows non avviata dal clic.')
  }
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const status = await request('/foreground/status', { nonce: grant.nonce }, 2_000)
      const state = String(status.state || '')
      if (state === 'granted') return grant.nonce
      if (state === 'denied' || state === 'consumed') {
        throw new Error('Windows non ha autorizzato l’apertura del PIN in primo piano. Premi di nuovo il comando.')
      }
    } catch (error) {
      if (error instanceof Error && /non ha autorizzato/.test(error.message)) throw error
    }
    await new Promise((resolve) => window.setTimeout(resolve, 100))
  }
  throw new Error(
    'Local Signer non ha confermato l’attivazione Windows entro pochi secondi. '
    + 'La richiesta PST non è stata avviata e nessun PIN è rimasto nascosto nella barra.',
  )
}
