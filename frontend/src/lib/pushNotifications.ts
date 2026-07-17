import { apiJson, apiPostJson } from '@/lib/apiClient'
import { isFeatureFlagEnabled } from '@/lib/featureFlags'

export type PushPermission = NotificationPermission | 'unsupported'

export type PushDeviceStatus = {
  supported: boolean
  enabled?: boolean
  configured: boolean
  active: boolean
  permission: PushPermission
  message: string
  diagnostics?: PushConfigDiagnostics
}

export type PushActionResult = {
  ok: boolean
  message: string
  active?: boolean
  sent?: number
  attempted?: number
  disabled?: number
  notificationId?: string
}

type PublicKeyPayload = {
  ok: boolean
  enabled?: boolean
  configured?: boolean
  publicKey?: string
  message?: string
  diagnostics?: PushConfigDiagnostics
}

export type PushConfigDiagnostics = {
  enabled?: boolean
  configured?: boolean
  hasPublicKey?: boolean
  hasPrivateKey?: boolean
  hasSubject?: boolean
  missing?: string[]
}

const fallbackPublicKey: PublicKeyPayload = {
  ok: false,
  configured: false,
  message: 'Notifiche su dispositivo non disponibili.',
}

const fallbackAction: PushActionResult = {
  ok: false,
  message: 'Operazione non completata.',
}

const SERVICE_WORKER_URL = '/sw.js?iusentra_sw=20260717_remote_hearing_v5'
const SERVICE_WORKER_OPTIONS: RegistrationOptions = {
  scope: '/',
  updateViaCache: 'none',
}

type ExtendedNotificationOptions = NotificationOptions & {
  renotify?: boolean
  timestamp?: number
  vibrate?: number[]
}

function notifyTopbarChanged(): void {
  window.dispatchEvent(new CustomEvent('iusentra:notifications-updated'))
}

export function browserSupportsPush(): boolean {
  return typeof window !== 'undefined'
    && 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window
}

function currentPermission(): PushPermission {
  if (!browserSupportsPush()) return 'unsupported'
  return Notification.permission
}

function urlBase64ToArrayBuffer(value: string): ArrayBuffer {
  const padding = '='.repeat((4 - value.length % 4) % 4)
  const base64 = `${value}${padding}`.replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const buffer = new ArrayBuffer(rawData.length)
  const output = new Uint8Array(buffer)
  for (let index = 0; index < rawData.length; index += 1) {
    output[index] = rawData.charCodeAt(index)
  }
  return buffer
}

function arrayBufferToUrlBase64(value: ArrayBuffer | null): string {
  if (!value) return ''
  const bytes = new Uint8Array(value)
  let binary = ''
  bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
  return window.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function subscriptionUsesPublicKey(subscription: PushSubscription, publicKey: string): boolean {
  const options = subscription.options as PushSubscriptionOptionsInit & { applicationServerKey?: BufferSource | null }
  const current = options.applicationServerKey
  if (!current) return true
  const currentBuffer = current instanceof ArrayBuffer
    ? current
    : current.buffer.slice(current.byteOffset, current.byteOffset + current.byteLength)
  return arrayBufferToUrlBase64(currentBuffer) === publicKey.replace(/=+$/g, '')
}

async function publicKey(): Promise<PublicKeyPayload> {
  return apiJson<PublicKeyPayload>('/api/push/public-key', fallbackPublicKey)
}

async function existingRegistration(): Promise<ServiceWorkerRegistration | undefined> {
  if (!browserSupportsPush()) return undefined
  return ensureRegistration()
}

async function ensureRegistration(): Promise<ServiceWorkerRegistration> {
  const registration = await navigator.serviceWorker.register(SERVICE_WORKER_URL, SERVICE_WORKER_OPTIONS)
  try {
    await registration.update()
  } catch {
    // L'aggiornamento del service worker non deve bloccare l'attivazione push.
  }
  return registration
}

function subscriptionPayload(subscription: PushSubscription): Record<string, unknown> {
  const payload = subscription.toJSON()
  return {
    endpoint: payload.endpoint,
    keys: payload.keys,
    deviceLabel: navigator.platform || '',
  }
}

async function syncServerSubscription(subscription: PushSubscription): Promise<PushActionResult> {
  return apiPostJson<PushActionResult>(
    '/api/push/subscribe',
    subscriptionPayload(subscription),
    fallbackAction,
  )
}

async function showLocalTestNotification(result: PushActionResult): Promise<PushActionResult> {
  if (!result.ok || !Number(result.sent || 0) || !browserSupportsPush() || Notification.permission !== 'granted') {
    return result
  }
  try {
    const registration = await ensureRegistration()
    const notificationOptions: ExtendedNotificationOptions = {
      body: 'Notifica di test pronta nel gestionale.',
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/badge-96.png',
      tag: result.notificationId || 'iusentra-test-device',
      data: {
        href: '/notifiche',
        notificationId: result.notificationId || '',
        source: 'device-test',
      },
      renotify: true,
      requireInteraction: false,
      silent: false,
      timestamp: Date.now(),
      vibrate: [120],
    }
    await registration.showNotification('IUSENTRA', notificationOptions)
    return {
      ...result,
      message: 'Notifica di test inviata e mostrata su questo dispositivo.',
    }
  } catch {
    return {
      ...result,
      message: 'Il server ha inviato il push, ma il dispositivo non ha mostrato la notifica locale: controlla le notifiche di Chrome/Android per app.iusentra.it.',
    }
  }
}

async function currentSubscription(publicKeyValue: string, options: { create: boolean }): Promise<PushSubscription | null> {
  const { create } = options
  const registration = create ? await ensureRegistration() : await existingRegistration()
  if (!registration) return null
  let subscription = await registration.pushManager.getSubscription()
  if (subscription && !subscriptionUsesPublicKey(subscription, publicKeyValue)) {
    await subscription.unsubscribe()
    subscription = null
  }
  if (!subscription && create) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToArrayBuffer(publicKeyValue),
    })
  }
  return subscription
}

