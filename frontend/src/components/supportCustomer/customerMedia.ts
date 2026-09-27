import type { AgentScreenRelay } from './agentScreenRelay'
import {
  browserScreenShareSupported,
  errorName,
  requestMicrophoneStream,
  requestScreenStream,
  stopStream,
} from './mediaCapture'
import type { SupportConsent } from './types'

/**
 * acquireMedia() dello script legacy: consenso allo schermo obbligatorio,
 * microfono facoltativo con avvio senza audio se negato, schermo dal browser
 * (getDisplayMedia) e, in mancanza, agente locale (Local Signer / IUSENTRA Assistenza).
 */

export type CustomerMediaStreams = {
  /** Flusso inviato in WebRTC: schermo + microfono, oppure solo microfono con l'agente locale. */
  localStream: MediaStream | null
  micStream: MediaStream | null
  screenStream: MediaStream | null
}

type AcquireOptions = {
  consent: SupportConsent
  micMuted: boolean
  relay: AgentScreenRelay
  /** Sessione avviata e non chiusa: serve a segnalare l'interruzione dal browser. */
  isActive: () => boolean
  onStatus: (text: string) => void
  onNotice: (text: string) => void
  onMicMuted: (muted: boolean) => void
}

export const SCREEN_CONSENT_REQUIRED_MESSAGE = 'Per continuare devi autorizzare la condivisione schermo.'
export const SCREEN_SHARE_UNAVAILABLE_MESSAGE =
  'Condivisione schermo non disponibile. Consenti la condivisione quando il browser la richiede, '
  + "oppure usa Local Signer aggiornato o l'agente IUSENTRA Assistenza per il controllo completo del PC."

async function acquireMicrophone(options: AcquireOptions): Promise<{ micStream: MediaStream | null; tracks: MediaStreamTrack[] }> {
  if (!options.consent.audio) {
    options.onMicMuted(false)
    return { micStream: null, tracks: [] }
  }
  let micStream: MediaStream | null = null
  try {
    micStream = await requestMicrophoneStream()
    const tracks = micStream.getAudioTracks()
    tracks.forEach((track) => {
      track.enabled = !options.micMuted
    })
    return { micStream, tracks }
  } catch (error) {
    stopStream(micStream)
    options.onMicMuted(true)
    console.warn('Microfono non autorizzato o non disponibile sul PC: assistenza avviata senza audio.', error)
    options.onNotice('Microfono non disponibile: assistenza avviata senza audio.')
    options.onStatus('Microfono non disponibile: assistenza avviata senza audio')
    return { micStream: null, tracks: [] }
  }
}

async function acquireBrowserScreen(options: AcquireOptions): Promise<MediaStream | null> {
  if (!browserScreenShareSupported()) return null
  try {
    const screenStream = await requestScreenStream()
    const screenTracks = screenStream.getVideoTracks()
    if (!screenTracks.length) {
      stopStream(screenStream)
      return null
    }
    // Se il cliente ferma la condivisione dalla barra del browser, lo si segnala.
    screenTracks[0].addEventListener('ended', () => {
      if (options.isActive()) {
        options.onStatus('Condivisione schermo interrotta dal cliente')
        options.onNotice('Hai interrotto la condivisione dello schermo.')
      }
    })
    return screenStream
  } catch (displayError) {
    // Richiesta annullata o non consentita dal browser: si prova l'agente locale.
    console.warn('getDisplayMedia non disponibile, provo agente locale.', displayError)
    if (errorName(displayError) === 'NotAllowedError') {
      options.onNotice("Condivisione schermo dal browser annullata: provo l'agente locale se installato.")
    }
    return null
  }
}

export async function acquireCustomerMedia(options: AcquireOptions): Promise<CustomerMediaStreams> {
  if (!options.consent.screen) throw new Error(SCREEN_CONSENT_REQUIRED_MESSAGE)

  const { micStream, tracks: audioTracks } = await acquireMicrophone(options)

  // 1) Percorso primario: condivisione nativa del browser, lo schermo viaggia in WebRTC.
  const screenStream = await acquireBrowserScreen(options)
  if (screenStream) {
    options.onStatus('Schermo condiviso')
    return {
      localStream: new MediaStream([...screenStream.getVideoTracks(), ...audioTracks]),
      micStream,
      screenStream,
    }
  }

  // 2) Fallback: Local Signer o agente locale IUSENTRA Assistenza (fotogrammi sul canale realtime).
  try {
    await options.relay.start()
    return {
      localStream: audioTracks.length ? new MediaStream(audioTracks) : null,
      micStream,
      screenStream: null,
    }
  } catch (agentError) {
    console.error('Né condivisione browser né agente locale disponibili.', agentError)
    stopStream(micStream)
    throw new Error(SCREEN_SHARE_UNAVAILABLE_MESSAGE)
  }
}
