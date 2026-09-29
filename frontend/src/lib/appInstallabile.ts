import { registraServiceWorker } from '@/lib/pushNotifications'

/**
 * App installabile (PWA): registra il service worker all'avvio dello studio, così l'app installata
 * mostra «Sei offline» invece di una pagina d'errore, e conserva l'invito all'installazione del
 * browser per il pulsante «Installa IUSENTRA» delle Impostazioni.
 */

type InvitoInstallazione = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> }

let invito: InvitoInstallazione | null = null
let avviata = false
const ascoltatori = new Set<() => void>()
const avvisa = () => ascoltatori.forEach((fn) => fn())

export function avviaAppInstallabile(): void {
  if (avviata || typeof window === 'undefined') return
  avviata = true
  window.addEventListener('beforeinstallprompt', (evento) => {
    evento.preventDefault()
    invito = evento as InvitoInstallazione
    avvisa()
  })
  window.addEventListener('appinstalled', () => { invito = null; avvisa() })
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return
  // Dopo l'avvio, senza attendere risorse esterne lente: la registrazione non blocca la pagina.
  window.setTimeout(() => { void registraServiceWorker().catch(() => undefined) }, 2000)
}

export function appInstallata(): boolean {
  if (typeof window === 'undefined') return false
  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone === true
  return standalone || window.matchMedia?.('(display-mode: standalone)').matches === true
}

export function dispositivoApple(): boolean {
  return typeof navigator !== 'undefined' && /iphone|ipad|ipod/i.test(navigator.userAgent)
}

export function installazioneDisponibile(): boolean {
  return invito !== null
}

export async function installaApp(): Promise<'accepted' | 'dismissed' | 'non_disponibile'> {
  if (!invito) return 'non_disponibile'
  const corrente = invito
  await corrente.prompt()
  const scelta = await corrente.userChoice
  invito = null
  avvisa()
  return scelta.outcome
}

export function ascoltaInstallazione(fn: () => void): () => void {
  ascoltatori.add(fn)
  return () => { ascoltatori.delete(fn) }
}
