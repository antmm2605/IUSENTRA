import {
  Bell,
  Bot,
  CheckCircle2,
  ChevronRight,
  Copy,
  FileText,
  HelpCircle,
  KeyRound,
  Loader2,
  Mic,
  MicOff,
  Navigation,
  PencilLine,
  RotateCw,
  Search,
  ShieldCheck,
  Trash2,
  UserPlus,
  Volume2,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ALL_STUDIO_VOICE_COMMANDS,
  MAX_STORED_VOICE_NOTES,
  MAX_VOICE_NOTE_TIMEOUT_MS,
  VOICE_NOTE_TIME_ZONE,
  VOICE_ROUTE_COMMANDS,
  buildClientConfirmation,
  compactVoiceNoteText,
  emptyVoiceClientDraft,
  extractSpokenPin,
  findStudioVoiceCommand,
  formatItalianDictationText,
  isVoiceNoteStartCommand,
  isVoiceNoteStopCommand,
  isVoiceCancel,
  isVoiceConfirmation,
  isDictationPolishCommand,
  isVoiceNegativeConfirmation,
  labelForClientField,
  nextMissingClientField,
  normalizeVoiceText,
  parseClientCorrectionField,
  parseVoiceNoteReminder,
  parseStudioSearchTerm,
  parseVoiceClientField,
  stripVoiceDictationCommand,
  stripVoiceNoteStartCommand,
  stripVoiceNoteStopPhrases,
  voiceCommandSummary,
  type StudioVoiceCommand,
  type VoiceClientDraft,
  type VoiceClientField,
  type VoiceNote,
} from '../studioVoiceAssistant'

type SpeechRecognitionAlternativeLike = { transcript: string }
type SpeechRecognitionResultLike = { readonly length: number; isFinal?: boolean; [index: number]: SpeechRecognitionAlternativeLike }
type SpeechRecognitionEventLike = { resultIndex?: number; results: ArrayLike<SpeechRecognitionResultLike> }
type SpeechRecognitionLike = {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives?: number
  start: () => void
  stop: () => void
  abort?: () => void
  onstart: (() => void) | null
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error?: string }) => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike
type IusentraVoiceInputService = {
  canAttach?: (target: Element | null | undefined) => boolean
  startForActiveField?: (options?: {
    context?: string
    lang?: string
    silenceMs?: number
    onStart?: () => void
    onTranscript?: (transcript: string, interim: boolean) => void
    onInserted?: (text: string) => void
  }) => Promise<string>
  insertTextIntoTarget?: (target: Element | null | undefined, text: string, options?: { selectInserted?: boolean }) => string
  formatDictationText?: (text: string) => string
  stop?: () => void
}
type StudioVoiceWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor
  webkitSpeechRecognition?: SpeechRecognitionConstructor
  IusentraVoiceInput?: IusentraVoiceInputService
}

type VoiceSignature = {
  energy: number
  centroid: number
  variance: number
  capturedAt: string
}

type VoiceProfile = {
  version: 1
  pinHash: string
  signature: VoiceSignature
  createdAt: string
  calibrationSeconds?: number
}

type ClientStep = VoiceClientField | 'confirm' | 'review' | 'saving' | 'success' | 'idle'
type VoicePanelTab = 'configurazione' | 'comandi' | 'richieste' | 'note'
type NotificationCapability = NotificationPermission | 'unsupported'
type MicrophonePermissionState = PermissionState | 'unsupported' | 'unknown'

const PROFILE_STORAGE_KEY = 'iusentra:studio-voice-profile'
const ACTIVATION_PHRASE_STORAGE_KEY = 'iusentra:studio-voice-activation-phrase'
const LISTENING_SESSION_STORAGE_KEY = 'iusentra:studio-voice-listening-active'
const OPERATIVE_SESSION_STORAGE_KEY = 'iusentra:studio-voice-operative-active'
const COMMAND_FEEDBACK_STORAGE_KEY = 'iusentra:studio-voice-command-feedback'
const NOTE_TRIGGER_STORAGE_KEY = 'iusentra:studio-voice-note-trigger'
const NOTES_STORAGE_KEY = 'iusentra:studio-voice-notes'
const PIN_SALT = 'iusentra-studio-voice-pin-v1'
const VOICE_MATCH_MIN_SCORE = 0.08
const VOICE_MIN_AUDIBLE_ENERGY = 0.8
const VOICE_CALIBRATION_SECONDS = 30
const VOICE_CALIBRATION_MS = VOICE_CALIBRATION_SECONDS * 1000
const VOICE_ACTIVATION_SAMPLE_MS = 2500
const VOICE_LISTENING_RESTART_MS = 650
const VOICE_CALIBRATION_MIN_TEXT_MATCH = 62
const DEFAULT_ACTIVATION_PHRASE = 'Studio'
const DEFAULT_NOTE_TRIGGER_PHRASE = 'note'
const PIN_LISTENING_PROMPT = 'Sto ascoltando il PIN. Pronuncia solo le cifre oppure inseriscile a mano.'
const MAX_PIN_VOICE_ATTEMPTS = 3

function navigateStudioRoute(href: string) {
  const target = new URL(href, window.location.origin)
  if (target.origin !== window.location.origin) {
    window.location.assign(href)
    return
  }

  const next = `${target.pathname}${target.search}${target.hash}`
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`
  if (next !== current) {
    window.history.pushState({}, '', next)
  }
  const routeEvent = typeof PopStateEvent === 'function'
    ? new PopStateEvent('popstate', { state: window.history.state })
    : new Event('popstate')
  window.dispatchEvent(routeEvent)
  window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
}

function resolveCurrentRecordEditRoute(commandId: string): { href: string; message: string } {
  const path = window.location.pathname
  if (commandId.includes('soggetto')) {
    const subjectMatch = path.match(/^\/soggetti\/([^/?#]+)/)
    const id = subjectMatch?.[1]
    if (id && id !== 'nuovo') {
      return {
        href: `/soggetti/${encodeURIComponent(id)}/modifica`,
        message: 'Apro la modifica del soggetto o della parte corrente.',
      }
    }
    return {
      href: '/soggetti',
      message: 'Apro Soggetti e Parti. Seleziona il soggetto da modificare.',
    }
  }

  const clientMatch = path.match(/^\/clienti\/([^/?#]+)/)
  const id = clientMatch?.[1]
  if (id && id !== 'nuovo') {
    return {
      href: `/clienti/${encodeURIComponent(id)}/modifica`,
      message: 'Apro la modifica del cliente corrente.',
    }
  }
  return {
    href: '/clienti',
    message: 'Apro Clienti. Seleziona il cliente da modificare.',
  }
}
const VOICE_CALIBRATION_TEXT = 'Studio legale IUSENTRA. Autorizzo l’assistente vocale dello studio. Apri panoramica, clienti, calendario e fascicoli. La mia voce è naturale, chiara, costante e professionale. Ripeto con lo stesso tono: autorizzo l’assistente dello studio.'
const CALIBRATION_KEYWORD_GROUPS = [
  ['studio'],
  ['legale'],
  ['iusentra', 'ius entra', 'i u sentra', 'ios entra', 'ios centro', 'iosentra', 'io sentra', 'iusenso', 'iossenso'],
  ['autorizzo', 'autorizza', 'autorizzato'],
  ['assistente'],
  ['vocale', 'voce'],
  ['panoramica'],
  ['clienti', 'cliente'],
  ['calendario'],
  ['fascicoli', 'fascicolo'],
  ['naturale'],
  ['chiara', 'chiaro'],
  ['costante'],
  ['professionale'],
]

function audioCaptureErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : (error as { name?: string } | null)?.name || ''
  const message = error instanceof Error ? error.message : String(error || '')
  const normalized = `${name} ${message}`.toLowerCase()

  if (!window.isSecureContext) {
    return 'Il microfono richiede una connessione sicura. Apri IUSENTRA da https oppure da 127.0.0.1 e riprova.'
  }
  if (['NotAllowedError', 'SecurityError', 'PermissionDeniedError'].includes(name) || /permission|denied|notallowed/.test(normalized)) {
    return 'Il browser non ha concesso il microfono. Controlla la card Microfono e riprova.'
  }
  if (['NotFoundError', 'DevicesNotFoundError'].includes(name) || /not found|no device|devices/.test(normalized)) {
    return 'Nessun microfono trovato. Collega o abilita un microfono e riprova.'
  }
  if (['NotReadableError', 'TrackStartError'].includes(name) || /could not start|notreadable|busy|occup/.test(normalized)) {
    return 'Microfono occupato da un altro programma. Chiudi la registrazione attiva e riprova.'
  }
  if (name === 'OverconstrainedError') {
    return 'Il microfono non accetta le impostazioni richieste. Riprova con il microfono predefinito del dispositivo.'
  }
  return message || 'Registrazione non completata. Controlla il microfono e riprova.'
}

function microphoneGrantedButStreamBlockedMessage(): string {
  return 'Chrome indica il microfono come consentito, ma la registrazione non parte. Seleziona il microfono corretto nel popup, chiudi eventuali registrazioni aperte e controlla che Windows consenta il microfono a Chrome.'
}

function isMicrophonePermissionError(error: unknown): boolean {
  const name = error instanceof DOMException ? error.name : (error as { name?: string } | null)?.name || ''
  const message = error instanceof Error ? error.message : String(error || '')
  return ['NotAllowedError', 'SecurityError', 'PermissionDeniedError'].includes(name) || /permission|denied|notallowed/i.test(`${name} ${message}`)
}

async function hasNamedAudioInputDevice(): Promise<boolean> {
  if (!navigator.mediaDevices?.enumerateDevices) return false
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    return devices.some((device) => device.kind === 'audioinput' && Boolean(device.label?.trim()))
  } catch {
    return false
  }
}

async function readMicrophonePermission(): Promise<MicrophonePermissionState> {
  if (!navigator.mediaDevices?.getUserMedia) return 'unsupported'
  const permissionsApi = navigator.permissions
  if (!permissionsApi?.query) {
    return await hasNamedAudioInputDevice() ? 'granted' : 'unknown'
  }
  try {
    const status = await permissionsApi.query({ name: 'microphone' as PermissionName })
    if (status.state !== 'granted' && await hasNamedAudioInputDevice()) {
      return 'granted'
    }
    return status.state
  } catch {
    return await hasNamedAudioInputDevice() ? 'granted' : 'unknown'
  }
}

function microphonePermissionLabel(state: MicrophonePermissionState): string {
  if (state === 'granted') return 'consentito'
  if (state === 'denied') return 'bloccato'
  if (state === 'prompt') return 'da autorizzare'
  if (state === 'unsupported') return 'non disponibile'
  return 'da verificare'
}

function microphonePermissionDescription(state: MicrophonePermissionState): string {
  if (state === 'granted') return 'Puoi registrare il tono di voce e attivare l’assistente.'
  if (state === 'denied') return 'Il browser ha negato il permesso: abilita il microfono e verifica di nuovo.'
  if (state === 'prompt') return 'Premi Verifica microfono e scegli Consenti quando il browser lo chiede.'
  if (state === 'unsupported') return 'Questo browser non espone un microfono utilizzabile.'
  return 'Premi Verifica microfono prima di registrare voce e PIN.'
}

async function requestMicrophoneStream(): Promise<MediaStream> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  await Promise.all(stream.getAudioTracks().map((track) => {
    if (!track.applyConstraints) return Promise.resolve()
    return track.applyConstraints({
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    }).catch(() => undefined)
  }))
  return stream
}

function chromeSiteMicrophoneSettingsUrl(): string {
  return `chrome://settings/content/siteDetails?site=${encodeURIComponent(window.location.origin)}`
}

function browserSiteMicrophoneSettingsUrl(protocol: string): string {
  return `${protocol}://settings/content/siteDetails?site=${encodeURIComponent(window.location.origin)}`
}

function detectBrowserRuntime() {
  const navWithUserAgentData = navigator as Navigator & {
    userAgentData?: { brands?: Array<{ brand: string; version?: string }> }
  }
  const userAgent = navigator.userAgent || ''
  const brands = navWithUserAgentData.userAgentData?.brands?.map((brand) => brand.brand).join(' ') || ''
  const fingerprint = `${userAgent} ${brands}`
  const isEdgeLike = /Edg\/|Microsoft Edge/i.test(fingerprint)
  const isChromeLike = /Chrome\/|Google Chrome|Chromium/i.test(fingerprint) && !isEdgeLike
  const isEmbedded = /Electron|WebView|wv|Codex/i.test(fingerprint)

  if (isChromeLike) {
    return {
      name: isEmbedded ? 'browser incorporato' : 'Chrome',
      settingsUrl: isEmbedded ? '' : chromeSiteMicrophoneSettingsUrl(),
      isEmbedded,
    }
  }
  if (isEdgeLike) {
    return {
      name: isEmbedded ? 'browser incorporato' : 'Edge',
      settingsUrl: browserSiteMicrophoneSettingsUrl('edge'),
      isEmbedded,
    }
  }
  return {
    name: isEmbedded ? 'browser incorporato' : 'browser in uso',
    settingsUrl: '',
    isEmbedded,
  }
}

function alternateLocalAppUrl(): string {
  const { protocol, hostname, port, pathname, search, hash } = window.location
  const alternateHost = hostname === 'localhost'
    ? '127.0.0.1'
    : hostname === '127.0.0.1'
      ? 'localhost'
      : ''
  if (!alternateHost) return ''
  return `${protocol}//${alternateHost}${port ? `:${port}` : ''}${pathname}${search}${hash}`
}

function getRecognitionConstructor(): SpeechRecognitionConstructor | null {
  const target = window as StudioVoiceWindow
  return target.SpeechRecognition || target.webkitSpeechRecognition || null
}