export async function getPushDeviceStatus(): Promise<PushDeviceStatus> {
  const enabled = await isFeatureFlagEnabled('routes.appV2.notifications.mobilePush')
  if (!enabled) {
    return {
      supported: browserSupportsPush(),
      enabled: false,
      configured: false,
      active: false,
      permission: currentPermission(),
      message: 'Notifiche su dispositivo non attive per questo studio.',
    }
  }
  if (!browserSupportsPush()) {
    return {
      supported: false,
      enabled: true,
      configured: false,
      active: false,
      permission: 'unsupported',
      message: 'Questo browser/dispositivo non supporta Web Push.',
    }
  }
  const key = await publicKey()
  const configured = Boolean(key.ok && key.configured && key.publicKey)
  const permission = currentPermission()
  const subscription = configured && key.publicKey
    ? await currentSubscription(key.publicKey, { create: false })
    : null
  const sync = subscription ? await syncServerSubscription(subscription) : null
  const serverActive = Boolean(sync?.ok && sync.active !== false)
  let message = key.message || fallbackPublicKey.message || ''
  if (!configured) {
    message = 'Sistema notifiche non ancora configurato sul server.'
  } else if (serverActive) {
    message = 'Notifiche attive su questo dispositivo.'
  } else if (subscription) {
    message = sync?.message || 'Dispositivo rilevato, ma registrazione server non confermata: premi Attiva notifiche.'
  } else if (permission === 'denied') {
    message = 'Le notifiche sono bloccate nelle impostazioni del browser o del dispositivo.'
  } else {
    message = 'Notifiche pronte: puoi attivarle su questo dispositivo.'
  }
  return {
    supported: true,
    enabled: key.enabled !== false,
    configured,
    active: serverActive,
    permission,
    message,
    diagnostics: key.diagnostics,
  }
}

export async function activatePushNotifications(): Promise<PushActionResult> {
  const enabled = await isFeatureFlagEnabled('routes.appV2.notifications.mobilePush')
  if (!enabled) {
    return { ok: false, message: 'Notifiche su dispositivo non attive per questo studio.' }
  }
  if (!browserSupportsPush()) {
    return { ok: false, message: 'Questo browser/dispositivo non supporta Web Push.' }
  }
  const key = await publicKey()
  if (!key.ok || !key.publicKey) {
    return { ok: false, message: key.message || 'Notifiche su dispositivo non configurate nel sistema.' }
  }
  const permission = await new Promise<NotificationPermission | 'timeout' | 'error'>((resolve) => {
    let completed = false
    const finish = (value: NotificationPermission | 'timeout' | 'error') => {
      if (completed) return
      completed = true
      window.clearTimeout(timeoutId)
      resolve(value)
    }
    const timeoutId = window.setTimeout(() => finish('timeout'), 15_000)
    void Notification.requestPermission()
      .then((value) => finish(value))
      .catch(() => finish('error'))
  })
  if (permission === 'timeout') {
    return {
      ok: false,
      message: 'Richiesta permesso non completata dal browser. Controlla il popup delle notifiche e riprova.',
    }
  }
  if (permission === 'error') {
    return { ok: false, message: 'Il browser non ha completato la richiesta del permesso notifiche.' }
  }
  if (permission !== 'granted') {
    return { ok: false, message: 'Autorizzazione notifiche non concessa.' }
  }
  const subscription = await currentSubscription(key.publicKey, { create: true })
  if (!subscription) return { ok: false, active: false, message: 'Subscription dispositivo non disponibile.' }
  return syncServerSubscription(subscription)
}

export async function deactivatePushNotifications(): Promise<PushActionResult> {
  const enabled = await isFeatureFlagEnabled('routes.appV2.notifications.mobilePush')
  if (!enabled) {
    return { ok: false, message: 'Notifiche su dispositivo non attive per questo studio.' }
  }
  if (!browserSupportsPush()) return { ok: false, message: 'Notifiche non supportate su questo dispositivo.' }
  const registration = await existingRegistration()
  const subscription = registration ? await registration.pushManager.getSubscription() : null
  const response = await apiPostJson<PushActionResult>(
    '/api/push/subscribe',
    { endpoint: subscription?.endpoint || '' },
    fallbackAction,
    { method: 'DELETE' },
  )
  if (subscription) await subscription.unsubscribe()
  return response
}

export async function sendPushTest(): Promise<PushActionResult> {
  const enabled = await isFeatureFlagEnabled('routes.appV2.notifications.mobilePush')
  if (!enabled) return { ok: false, message: 'Notifiche su dispositivo non attive per questo studio.' }
  if (browserSupportsPush()) {
    const key = await publicKey()
    if (key.ok && key.publicKey) {
      const subscription = await currentSubscription(key.publicKey, { create: false })
      if (subscription) {
        const sync = await syncServerSubscription(subscription)
        if (!sync.ok || sync.active === false) {
          return { ok: false, active: false, message: sync.message || 'Dispositivo non registrato sul server.' }
        }
      }
    }
  }
  const response = await apiPostJson<PushActionResult>('/api/push/test', {}, fallbackAction)
  if (response.ok) notifyTopbarChanged()
  return showLocalTestNotification(response)
}
