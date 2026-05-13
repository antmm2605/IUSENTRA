import { apiJson, apiPostJson } from '@/lib/apiClient'
import { isFeatureFlagEnabled } from '@/lib/featureFlags'

export type PushPermission = NotificationPermission | 'unsupported'

export type PushDeviceStatus = {
  supported: boolean
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
}

type PublicKeyPayload = {
  ok: boolean
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

async function publicKey(): Promise<PublicKeyPayload> {
  return apiJson<PublicKeyPayload>('/api/push/public-key', fallbackPublicKey)
}

async function existingRegistration(): Promise<ServiceWorkerRegistration | undefined> {
  if (!browserSupportsPush()) return undefined
  return navigator.serviceWorker.getRegistration('/')
}

async function ensureRegistration(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.register('/sw.js', { scope: '/' })
}

function subscriptionPayload(subscription: PushSubscription): Record<string, unknown> {
  const payload = subscription.toJSON()
  return {
    endpoint: payload.endpoint,
    keys: payload.keys,
    deviceLabel: navigator.platform || '',
  }
}

export async function getPushDeviceStatus(): Promise<PushDeviceStatus> {
  const enabled = await isFeatureFlagEnabled('notifications.mobilePush')
  if (!enabled) {
    return {
      supported: browserSupportsPush(),
      configured: false,
      active: false,
      permission: currentPermission(),
      message: 'Notifiche su dispositivo non attive per questo studio.',
    }
  }
  if (!browserSupportsPush()) {
    return {
      supported: false,
      configured: false,
      active: false,
      permission: 'unsupported',
      message: 'Questo browser/dispositivo non supporta Web Push.',
    }
  }
  const key = await publicKey()
  const registration = await existingRegistration()
  const subscription = registration ? await registration.pushManager.getSubscription() : null
  const configured = Boolean(key.ok && key.configured && key.publicKey)
  const permission = currentPermission()
  let message = key.message || fallbackPublicKey.message || ''
  if (!configured) {
    message = 'Sistema notifiche non ancora configurato sul server.'
  } else if (subscription) {
    message = 'Notifiche attive su questo dispositivo.'
  } else if (permission === 'denied') {
    message = 'Le notifiche sono bloccate nelle impostazioni del browser o del dispositivo.'
  } else {
    message = 'Notifiche pronte: puoi attivarle su questo dispositivo.'
  }
  return {
    supported: true,
    configured,
    active: Boolean(subscription),
    permission,
    message,
    diagnostics: key.diagnostics,
  }
}

export async function activatePushNotifications(): Promise<PushActionResult> {
  const enabled = await isFeatureFlagEnabled('notifications.mobilePush')
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
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    return { ok: false, message: 'Autorizzazione notifiche non concessa.' }
  }
  const registration = await ensureRegistration()
  let subscription = await registration.pushManager.getSubscription()
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToArrayBuffer(key.publicKey),
    })
  }
  return apiPostJson<PushActionResult>(
    '/api/push/subscribe',
    subscriptionPayload(subscription),
    fallbackAction,
  )
}

export async function deactivatePushNotifications(): Promise<PushActionResult> {
  const enabled = await isFeatureFlagEnabled('notifications.mobilePush')
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

export function sendPushTest(): Promise<PushActionResult> {
  return isFeatureFlagEnabled('notifications.mobilePush').then((enabled) => {
    if (!enabled) return { ok: false, message: 'Notifiche su dispositivo non attive per questo studio.' }
    return apiPostJson<PushActionResult>('/api/push/test', {}, fallbackAction)
  })
}