function loadProfile(): VoiceProfile | null {
  try {
    const stored = window.localStorage.getItem(PROFILE_STORAGE_KEY)
    if (!stored) return null
    const parsed = JSON.parse(stored) as VoiceProfile
    if (parsed?.version === 1 && parsed.pinHash && parsed.signature) return parsed
  } catch {
    return null
  }
  return null
}

function saveProfile(profile: VoiceProfile) {
  window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile))
}

function normalizeActivationPhrase(value: string | null | undefined): string {
  return value?.trim() || DEFAULT_ACTIVATION_PHRASE
}

function loadActivationPhrase(): string {
  try {
    return normalizeActivationPhrase(window.localStorage.getItem(ACTIVATION_PHRASE_STORAGE_KEY))
  } catch {
    return DEFAULT_ACTIVATION_PHRASE
  }
}

function saveActivationPhrase(value: string): string {
  const nextPhrase = normalizeActivationPhrase(value)
  window.localStorage.setItem(ACTIVATION_PHRASE_STORAGE_KEY, nextPhrase)
  return nextPhrase
}

function loadCommandFeedback(): string {
  try {
    return window.sessionStorage.getItem(COMMAND_FEEDBACK_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function loadListeningSessionActive(): boolean {
  try {
    return window.sessionStorage.getItem(LISTENING_SESSION_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function loadOperativeSessionActive(): boolean {
  try {
    return window.sessionStorage.getItem(OPERATIVE_SESSION_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function saveOperativeSessionActive(active: boolean) {
  try {
    if (active) {
      window.sessionStorage.setItem(OPERATIVE_SESSION_STORAGE_KEY, '1')
    } else {
      window.sessionStorage.removeItem(OPERATIVE_SESSION_STORAGE_KEY)
    }
  } catch {
    // La sessione operativa è un aiuto locale: l'ascolto resta governato dallo stato React.
  }
}

function saveListeningSessionActive(active: boolean) {
  try {
    if (active) {
      window.sessionStorage.setItem(LISTENING_SESSION_STORAGE_KEY, '1')
    } else {
      window.sessionStorage.removeItem(LISTENING_SESSION_STORAGE_KEY)
    }
  } catch {
    // La persistenza di sessione è un aiuto locale: l'ascolto resta governato dallo stato React.
  }
}

async function copyTextToClipboard(value: string): Promise<boolean> {
  try {
    await navigator.clipboard?.writeText(value)
    return true
  } catch {
    // Chrome non concede sempre Clipboard API su pagine locali o con permessi bloccati.
  }

  try {
    const field = document.createElement('textarea')
    field.value = value
    field.setAttribute('readonly', 'true')
    field.style.position = 'fixed'
    field.style.left = '-9999px'
    field.style.top = '0'
    document.body.appendChild(field)
    field.select()
    field.setSelectionRange(0, field.value.length)
    const copied = document.execCommand('copy')
    document.body.removeChild(field)
    return copied
  } catch {
    return false
  }
}

function saveCommandFeedback(message: string) {
  try {
    window.sessionStorage.setItem(COMMAND_FEEDBACK_STORAGE_KEY, message)
  } catch {
    // Lo stato resta visibile almeno fino al cambio pagina corrente.
  }
}

function normalizeNoteTriggerPhrase(value: string | null | undefined, activationPhrase = DEFAULT_ACTIVATION_PHRASE): string {
  let normalized = normalizeVoiceText(value || DEFAULT_NOTE_TRIGGER_PHRASE)
  const normalizedActivation = normalizeVoiceText(activationPhrase)
  if (normalizedActivation && normalized.startsWith(`${normalizedActivation} `)) {
    normalized = normalized.slice(normalizedActivation.length).trim()
  }
  normalized = normalized.replace(/^studio\s+/, '').replace(/^iusentra\s+/, '').trim()
  return normalized || DEFAULT_NOTE_TRIGGER_PHRASE
}

function loadNoteTriggerPhrase(): string {
  try {
    return normalizeNoteTriggerPhrase(window.localStorage.getItem(NOTE_TRIGGER_STORAGE_KEY))
  } catch {
    return DEFAULT_NOTE_TRIGGER_PHRASE
  }
}

function saveNoteTriggerPhrase(value: string, activationPhrase: string): string {
  const nextPhrase = normalizeNoteTriggerPhrase(value, activationPhrase)
  window.localStorage.setItem(NOTE_TRIGGER_STORAGE_KEY, nextPhrase)
  return nextPhrase
}

function notificationCapability(): NotificationCapability {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported'
  return Notification.permission
}

function voiceNoteId(): string {
  return window.crypto?.randomUUID?.() || `voice-note-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function loadVoiceNotes(): VoiceNote[] {
  try {
    const stored = window.localStorage.getItem(NOTES_STORAGE_KEY)
    if (!stored) return []
    const parsed = JSON.parse(stored) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((item): item is VoiceNote => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) return false
        const record = item as Record<string, unknown>
        return typeof record.id === 'string' && typeof record.text === 'string' && typeof record.createdAt === 'string'
      })
      .map((item) => ({
        id: item.id,
        text: item.text,
        createdAt: item.createdAt,
        targetAt: typeof item.targetAt === 'string' ? item.targetAt : null,
        notifyAt: typeof item.notifyAt === 'string' ? item.notifyAt : null,
        notifiedAt: typeof item.notifiedAt === 'string' ? item.notifiedAt : null,
      }))
      .slice(0, MAX_STORED_VOICE_NOTES)
  } catch {
    return []
  }
}

function saveVoiceNotes(notes: VoiceNote[]) {
  window.localStorage.setItem(NOTES_STORAGE_KEY, JSON.stringify(notes.slice(0, MAX_STORED_VOICE_NOTES)))
}

function formatItalianDateTime(value: string | Date): string {
  const parsed = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'data non disponibile'
  return new Intl.DateTimeFormat('it-IT', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: VOICE_NOTE_TIME_ZONE,
  }).format(parsed)
}

function transcriptIncludesCalibrationAlias(normalizedTranscript: string, spokenTokens: Set<string>, alias: string): boolean {
  const normalizedAlias = normalizeVoiceText(alias)
  if (!normalizedAlias) return false
  if (normalizedAlias.includes(' ')) return normalizedTranscript.includes(normalizedAlias)
  return spokenTokens.has(normalizedAlias)
}

function scoreCalibrationTranscript(transcript: string): number {
  const normalizedTranscript = normalizeVoiceText(transcript)
  if (!normalizedTranscript) return 0
  const spokenTokens = new Set(normalizedTranscript.split(' ').filter(Boolean))
  const matched = CALIBRATION_KEYWORD_GROUPS.filter((group) => (
    group.some((alias) => transcriptIncludesCalibrationAlias(normalizedTranscript, spokenTokens, alias))
  )).length
  return Math.round((matched / CALIBRATION_KEYWORD_GROUPS.length) * 100)
}

function calibrationQualityMessage(match: number): string {
  if (match >= 86) return 'Lettura chiara: il profilo vocale può essere salvato.'
  if (match >= VOICE_CALIBRATION_MIN_TEXT_MATCH) return 'Lettura sufficiente: il profilo può essere salvato, ma resta meglio parlare lentamente e tenere il microfono vicino.'
  return 'Lettura non abbastanza chiara: ripeti la registrazione scandendo la frase consigliata e riducendo i rumori di fondo.'
}

async function hashPin(pin: string): Promise<string> {
  const source = `${PIN_SALT}:${pin.trim()}`
  if (window.crypto?.subtle) {
    const digest = await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(source))
    return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('')
  }
  return window.btoa(source)
}

function averageSignature(samples: VoiceSignature[]): VoiceSignature {
  const total = samples.reduce(
    (acc, sample) => ({
      energy: acc.energy + sample.energy,
      centroid: acc.centroid + sample.centroid,
      variance: acc.variance + sample.variance,
    }),
    { energy: 0, centroid: 0, variance: 0 },
  )
  const count = Math.max(1, samples.length)
  return {
    energy: total.energy / count,
    centroid: total.centroid / count,
    variance: total.variance / count,
    capturedAt: new Date().toISOString(),
  }
}

function compareSignature(sample: VoiceSignature, profile: VoiceSignature): number {
  const energy = Math.abs(sample.energy - profile.energy) / Math.max(1, profile.energy, sample.energy)
  const centroid = Math.abs(sample.centroid - profile.centroid) / Math.max(1, profile.centroid, sample.centroid)
  const variance = Math.abs(sample.variance - profile.variance) / Math.max(1, profile.variance, sample.variance)
  return Math.max(0, 1 - (energy + centroid + variance) / 3)
}

function voiceSampleLooksAudible(sample: VoiceSignature): boolean {
  return sample.energy >= VOICE_MIN_AUDIBLE_ENERGY || sample.variance >= 1.5
}

function voiceActivationAccepted(score: number, sample: VoiceSignature): boolean {
  return score >= VOICE_MATCH_MIN_SCORE || voiceSampleLooksAudible(sample)
}

async function captureVoiceSignature(durationMs = 950, onProgress?: (progress: number) => void): Promise<VoiceSignature> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('Microfono non disponibile nel browser.')
  }
  let stream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  try {
    stream = await requestMicrophoneStream()
    const AudioContextCtor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioContextCtor) {
      throw new Error('Controllo audio non disponibile nel browser.')
    }
    audioContext = new AudioContextCtor()
    if (audioContext.state === 'suspended') {
      await audioContext.resume().catch(() => undefined)
    }
    const source = audioContext.createMediaStreamSource(stream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)
    const frequencies = new Uint8Array(analyser.frequencyBinCount)
    const waveform = new Uint8Array(analyser.fftSize)
    const startedAt = performance.now()
    const metrics: VoiceSignature[] = []
    onProgress?.(0)
    while (performance.now() - startedAt < durationMs) {
      analyser.getByteFrequencyData(frequencies)
      analyser.getByteTimeDomainData(waveform)
      const energy = waveform.reduce((sum, value) => sum + Math.abs(value - 128), 0) / waveform.length
      const weighted = frequencies.reduce((sum, value, index) => sum + value * index, 0)
      const total = frequencies.reduce((sum, value) => sum + value, 0) || 1
      const centroid = weighted / total
      const mean = total / frequencies.length
      const variance = frequencies.reduce((sum, value) => sum + Math.abs(value - mean), 0) / frequencies.length
      metrics.push({ energy, centroid, variance, capturedAt: new Date().toISOString() })
      onProgress?.(Math.min(100, Math.round(((performance.now() - startedAt) / durationMs) * 100)))
      await new Promise((resolve) => window.setTimeout(resolve, 250))
    }
    onProgress?.(100)
    return averageSignature(metrics)
  } finally {
    stream?.getTracks().forEach((track) => track.stop())
    if (audioContext && audioContext.state !== 'closed') {
      await audioContext.close().catch(() => undefined)
    }
  }
}

function speakItalianThen(text: string, after?: () => void) {
  if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
    after?.()
    return
  }
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'it-IT'
  utterance.rate = 0.96
  utterance.volume = 1
  utterance.pitch = 1
  const italianVoice = window.speechSynthesis.getVoices().find((voice) => (
    voice.lang.toLocaleLowerCase('it-IT').startsWith('it')
  ))
  if (italianVoice) utterance.voice = italianVoice
  let completed = false
  let fallbackTimer: number | null = null
  const finish = () => {
    if (completed) return
    completed = true
    if (fallbackTimer !== null) window.clearTimeout(fallbackTimer)
    after?.()
  }
  if (after) {
    fallbackTimer = window.setTimeout(finish, Math.min(9000, Math.max(1400, text.length * 90)))
    utterance.onend = finish
    utterance.onerror = finish
  }
  window.speechSynthesis.resume?.()
  window.speechSynthesis.speak(utterance)
}

function speakItalian(text: string) {
  speakItalianThen(text)
}

function speakItalianAndWait(text: string): Promise<void> {
  return new Promise((resolve) => speakItalianThen(text, resolve))
}

function commandIcon(command: StudioVoiceCommand) {
  if (command.kind === 'note-flow') return <FileText size={15} />
  if (command.kind === 'dictation') return <Mic size={15} />
  if (command.kind === 'edit-current-record') return <PencilLine size={15} />
  if (command.kind === 'search') return <Search size={15} />
  if (command.kind === 'new-client-flow') return <UserPlus size={15} />
  if (command.kind === 'lex') return <Bot size={15} />
  if (command.kind === 'reload') return <RotateCw size={15} />
  if (command.kind === 'help') return <HelpCircle size={15} />
  return <Navigation size={15} />
}

export function StudioVoiceAssistant({ activePath }: { activePath: string }) {
  const [open, setOpen] = useState(false)
  const [profile, setProfile] = useState<VoiceProfile | null>(() => loadProfile())
  const [pin, setPin] = useState('')
  const [pinCheck, setPinCheck] = useState('')
  const [activationWaitingPin, setActivationWaitingPin] = useState(false)
  const [showManualPinEntry, setShowManualPinEntry] = useState(false)
  const [enabled, setEnabled] = useState(() => Boolean(profile) && loadListeningSessionActive())
  const [operativeSession, setOperativeSession] = useState(() => Boolean(profile) && loadListeningSessionActive() && loadOperativeSessionActive())
  const [listening, setListening] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(() => (Boolean(profile) && loadListeningSessionActive()
    ? 'Riprendo il richiamo vocale in questa scheda.'
    : 'Assistente pronto per la configurazione.'))
  const [lastTranscript, setLastTranscript] = useState('')
  const [lastCommandAction, setLastCommandAction] = useState(() => loadCommandFeedback())
  const [transcriptHistory, setTranscriptHistory] = useState<string[]>([])
  const [activationPhrase, setActivationPhrase] = useState(() => loadActivationPhrase())
  const [savedActivationPhrase, setSavedActivationPhrase] = useState(() => loadActivationPhrase())
  const [calibrationProgress, setCalibrationProgress] = useState(0)
  const [calibrationRemaining, setCalibrationRemaining] = useState(0)
  const [calibrationTranscript, setCalibrationTranscript] = useState('')
  const [calibrationMatch, setCalibrationMatch] = useState(0)
  const [activeTab, setActiveTab] = useState<VoicePanelTab>('configurazione')
  const [microphonePermission, setMicrophonePermission] = useState<MicrophonePermissionState>('unknown')
  const [microphoneLastCheckedAt, setMicrophoneLastCheckedAt] = useState('')
  const [microphoneHelpOpen, setMicrophoneHelpOpen] = useState(false)
  const [noteTriggerPhrase, setNoteTriggerPhrase] = useState(() => loadNoteTriggerPhrase())
  const [savedNoteTriggerPhrase, setSavedNoteTriggerPhrase] = useState(() => loadNoteTriggerPhrase())
  const [voiceNotes, setVoiceNotes] = useState<VoiceNote[]>(() => loadVoiceNotes())
  const [noteMode, setNoteMode] = useState(false)
  const [draftNote, setDraftNote] = useState('')
  const [notificationPermission, setNotificationPermission] = useState<NotificationCapability>(() => notificationCapability())
  const [clientDraft, setClientDraft] = useState<VoiceClientDraft>(() => emptyVoiceClientDraft())
  const [clientStep, setClientStep] = useState<ClientStep>('idle')
  const [clientMessage, setClientMessage] = useState('')
  const [clientHref, setClientHref] = useState('')
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const recognitionRestartTimerRef = useRef<number | null>(null)
  const enabledRef = useRef(enabled)
  const operativeSessionRef = useRef(operativeSession)
  const listeningSessionRestoreAttemptedRef = useRef(false)
  const savedActivationPhraseRef = useRef(savedActivationPhrase)
  const savedNoteTriggerPhraseRef = useRef(savedNoteTriggerPhrase)
  const clientStepRef = useRef(clientStep)
  const clientDraftRef = useRef(clientDraft)
  const noteModeRef = useRef(noteMode)
  const pendingFieldDictationRef = useRef(false)
  const noteBufferRef = useRef('')
  const microphonePermissionRef = useRef<MicrophonePermissionState>(microphonePermission)
  const reminderTimersRef = useRef<number[]>([])
  const calibrationTranscriptRef = useRef('')
  const summary = useMemo(() => voiceCommandSummary(), [])
  const groupedCommands = useMemo(() => {
    const groups = new Map<string, StudioVoiceCommand[]>()
    for (const command of ALL_STUDIO_VOICE_COMMANDS) {
      const entries = groups.get(command.group) || []
      entries.push(command)
      groups.set(command.group, entries)
    }
    return Array.from(groups.entries())
  }, [])
  const browserRuntime = useMemo(() => detectBrowserRuntime(), [])
  const chromeSettingsAddress = browserRuntime.settingsUrl || chromeSiteMicrophoneSettingsUrl()
  const currentPageAddress = typeof window !== 'undefined' ? window.location.href : ''
  const alternateMicrophoneUrl = useMemo(() => alternateLocalAppUrl(), [])

  const refreshMicrophonePermission = async (options: { announceGrant?: boolean } = {}) => {
    const previous = microphonePermissionRef.current
    const permission = await readMicrophonePermission()
    const checkedAt = formatItalianDateTime(new Date())
    setMicrophonePermission(permission)
    microphonePermissionRef.current = permission
    if (permission === 'granted') {
      setMicrophoneLastCheckedAt(checkedAt)
      setMicrophoneHelpOpen(false)
      if (options.announceGrant && previous !== 'granted') {
        setStatus(`Microfono consentito alle ${checkedAt}. Ora puoi registrare voce e PIN.`)
      }
    }
    return permission
  }

  const openChromeMicrophoneUnlock = async () => {
    setMicrophoneHelpOpen(true)
    const copied = await copyTextToClipboard(chromeSettingsAddress)

    let opened = false
    try {
      opened = Boolean(window.open(chromeSettingsAddress, '_blank', 'noopener,noreferrer'))
    } catch {
      opened = false
    }

    setStatus(opened
      ? `Ho aperto le impostazioni microfono di ${browserRuntime.name}. Dopo aver impostato Consenti, torna qui e premi Verifica di nuovo.`
      : copied
        ? `Ho copiato l’indirizzo delle impostazioni di ${browserRuntime.name}. Imposta Microfono su Consenti e torna qui con Verifica di nuovo.`
        : `Non posso aprire automaticamente le impostazioni di ${browserRuntime.name}. Usa l’icona dei permessi nella barra indirizzi e poi premi Verifica di nuovo.`)
  }

  const copyChromeMicrophoneAddress = async () => {
    const copied = await copyTextToClipboard(chromeSettingsAddress)
    setStatus(copied
      ? `Indirizzo delle impostazioni copiato. Imposta Microfono su Consenti e poi premi Verifica di nuovo.`
      : 'Copia non riuscita. Seleziona l’indirizzo mostrato nei dettagli e riprova.')
  }

  const copyCurrentPageAddress = async () => {
    const copied = await copyTextToClipboard(currentPageAddress)
    setStatus(copied
      ? 'Indirizzo della pagina copiato. Aprilo in Chrome o Edge e poi premi Verifica microfono.'
      : 'Copia non riuscita. Copia l’indirizzo dalla barra del browser e aprilo in Chrome o Edge.')
  }

  const openAlternateMicrophoneAddress = () => {
    if (!alternateMicrophoneUrl) return
    setStatus('Apro la stessa copia locale di IUSENTRA con un indirizzo alternativo per richiedere di nuovo il consenso.')
    window.location.assign(alternateMicrophoneUrl)
  }

  const verifyMicrophoneAccess = async (silent = false): Promise<boolean> => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicrophonePermission('unsupported')
      setMicrophoneHelpOpen(true)
      if (!silent) setStatus('Microfono non disponibile nel browser.')
      return false
    }

    await refreshMicrophonePermission()
    setBusy(true)
    if (!silent) setStatus('Verifica microfono in corso. Se il browser chiede il permesso, scegli Consenti.')
    let stream: MediaStream | null = null
    try {
      stream = await requestMicrophoneStream()
      const checkedAt = formatItalianDateTime(new Date())
      setMicrophonePermission('granted')
      microphonePermissionRef.current = 'granted'
      setMicrophoneLastCheckedAt(checkedAt)
      setMicrophoneHelpOpen(false)
      if (!silent) setStatus(`Microfono autorizzato alle ${checkedAt}. Ora puoi registrare voce e PIN.`)
      return true
    } catch (error) {
      const checkedAt = formatItalianDateTime(new Date())
      const permissionError = isMicrophonePermissionError(error)
      const currentPermission = await readMicrophonePermission()
      const chromeAllowsMicrophone = currentPermission === 'granted'
      const nextPermission = permissionError && !chromeAllowsMicrophone ? 'denied' : chromeAllowsMicrophone ? 'granted' : 'unknown'
      setMicrophonePermission(nextPermission)
      microphonePermissionRef.current = nextPermission
      setMicrophoneLastCheckedAt(checkedAt)
      setMicrophoneHelpOpen(!chromeAllowsMicrophone)
      if (!silent) {
        setStatus(permissionError && chromeAllowsMicrophone
          ? `${microphoneGrantedButStreamBlockedMessage()} Controllo reale: ${checkedAt}.`
          : permissionError
            ? `Microfono non concesso dal browser. Controllo reale: ${checkedAt}.`
          : audioCaptureErrorMessage(error))
      }
      return false
    } finally {
      stream?.getTracks().forEach((track) => track.stop())
      setBusy(false)
    }
  }

  useEffect(() => {
    enabledRef.current = enabled
    saveListeningSessionActive(Boolean(profile) && enabled)
  }, [enabled, profile])

  useEffect(() => {
    operativeSessionRef.current = operativeSession
    saveOperativeSessionActive(Boolean(profile) && enabled && operativeSession)
  }, [operativeSession, enabled, profile])

  useEffect(() => {
    microphonePermissionRef.current = microphonePermission
  }, [microphonePermission])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    let permissionStatus: PermissionStatus | null = null

    const syncMicrophone = async (announceGrant = false) => {
      if (cancelled) return
      await refreshMicrophonePermission({ announceGrant })
    }

    void syncMicrophone(false)

    const onFocus = () => {
      void syncMicrophone(true)
    }
    const onVisibilityChange = () => {
      if (!document.hidden) void syncMicrophone(true)
    }
    const onDeviceChange = () => {
      void syncMicrophone(true)
    }

    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibilityChange)
    navigator.mediaDevices?.addEventListener?.('devicechange', onDeviceChange)

    if (navigator.permissions?.query) {
      void navigator.permissions.query({ name: 'microphone' as PermissionName }).then((status) => {
        if (cancelled) return
        permissionStatus = status
        permissionStatus.onchange = () => {
          void syncMicrophone(true)
        }
      }).catch(() => undefined)
    }

    const timer = window.setInterval(() => {
      void syncMicrophone(true)
    }, 2500)

    return () => {
      cancelled = true
      window.clearInterval(timer)
      permissionStatus && (permissionStatus.onchange = null)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      navigator.mediaDevices?.removeEventListener?.('devicechange', onDeviceChange)
    }
  }, [open])

  useEffect(() => {
    savedActivationPhraseRef.current = savedActivationPhrase
  }, [savedActivationPhrase])

  useEffect(() => {
    savedNoteTriggerPhraseRef.current = savedNoteTriggerPhrase
  }, [savedNoteTriggerPhrase])

  useEffect(() => {
    clientStepRef.current = clientStep
  }, [clientStep])

  useEffect(() => {
    clientDraftRef.current = clientDraft
  }, [clientDraft])

  useEffect(() => {
    noteModeRef.current = noteMode
  }, [noteMode])

  useEffect(() => {
    calibrationTranscriptRef.current = calibrationTranscript
  }, [calibrationTranscript])

  useEffect(() => {
    reminderTimersRef.current.forEach((timer) => window.clearTimeout(timer))
    reminderTimersRef.current = []

    const schedule = (note: VoiceNote) => {
      if (!note.notifyAt || note.notifiedAt) return
      const notifyAt = new Date(note.notifyAt).getTime()
      if (!Number.isFinite(notifyAt)) return

      const scheduleNext = () => {
        const remaining = notifyAt - Date.now()
        if (remaining > MAX_VOICE_NOTE_TIMEOUT_MS) {
          reminderTimersRef.current.push(window.setTimeout(scheduleNext, MAX_VOICE_NOTE_TIMEOUT_MS))
          return
        }
        reminderTimersRef.current.push(window.setTimeout(() => showNoteReminder(note), Math.max(0, remaining)))
      }

      scheduleNext()
    }

    voiceNotes.forEach(schedule)
    return () => {
      reminderTimersRef.current.forEach((timer) => window.clearTimeout(timer))
      reminderTimersRef.current = []
    }
  }, [voiceNotes])

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort?.()
      recognitionRef.current?.stop()
      reminderTimersRef.current.forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  const rememberTranscript = (transcript: string) => {
    setLastTranscript(transcript)
    setTranscriptHistory((current) => [transcript, ...current.filter((item) => item !== transcript)].slice(0, 5))
  }

  const rememberCommandAction = (message: string) => {
    setLastCommandAction(message)
    saveCommandFeedback(message)
  }

  const saveCustomActivationPhrase = () => {
    const nextPhrase = saveActivationPhrase(activationPhrase)
    setActivationPhrase(nextPhrase)
    setSavedActivationPhrase(nextPhrase)
    savedActivationPhraseRef.current = nextPhrase
    setStatus(`Frase di attivazione salvata: “${nextPhrase}”.`)
  }

  const saveCustomNoteTriggerPhrase = () => {
    const currentActivationPhrase = savedActivationPhraseRef.current || DEFAULT_ACTIVATION_PHRASE
    const nextPhrase = saveNoteTriggerPhrase(noteTriggerPhrase, currentActivationPhrase)
    setNoteTriggerPhrase(nextPhrase)
    setSavedNoteTriggerPhrase(nextPhrase)
    savedNoteTriggerPhraseRef.current = nextPhrase
    setActiveTab('note')
    setStatus(`Comando note salvato: "${currentActivationPhrase}, ${nextPhrase}".`)
    rememberCommandAction(`Comando note personalizzato: "${currentActivationPhrase}, ${nextPhrase}".`)
  }

  const updateVoiceNotes = (updater: (current: VoiceNote[]) => VoiceNote[]) => {
    setVoiceNotes((current) => {
      const next = updater(current).slice(0, MAX_STORED_VOICE_NOTES)
      saveVoiceNotes(next)
      return next
    })
  }

  const showNoteReminder = (note: VoiceNote) => {
    const reminderText = compactVoiceNoteText(note.text, 220)
    setOpen(true)
    setActiveTab('note')
    setStatus(`Promemoria nota: ${reminderText}`)
    rememberCommandAction(`Promemoria nota mostrato in ora italiana: ${reminderText}`)
    speakItalian(`Promemoria nota. ${reminderText}`)

    if ('Notification' in window && Notification.permission === 'granted') {
      try {
        const notification = new Notification('Promemoria nota Studio', {
          body: reminderText,
          tag: note.id,
          requireInteraction: true,
        })
        notification.onclick = () => {
          window.focus()
          setOpen(true)
          setActiveTab('note')
          notification.close()
        }
      } catch {
        setStatus('Promemoria interno mostrato. Il browser richiede notifiche tramite servizio dedicato.')
      }
    }

    updateVoiceNotes((current) => current.map((item) => (item.id === note.id ? { ...item, notifiedAt: new Date().toISOString() } : item)))
  }

  const requestNotificationPermission = async () => {
    if (!('Notification' in window)) {
      setNotificationPermission('unsupported')
      setStatus('Questo browser non supporta le notifiche di sistema. Userò solo avvisi interni quando IUSENTRA è aperto.')
      return
    }

    if (Notification.permission === 'granted') {
      setNotificationPermission('granted')
      setStatus('Notifiche già abilitate. I promemoria note verranno mostrati 10 minuti prima, se IUSENTRA resta aperto.')
      return
    }

    setBusy(true)
    try {
      const permission = await Notification.requestPermission()
      setNotificationPermission(permission)
      setStatus(
        permission === 'granted'
          ? 'Notifiche abilitate. I promemoria note verranno mostrati 10 minuti prima, se IUSENTRA resta aperto.'
          : 'Notifiche non abilitate. Le note restano salvate e vedrai solo avvisi interni mentre IUSENTRA è aperto.',
      )
    } finally {
      setBusy(false)
    }
  }

  const finishVoiceNote = (transcript = 'fine nota') => {
    const noteText = formatItalianDictationText(noteBufferRef.current)
    noteBufferRef.current = ''
    setDraftNote('')
    setNoteMode(false)
    noteModeRef.current = false
    setActiveTab('note')

    if (!noteText) {
      setStatus('Nota vuota: non ho salvato nulla.')
      rememberCommandAction('Nota vocale vuota non salvata.')
      speakItalian('Nota vuota, non salvo nulla.')
      return
    }

    const reminder = parseVoiceNoteReminder(noteText)
    const note: VoiceNote = {
      id: voiceNoteId(),
      text: noteText,
      createdAt: new Date().toISOString(),
      targetAt: reminder ? reminder.targetAt.toISOString() : null,
      notifyAt: reminder ? reminder.notifyAt.toISOString() : null,
      notifiedAt: null,
    }

    updateVoiceNotes((current) => [note, ...current])
    rememberTranscript(transcript)

    if (reminder) {
      const targetLabel = formatItalianDateTime(reminder.targetAt)
      const notifyLabel = formatItalianDateTime(reminder.notifyAt)
      setStatus(`Nota salvata. Evento: ${targetLabel}. Promemoria browser: ${notifyLabel}, 10 minuti prima.`)
      rememberCommandAction(`Nota salvata con promemoria in ora italiana: ${notifyLabel}.`)
      speakItalian('Nota salvata. Ti avviso dieci minuti prima.')
    } else {
      setStatus('Nota salvata. Non ho trovato insieme data e ora, quindi non ho programmato un promemoria.')
      rememberCommandAction('Nota salvata senza promemoria: data e ora non riconosciute insieme.')
      speakItalian('Nota salvata, senza promemoria.')
    }
  }

  const appendVoiceNoteTranscript = (transcript: string) => {
    if (isDictationPolishCommand(transcript)) {
      const polished = formatItalianDictationText(noteBufferRef.current)
      noteBufferRef.current = polished
      setDraftNote(polished)
      setStatus(polished ? 'Punteggiatura e spaziatura della nota corrette.' : 'Non ho ancora testo da correggere nella nota.')
      rememberCommandAction('Dettatura nota rifinita con correzione locale di punteggiatura e spaziatura.')
      return
    }
    const parsed = stripVoiceNoteStopPhrases(transcript)
    const formattedText = formatItalianDictationText(parsed.text)
    if (formattedText) {
      noteBufferRef.current = formatItalianDictationText(`${noteBufferRef.current} ${formattedText}`)
      setDraftNote(noteBufferRef.current)
      setStatus('Nota in registrazione. Di’ "fine nota" per salvarla.')
    }
    if (parsed.shouldStop || isVoiceNoteStopCommand(transcript)) {
      finishVoiceNote(transcript)
    }
  }

  const beginVoiceNote = (transcript = savedNoteTriggerPhraseRef.current) => {
    const currentActivationPhrase = savedActivationPhraseRef.current || DEFAULT_ACTIVATION_PHRASE
    const currentNoteTriggerPhrase = savedNoteTriggerPhraseRef.current || DEFAULT_NOTE_TRIGGER_PHRASE
    if (!enabledRef.current) {
      setOpen(true)
      setActiveTab('note')
      setStatus('Attiva prima l’assistente con voce e PIN, poi usa il comando note personalizzato.')
      rememberCommandAction(`Note vocali in attesa: attiva l'ascolto e pronuncia "${currentActivationPhrase}, ${currentNoteTriggerPhrase}".`)
      return
    }

    const inlineNote = stripVoiceNoteStartCommand(transcript, currentNoteTriggerPhrase)
    noteBufferRef.current = ''
    setDraftNote('')
    setNoteMode(true)
    noteModeRef.current = true
    setOpen(true)
    setActiveTab('note')
    rememberCommandAction(`Dettatura nota avviata con "${currentActivationPhrase}, ${currentNoteTriggerPhrase}".`)

    if (inlineNote) {
      appendVoiceNoteTranscript(inlineNote)
      return
    }

    setStatus('Sto registrando la nota. Dettala liberamente e chiudi con "fine nota" o "fine note".')
    speakItalian('Registro la nota. Dimmi fine nota quando hai terminato.')
  }

  const deleteVoiceNote = (id: string) => {
    updateVoiceNotes((current) => current.filter((note) => note.id !== id))
    setStatus('Nota vocale eliminata da questo dispositivo.')
    rememberCommandAction('Nota vocale eliminata.')
  }

  const activationCommandFromTranscript = (transcript: string): { wakeOnly: boolean; commandText: string } => {
    const normalizedTranscript = normalizeVoiceText(transcript)
    const normalizedPhrase = normalizeVoiceText(savedActivationPhraseRef.current || DEFAULT_ACTIVATION_PHRASE)
    if (!normalizedPhrase) return { wakeOnly: false, commandText: '' }
    const acceptedWakePhrases = [
      normalizedPhrase,
      `lo ${normalizedPhrase}`,
      `ok ${normalizedPhrase}`,
      `ehi ${normalizedPhrase}`,
      `ciao ${normalizedPhrase}`,
      ...(normalizedPhrase === 'iusentra' ? ['ius entra', 'ios entra', 'ios centro', 'iosentra', 'io sentra'] : []),
    ]
    for (const phrase of acceptedWakePhrases) {
      if (normalizedTranscript === phrase) return { wakeOnly: true, commandText: '' }
      if (normalizedTranscript.startsWith(`${phrase} `)) {
        return { wakeOnly: false, commandText: normalizedTranscript.slice(phrase.length).trim() }
      }
    }
    return { wakeOnly: false, commandText: '' }
  }

  const askClientField = (field: VoiceClientField) => {
    const label = labelForClientField(field)
    const message = `Dimmi ${label} del cliente.`
    setStatus(message)
    setClientMessage(message)
    speakItalian(message)
  }

  const cancelClientFlow = () => {
    const message = 'Inserimento cliente annullato. Nessun cliente è stato aggiunto.'
    setClientStep('idle')
    setClientDraft(emptyVoiceClientDraft())
    setClientHref('')
    setClientMessage(message)
    setStatus(message)
    speakItalian(message)
  }

  const askClientReviewChoice = () => {
    const message = 'Non inserisco il cliente per ora. Vuoi annullare tutto oppure modificare nome, cognome o codice fiscale?'
    setClientStep('review')
    setClientMessage(message)
    setStatus(message)
    speakItalian(message)
  }

  const askClientCorrectionField = (field: VoiceClientField) => {
    const label = labelForClientField(field)
    const message = `Va bene, modifico ${label}. Dimmi il nuovo ${label} del cliente.`
    setClientStep(field)
    setClientMessage(message)
    setStatus(message)
    speakItalian(message)
  }

  const beginClientFlow = () => {
    const draft = emptyVoiceClientDraft()
    setClientDraft(draft)
    setClientHref('')
    setClientMessage('')
    setClientStep('nome')
    setOpen(true)
    setActiveTab('richieste')
    askClientField('nome')
  }

  const applyClientFieldValue = (field: { field: VoiceClientField; value: string }) => {
    const updated = { ...clientDraftRef.current, [field.field]: field.value }
    setClientDraft(updated)
    const missing = nextMissingClientField(updated)
    if (missing) {
      setClientStep(missing)
      askClientField(missing)
      return
    }
    const confirmation = buildClientConfirmation(updated)
    setClientStep('confirm')
    setClientMessage(`Ho aggiornato ${labelForClientField(field.field)}. ${confirmation}`)
    setStatus('Rileggi i dati e conferma.')
    speakItalian(`Ho aggiornato ${labelForClientField(field.field)}. ${confirmation}`)
  }

  const clearRecognitionRestartTimer = () => {
    if (recognitionRestartTimerRef.current !== null) {
      window.clearTimeout(recognitionRestartTimerRef.current)
      recognitionRestartTimerRef.current = null
    }
  }

  const stopCurrentRecognition = () => {
    clearRecognitionRestartTimer()
    const recognition = recognitionRef.current
    recognitionRef.current = null
    if (!recognition) return
    recognition.onstart = null
    recognition.onresult = null
    recognition.onerror = null
    recognition.onend = null
    try {
      recognition.abort?.()
    } catch {
      // Il browser puo' gia' avere chiuso il motore di ascolto.
    }
    try {
      recognition.stop()
    } catch {
      // Nessuna azione: lo stato React viene riallineato subito sotto.
    }
  }

  const scheduleContinuousRecognitionRestart = (message?: string) => {
    if (!enabledRef.current) return
    clearRecognitionRestartTimer()
    if (message) setStatus(message)
    recognitionRestartTimerRef.current = window.setTimeout(() => {
      recognitionRestartTimerRef.current = null
      if (enabledRef.current) startContinuousRecognition({ restarted: true })
    }, VOICE_LISTENING_RESTART_MS)
  }

  const stopListening = (message = 'Assistente vocale disattivato.') => {
    enabledRef.current = false
    operativeSessionRef.current = false
    saveListeningSessionActive(false)
    saveOperativeSessionActive(false)
    stopCurrentRecognition()
    setEnabled(false)
    setOperativeSession(false)
    setListening(false)
    setNoteMode(false)
    noteModeRef.current = false
    noteBufferRef.current = ''
    setDraftNote('')
    setActivationWaitingPin(false)
    setShowManualPinEntry(false)
    setStatus(message)
    rememberCommandAction('Ascolto disattivato. Puoi riattivarlo dalla sezione Configurazione.')
    speakItalian(message)
  }

  const activateOperativeSession = (options: { commandText?: string; announce?: boolean } = {}) => {
    operativeSessionRef.current = true
    saveOperativeSessionActive(true)
    setOperativeSession(true)
    const message = options.commandText
      ? 'Sessione operativa attiva: eseguo il comando richiesto.'
      : 'Sessione operativa attiva. Puoi compilare i campi e cambiare pagina; di’ “stop” quando hai finito.'
    setStatus(message)
    rememberCommandAction('Sessione operativa attiva. I comandi funzionano senza ripetere la frase di attivazione.')
    if (options.announce !== false && !options.commandText) {
      speakItalian('Sessione operativa attiva.')
    }
  }

  const pauseOperativeSession = () => {
    pendingFieldDictationRef.current = false
    operativeSessionRef.current = false
    saveOperativeSessionActive(false)
    setOperativeSession(false)
    setStatus(`Sessione operativa sospesa. Di’ “${savedActivationPhraseRef.current}” per riattivare i comandi.`)
    rememberCommandAction(`Sessione operativa sospesa. L’assistente resta pronto al richiamo “${savedActivationPhraseRef.current}”.`)
    speakItalian('Sessione operativa sospesa.')
  }

  const voiceRecallReadyMessage = () => (
    `Richiamo pronto. Di’ “${savedActivationPhraseRef.current}” per attivare la sessione operativa. Di’ “stop” per bloccare la sessione operativa e tornare al richiamo.`
  )

  const openLex = () => {
    const detail = {
      context: 'assistente-vocale',
      title: 'Lex AI',
      body: 'Aperto dall’assistente vocale nel contesto della pagina corrente.',
      pagePath: activePath || window.location.pathname,
    }
    window.dispatchEvent(new CustomEvent('iusentra:lex-context', { detail }))
    window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex', { detail }))
    setStatus('Lex AI aperto nel contesto corrente.')
    rememberCommandAction('Comando eseguito: Lex AI aperto nel contesto corrente.')
  }

  const confirmClient = async () => {
    const draft = clientDraftRef.current
    const missing = nextMissingClientField(draft)
    if (missing) {
      setClientStep(missing)
      askClientField(missing)
      return
    }
    setClientStep('saving')
    setClientMessage('Sto aggiungendo il cliente.')
    try {
      const response = await fetch('/api/v1/ui/clienti/voce/crea', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(draft),
      })
      const responseData = await response.json().catch(() => ({}))
      if (!response.ok || !responseData?.ok) {
        const message = String(responseData?.message || 'Cliente non aggiunto. Controlla i dati obbligatori.')
        setClientStep('confirm')
        setClientMessage(message)
        setStatus(message)
        speakItalian(message)
        return
      }
      const message = String(responseData.message || 'Cliente aggiunto.')
      const href = String(responseData.redirect || `/clienti/${responseData.id || ''}`)
      setClientHref(href)
      setClientStep('success')
      setClientMessage(message)
      setStatus(message)
      speakItalian(message)
    } catch {
      const message = 'Cliente non aggiunto. Verifica la connessione dello studio e riprova.'
      setClientStep('confirm')
      setClientMessage(message)
      setStatus(message)
      speakItalian(message)
    }
  }

  const processClientTranscript = (transcript: string): boolean => {
    const step = clientStepRef.current
    if (step === 'idle' || step === 'success') return false
    if (isVoiceCancel(transcript)) {
      cancelClientFlow()
      return true
    }
    if (step === 'confirm') {
      const directField = parseVoiceClientField(transcript)
      if (directField) {
        applyClientFieldValue(directField)
        return true
      }
      const correctionField = parseClientCorrectionField(transcript)
      if (correctionField) {
        askClientCorrectionField(correctionField)
        return true
      }
      if (isVoiceNegativeConfirmation(transcript)) {
        askClientReviewChoice()
        return true
      }
      if (isVoiceConfirmation(transcript)) {
        void confirmClient()
        return true
      }
      const message = `${buildClientConfirmation(clientDraftRef.current)} Se i dati sono corretti dì “confermo”. Se non sono corretti dì “no”, oppure “modifica nome”, “modifica cognome” o “modifica codice fiscale”.`
      setClientMessage(message)
      speakItalian(message)
      return true
    }
    if (step === 'review') {
      const directField = parseVoiceClientField(transcript)
      if (directField) {
        applyClientFieldValue(directField)
        return true
      }
      const correctionField = parseClientCorrectionField(transcript)
      if (correctionField) {
        askClientCorrectionField(correctionField)
        return true
      }
      const message = 'Dimmi “annulla tutto” per fermare l’inserimento oppure “modifica nome”, “modifica cognome” o “modifica codice fiscale”.'
      setClientMessage(message)
      speakItalian(message)
      return true
    }
    if (step === 'saving') return true
    const field = parseVoiceClientField(transcript, step)
    if (!field) {
      askClientField(step)
      return true
    }
    applyClientFieldValue(field)
    return true
  }

  const insertDictationIntoActiveField = (text: string, options: { passive?: boolean } = {}): boolean => {
    const voiceInput = (window as StudioVoiceWindow).IusentraVoiceInput
    const dictatedText = text.trim()
    if (!dictatedText) return false
    if (!voiceInput?.insertTextIntoTarget) {
      if (options.passive) return false
      setOpen(true)
      setStatus('Dettatura non disponibile in questa sessione.')
      rememberCommandAction('Dettatura non eseguita: servizio vocale non disponibile.')
      return false
    }
    try {
      const activeElement = typeof document !== 'undefined' ? document.activeElement : null
      const insertedText = voiceInput.insertTextIntoTarget(activeElement, dictatedText, { selectInserted: true })
      pendingFieldDictationRef.current = false
      setStatus(insertedText ? 'Testo dettato inserito nel campo selezionato.' : 'Nessun testo vocale rilevato.')
      rememberCommandAction(insertedText ? `Dettatura inserita: ${insertedText}` : 'Dettatura chiusa senza testo rilevato.')
      return Boolean(insertedText)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Dettatura non disponibile.'
      if (options.passive) return false
      setOpen(true)
      setStatus(message)
      rememberCommandAction(`Dettatura non eseguita: ${message}`)
      speakItalian(message)
      return false
    }
  }

  const tryPassiveFieldDictation = (text: string): boolean => {
    if (!operativeSessionRef.current) return false
    const voiceInput = (window as StudioVoiceWindow).IusentraVoiceInput
    if (!voiceInput?.insertTextIntoTarget) return false
    const activeElement = typeof document !== 'undefined' ? document.activeElement : null
    if (voiceInput.canAttach && !voiceInput.canAttach(activeElement)) {
      return insertDictationIntoActiveField(text, { passive: true })
    }
    return insertDictationIntoActiveField(text, { passive: true })
  }

  const isPendingDictationControlText = (text: string) => {
    const normalized = normalizeVoiceText(text)
    const activation = normalizeVoiceText(savedActivationPhraseRef.current || DEFAULT_ACTIVATION_PHRASE)
    return normalized === activation ||
      normalized === 'scrivi qui' ||
      normalized === 'detta' ||
      normalized === 'dettatura' ||
      normalized === 'avvia dettatura'
  }

  const stripPendingDictationActivationText = (text: string) => {
    const normalized = normalizeVoiceText(text)
    const activation = normalizeVoiceText(savedActivationPhraseRef.current || DEFAULT_ACTIVATION_PHRASE)
    if (!activation) return normalized || text.trim()
    const acceptedWakePhrases = [
      activation,
      `lo ${activation}`,
      `ok ${activation}`,
      `ehi ${activation}`,
      `ciao ${activation}`,
    ]
    for (const phrase of acceptedWakePhrases) {
      if (normalized === phrase) return ''
      if (normalized.startsWith(`${phrase} `)) return normalized.slice(phrase.length).trim()
    }
    return normalized || text.trim()
  }

  const preparePendingFieldDictation = () => {
    pendingFieldDictationRef.current = true
    setStatus('Dettatura pronta: dimmi ora il testo da inserire nel campo selezionato.')
    rememberCommandAction('Dettatura pronta nel campo selezionato. Dimmi il testo da inserire.')
    speakItalian('Dettatura pronta. Dimmi ora il testo da inserire.')
  }

  const startActiveFieldDictation = (initialText = '') => {
    if (initialText.trim()) {
      insertDictationIntoActiveField(initialText)
      return
    }
    if (enabledRef.current && listening) {
      preparePendingFieldDictation()
      return
    }

    const voiceInput = (window as StudioVoiceWindow).IusentraVoiceInput
    if (!voiceInput?.startForActiveField) {
      setOpen(true)
      setStatus('Dettatura non disponibile in questa sessione.')
      rememberCommandAction('Dettatura non eseguita: servizio vocale non disponibile.')
      return
    }

    setStatus('Controllo microfono per dettare nel campo selezionato.')
    rememberCommandAction('Dettatura richiesta nel campo selezionato.')
    void voiceInput.startForActiveField({
      context: 'studio-voice-active-field',
      lang: 'it-IT',
      silenceMs: 3200,
      onStart: () => {
        setStatus('Dettatura attiva: parla ora, il testo verrà inserito nel campo selezionato.')
        rememberCommandAction('Dettatura attiva nel campo selezionato.')
      },
      onTranscript: (detectedText) => {
        if (detectedText) {
          rememberCommandAction(`Sto ascoltando: ${detectedText}`)
        }
      },
      onInserted: (insertedText) => {
        rememberCommandAction(insertedText ? `Dettatura inserita: ${insertedText}` : 'Dettatura chiusa senza testo rilevato.')
      },
    }).then((insertedText) => {
      setStatus(insertedText ? 'Testo dettato inserito nel campo selezionato.' : 'Nessun testo vocale rilevato.')
    }).catch((error) => {
      const message = error instanceof Error ? error.message : 'Dettatura non disponibile.'
      setStatus(message)
      rememberCommandAction(`Dettatura non eseguita: ${message}`)
    })
  }

  const runCommand = (command: StudioVoiceCommand, transcript: string) => {
    if (command.kind === 'new-client-flow') {
      beginClientFlow()
      return
    }
    if (command.kind === 'edit-current-record') {
      const target = resolveCurrentRecordEditRoute(command.id)
      rememberCommandAction(target.message)
      setStatus(target.message)
      navigateStudioRoute(target.href)
      return
    }
    if (command.kind === 'note-flow') {
      beginVoiceNote(transcript)
      return
    }
    if (command.kind === 'dictation') {
      startActiveFieldDictation(stripVoiceDictationCommand(transcript))
      return
    }
    if (command.kind === 'search') {
      const term = parseStudioSearchTerm(transcript)
      if (!term) {
        setOpen(true)
        setStatus('Dimmi cosa vuoi cercare dopo il comando “cerca”.')
        rememberCommandAction('Ricerca non eseguita: manca il testo da cercare.')
        return
      }
      rememberCommandAction(`Comando eseguito: ricerca studio per "${term}".`)
      navigateStudioRoute(`/global-search?q=${encodeURIComponent(term)}`)
      return
    }
    if (command.kind === 'lex') {
      openLex()
      return
    }
    if (command.kind === 'help') {
      setOpen(true)
      setActiveTab('comandi')
      setStatus('Elenco comandi aperto.')
      rememberCommandAction('Comando eseguito: elenco comandi autorizzati aperto.')
      return
    }
    if (command.kind === 'back') {
      rememberCommandAction('Comando eseguito: ritorno alla pagina precedente.')
      window.history.back()
      return
    }
    if (command.kind === 'reload') {
      rememberCommandAction('Comando eseguito: ricarica pagina.')
      window.location.reload()
      return
    }
    if (command.kind === 'stop') {
      const normalizedStop = normalizeVoiceText(transcript)
      if (normalizedStop.includes('disattiva assistente') || normalizedStop.includes('chiudi assistente')) {
        stopListening()
      } else {
        pauseOperativeSession()
      }
      return
    }
    if (command.href) {
      rememberCommandAction(`Comando eseguito: apertura ${command.label}.`)
      navigateStudioRoute(command.href)
    }
  }

  const handleTranscript = (transcript: string) => {
    const clean = transcript.trim()
    if (!clean) return
    rememberTranscript(clean)
    const activation = activationCommandFromTranscript(clean)
    let commandTranscript = activation.commandText || clean

    if (!operativeSessionRef.current) {
      if (activation.wakeOnly) {
        activateOperativeSession()
        return
      }
      if (activation.commandText) {
        activateOperativeSession({ commandText: activation.commandText, announce: false })
      } else {
        setStatus(`Comandi sospesi. ${voiceRecallReadyMessage()}`)
        rememberCommandAction(`In attesa del richiamo “${savedActivationPhraseRef.current}”. Nessun comando operativo eseguito.`)
        return
      }
    } else if (activation.wakeOnly) {
      setStatus('Sessione operativa già attiva. Puoi pronunciare direttamente il comando.')
      rememberCommandAction('Sessione operativa già attiva.')
      return
    }

    if (noteModeRef.current) {
      appendVoiceNoteTranscript(commandTranscript)
      return
    }
    if (processClientTranscript(commandTranscript)) return
    if (pendingFieldDictationRef.current) {
      const pendingCommand = findStudioVoiceCommand(commandTranscript)
      if (pendingCommand?.kind === 'dictation' || isPendingDictationControlText(commandTranscript)) {
        setStatus('Dettatura pronta: dimmi solo il testo da inserire nel campo selezionato.')
        rememberCommandAction('Dettatura in attesa del testo da inserire.')
        return
      }
      if (pendingCommand) {
        pendingFieldDictationRef.current = false
      } else {
        const pendingText = stripVoiceDictationCommand(commandTranscript) || stripPendingDictationActivationText(commandTranscript)
        insertDictationIntoActiveField(pendingText)
        return
      }
    }
    if (isVoiceNoteStartCommand(commandTranscript, savedNoteTriggerPhraseRef.current)) {
      beginVoiceNote(commandTranscript)
      return
    }
    const command = findStudioVoiceCommand(commandTranscript)
    if (!command) {
      if (tryPassiveFieldDictation(commandTranscript)) {
        return
      }
      setStatus(`Comando non riconosciuto. Frase rilevata: “${clean}”.`)
      rememberCommandAction(`Comando non riconosciuto: "${clean}".`)
      return
    }
    setStatus(`Eseguo: ${command.label}.`)
    rememberCommandAction(`Comando richiesto: ${command.label}.`)
    runCommand(command, commandTranscript)
  }

  const startContinuousRecognition = (options: { restarted?: boolean; restored?: boolean } = {}) => {
    const Recognition = getRecognitionConstructor()
    if (!Recognition) {
      enabledRef.current = false
      saveListeningSessionActive(false)
      setEnabled(false)
      setStatus('Riconoscimento vocale non disponibile in questo browser.')
      return
    }
    stopCurrentRecognition()
    const recognition = new Recognition()
    recognition.lang = 'it-IT'
    recognition.continuous = true
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    recognition.onstart = () => {
      setListening(true)
      if (!options.restarted && !options.restored) {
        setOpen(true)
        setActiveTab('comandi')
      }
      const activeMessage = operativeSessionRef.current
        ? 'Sessione operativa attiva. Puoi pronunciare direttamente il comando; di’ “stop” quando hai finito.'
        : voiceRecallReadyMessage()
      setStatus(activeMessage)
      if (!options.restarted) {
        rememberCommandAction(options.restored
          ? (operativeSessionRef.current
              ? 'Sessione operativa ancora attiva dopo il cambio pagina.'
              : `Richiamo ancora pronto dopo il cambio pagina. ${voiceRecallReadyMessage()}`)
          : voiceRecallReadyMessage())
      }
    }
    recognition.onresult = (event) => {
      const startIndex = typeof event.resultIndex === 'number' ? event.resultIndex : 0
      for (let index = startIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index]?.[0]?.transcript || ''
        handleTranscript(transcript)
      }
    }
    recognition.onerror = (event) => {
      const error = event.error || ''
      setListening(false)
      if (error === 'not-allowed' || error === 'service-not-allowed') {
        enabledRef.current = false
        saveListeningSessionActive(false)
        setEnabled(false)
        setStatus('Ascolto non autorizzato dal browser. Verifica il microfono e riattiva l’assistente.')
        rememberCommandAction('Ascolto fermato: il browser non ha autorizzato il riconoscimento vocale.')
        return
      }
      if (enabledRef.current) {
        scheduleContinuousRecognitionRestart(
          error === 'no-speech'
            ? (operativeSessionRef.current
                ? 'Non ho sentito parole. La sessione operativa resta attiva.'
                : `Non ho sentito parole. ${voiceRecallReadyMessage()}`)
            : 'Ascolto interrotto dal browser. Lo riattivo automaticamente.',
        )
      }
    }
    recognition.onend = () => {
      setListening(false)
      if (enabledRef.current) {
        scheduleContinuousRecognitionRestart('Chrome ha chiuso temporaneamente l’ascolto. Lo riattivo automaticamente.')
      }
    }
    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch (error) {
      recognitionRef.current = null
      setListening(false)
      if (enabledRef.current) {
        scheduleContinuousRecognitionRestart('Ascolto non partito al primo tentativo. Riprovo automaticamente.')
      } else {
        setStatus(audioCaptureErrorMessage(error))
      }
    }
  }

  useEffect(() => {
    if (listeningSessionRestoreAttemptedRef.current) return
    listeningSessionRestoreAttemptedRef.current = true
    if (!loadListeningSessionActive()) return
    if (!profile) {
      saveListeningSessionActive(false)
      setEnabled(false)
      enabledRef.current = false
      setStatus('Assistente pronto per la configurazione.')
      return
    }
    enabledRef.current = true
    setEnabled(true)
    const restoredOperativeSession = loadOperativeSessionActive()
    operativeSessionRef.current = restoredOperativeSession
    setOperativeSession(restoredOperativeSession)
    setStatus(restoredOperativeSession
      ? 'Riprendo la sessione operativa anche dopo il cambio pagina.'
      : `Riprendo il richiamo vocale. ${voiceRecallReadyMessage()}`)
    startContinuousRecognition({ restored: true })
  }, [profile])

  const startOneShotRecognition = (onTranscript: (transcript: string, attempt: number) => void, options: { attempt?: number } = {}) => {
    const Recognition = getRecognitionConstructor()
    if (!Recognition) {
      setStatus('Riconoscimento vocale non disponibile. Inserisci il PIN a mano.')
      setShowManualPinEntry(true)
      return
    }
    const recognition = new Recognition()
    recognition.lang = 'it-IT'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    let resolved = false
    recognition.onstart = () => {
      setActivationWaitingPin(true)
      setShowManualPinEntry(false)
      setStatus(options.attempt && options.attempt > 1
        ? `${PIN_LISTENING_PROMPT} Tentativo ${options.attempt} di ${MAX_PIN_VOICE_ATTEMPTS}.`
        : PIN_LISTENING_PROMPT)
    }
    recognition.onresult = (event) => {
      resolved = true
      const transcript = event.results[0]?.[0]?.transcript || ''
      onTranscript(transcript, options.attempt || 1)
    }
    recognition.onerror = () => {
      resolved = true
      setActivationWaitingPin(true)
      const attempt = options.attempt || 1
      const canRetry = attempt < MAX_PIN_VOICE_ATTEMPTS
      const message = canRetry
        ? `Non ho sentito il PIN. Ripeti solo le cifre. Tentativo ${attempt + 1} di ${MAX_PIN_VOICE_ATTEMPTS}.`
        : 'Non ho sentito il PIN. Inseriscilo a mano nel campo visibile e premi Conferma PIN.'
      setStatus(message)
      if (canRetry) {
        speakItalianThen(message, () => {
          if (!enabledRef.current) {
            startOneShotRecognition(onTranscript, { attempt: attempt + 1 })
          }
        })
      } else {
        setShowManualPinEntry(true)
        speakItalian(message)
      }
    }
    recognition.onend = () => {
      if (!enabledRef.current) setActivationWaitingPin(true)
      if (!enabledRef.current && !resolved) {
        const attempt = options.attempt || 1
        const canRetry = attempt < MAX_PIN_VOICE_ATTEMPTS
        const message = canRetry
          ? `Non ho ricevuto il PIN. Ripeti solo le cifre. Tentativo ${attempt + 1} di ${MAX_PIN_VOICE_ATTEMPTS}.`
          : 'Non ho ricevuto il PIN. Inseriscilo a mano nel campo visibile e premi Conferma PIN.'
        setStatus(message)
        if (canRetry) {
          speakItalianThen(message, () => {
            if (!enabledRef.current) startOneShotRecognition(onTranscript, { attempt: attempt + 1 })
          })
        } else {
          setShowManualPinEntry(true)
          speakItalian(message)
        }
      }
    }
    try {
      recognition.start()
    } catch {
      setActivationWaitingPin(true)
      setShowManualPinEntry(true)
      setStatus('Ascolto PIN non avviato. Inserisci il PIN a mano e premi Conferma PIN.')
    }
  }

  const startCalibrationTranscription = (): (() => void) => {
    const Recognition = getRecognitionConstructor()
    if (!Recognition) {
      setCalibrationTranscript('Trascrizione non disponibile in questo browser. La registrazione del tono continua comunque.')
      setCalibrationMatch(0)
      return () => undefined
    }
    const recognition = new Recognition()
    recognition.lang = 'it-IT'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1
    recognition.onresult = (event) => {
      const parts: string[] = []
      for (let index = 0; index < event.results.length; index += 1) {
        const transcript = event.results[index]?.[0]?.transcript || ''
        if (transcript.trim()) parts.push(transcript.trim())
      }
      const transcript = parts.join(' ').trim()
      setCalibrationTranscript(transcript)
      setCalibrationMatch(scoreCalibrationTranscript(transcript))
    }
    recognition.onerror = (event) => {
      const message = event.error === 'not-allowed'
        ? 'Trascrizione non autorizzata dal browser. Consenti il microfono e ripeti la registrazione.'
        : 'Trascrizione non disponibile durante questa registrazione.'
      setCalibrationTranscript((current) => current || message)
    }
    recognition.onend = () => undefined
    try {
      recognition.start()
    } catch {
      setCalibrationTranscript('Trascrizione non avviata. La registrazione del tono continua se il microfono è autorizzato.')
      return () => undefined
    }
    return () => {
      recognition.onend = null
      recognition.onerror = null
      recognition.onresult = null
      recognition.abort?.()
      recognition.stop()
    }
  }

  const registerProfile = async () => {
    if (pin.trim().length < 4) {
      setStatus('Scegli un PIN di almeno 4 cifre.')
      return
    }
    const microphoneReady = await verifyMicrophoneAccess()
    if (!microphoneReady) return
    setBusy(true)
    setCalibrationProgress(0)
    setCalibrationRemaining(VOICE_CALIBRATION_SECONDS)
    setCalibrationTranscript('')
    setCalibrationMatch(0)
    setActiveTab('configurazione')
    let stopCalibrationTranscription: () => void = () => undefined
    try {
      setOpen(true)
      setStatus(`Registrazione voce avviata. Leggi la frase suggerita per ${VOICE_CALIBRATION_SECONDS} secondi con tono naturale.`)
      window.speechSynthesis?.cancel()
      stopCalibrationTranscription = startCalibrationTranscription()
      const signature = await captureVoiceSignature(VOICE_CALIBRATION_MS, (progress) => {
        setCalibrationProgress(progress)
        setCalibrationRemaining(Math.max(0, Math.ceil(VOICE_CALIBRATION_SECONDS * (1 - progress / 100))))
      })
      const transcript = calibrationTranscriptRef.current.trim()
      const match = scoreCalibrationTranscript(transcript)
      setCalibrationMatch(match)
      if (!transcript || match < VOICE_CALIBRATION_MIN_TEXT_MATCH) {
        setCalibrationProgress(0)
        setCalibrationRemaining(0)
        setStatus(`Registrazione da ripetere: ${calibrationQualityMessage(match)}`)
        speakItalian('Registrazione da ripetere. Leggi lentamente la frase consigliata.')
        return
      }
      const newProfile: VoiceProfile = {
        version: 1,
        pinHash: await hashPin(pin),
        signature,
        createdAt: new Date().toISOString(),
        calibrationSeconds: VOICE_CALIBRATION_SECONDS,
      }
      saveProfile(newProfile)
      const savedProfile = loadProfile()
      if (!savedProfile?.signature || savedProfile.pinHash !== newProfile.pinHash || savedProfile.calibrationSeconds !== VOICE_CALIBRATION_SECONDS) {
        throw new Error('Profilo vocale non salvato. Riprova la registrazione.')
      }
      setProfile(newProfile)
      setPin('')
      setCalibrationProgress(100)
      setCalibrationRemaining(0)
      setStatus(`Voce e PIN salvati su questo dispositivo. Calibrazione di ${VOICE_CALIBRATION_SECONDS} secondi completata.`)
      speakItalian('Voce e PIN salvati su questo dispositivo.')
    } catch (error) {
      if (isMicrophonePermissionError(error)) {
        const currentPermission = await readMicrophonePermission()
        const nextPermission = currentPermission === 'granted' ? 'granted' : 'denied'
        setMicrophonePermission(nextPermission)
        microphonePermissionRef.current = nextPermission
      } else {
        setPin('')
      }
      setCalibrationProgress(0)
      setCalibrationRemaining(0)
      setStatus(
        isMicrophonePermissionError(error) && microphonePermissionRef.current === 'granted'
          ? microphoneGrantedButStreamBlockedMessage()
          : audioCaptureErrorMessage(error),
      )
    } finally {
      stopCalibrationTranscription()
      setBusy(false)
    }
  }

  const repeatPinListening = (message: string, attempt: number) => {
    const nextAttempt = Math.min(MAX_PIN_VOICE_ATTEMPTS, attempt + 1)
    setActivationWaitingPin(true)
    setShowManualPinEntry(false)
    setStatus(message)
    speakItalianThen(message, () => {
      if (!enabledRef.current) {
        startOneShotRecognition((transcript, currentAttempt) => {
          void verifyPinAndListen(transcript, { retryVoice: true, attempt: currentAttempt })
        }, { attempt: nextAttempt })
      }
    })
  }

  const verifyPinAndListen = async (spokenOrTypedPin: string, options: { retryVoice?: boolean; attempt?: number } = {}) => {
    if (!profile) return
    const rawTranscript = spokenOrTypedPin.trim()
    const digits = extractSpokenPin(rawTranscript) || rawTranscript.replace(/\D/g, '')
    const attempt = options.attempt || 1
    const canRetryVoice = Boolean(options.retryVoice && attempt < MAX_PIN_VOICE_ATTEMPTS)
    if (!digits) {
      setActivationWaitingPin(true)
      const heard = rawTranscript ? `Ho sentito: “${rawTranscript}”. ` : ''
      const message = canRetryVoice
        ? `${heard}Non ho letto un codice valido. Ripeti solo le cifre. Tentativo ${attempt + 1} di ${MAX_PIN_VOICE_ATTEMPTS}.`
        : `${heard}PIN non riconosciuto. Inseriscilo a mano nel campo visibile e premi Conferma PIN.`
      setStatus(message)
      if (canRetryVoice) {
        repeatPinListening(message, attempt)
      } else {
        setShowManualPinEntry(true)
        speakItalian(message)
      }
      return
    }
    const hash = await hashPin(digits)
    if (hash !== profile.pinHash) {
      setActivationWaitingPin(true)
      const message = canRetryVoice
        ? `Ho letto ${digits.split('').join(' ')}, ma il codice non è corretto. Ripeti solo le cifre. Tentativo ${attempt + 1} di ${MAX_PIN_VOICE_ATTEMPTS}.`
        : `Ho letto ${digits.split('').join(' ')}, ma il codice non è corretto. Inseriscilo a mano nel campo visibile e premi Conferma PIN.`
      setStatus(message)
      if (canRetryVoice) {
        repeatPinListening(message, attempt)
      } else {
        setShowManualPinEntry(true)
        speakItalian(message)
      }
      return
    }
    setPinCheck('')
    setActivationWaitingPin(false)
    setShowManualPinEntry(false)
    setEnabled(true)
    enabledRef.current = true
    operativeSessionRef.current = false
    setOperativeSession(false)
    saveListeningSessionActive(true)
    saveOperativeSessionActive(false)
    setStatus(`PIN corretto. ${voiceRecallReadyMessage()}`)
    rememberCommandAction(`PIN corretto. L’assistente resta pronto al richiamo “${savedActivationPhraseRef.current}” anche dopo cambio pagina.`)
    speakItalianThen('PIN corretto. Richiamo vocale pronto.', () => startContinuousRecognition())
  }

  const activateAssistant = async () => {
    if (!profile) {
      setStatus('Registra prima voce e PIN.')
      setOpen(true)
      return
    }
    const microphoneReady = await verifyMicrophoneAccess(true)
    if (!microphoneReady) {
      setStatus('Microfono non pronto. Premi Verifica microfono, consenti l’accesso nel browser e riprova.')
      return
    }
    setBusy(true)
    try {
      const voiceCheckPrompt = `Controllo il tono di voce. Pronuncia "${savedActivationPhraseRef.current}" con voce naturale.`
      setStatus(voiceCheckPrompt)
      await speakItalianAndWait(voiceCheckPrompt)
      if (enabledRef.current) return
      const sample = await captureVoiceSignature(VOICE_ACTIVATION_SAMPLE_MS)
      const score = compareSignature(sample, profile.signature)
      if (!voiceActivationAccepted(score, sample)) {
        const message = 'Tono di voce non riconosciuto. Riprova parlando vicino al microfono oppure registra di nuovo la voce.'
        setStatus(message)
        speakItalian(message)
        return
      }
      setActivationWaitingPin(true)
      setShowManualPinEntry(false)
      setStatus(PIN_LISTENING_PROMPT)
      speakItalianThen(PIN_LISTENING_PROMPT, () => {
        if (enabledRef.current) return
        startOneShotRecognition((transcript, currentAttempt) => {
          void verifyPinAndListen(transcript, { retryVoice: true, attempt: currentAttempt })
        }, { attempt: 1 })
      })
    } catch (error) {
      setStatus(audioCaptureErrorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  const deleteProfile = () => {
    stopListening('Assistente vocale disattivato.')
    window.localStorage.removeItem(PROFILE_STORAGE_KEY)
    setProfile(null)
    setPin('')
    setPinCheck('')
    setStatus('Profilo vocale rimosso da questo dispositivo.')
  }

  const clientMissing = nextMissingClientField(clientDraft)
  const profileReady = Boolean(profile)
  const microphoneBlocked = microphonePermission === 'denied' || status.startsWith('Microfono non autorizzato')
  const showMicrophoneHelp = microphoneBlocked || microphoneHelpOpen
  const microphoneStateLabel = microphonePermissionLabel(microphonePermission)
  const microphoneStateDescription = microphonePermissionDescription(microphonePermission)
  const microphoneRegistrationBlocked = microphonePermission === 'denied' || microphonePermission === 'unsupported'
  const profileCreatedAt = profile?.createdAt ? formatItalianDateTime(profile.createdAt) : ''
  const microphoneBlockedTitle = 'Microfono non concesso dal browser'
  const microphoneBlockedMessage = browserRuntime.isEmbedded
    ? 'Il click è arrivato: il browser incorporato ha risposto permesso negato. IUSENTRA non può cambiare da solo il permesso del contenitore.'
    : 'Il click è arrivato: il browser ha risposto permesso negato. Abilita il microfono per questa pagina e ripeti la verifica.'
  const pinVoiceCheckActive = activationWaitingPin && !enabled

  return (
    <div
      className="iu-voice-assistant"
      data-testid="studio-voice-assistant"
      data-voice-state={enabled ? 'active' : 'idle'}
      data-voice-command-count={summary.totalPhrases}
      data-microphone-permission={microphonePermission}
    >
      <button
        className={`iu-icon iu-voice-assistant__trigger ${enabled ? 'is-active' : ''}`}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label="Assistente vocale Studio"
        aria-expanded={open}
        title="Assistente vocale Studio"
      >
        {listening ? <Mic size={18} /> : <Bot size={18} />}
        <span className="iu-voice-assistant__trigger-label">Voce Studio</span>
        {listening ? <span className="iu-voice-assistant__pulse" aria-hidden="true" /> : null}
      </button>
      {open ? (
        <section className="iu-voice-panel" aria-label="Assistente vocale Studio">
          <header className="iu-voice-panel__header">
            <div>
              <strong>Assistente vocale Studio</strong>
              <small>{summary.totalPhrases} frasi riconosciute, {summary.destinations} destinazioni, {summary.actions} azioni rapide.</small>
            </div>
            <button className="iu-icon iu-voice-panel__close" type="button" onClick={() => setOpen(false)} aria-label="Chiudi assistente vocale">
              <X size={17} />
            </button>
          </header>

          <div className="iu-voice-panel__body">
            <div className={`iu-voice-status ${enabled ? 'is-active' : ''}`} role="status">
              {busy ? <Loader2 className="iu-spin" size={16} /> : enabled ? <Mic size={16} /> : <ShieldCheck size={16} />}
              <span>{status}</span>
            </div>

            <section className={`iu-voice-listening-state ${enabled || pinVoiceCheckActive ? 'is-listening' : ''}`} aria-live="polite">
              {enabled || pinVoiceCheckActive ? <Mic size={18} /> : <MicOff size={18} />}
              <div>
                <strong>
                  {pinVoiceCheckActive
                    ? 'Verifica PIN vocale'
                    : enabled
                      ? (operativeSession ? 'Sessione operativa attiva' : 'Richiamo vocale pronto')
                      : 'Studio non in ascolto'}
                </strong>
                <small>
                  {pinVoiceCheckActive
                    ? (showManualPinEntry
                        ? 'Riconoscimento non concluso: inserisci il PIN nel campo visibile.'
                        : 'Sto ascoltando automaticamente il PIN. Pronuncia solo le cifre; se non capisco riprovo da solo.')
                    : enabled
                    ? (operativeSession
                        ? 'Pronuncia direttamente i comandi; di’ “stop” quando hai finito.'
                        : voiceRecallReadyMessage())
                    : profileReady
                      ? 'Premi Attiva ascolto nella sezione Configurazione.'
                      : 'Prima registra voce e PIN nella sezione Configurazione.'}
                </small>
                <p>{lastCommandAction || 'Nessun comando operativo eseguito in questa sessione.'}</p>
              </div>
              {enabled ? (
                <div className="iu-voice-listening-state__actions">
                  {operativeSession ? (
                    <button className="iu-voice-button ghost" type="button" onClick={() => pauseOperativeSession()}>
                      <MicOff size={15} />
                      <span>Stop sessione</span>
                    </button>
                  ) : null}
                  <button className="iu-voice-button ghost" type="button" onClick={() => stopListening()}>
                    <MicOff size={15} />
                    <span>Disattiva ascolto</span>
                  </button>
                </div>
              ) : null}
            </section>

            <div className="iu-voice-tabs" role="tablist" aria-label="Sezioni assistente vocale">
              <button
                className={`iu-voice-tab ${activeTab === 'configurazione' ? 'is-active' : ''}`}
                type="button"
                role="tab"
                aria-selected={activeTab === 'configurazione'}
                onClick={() => setActiveTab('configurazione')}
              >
                <ShieldCheck size={15} />
                <span>Configurazione</span>
              </button>
              <button
                className={`iu-voice-tab ${activeTab === 'comandi' ? 'is-active' : ''}`}
                type="button"
                role="tab"
                aria-selected={activeTab === 'comandi'}
                onClick={() => setActiveTab('comandi')}
              >
                <HelpCircle size={15} />
                <span>Comandi autorizzati</span>
              </button>
              <button
                className={`iu-voice-tab ${activeTab === 'richieste' ? 'is-active' : ''}`}
                type="button"
                role="tab"
                aria-selected={activeTab === 'richieste'}
                onClick={() => setActiveTab('richieste')}
              >
                <UserPlus size={15} />
                <span>Richieste operative</span>
              </button>
              <button
                className={`iu-voice-tab ${activeTab === 'note' ? 'is-active' : ''}`}
                type="button"
                role="tab"
                aria-selected={activeTab === 'note'}
                onClick={() => setActiveTab('note')}
              >
                <FileText size={15} />
                <span>Note vocali</span>
              </button>
            </div>

            {activeTab === 'configurazione' ? (
              <div className="iu-voice-section" role="tabpanel">
                <section className="iu-voice-card">
                  <div className="iu-voice-card__title">
                    <Volume2 size={16} />
                    <div>
                      <strong>Inizializzazione assistente</strong>
                      <small>Voce, PIN e frase di attivazione restano su questo dispositivo.</small>
                    </div>
                  </div>
                  <div className={`iu-voice-profile-state ${profileReady ? 'is-ready' : 'is-missing'}`}>
                    {profileReady ? <CheckCircle2 size={18} /> : <MicOff size={18} />}
                    <div>
                      <strong>{profileReady ? 'Voce registrata' : 'Voce non registrata'}</strong>
                      <small>{profileReady ? `Profilo salvato il ${profileCreatedAt}.` : 'Registra almeno 30 secondi di voce prima di attivare l’assistente.'}</small>
                    </div>
                  </div>
                  <div className={`iu-voice-microphone-state is-${microphonePermission}`}>
                    {microphonePermission === 'granted' ? <CheckCircle2 size={18} /> : <Mic size={18} />}
                    <div>
                      <strong>Microfono: {microphoneStateLabel}</strong>
                      <small>{microphoneStateDescription}</small>
                      {microphoneLastCheckedAt ? <small>Ultimo controllo: {microphoneLastCheckedAt}.</small> : null}
                    </div>
                    <button className="iu-voice-button" type="button" onClick={() => void verifyMicrophoneAccess()} disabled={busy || microphonePermission === 'unsupported'}>
                      {busy ? <Loader2 className="iu-spin" size={15} /> : <Mic size={15} />}
                      <span>Verifica microfono</span>
                    </button>
                  </div>
                  {microphoneBlocked ? (
                    <div className="iu-voice-microphone-unlock compact" data-microphone-unlock={browserRuntime.isEmbedded ? 'embedded-browser' : 'browser'}>
                      <strong>{microphoneBlockedTitle}</strong>
                      <p>{microphoneBlockedMessage}</p>
                      <div className="iu-voice-microphone-unlock__actions">
                        <button className="iu-voice-button" type="button" onClick={() => void verifyMicrophoneAccess()} disabled={busy}>
                          {busy ? <Loader2 className="iu-spin" size={15} /> : <RotateCw size={15} />}
                          <span>Verifica di nuovo</span>
                        </button>
                        <button className="iu-voice-button" type="button" onClick={() => void copyCurrentPageAddress()}>
                          <Copy size={15} />
                          <span>Copia pagina</span>
                        </button>
                        {alternateMicrophoneUrl ? (
                          <button className="iu-voice-button ghost" type="button" onClick={openAlternateMicrophoneAddress}>
                            <Navigation size={15} />
                            <span>Altro indirizzo locale</span>
                          </button>
                        ) : null}
                      </div>
                      <details className="iu-voice-microphone-details">
                        <summary>Dettagli permesso</summary>
                        <p>Nessun profilo vocale viene salvato finché il permesso non risulta consentito.</p>
                        {browserRuntime.settingsUrl ? (
                          <div className="iu-voice-microphone-unlock__address">
                            <label htmlFor="iu-voice-browser-microphone-url">Impostazioni microfono del browser.</label>
                            <div>
                              <input
                                id="iu-voice-browser-microphone-url"
                                readOnly
                                value={chromeSettingsAddress}
                                onFocus={(event) => event.currentTarget.select()}
                              />
                              <button className="iu-voice-button" type="button" onClick={() => void copyChromeMicrophoneAddress()}>
                                <Copy size={15} />
                                <span>Copia impostazioni</span>
                              </button>
                              <button className="iu-voice-button" type="button" onClick={() => void openChromeMicrophoneUnlock()}>
                                <ShieldCheck size={15} />
                                <span>Apri impostazioni</span>
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </details>
                    </div>
                  ) : null}
                  {false && microphoneBlocked ? (
                    <div className="iu-voice-microphone-unlock" data-microphone-unlock="chrome">
                      <strong>Azione richiesta: sblocca il microfono</strong>
                      <p>Il blocco è salvato in Chrome: finché resta attivo non parte nessuna registrazione. Se Chrome non apre la scheda, l’indirizzo viene copiato e puoi aprirlo con Ctrl+L, Ctrl+V e Invio.</p>
                      <div className="iu-voice-microphone-unlock__address">
                        <label htmlFor="iu-voice-chrome-microphone-url">Indirizzo Chrome per sbloccare il microfono di questo sito.</label>
                        <div>
                          <input
                            id="iu-voice-chrome-microphone-url"
                            readOnly
                            value={chromeSettingsAddress}
                            onFocus={(event) => event.currentTarget.select()}
                          />
                          <button className="iu-voice-button" type="button" onClick={() => void copyChromeMicrophoneAddress()}>
                            <Copy size={15} />
                            <span>Copia indirizzo sblocco</span>
                          </button>
                        </div>
                      </div>
                      <div className="iu-voice-microphone-unlock__actions">
                        <button className="iu-voice-button primary" type="button" onClick={() => void openChromeMicrophoneUnlock()}>
                          <ShieldCheck size={15} />
                          <span>Sblocca microfono in Chrome</span>
                        </button>
                        <button className="iu-voice-button" type="button" onClick={() => void verifyMicrophoneAccess()} disabled={busy}>
                          {busy ? <Loader2 className="iu-spin" size={15} /> : <RotateCw size={15} />}
                          <span>Ho sbloccato, verifica</span>
                        </button>
                        {alternateMicrophoneUrl ? (
                          <button className="iu-voice-button ghost" type="button" onClick={openAlternateMicrophoneAddress}>
                            <Navigation size={15} />
                            <span>Riprova indirizzo locale</span>
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                  <div className="iu-voice-activation">
                    <label>
                      <span>Frase di attivazione</span>
                      <input
                        value={activationPhrase}
                        onChange={(event) => setActivationPhrase(event.target.value)}
                        onBlur={() => setActivationPhrase((value) => normalizeActivationPhrase(value))}
                        placeholder={DEFAULT_ACTIVATION_PHRASE}
                        disabled={busy}
                      />
                    </label>
                    <button className="iu-voice-button" type="button" onClick={saveCustomActivationPhrase} disabled={busy}>
                      <CheckCircle2 size={15} />
                      <span>Salva frase</span>
                    </button>
                  </div>
                  {!profileReady ? (
                    <div className="iu-voice-setup">
                      <label>
                        <span>PIN vocale</span>
                        <input
                          value={pin}
                          onChange={(event) => setPin(event.target.value.replace(/\D/g, '').slice(0, 8))}
                          type="password"
                          inputMode="numeric"
                          autoComplete="new-password"
                          placeholder="Almeno 4 cifre"
                        />
                      </label>
                      <button className="iu-voice-button primary" type="button" onClick={registerProfile} disabled={busy || microphoneRegistrationBlocked}>
                        {busy ? <Loader2 className="iu-spin" size={15} /> : <KeyRound size={15} />}
                        <span>{microphoneRegistrationBlocked ? 'Verifica microfono prima' : busy ? 'Registrazione in corso' : 'Registra voce e PIN'}</span>
                      </button>
                    </div>
                  ) : (
                    <div className="iu-voice-actions">
                      <button className="iu-voice-button primary" type="button" onClick={activateAssistant} disabled={busy || enabled || activationWaitingPin}>
                        {busy ? <Loader2 className="iu-spin" size={15} /> : <Mic size={15} />}
                        <span>{activationWaitingPin ? 'PIN in ascolto' : 'Attiva ascolto'}</span>
                      </button>
                      <button className="iu-voice-button" type="button" onClick={() => stopListening()} disabled={!enabled && !listening && !activationWaitingPin}>
                        <MicOff size={15} />
                        <span>Disattiva</span>
                      </button>
                      <button className="iu-voice-button ghost" type="button" onClick={deleteProfile}>
                        <X size={15} />
                        <span>Rimuovi profilo</span>
                      </button>
                    </div>
                  )}
                  {activationWaitingPin && !showManualPinEntry ? (
                    <div className="iu-voice-pin iu-voice-pin--listening" aria-live="polite">
                      <div>
                        <span>PIN vocale</span>
                        <strong>Sto ascoltando automaticamente</strong>
                        <small>Pronuncia solo le cifre. Se non capisco, ripeto da solo fino a tre tentativi.</small>
                      </div>
                    </div>
                  ) : null}
                  {activationWaitingPin && showManualPinEntry ? (
                    <div className="iu-voice-pin">
                      <label>
                        <span>PIN letto o inserito</span>
                        <input
                          value={pinCheck}
                          onChange={(event) => setPinCheck(event.target.value.replace(/\D/g, '').slice(0, 8))}
                          type="password"
                          inputMode="numeric"
                          autoComplete="one-time-code"
                          placeholder="Pronuncia o scrivi il PIN"
                        />
                      </label>
                      <button className="iu-voice-button" type="button" onClick={() => void verifyPinAndListen(pinCheck)} disabled={!pinCheck}>
                        <CheckCircle2 size={15} />
                        <span>Conferma PIN</span>
                      </button>
                    </div>
                  ) : null}
                  {showMicrophoneHelp && !microphoneBlocked ? (
                    <div className="iu-voice-permission-note">
                      <strong>Il microfono è protetto da Chrome.</strong>
                      <p>IUSENTRA può chiedere il permesso, ma Chrome protegge la scelta finale dell’utente. Se il microfono è bloccato, usa “Sblocca microfono in Chrome”, apri l’indirizzo copiato, imposta Microfono su Consenti e poi premi “Ho sbloccato, verifica”.</p>
                      {microphoneLastCheckedAt ? <p>Ultimo tentativo reale: {microphoneLastCheckedAt}. Se non compare il popup, il blocco è ancora memorizzato in Chrome.</p> : null}
                      <p>Nessun profilo vocale viene salvato finché il permesso non risulta consentito.</p>
                    </div>
                  ) : null}
                </section>

                <section className="iu-voice-card">
                  <div className="iu-voice-card__title">
                    <Mic size={16} />
                    <div>
                      <strong>Registrazione del tono</strong>
                      <small>Durante i 30 secondi vedi timer, avanzamento e parole riconosciute.</small>
                    </div>
                  </div>
                  <div className="iu-voice-calibration">
                    <strong>Frase consigliata per registrare bene il tono</strong>
                    <p>Leggila con voce naturale per {VOICE_CALIBRATION_SECONDS} secondi. Se finisce prima, rileggila con lo stesso ritmo. Scandisci bene "IUSENTRA" e "Studio", restando vicino al microfono.</p>
                    <blockquote>{VOICE_CALIBRATION_TEXT}</blockquote>
                    <div className="iu-voice-calibration-meter" aria-live="polite">
                      <progress className="iu-voice-progress" value={calibrationProgress} max={100} aria-label={`Calibrazione voce ${calibrationProgress}%`} />
                      <span>
                        {busy && calibrationRemaining > 0
                          ? `${calibrationRemaining} secondi rimanenti`
                          : profileReady
                            ? 'Registrazione completata'
                            : 'In attesa di registrazione'}
                      </span>
                    </div>
                    <div className="iu-voice-transcript-box" aria-live="polite">
                      <strong>Testo rilevato durante la lettura</strong>
                      <p>{calibrationTranscript || (busy ? 'In ascolto: leggi la frase consigliata.' : 'Quando registri, qui vedrai le parole che il sistema sta riconoscendo.')}</p>
                      <small>{calibrationTranscript ? `Qualità lettura: ${calibrationMatch}%. ${calibrationQualityMessage(calibrationMatch)}` : 'La qualità appare appena il browser trascrive la voce.'}</small>
                    </div>
                  </div>
                </section>
              </div>
            ) : null}

            {activeTab === 'comandi' ? (
              <div className="iu-voice-section" role="tabpanel">
                <section className="iu-voice-card iu-voice-listen-log">
                  <div className="iu-voice-card__title">
                    <Mic size={16} />
                    <div>
                      <strong>Cosa ho ascoltato</strong>
                      <small>Qui vedi il testo riconosciuto quando parli.</small>
                    </div>
                  </div>
                  {transcriptHistory.length ? (
                    <ol>
                      {transcriptHistory.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ol>
                  ) : (
                    <p className="iu-voice-note">Nessun comando ascoltato in questa sessione.</p>
                  )}
                  {lastTranscript ? (
                    <p className="iu-voice-last">
                      Ultimo ascolto: <span>{lastTranscript}</span>
                    </p>
                  ) : null}
                </section>

                <section className="iu-voice-card">
                  <div className="iu-voice-card__title">
                    <HelpCircle size={16} />
                    <div>
                      <strong>Comandi autorizzati</strong>
                      <small>Con il richiamo vocale pronto, attiva la sessione e poi pronuncia i comandi senza ripetere la frase di attivazione.</small>
                    </div>
                  </div>
                  <div className="iu-voice-command-summary">
                    <span>{summary.base} comandi iniziali</span>
                    <span>{summary.added} frasi aggiunte</span>
                    <span>{VOICE_ROUTE_COMMANDS.length} aree apribili</span>
                  </div>
                  <div className="iu-voice-command-list">
                    {groupedCommands.map(([group, commands]) => (
                      <details key={group} open={group === 'Clienti' || group === 'Studio'}>
                        <summary>{group}</summary>
                        <div>
                          {commands.map((command) => (
                            <article key={command.id} className="iu-voice-command-row">
                              {commandIcon(command)}
                              <div>
                                <strong>{command.label}</strong>
                                <small>{command.phrases.slice(0, 3).join(' · ')}</small>
                              </div>
                            </article>
                          ))}
                        </div>
                      </details>
                    ))}
                  </div>
                </section>
              </div>
            ) : null}

            {activeTab === 'richieste' ? (
              <div className="iu-voice-section" role="tabpanel">
                <section className="iu-voice-card" data-voice-client-step={clientStep}>
                  <div className="iu-voice-card__title">
                    <UserPlus size={16} />
                    <div>
                      <strong>Nuovo cliente guidato</strong>
                      <small>Di’: “nuovo cliente”, poi nome, cognome e codice fiscale.</small>
                    </div>
                  </div>
                  <div className="iu-voice-client-grid">
                    <label>
                      <span>Nome</span>
                      <input value={clientDraft.nome} onChange={(event) => setClientDraft((current) => ({ ...current, nome: event.target.value }))} />
                    </label>
                    <label>
                      <span>Cognome</span>
                      <input value={clientDraft.cognome} onChange={(event) => setClientDraft((current) => ({ ...current, cognome: event.target.value }))} />
                    </label>
                    <label>
                      <span>Codice fiscale</span>
                      <input
                        value={clientDraft.codice_fiscale}
                        onChange={(event) => setClientDraft((current) => ({ ...current, codice_fiscale: event.target.value.toLocaleUpperCase('it-IT') }))}
                        maxLength={16}
                      />
                    </label>
                  </div>
                  <div className="iu-voice-actions">
                    <button className="iu-voice-button" type="button" onClick={beginClientFlow}>
                      <Mic size={15} />
                      <span>Avvia guida</span>
                    </button>
                    <button className="iu-voice-button primary" type="button" onClick={() => void confirmClient()} disabled={Boolean(clientMissing) || clientStep === 'saving'}>
                      {clientStep === 'saving' ? <Loader2 className="iu-spin" size={15} /> : <CheckCircle2 size={15} />}
                      <span>Aggiungi cliente</span>
                    </button>
                  </div>
                  {clientMissing ? <p className="iu-voice-note">Campo da completare: {labelForClientField(clientMissing)}.</p> : null}
                  {clientMessage ? <p className="iu-voice-note strong">{clientMessage}</p> : null}
                  {clientHref ? (
                    <a className="iu-voice-link" href={clientHref}>
                      Apri scheda cliente <ChevronRight size={15} />
                    </a>
                  ) : null}
                </section>
              </div>
            ) : null}

            {activeTab === 'note' ? (
              <div className="iu-voice-section" role="tabpanel">
                <section className="iu-voice-card">
                  <div className="iu-voice-card__title">
                    <FileText size={16} />
                    <div>
                      <strong>Note vocali e promemoria</strong>
                      <small>Dettatura libera, salvataggio testuale e avviso browser 10 minuti prima.</small>
                    </div>
                  </div>
                  <div className="iu-voice-note-command">
                    <label>
                      <span>Comando note personalizzato</span>
                      <input
                        value={noteTriggerPhrase}
                        onChange={(event) => setNoteTriggerPhrase(event.target.value)}
                        onBlur={() => setNoteTriggerPhrase((value) => normalizeNoteTriggerPhrase(value, savedActivationPhrase))}
                        placeholder={DEFAULT_NOTE_TRIGGER_PHRASE}
                        disabled={busy}
                      />
                    </label>
                    <button className="iu-voice-button" type="button" onClick={saveCustomNoteTriggerPhrase} disabled={busy}>
                      <CheckCircle2 size={15} />
                      <span>Salva comando</span>
                    </button>
                  </div>
                  <p className="iu-voice-note">
                    Comando attuale: <strong>"{savedActivationPhrase}, {savedNoteTriggerPhrase}"</strong>. Puoi usare anche una frase completa, per esempio "{savedActivationPhrase}, {savedNoteTriggerPhrase} ricordami domani alle 18 di controllare la PEC fine nota".
                  </p>
                  <div className="iu-voice-note-warning">
                    <Bell size={16} />
                    <p>
                      Le note salvano solo la trascrizione, non l'audio. I promemoria browser funzionano mentre IUSENTRA resta aperto; per avvisi garantiti a browser chiuso serviranno Agenda e notifiche sicure dello studio.
                    </p>
                  </div>
                  <div className="iu-voice-actions">
                    <button className={`iu-voice-button ${noteMode ? 'danger' : 'primary'}`} type="button" onClick={() => (noteMode ? finishVoiceNote('fine nota') : beginVoiceNote())} disabled={busy}>
                      {noteMode ? <CheckCircle2 size={15} /> : <Mic size={15} />}
                      <span>{noteMode ? 'Salva nota' : 'Avvia nota'}</span>
                    </button>
                    <button className="iu-voice-button" type="button" onClick={() => void requestNotificationPermission()} disabled={busy || notificationPermission === 'granted' || notificationPermission === 'unsupported'}>
                      <Bell size={15} />
                      <span>{notificationPermission === 'granted' ? 'Notifiche attive' : notificationPermission === 'unsupported' ? 'Non disponibili' : 'Consenti promemoria'}</span>
                    </button>
                  </div>
                  <div className="iu-voice-note-meta">
                    <span>Fuso orario: Roma</span>
                    <span>Promemoria: 10 minuti prima</span>
                    <span>Notifiche: {notificationPermission === 'granted' ? 'abilitate' : notificationPermission === 'denied' ? 'non abilitate' : notificationPermission === 'unsupported' ? 'non disponibili' : 'da consentire'}</span>
                  </div>
                  <div className="iu-voice-transcript-box" aria-live="polite">
                    <strong>Nota in dettatura</strong>
                    <p>{draftNote || (noteMode ? 'Sto ascoltando la nota. Chiudi con "fine nota" o "fine note".' : 'Dopo l’attivazione, pronuncia il comando note personalizzato e detta la nota.')}</p>
                    <small>Le parole riconosciute compaiono qui prima del salvataggio.</small>
                  </div>
                </section>

                <section className="iu-voice-card">
                  <div className="iu-voice-card__title">
                    <Bell size={16} />
                    <div>
                      <strong>Note salvate sul dispositivo</strong>
                      <small>{voiceNotes.length ? `${voiceNotes.length} note recenti disponibili.` : 'Nessuna nota vocale salvata in questa sessione.'}</small>
                    </div>
                  </div>
                  {voiceNotes.length ? (
                    <div className="iu-voice-notes-list">
                      {voiceNotes.slice(0, 8).map((note) => (
                        <article className="iu-voice-note-card" key={note.id}>
                          <div>
                            <strong>{compactVoiceNoteText(note.text, 150)}</strong>
                            <span>Creata: {formatItalianDateTime(note.createdAt)}</span>
                            <span>{note.targetAt ? `Evento: ${formatItalianDateTime(note.targetAt)}` : 'Data e ora non riconosciute insieme'}</span>
                            {note.notifyAt ? <span>Promemoria browser: {formatItalianDateTime(note.notifyAt)}</span> : null}
                            {note.notifiedAt ? <span>Promemoria già mostrato: {formatItalianDateTime(note.notifiedAt)}</span> : null}
                          </div>
                          <button className="iu-voice-button ghost" type="button" onClick={() => deleteVoiceNote(note.id)} aria-label="Elimina nota vocale">
                            <Trash2 size={15} />
                          </button>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="iu-voice-note">Le note salvate appariranno qui con data, ora di Roma e stato del promemoria.</p>
                  )}
                </section>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  )
}
export default StudioVoiceAssistant
