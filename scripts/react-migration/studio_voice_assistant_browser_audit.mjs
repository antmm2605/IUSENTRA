import { spawn } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..', '..')
const BASE_URL = process.env.IUSENTRA_VOICE_E2E_BASE_URL || 'http://127.0.0.1:8080'
const STUDIO_SLUG = process.env.IUSENTRA_VOICE_E2E_STUDIO || 'antonella-mammola'
const USERNAME = process.env.IUSENTRA_VOICE_E2E_USERNAME || 'codex-voce-e2e'
const PASSWORD = process.env.IUSENTRA_VOICE_E2E_PASSWORD || ''
const PIN = process.env.IUSENTRA_VOICE_E2E_PIN || '1234'
const SPOKEN_PIN = process.env.IUSENTRA_VOICE_E2E_SPOKEN_PIN || 'uno due tre quattro'
const CALIBRATION_TRANSCRIPT = 'Studio legale IUSENTRA autorizzo l’assistente vocale dello studio apri panoramica clienti calendario e fascicoli la mia voce è naturale chiara costante e professionale ripeto con lo stesso tono autorizzo l’assistente dello studio'
const VISIBLE_BROWSER = process.env.IUSENTRA_VOICE_E2E_VISIBLE === '1'
const REAL_MICROPHONE = process.env.IUSENTRA_VOICE_E2E_REAL_MICROPHONE === '1'
const PERMISSION_ONLY = process.env.IUSENTRA_VOICE_E2E_PERMISSION_ONLY === '1'
const MICROPHONE_GRANTED_DEVICE_HINT = process.env.IUSENTRA_VOICE_E2E_GRANTED_DEVICE_HINT === '1'
const REPORT_DIR = path.join(ROOT, 'artifacts', 'react-migration')
const REPORT_PATH = path.join(REPORT_DIR, 'studio-voice-assistant-browser-audit.json')
const MICROPHONE_PERMISSION_REPORT_PATH = path.join(REPORT_DIR, 'studio-voice-assistant-microphone-permission-audit.json')
const DESKTOP_SCREENSHOT = path.join(REPORT_DIR, 'studio-voice-assistant-desktop.png')
const MOBILE_SCREENSHOT = path.join(REPORT_DIR, 'studio-voice-assistant-mobile.png')
const MICROPHONE_SCREENSHOT = path.join(REPORT_DIR, 'studio-voice-assistant-microphone-permission.png')
const MICROPHONE_BOTTOM_SCREENSHOT = path.join(REPORT_DIR, 'studio-voice-assistant-microphone-permission-bottom.png')
const FIELD_DICTATION_SCREENSHOT = path.join(REPORT_DIR, 'studio-voice-assistant-field-dictation.png')
const COMMAND_CATALOG_PATH = path.join(ROOT, 'frontend', 'src', 'studioVoiceCommands.json')

if (!PASSWORD) {
  throw new Error('Impostare IUSENTRA_VOICE_E2E_PASSWORD con la password dell’utente locale temporaneo di audit.')
}

const forbiddenVisibleTerms = [
  'backend',
  'frontend',
  'payload',
  'runtime',
  'json_api',
  'provider',
  'webhook',
  'legacy',
  'undefined',
  'null',
  'demo',
  'sample',
  'repository',
]

const commandCatalog = JSON.parse(fs.readFileSync(COMMAND_CATALOG_PATH, 'utf8'))
const EXPECTED_PHRASE_COUNT = commandCatalog.routeCommands.concat(commandCatalog.specialCommands)
  .flatMap((command) => command.phrases).length
const ROUTE_CONTENT_EXPECTATIONS = {
  panoramica: ['Panoramica', 'Ultime PEC ricevute', 'Agenda'],
  'regia-operativa': ['Regia Operativa', 'priorità', 'prossime azioni'],
  'ricerca-studio': ['Ricerca Studio', 'Cerca'],
  calendario: ['Agenda', 'Calendario'],
  'nuovo-appuntamento': ['Nuovo appuntamento', 'Appuntamento'],
  timesheet: ['Timesheet'],
  fascicoli: ['Fascicoli'],
  'tutti-fascicoli': ['Fascicoli'],
  'nuovo-fascicolo': ['Nuovo fascicolo', 'Fascicolo'],
  'archivio-fascicoli': ['Archivio', 'Fascicoli'],
  clienti: ['Clienti', 'Anagrafiche'],
  'cliente-manuale': ['Nuovo cliente', 'Cliente'],
  'cartelle-condivise': ['Cartelle condivise'],
  soggetti: ['Soggetti', 'Parti'],
  'nuovo-soggetto': ['Nuovo soggetto', 'Soggetto'],
  pec: ['PEC', 'Email'],
  'email-ordinaria': ['Email', 'SMTP'],
  notifiche: ['Notifiche'],
  'notifiche-whatsapp': ['WhatsApp', 'Notifiche'],
  messaggi: ['Messaggi'],
  'nuovo-messaggio': ['Nuovo', 'messaggio'],
  scadenze: ['Scadenze', 'Scadenziario'],
  'nuova-scadenza': ['Nuova scadenza', 'Scadenza'],
  'preparazione-udienza': ['Preparazione', 'Udienza'],
  'controlli-atti': ['Controlli Atti', 'Deposito'],
  'servizi-telematici': ['Servizi Telematici', 'Telematico'],
  polisweb: ['PolisWeb'],
  pdp: ['PDP'],
  pat: ['PAT'],
  ptt: ['PTT'],
  studio: ['Studio'],
  fatture: ['Fatture', 'Parcelle'],
  preventivi: ['Preventivi'],
  'preventivo-nuovo': ['Nuovo preventivo', 'Preventivo'],
  compensi: ['Compensi Forensi', 'Compensi'],
  documenti: ['Documenti'],
  'template-atti': ['Template Atti', 'Modelli'],
  'redazione-atti': ['Redazione Atti', 'Atti'],
  statistiche: ['Statistiche'],
  'ricerca-legale': ['Ricerca Legale'],
  'news-legali': ['News', 'Ricerca Legale'],
  'archivio-giurisprudenza': ['Giurisprudenza'],
  'strumenti-forensi': ['Strumenti Forensi'],
  'strumenti-operativi': ['Strumenti Operativi'],
  'sito-studio': ['Sito Studio'],
  'sito-builder': ['Builder', 'Sito'],
  'sito-redazione': ['Redazione', 'Sito'],
  'sito-contatti': ['Contatti Sito', 'Ingressi pubblici'],
  impostazioni: ['Impostazioni'],
  'impostazioni-pec': ['PEC', 'Impostazioni'],
  'impostazioni-firma': ['Firma Digitale', 'Impostazioni'],
  'impostazioni-backup': ['Backup'],
  calendari: ['Calendari', 'Sincronizzazione'],
  amministrazione: ['Amministrazione'],
  utenti: ['Utenti'],
  profili: ['Profili', 'Permessi'],
  database: ['Database'],
  'registro-attivita': ['Registro attività', 'Audit'],
  'registro-gdpr': ['Registro GDPR', 'Privacy'],
}
const chromeCandidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Users/antmm/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe',
  'C:/Users/antmm/AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe',
  'C:/Users/antmm/AppData/Local/ms-playwright/chromium-1194/chrome-win/chrome.exe',
  'C:/Users/antmm/.cache/puppeteer/chrome/win64-148.0.7778.97/chrome-win64/chrome.exe',
  'C:/Users/antmm/.cache/puppeteer/chrome/win64-146.0.7680.31/chrome-win64/chrome.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)

function findChrome() {
  const found = chromeCandidates.find((candidate) => fs.existsSync(candidate))
  if (!found) {
    throw new Error('Chromium/Chrome non trovato per il test CDP.')
  }
  return found
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitFor(fn, label, timeoutMs = 15000, intervalMs = 150) {
  const started = Date.now()
  let lastError = null
  while (Date.now() - started < timeoutMs) {
    try {
      const value = await fn()
      if (value) return value
    } catch (error) {
      lastError = error
    }
    await sleep(intervalMs)
  }
  throw new Error(`${label} non verificato entro ${timeoutMs} ms${lastError ? `: ${lastError.message}` : ''}`)
}

class CdpConnection {
  constructor(wsUrl) {
    this.nextId = 1
    this.pending = new Map()
    this.listeners = []
    this.events = []
    this.ws = new WebSocket(wsUrl)
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true })
      this.ws.addEventListener('error', reject, { once: true })
    })
    this.ws.addEventListener('message', (message) => {
      const payload = JSON.parse(String(message.data))
      if (payload.id && this.pending.has(payload.id)) {
        const { resolve, reject } = this.pending.get(payload.id)
        this.pending.delete(payload.id)
        if (payload.error) reject(new Error(payload.error.message || JSON.stringify(payload.error)))
        else resolve(payload.result || {})
        return
      }
      this.events.push(payload)
      for (const listener of [...this.listeners]) listener(payload)
    })
  }

  async send(method, params = {}) {
    await this.ready
    const id = this.nextId++
    const payload = { id, method, params }
    const promise = new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
    })
    this.ws.send(JSON.stringify(payload))
    return promise
  }

  close() {
    try {
      this.ws.close()
    } catch {
      // niente da chiudere
    }
  }
}

async function evaluate(cdp, expression, timeoutMs = 10000) {
  const result = await cdp.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true,
    timeout: timeoutMs,
  })
  if (result.exceptionDetails) {
    const exception = result.exceptionDetails.exception || {}
    const text = exception.description || exception.value || result.exceptionDetails.text || 'Errore Runtime.evaluate'
    throw new Error(text)
  }
  return result.result?.value
}

async function pageEval(cdp, fn, args = [], timeoutMs = 10000) {
  return evaluate(cdp, `(${fn.toString()})(...${JSON.stringify(args)})`, timeoutMs)
}

async function waitReady(cdp) {
  await waitFor(
    () => evaluate(cdp, 'document.readyState === "interactive" || document.readyState === "complete"'),
    'pagina pronta',
    20000,
  )
}

async function waitVoiceShell(cdp, label, timeoutMs = 30000) {
  return waitFor(async () => {
    const state = await appState(cdp).catch(() => null)
    if (state?.commandCount === String(EXPECTED_PHRASE_COUNT) && !state.href.includes('/login')) {
      return state
    }
    return false
  }, label, timeoutMs, 250)
}

async function navigate(cdp, url) {
  await cdp.send('Page.navigate', { url })
  await waitReady(cdp)
}

async function browserJson(port, endpoint, options = {}) {
  const response = await fetch(`http://127.0.0.1:${port}${endpoint}`, options)
  if (!response.ok) throw new Error(`${endpoint} HTTP ${response.status}`)
  return response.json()
}

async function browserTargetUrls(port) {
  const targets = await browserJson(port, '/json/list')
  return targets.map((target) => target.url || '').filter(Boolean)
}

async function waitChrome(port) {
  return waitFor(() => browserJson(port, '/json/version').catch(() => null), 'debugger Chromium', 20000, 250)
}

async function createTarget(port) {
  try {
    return await browserJson(port, '/json/new?about:blank', { method: 'PUT' })
  } catch {
    return browserJson(port, '/json/new?about:blank')
  }
}

function normalizePathname(urlValue) {
  const parsed = new URL(urlValue, BASE_URL)
  let pathname = parsed.pathname.toLowerCase()
  if (pathname.length > 1) pathname = pathname.replace(/\/+$/, '')
  return `${pathname}${parsed.search}`
}

function expectedPath(value) {
  return normalizePathname(new URL(value, BASE_URL).href)
}

function firstVoicePhrase(command) {
  return command.phrases.find((phrase) => /^studio\s/i.test(phrase)) || command.phrases[0]
}

function normalizeVisibleText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('it-IT')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function routeContentTerms(command) {
  const configured = ROUTE_CONTENT_EXPECTATIONS[command.id] || []
  return Array.from(new Set([command.label, ...configured].filter(Boolean)))
}

function routeContentMatches(state, command) {
  const mainText = normalizeVisibleText(`${state.mainH1 || ''} ${state.mainText || ''}`)
  const terms = routeContentTerms(command)
  const matched = terms.filter((term) => mainText.includes(normalizeVisibleText(term)))
  return {
    ok: matched.length > 0,
    matched,
    expected: terms,
  }
}

function injectionScript() {
  const microphonePermissionState = MICROPHONE_GRANTED_DEVICE_HINT ? 'denied' : 'granted'
  return `
(() => {
  const speechLog = [];
  const recognitions = [];
  const notifications = [];
  const audit = { speechLog, recognitions, notifications };
  Object.defineProperty(window, '__iusentraVoiceAudit', { value: audit, configurable: true });

  class FakeAnalyser {
    constructor() {
      this.fftSize = 2048;
      this.frequencyBinCount = 1024;
    }
    getByteTimeDomainData(target) {
      for (let index = 0; index < target.length; index += 1) {
        target[index] = 128 + ((index % 17) - 8);
      }
    }
    getByteFrequencyData(target) {
      for (let index = 0; index < target.length; index += 1) {
        target[index] = index < 96 ? 42 : 5;
      }
    }
  }

  class FakeAudioContext {
    createMediaStreamSource() {
      return { connect() {}, disconnect() {} };
    }
    createAnalyser() {
      return new FakeAnalyser();
    }
    close() {
      return Promise.resolve();
    }
  }

  const fakeTrack = { stop() {}, kind: 'audio', enabled: true, readyState: 'live' };
  const fakeStream = { getTracks: () => [fakeTrack], getAudioTracks: () => [fakeTrack] };
  Object.defineProperty(navigator, 'mediaDevices', {
    value: {
      getUserMedia: async () => fakeStream,
      enumerateDevices: async () => [
        { kind: 'audioinput', label: 'Headset audit autorizzato', deviceId: 'default', groupId: 'audit' },
      ],
      addEventListener() {},
      removeEventListener() {},
    },
    configurable: true,
  });
  const nativePermissions = navigator.permissions;
  Object.defineProperty(navigator, 'permissions', {
    value: {
      query: async (descriptor) => {
        if (descriptor && descriptor.name === 'microphone') {
          return {
            state: '${microphonePermissionState}',
            onchange: null,
            addEventListener() {},
            removeEventListener() {},
          };
        }
        return nativePermissions?.query ? nativePermissions.query(descriptor) : { state: 'granted' };
      },
    },
    configurable: true,
  });
  Object.defineProperty(window, 'AudioContext', { value: FakeAudioContext, configurable: true });
  Object.defineProperty(window, 'webkitAudioContext', { value: FakeAudioContext, configurable: true });

  class FakeSpeechRecognition {
    constructor() {
      this.lang = 'it-IT';
      this.continuous = false;
      this.interimResults = false;
      this.maxAlternatives = 1;
      this.started = false;
      this.onresult = null;
      this.onerror = null;
      this.onend = null;
      recognitions.push(this);
    }
    start() {
      this.started = true;
      audit.activeRecognition = this;
    }
    stop() {
      this.started = false;
      if (typeof this.onend === 'function') window.setTimeout(() => this.onend(), 0);
    }
    abort() {
      this.started = false;
      if (typeof this.onend === 'function') window.setTimeout(() => this.onend(), 0);
    }
  }

  Object.defineProperty(window, 'SpeechRecognition', { value: FakeSpeechRecognition, configurable: true });
  Object.defineProperty(window, 'webkitSpeechRecognition', { value: FakeSpeechRecognition, configurable: true });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', {
    value: class SpeechSynthesisUtterance {
      constructor(text) {
        this.text = text;
        this.lang = 'it-IT';
        this.rate = 1;
      }
    },
    configurable: true,
  });
  Object.defineProperty(window, 'speechSynthesis', {
    value: {
      speak(utterance) {
        speechLog.push({ type: 'speak', text: String(utterance?.text || '') });
        window.setTimeout(() => {
          if (typeof utterance?.onend === 'function') utterance.onend();
        }, 20);
      },
      cancel() {},
      getVoices() { return []; },
      paused: false,
      pending: false,
      speaking: false,
    },
    configurable: true,
  });

  class FakeNotification {
    static permission = 'default';
    static requestPermission() {
      FakeNotification.permission = 'granted';
      return Promise.resolve('granted');
    }
    constructor(title, options = {}) {
      this.title = title;
      this.options = options;
      notifications.push({ title, options });
    }
    close() {}
  }
  Object.defineProperty(window, 'Notification', { value: FakeNotification, configurable: true });

  Object.defineProperty(window, '__emitSpeech', {
    value(transcript) {
      const recognition = [...recognitions].reverse().find((item) => item.started) || audit.activeRecognition;
      if (!recognition || typeof recognition.onresult !== 'function') return false;
      speechLog.push({ type: 'heard', text: transcript, continuous: Boolean(recognition.continuous) });
      const results = [[{ transcript }]];
      results[0].isFinal = true;
      recognition.onresult({ resultIndex: 0, results });
      if (!recognition.continuous && typeof recognition.onend === 'function') {
        window.setTimeout(() => recognition.onend(), 0);
      }
      return true;
    },
    configurable: true,
  });
})();
`
}

async function appState(cdp) {
  return pageEval(cdp, (forbiddenTerms) => {
    const root = document.querySelector('[data-testid="studio-voice-assistant"]')
    const panel = document.querySelector('.iu-voice-panel')
    const panelRect = panel?.getBoundingClientRect()
    const main = document.querySelector('main.iu-content') || document.querySelector('.iu-main main') || document.querySelector('main')
    const mainText = main?.innerText || ''
    const visibleText = document.body?.innerText || ''
    const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const forbiddenContexts = forbiddenTerms.flatMap((term) => {
      const contexts = []
      const pattern = new RegExp(`(^|[^a-z0-9_])(${escapeRegExp(term)})(?=$|[^a-z0-9_])`, 'gi')
      let match = pattern.exec(visibleText)
      while (match) {
        const index = match.index + match[1].length
        const start = Math.max(0, index - 90)
        const end = Math.min(visibleText.length, index + term.length + 90)
        contexts.push({
          term,
          context: visibleText.slice(start, end).replace(/\s+/g, ' ').trim(),
        })
        match = pattern.exec(visibleText)
      }
      return contexts
    })
    const buttons = Array.from((panel || document).querySelectorAll('button')).map((button) => {
      const rect = button.getBoundingClientRect()
      return {
        text: (button.innerText || button.getAttribute('aria-label') || button.title || '').trim(),
        disabled: button.disabled,
        width: Math.round(rect.width),
        scrollWidth: button.scrollWidth,
        overflow: button.scrollWidth > Math.ceil(rect.width) + 1,
      }
    })
    return {
      href: location.href,
      title: document.title,
      h1: document.querySelector('h1')?.textContent?.trim() || '',
      mainH1: main?.querySelector('h1')?.textContent?.trim() || '',
      mainText: mainText.replace(/\s+/g, ' ').trim().slice(0, 4000),
      voiceState: root?.getAttribute('data-voice-state') || '',
      microphonePermission: root?.getAttribute('data-microphone-permission') || '',
      microphoneUnlockVisible: Boolean(document.querySelector('[data-microphone-unlock="chrome"]')),
      microphoneUnlockText: document.querySelector('[data-microphone-unlock="chrome"]')?.innerText?.replace(/\s+/g, ' ').trim() || '',
      commandCount: root?.getAttribute('data-voice-command-count') || '',
      panelOpen: Boolean(panel),
      panelVisible: Boolean(panelRect && panelRect.width > 20 && panelRect.height > 20),
      panelRect: panelRect
        ? {
          x: Math.round(panelRect.x),
          y: Math.round(panelRect.y),
          width: Math.round(panelRect.width),
          height: Math.round(panelRect.height),
        }
        : null,
      status: document.querySelector('.iu-voice-status span')?.textContent?.trim() || '',
      clientMessage: document.querySelector('.iu-voice-note.strong')?.textContent?.trim() || '',
      clientHref: document.querySelector('.iu-voice-link')?.getAttribute('href') || '',
      clientStep: document.querySelector('[data-voice-client-step]')?.getAttribute('data-voice-client-step') || '',
      noteTriggerValue: document.querySelector('.iu-voice-note-command input')?.value || '',
      noteTriggerStored: window.localStorage?.getItem('iusentra:studio-voice-note-trigger') || '',
      noteDraft: document.querySelector('.iu-voice-transcript-box p')?.textContent?.trim() || '',
      noteCards: Array.from(document.querySelectorAll('.iu-voice-note-card')).map((card) => card.innerText.replace(/\s+/g, ' ').trim()),
      noteMeta: document.querySelector('.iu-voice-note-meta')?.innerText?.replace(/\s+/g, ' ').trim() || '',
      auditNotifications: window.__iusentraVoiceAudit?.notifications || [],
      bodyOverflowX: document.documentElement
        ? document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
        : false,
      forbiddenVisible: Array.from(new Set(forbiddenContexts.map((item) => item.term))),
      forbiddenContexts,
      emptyVisibleButtons: buttons.filter((button) => !button.text),
      overflowingButtons: buttons.filter((button) => button.overflow),
      requiredVoiceTextsMissing: [
        'Assistente vocale Studio',
        'Configurazione',
        'Comandi autorizzati',
        'Richieste operative',
        'Note vocali',
        'Comando note personalizzato',
        'Fuso orario: Roma',
        'Promemoria',
      ].filter((text) => !visibleText.includes(text)),
      textSample: visibleText.slice(0, 1400),
    }
  }, [forbiddenVisibleTerms])
}

async function openVoicePanel(cdp) {
  await waitFor(async () => pageEval(cdp, () => {
    const panel = document.querySelector('.iu-voice-panel')
    const panelRect = panel?.getBoundingClientRect()
    if (panelRect && panelRect.width > 20 && panelRect.height > 20) return true
    const trigger = document.querySelector('.iu-voice-assistant__trigger')
    if (!trigger) return false
    trigger.click()
    return true
  }).catch(() => false), 'pulsante assistente vocale disponibile', 30000, 250)
  try {
    await waitFor(async () => (await appState(cdp)).panelVisible, 'pannello vocale visibile')
  } catch (error) {
    const debugState = await pageEval(cdp, () => {
      const trigger = document.querySelector('.iu-voice-assistant__trigger')
      const panel = document.querySelector('.iu-voice-panel')
      const triggerRect = trigger?.getBoundingClientRect()
      const panelRect = panel?.getBoundingClientRect()
      const panelStyle = panel ? getComputedStyle(panel) : null
      const toRect = (rect) => rect
        ? { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) }
        : null
      return {
        triggerExists: Boolean(trigger),
        triggerText: trigger?.innerText || '',
        triggerAriaExpanded: trigger?.getAttribute('aria-expanded') || '',
        triggerRect: toRect(triggerRect),
        panelExists: Boolean(panel),
        panelRect: toRect(panelRect),
        panelComputed: panelStyle
          ? {
            position: panelStyle.position,
            top: panelStyle.top,
            right: panelStyle.right,
            bottom: panelStyle.bottom,
            left: panelStyle.left,
            width: panelStyle.width,
            height: panelStyle.height,
            maxHeight: panelStyle.maxHeight,
            overflowY: panelStyle.overflowY,
            display: panelStyle.display,
            zIndex: panelStyle.zIndex,
          }
          : null,
        viewport: { width: window.innerWidth, height: window.innerHeight },
        panelHtmlStart: panel?.outerHTML?.slice(0, 400) || '',
      }
    }).catch((stateError) => ({ debugError: stateError.message }))
    throw new Error(`${error.message}; debug=${JSON.stringify(debugState)}`)
  }
}

async function clickVoiceButton(cdp, text) {
  const result = await pageEval(cdp, (label) => {
    const buttons = Array.from(document.querySelectorAll('.iu-voice-panel button'))
    const button = buttons.find((item) => (item.innerText || item.getAttribute('aria-label') || '').trim().includes(label))
    const available = buttons.map((item) => ({
      text: (item.innerText || item.getAttribute('aria-label') || '').trim(),
      disabled: item.disabled,
    }))
    if (!button) return { ok: false, message: `Pulsante non trovato: ${label}`, available }
    if (button.disabled) return { ok: false, message: `Pulsante disabilitato: ${label}`, available }
    button.click()
    return { ok: true, available }
  }, [text])
  if (!result?.ok) {
    throw new Error(`${result?.message || 'Pulsante non azionato'}; presenti=${JSON.stringify(result?.available || [])}`)
  }
  return true
}

async function clickVoiceTab(cdp, text) {
  const result = await pageEval(cdp, (label) => {
    const tabs = Array.from(document.querySelectorAll('.iu-voice-tab'))
    const tab = tabs.find((item) => (item.innerText || '').trim().includes(label))
    if (!tab) return { ok: false, labels: tabs.map((item) => (item.innerText || '').trim()) }
    tab.click()
    return { ok: true, labels: tabs.map((item) => (item.innerText || '').trim()) }
  }, [text])
  if (!result?.ok) {
    throw new Error(`Tab vocale non trovata: ${text}; presenti=${JSON.stringify(result?.labels || [])}`)
  }
  await sleep(150)
}

async function emitSpeech(cdp, transcript) {
  const emitted = await pageEval(cdp, (value) => {
    if (typeof window.__emitSpeech !== 'function') return false
    return window.__emitSpeech(value)
  }, [transcript])
  if (!emitted) throw new Error(`Nessun riconoscimento vocale attivo per: ${transcript}`)
}

async function registerProfile(cdp) {
  await openVoicePanel(cdp)
  const alreadyReady = await pageEval(cdp, () => Array.from(document.querySelectorAll('.iu-voice-panel button'))
    .some((button) => (button.innerText || '').includes('Attiva ascolto')))
  if (alreadyReady) return
  await pageEval(cdp, (pin) => {
    const input = document.querySelector('.iu-voice-setup input')
    if (!input) throw new Error('Campo PIN registrazione non trovato')
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value')?.set
    setter ? setter.call(input, pin) : (input.value = pin)
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }, [PIN])
  await clickVoiceButton(cdp, 'Registra voce e PIN')
  await waitFor(async () => pageEval(cdp, (transcript) => {
    if (typeof window.__emitSpeech !== 'function') return false
    return window.__emitSpeech(transcript)
  }, [CALIBRATION_TRANSCRIPT]).catch(() => false), 'trascrizione frase calibrazione', 15000)
  await sleep(1200)
  await pageEval(cdp, (transcript) => {
    if (typeof window.__emitSpeech !== 'function') return false
    return window.__emitSpeech(transcript)
  }, [CALIBRATION_TRANSCRIPT]).catch(() => false)
  try {
    await waitFor(async () => {
      const status = (await appState(cdp)).status.toLowerCase()
      return status.includes('salvati') || status.includes('registrati')
    }, 'registrazione voce e PIN', 75000)
  } catch (error) {
    const state = await appState(cdp).catch((stateError) => ({ error: stateError.message }))
    throw new Error(`${error.message}; stato=${JSON.stringify(state)}`)
  }
  await waitFor(async () => pageEval(cdp, () => Array.from(document.querySelectorAll('.iu-voice-panel button'))
    .some((button) => (button.innerText || '').includes('Attiva ascolto'))), 'pulsante attiva ascolto dopo registrazione', 10000)
}

async function activateVoice(cdp) {
  await openVoicePanel(cdp)
  if ((await appState(cdp)).voiceState === 'active') return
  await clickVoiceTab(cdp, 'Configurazione')
  await clickVoiceButton(cdp, 'Attiva ascolto')
  await waitFor(async () => {
    const state = await appState(cdp)
    return state.status.includes('Sto ascoltando il PIN') || state.status.includes('PIN in ascolto') || state.textSample.includes('PIN in ascolto')
  }, 'richiesta PIN vocale', 20000)
  await emitSpeech(cdp, SPOKEN_PIN)
  await waitFor(async () => (await appState(cdp)).voiceState === 'active', 'ascolto attivo', 15000)
}

async function activateOperativeSession(cdp) {
  await activateVoice(cdp)
  await waitFor(async () => {
    const state = await appState(cdp)
    if (state.status.includes('Sessione operativa attiva') || state.textSample.includes('Sessione operativa attiva')) return state
    return state.status.includes('Richiamo pronto') || state.textSample.includes('Richiamo pronto') ? state : false
  }, 'richiamo pronto prima della sessione operativa', 15000)
  const current = await appState(cdp)
  if (current.status.includes('Sessione operativa attiva') || current.textSample.includes('Sessione operativa attiva')) {
    return current
  }
  await sleep(300)
  await emitSpeech(cdp, 'Studio')
  return waitFor(async () => {
    const state = await appState(cdp)
    return state.status.includes('Sessione operativa attiva') || state.textSample.includes('Sessione operativa attiva') ? state : false
  }, 'sessione operativa attiva', 15000)
}

async function configureVoiceNoteCommand(cdp, phrase) {
  await openVoicePanel(cdp)
  await clickVoiceTab(cdp, 'Note vocali')
  await pageEval(cdp, (value) => {
    const input = document.querySelector('.iu-voice-note-command input')
    if (!input) throw new Error('Campo comando note non trovato')
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value')?.set
    setter ? setter.call(input, value) : (input.value = value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }, [phrase])
  await clickVoiceButton(cdp, 'Salva comando')
  await waitFor(async () => {
    const state = await appState(cdp)
    return state.noteTriggerValue === phrase && state.noteTriggerStored === phrase
  }, 'comando note personalizzato salvato', 10000)
}

async function auditFieldDictation(cdp) {
  await navigate(cdp, `${BASE_URL}/clienti/nuovo`)
  await waitVoiceShell(cdp, 'pagina nuovo cliente per dettatura campi', 30000)
  await waitFor(async () => pageEval(cdp, () => {
    return Boolean(window.IusentraVoiceInput && document.querySelector('input[name="telefono"]'))
  }).catch(() => false), 'servizio dettatura e campi anagrafici disponibili', 20000)

  const result = await pageEval(cdp, () => {
    const normalize = (value) => String(value || '').trim()
    const insert = (selector, text) => {
      const element = document.querySelector(selector)
      if (!element) throw new Error(`Campo non trovato: ${selector}`)
      element.scrollIntoView({ block: 'center', inline: 'nearest' })
      element.focus()
      window.IusentraVoiceInput.insertTextIntoTarget(element, text, { selectInserted: true })
      return normalize(element.value)
    }
    const values = {
      nome: insert('input[name="nome"]', 'mario'),
      telefono: insert('input[name="telefono"]', 'zero zero cento'),
      cap: insert('input[name="cap"]', 'zero zero cento'),
      numeroDocumento: insert('input[name="doc_numero"]', 'CA 61 007 P'),
      email: insert('input[name="email"]', 'ant-mm 2605@gmail.com'),
      pec: insert('input[name="pec"]', 'studio-legale@example.com'),
      sitoWeb: insert('input[name="sito_web"]', 'Www.Marco.rossi.it'),
      dataNascita: insert('input[name="data_nascita"]', 'tredici giugno duemila ventisei'),
      dataRilascio: insert('input[name="doc_data_rilascio"]', 'sette giugno duemila ventisei'),
      sesso: insert('select[name="sesso"]', 'femminile'),
    }
    const form = document.querySelector('form')
    return {
      href: location.href,
      h1: document.querySelector('h1')?.textContent?.trim() || '',
      values,
      visibleText: (form?.innerText || document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 1200),
      activeName: document.activeElement?.getAttribute?.('name') || '',
    }
  }, [], 20000)

  const expected = {
    nome: 'Mario',
    telefono: '00100',
    cap: '00100',
    numeroDocumento: 'CA61007P',
    email: 'antmm2605@gmail.com',
    pec: 'studio-legale@example.com',
    sitoWeb: 'www.marco.rossi.it',
    dataNascita: '2026-06-13',
    dataRilascio: '2026-06-07',
    sesso: 'F',
  }
  const mismatches = Object.entries(expected)
    .filter(([key, value]) => result.values?.[key] !== value)
    .map(([key, value]) => ({ field: key, expected: value, actual: result.values?.[key] || '' }))
  await screenshot(cdp, FIELD_DICTATION_SCREENSHOT)
  return {
    ...result,
    expected,
    mismatches,
    screenshot: path.relative(ROOT, FIELD_DICTATION_SCREENSHOT),
  }
}

async function setViewport(cdp, width, height) {
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 700,
  })
  await sleep(300)
}

async function screenshot(cdp, filePath) {
  const capture = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  fs.writeFileSync(filePath, Buffer.from(capture.data, 'base64'))
}

async function scrollVoicePanel(cdp, position = 'top') {
  return pageEval(cdp, (targetPosition) => {
    const panel = document.querySelector('.iu-voice-panel')
    const scrollTargets = [
      panel,
      document.querySelector('.iu-voice-panel__body'),
      document.querySelector('[data-testid="studio-voice-assistant"]'),
    ].filter(Boolean)
    const results = []
    for (const target of scrollTargets) {
      if (target.scrollHeight <= target.clientHeight + 1) continue
      const top = targetPosition === 'bottom'
        ? target.scrollHeight
        : targetPosition === 'middle'
          ? Math.round((target.scrollHeight - target.clientHeight) / 2)
          : 0
      target.scrollTop = top
      results.push({
        className: target.className || target.getAttribute('data-testid') || target.tagName,
        scrollTop: Math.round(target.scrollTop),
        scrollHeight: Math.round(target.scrollHeight),
        clientHeight: Math.round(target.clientHeight),
      })
    }
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    return results
  }, [position])
}

async function cleanupCreatedClient(cdp, id) {
  if (!id) return null
  return pageEval(cdp, async (clientId) => {
    const response = await fetch('/api/v1/ui/clienti/delete', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ ids: [clientId] }),
    })
    return { status: response.status, payload: await response.json().catch(() => ({})) }
  }, [id], 20000)
}

async function routeByVoice(cdp, command) {
  const startedAt = Date.now()
  const phrase = firstVoicePhrase(command)
  await activateOperativeSession(cdp)
  const before = await appState(cdp)
  await emitSpeech(cdp, phrase)
  const target = expectedPath(command.href)
  const targetHasSearch = target.includes('?')
  const finalHref = await waitFor(async () => {
    const state = await appState(cdp)
    const actual = normalizePathname(state.href)
    if (actual === target) return state.href
    if (!targetHasSearch && actual.split('?')[0] === target.split('?')[0]) return state.href
    if (command.href === '/' && actual === '/') return state.href
    return false
  }, `navigazione ${command.id} verso ${command.href}`, 25000, 250)
  const after = await waitFor(async () => {
    const state = await appState(cdp)
    if (state.commandCount !== String(EXPECTED_PHRASE_COUNT) || state.href.includes('/login')) return false
    const sameDestination = normalizePathname(before.href) === normalizePathname(state.href)
    const visibleAreaChanged = sameDestination || state.mainH1 !== before.mainH1 || state.mainText !== before.mainText
    if (!visibleAreaChanged) return false
    const match = routeContentMatches(state, command)
    if (!match.ok) return false
    return { ...state, routeContentMatch: match }
  }, `contenuto visibile ${command.id}`, 90000, 300)
  return {
    id: command.id,
    label: command.label,
    phrase,
    expected: command.href,
    expectedContent: after.routeContentMatch.expected,
    matchedContent: after.routeContentMatch.matched,
    before: before.href,
    href: finalHref,
    h1: after.mainH1 || after.h1,
    commandCount: after.commandCount,
    elapsedMs: Date.now() - startedAt,
    forbiddenVisible: after.forbiddenVisible,
    forbiddenContexts: after.forbiddenContexts,
    bodyOverflowX: after.bodyOverflowX,
  }
}

async function main() {
  fs.mkdirSync(REPORT_DIR, { recursive: true })
  const chromePath = findChrome()
  const port = 9700 + Number.parseInt(crypto.randomBytes(1).toString('hex'), 16)
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'iusentra-voice-audit-'))
  const chromeArgs = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1365,768',
    'about:blank',
  ]
  if (!REAL_MICROPHONE) {
    chromeArgs.splice(5, 0, '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream')
  }
  if (!VISIBLE_BROWSER) {
    chromeArgs.unshift('--headless=new')
  }
  const chrome = spawn(chromePath, chromeArgs, { stdio: 'ignore' })

  const report = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    chromePath,
    visibleBrowser: VISIBLE_BROWSER,
    totalPhrases: EXPECTED_PHRASE_COUNT,
    routeCommandCount: commandCatalog.routeCommands.length,
    specialCommandCount: commandCatalog.specialCommands.length,
    screenshots: {
      desktop: path.relative(ROOT, DESKTOP_SCREENSHOT),
      mobile: path.relative(ROOT, MOBILE_SCREENSHOT),
    },
    consoleErrors: [],
    responsive: [],
    special: {},
    routes: [],
    failures: [],
  }

  let cdp = null
  try {
    await waitChrome(port)
    const target = await createTarget(port)
    cdp = new CdpConnection(target.webSocketDebuggerUrl)
    await cdp.ready
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Network.enable')
    await cdp.send('Log.enable')
    if (!REAL_MICROPHONE) {
      await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: injectionScript() })
    }

    cdp.listeners.push((event) => {
      if (event.method === 'Runtime.exceptionThrown') {
        report.consoleErrors.push({ type: 'exception', details: event.params?.exceptionDetails?.text || '' })
      }
      if (event.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(event.params?.type)) {
        report.consoleErrors.push({
          type: event.params.type,
          details: (event.params.args || []).map((arg) => arg.value || arg.description || '').join(' '),
        })
      }
      if (event.method === 'Log.entryAdded' && ['error', 'warning'].includes(event.params?.entry?.level)) {
        report.consoleErrors.push({
          type: event.params.entry.level,
          details: event.params.entry.text,
          url: event.params.entry.url,
        })
      }
    })

    await setViewport(cdp, 1365, 768)
    await navigate(cdp, `${BASE_URL}/login?next=/`)
    await pageEval(cdp, ([studio, username, password]) => {
      const setValue = (selector, value) => {
        const input = document.querySelector(selector)
        if (!input) throw new Error(`Campo login mancante: ${selector}`)
        input.value = value
        input.dispatchEvent(new Event('input', { bubbles: true }))
      }
      setValue('input[name="studio_slug"]', studio)
      setValue('input[name="username"]', username)
      setValue('input[name="password"]', password)
      document.querySelector('button[type="submit"]').click()
      return true
    }, [[STUDIO_SLUG, USERNAME, PASSWORD]])
    await waitFor(async () => {
      const state = await appState(cdp).catch(() => null)
      return state?.commandCount === String(EXPECTED_PHRASE_COUNT) && !state.href.includes('/login')
    }, 'login studio e shell React', 180000)

    if (PERMISSION_ONLY) {
      await openVoicePanel(cdp)
      await clickVoiceTab(cdp, 'Configurazione')
      const beforePermission = await appState(cdp)
      await clickVoiceButton(cdp, 'Verifica microfono')
      await sleep(12000)
      const afterPermission = await appState(cdp)
      const deniedButUnguided = afterPermission.microphonePermission === 'denied'
        && (!afterPermission.microphoneUnlockVisible
          || !afterPermission.microphoneUnlockText.includes('Sblocca microfono in Chrome')
          || !afterPermission.microphoneUnlockText.includes('Ho sbloccato, verifica'))
      if (deniedButUnguided) {
        throw new Error(`Microfono bloccato senza flusso guidato di sblocco: ${JSON.stringify(afterPermission)}`)
      }
      const permissionGranted = afterPermission.microphonePermission === 'granted'
      let beforeUnlockUrls = []
      let afterUnlockUrls = []
      let unlockStatus = afterPermission
      let openedChromeSettings = false
      let unlockStatusActionable = false
      let unlockSkippedReason = ''
      if (permissionGranted) {
        unlockSkippedReason = 'Microfono gia concesso: il pulsante di sblocco deve restare nascosto.'
        if (afterPermission.microphoneUnlockVisible) {
          throw new Error(`Microfono concesso ma pannello sblocco ancora visibile: ${JSON.stringify(afterPermission)}`)
        }
      } else {
        beforeUnlockUrls = await browserTargetUrls(port)
        await clickVoiceButton(cdp, 'Sblocca microfono in Chrome')
        await sleep(1500)
        afterUnlockUrls = await browserTargetUrls(port)
        unlockStatus = await appState(cdp)
        openedChromeSettings = afterUnlockUrls.some((url) => url.startsWith('chrome://settings/content/siteDetails'))
        unlockStatusActionable = [
          'Ho aperto lo sblocco microfono di Chrome',
          'Ho copiato',
          'Indirizzo di sblocco copiato',
          'Apri le impostazioni del sito in Chrome',
          'Chrome non ha consentito apertura o copia automatica',
        ].some((text) => unlockStatus.status.includes(text))
        if (!openedChromeSettings && !unlockStatusActionable) {
          throw new Error(`Click sblocco microfono senza esito guidato: ${JSON.stringify({ beforeUnlockUrls, afterUnlockUrls, status: unlockStatus.status })}`)
        }
      }
      const topScroll = await scrollVoicePanel(cdp, 'top')
      await screenshot(cdp, MICROPHONE_SCREENSHOT)
      const bottomScroll = await scrollVoicePanel(cdp, 'bottom')
      await sleep(250)
      await screenshot(cdp, MICROPHONE_BOTTOM_SCREENSHOT)
      const permissionReport = {
        generatedAt: new Date().toISOString(),
        baseUrl: BASE_URL,
        chromePath,
        visibleBrowser: VISIBLE_BROWSER,
        realMicrophone: REAL_MICROPHONE,
        permissionOnly: true,
        screenshot: path.relative(ROOT, MICROPHONE_SCREENSHOT),
        bottomScreenshot: path.relative(ROOT, MICROPHONE_BOTTOM_SCREENSHOT),
        before: beforePermission,
        after: afterPermission,
        unlockAction: {
          beforeTargetUrls: beforeUnlockUrls,
          afterTargetUrls: afterUnlockUrls,
          openedChromeSettings,
          statusAfterClick: unlockStatus.status,
          statusActionable: unlockStatusActionable,
          skippedReason: unlockSkippedReason,
        },
        scrollAudit: {
          top: topScroll,
          bottom: bottomScroll,
        },
        interpretation: afterPermission.microphonePermission === 'granted'
          ? 'Il browser ha concesso il microfono.'
          : afterPermission.microphonePermission === 'denied'
            ? 'Il browser sta bloccando il microfono: la registrazione non deve partire e il profilo non deve essere salvato.'
            : 'Il browser non ha ancora concesso il microfono: serve il consenso esplicito nella richiesta del browser.',
      }
      fs.writeFileSync(MICROPHONE_PERMISSION_REPORT_PATH, JSON.stringify(permissionReport, null, 2))
      console.log(`Audit permesso microfono Chrome completato: ${MICROPHONE_PERMISSION_REPORT_PATH}`)
      console.log(permissionReport.interpretation)
      return
    }

    await registerProfile(cdp)
    report.special.afterRegister = await appState(cdp)
    await activateVoice(cdp)
    report.special.activation = await appState(cdp)

    await configureVoiceNoteCommand(cdp, 'appunti')
    await clickVoiceButton(cdp, 'Consenti promemoria')
    await waitFor(async () => (await appState(cdp)).noteMeta.includes('abilitate'), 'permesso promemoria note', 10000)
    await activateOperativeSession(cdp)
    await emitSpeech(cdp, 'appunti domani alle 18 ricordami di controllare la PEC del fascicolo Bianchi fine nota')
    let scheduledNote
    try {
      scheduledNote = await waitFor(async () => {
        const state = await appState(cdp)
        return state.noteCards.some((card) => card.includes('Evento:') && card.includes('Promemoria browser:')) ? state : false
      }, 'nota vocale con data e promemoria', 10000)
    } catch (error) {
      report.special.voiceNoteFailureState = await appState(cdp).catch((stateError) => ({ error: stateError.message }))
      throw error
    }
    await emitSpeech(cdp, 'appunti ricordami tra 1 minuto di richiamare il cliente fine nota')
    const remindedNote = await waitFor(async () => {
      const state = await appState(cdp)
      return state.auditNotifications.length > 0 || state.status.includes('Promemoria nota') ? state : false
    }, 'promemoria browser note simulato', 10000)
    report.special.voiceNotes = {
      trigger: scheduledNote.noteTriggerValue,
      firstNote: scheduledNote.noteCards[0] || '',
      noteMeta: scheduledNote.noteMeta,
      reminderStatus: remindedNote.status,
      notificationCount: remindedNote.auditNotifications.length,
    }

    for (const item of [
      { name: 'desktop', width: 1365, height: 768, screenshot: DESKTOP_SCREENSHOT },
      { name: 'tablet', width: 820, height: 1180 },
      { name: 'mobile', width: 390, height: 844, screenshot: MOBILE_SCREENSHOT },
    ]) {
      await setViewport(cdp, item.width, item.height)
      await openVoicePanel(cdp)
      await clickVoiceTab(cdp, 'Note vocali')
      const state = await appState(cdp)
      report.responsive.push({
        name: item.name,
        width: item.width,
        height: item.height,
        bodyOverflowX: state.bodyOverflowX,
        forbiddenVisible: state.forbiddenVisible,
        emptyVisibleButtons: state.emptyVisibleButtons,
        overflowingButtons: state.overflowingButtons,
        requiredVoiceTextsMissing: state.requiredVoiceTextsMissing,
      })
      if (item.screenshot) await screenshot(cdp, item.screenshot)
    }
    await setViewport(cdp, 1365, 768)

    report.special.fieldDictation = await auditFieldDictation(cdp)
    if (report.special.fieldDictation.mismatches.length) {
      report.failures.push({ type: 'field-dictation', fieldDictation: report.special.fieldDictation })
    }

    await activateOperativeSession(cdp)
    await emitSpeech(cdp, 'aiuto')
    report.special.help = await appState(cdp)

    await activateOperativeSession(cdp)
    await emitSpeech(cdp, 'apri Lex')
    await sleep(700)
    report.special.lex = await pageEval(cdp, () => ({
      href: location.href,
      status: document.querySelector('.iu-voice-status span')?.textContent?.trim() || '',
      hasLexText: (document.body.innerText || '').includes('Lex'),
    }))

    await activateOperativeSession(cdp)
    await emitSpeech(cdp, 'cerca Rossi')
    await waitFor(async () => normalizePathname(await evaluate(cdp, 'location.href')) === '/global-search?q=rossi', 'ricerca vocale Rossi', 20000)
    report.special.search = await appState(cdp)
    await navigate(cdp, `${BASE_URL}/`)
    await waitFor(async () => (await appState(cdp)).commandCount === String(EXPECTED_PHRASE_COUNT), 'ritorno dopo ricerca vocale', 20000)

    await activateOperativeSession(cdp)
    await emitSpeech(cdp, 'nuovo cliente')
    await waitFor(async () => (await appState(cdp)).clientStep === 'nome', 'richiesta nome cliente', 10000)
    await emitSpeech(cdp, 'Luca')
    await waitFor(async () => (await appState(cdp)).clientStep === 'cognome', 'richiesta cognome cliente', 10000)
    await emitSpeech(cdp, 'Verdi')
    await waitFor(async () => (await appState(cdp)).clientStep === 'codice_fiscale', 'richiesta codice fiscale cliente', 10000)
    const cfTail = String(500 + (Date.now() % 400)).padStart(3, '0')
    const fiscalCode = `VRDLCU90A01H${cfTail}X`
    await emitSpeech(cdp, fiscalCode)
    await waitFor(async () => (await appState(cdp)).clientStep === 'confirm', 'conferma dati cliente', 10000)
    const confirmation = await appState(cdp)
    await emitSpeech(cdp, 'confermo')
    const savedState = await waitFor(async () => {
      const state = await appState(cdp)
      return state.clientStep === 'success' ? state : false
    }, 'salvataggio cliente vocale', 20000)
    const createdId = savedState.clientHref.split('/').filter(Boolean).pop() || ''
    const cleanup = await cleanupCreatedClient(cdp, createdId)
    report.special.newClient = {
      fiscalCode,
      confirmation: confirmation.clientMessage,
      message: savedState.clientMessage,
      href: savedState.clientHref,
      createdId,
      cleanup,
    }

    await activateOperativeSession(cdp)
    await emitSpeech(cdp, 'disattiva assistente')
    await waitFor(async () => (await appState(cdp)).voiceState === 'idle', 'disattivazione ascolto', 10000)
    report.special.stop = await appState(cdp)

    await navigate(cdp, `${BASE_URL}/`)
    await waitFor(async () => (await appState(cdp)).commandCount === String(EXPECTED_PHRASE_COUNT), 'ritorno panoramica', 20000)
    for (const command of commandCatalog.routeCommands) {
      const routeResult = await routeByVoice(cdp, command)
      report.routes.push(routeResult)
      if (routeResult.forbiddenVisible.length || routeResult.bodyOverflowX || routeResult.commandCount !== String(EXPECTED_PHRASE_COUNT)) {
        report.failures.push({ type: 'route-quality', route: routeResult })
      }
    }

    await activateOperativeSession(cdp)
    const beforeBack = await evaluate(cdp, 'location.href')
    await emitSpeech(cdp, 'torna indietro')
    await waitFor(async () => (await evaluate(cdp, 'location.href')) !== beforeBack, 'torna indietro vocale', 15000)
    await waitFor(async () => (await appState(cdp)).commandCount === String(EXPECTED_PHRASE_COUNT), 'shell React dopo torna indietro', 20000)
    report.special.back = await appState(cdp)

    await activateOperativeSession(cdp)
    const beforeReload = await evaluate(cdp, 'location.href')
    await emitSpeech(cdp, 'ricarica pagina')
    await waitReady(cdp)
    report.special.reload = { before: beforeReload, after: await evaluate(cdp, 'location.href') }

    const routeDurations = report.routes.map((route) => route.elapsedMs).filter((value) => Number.isFinite(value))
    const sortedRouteDurations = [...routeDurations].sort((left, right) => left - right)
    const slowestRoutes = [...report.routes]
      .sort((left, right) => (right.elapsedMs || 0) - (left.elapsedMs || 0))
      .slice(0, 8)
      .map((route) => ({
        id: route.id,
        label: route.label,
        href: route.href,
        elapsedMs: route.elapsedMs,
      }))
    const voiceNavigation = routeDurations.length ? {
      count: routeDurations.length,
      minMs: sortedRouteDurations[0],
      avgMs: Math.round(routeDurations.reduce((total, value) => total + value, 0) / routeDurations.length),
      p95Ms: sortedRouteDurations[Math.min(sortedRouteDurations.length - 1, Math.floor(sortedRouteDurations.length * 0.95))],
      maxMs: sortedRouteDurations[sortedRouteDurations.length - 1],
      slowestRoutes,
    } : null

    report.performance = await pageEval(cdp, () => {
      const navigation = performance.getEntriesByType('navigation')[0]
      const timing = performance.timing
      const legacyNavigation = timing && timing.navigationStart ? {
        domContentLoaded: Math.max(0, timing.domContentLoadedEventEnd - timing.navigationStart),
        loadEventEnd: Math.max(0, timing.loadEventEnd - timing.navigationStart),
        responseEnd: Math.max(0, timing.responseEnd - timing.navigationStart),
      } : null
      const resources = performance.getEntriesByType('resource')
        .filter((entry) => entry.duration > 700 || /StudioVoiceAssistant|index-.*\\.(js|css)$/.test(entry.name))
        .map((entry) => ({
          name: entry.name.replace(location.origin, ''),
          duration: Math.round(entry.duration),
          transferSize: entry.transferSize || 0,
          encodedBodySize: entry.encodedBodySize || 0,
        }))
        .slice(0, 30)
      return {
        navigation: navigation ? {
          type: navigation.type,
          domContentLoaded: Math.round(navigation.domContentLoadedEventEnd),
          loadEventEnd: Math.round(navigation.loadEventEnd),
          duration: Math.round(navigation.duration),
        } : null,
        legacyNavigation,
        resources,
      }
    })
    report.performance.voiceNavigation = voiceNavigation

    for (const responsive of report.responsive) {
      if (
        responsive.bodyOverflowX ||
        responsive.forbiddenVisible.length ||
        responsive.emptyVisibleButtons.length ||
        responsive.overflowingButtons.length ||
        responsive.requiredVoiceTextsMissing.length
      ) {
        report.failures.push({ type: 'responsive-quality', responsive })
      }
    }

    const blockingConsole = report.consoleErrors.filter((entry) => {
      const details = String(entry.details || '')
      return !/favicon|AbortError|ResizeObserver/i.test(details)
    })
    if (blockingConsole.length) {
      report.failures.push({ type: 'console', entries: blockingConsole })
    }
  } catch (error) {
    report.failures.push({ type: 'fatal', message: error?.stack || String(error) })
  } finally {
    if (cdp) cdp.close()
    try {
      chrome.kill()
      await Promise.race([
        new Promise((resolve) => chrome.once('exit', resolve)),
        sleep(2500),
      ])
    } catch (error) {
      report.cleanupWarning = `Chiusura Chromium non completata: ${error?.message || error}`
    }
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        fs.rmSync(userDataDir, { recursive: true, force: true })
        break
      } catch (error) {
        if (attempt === 4) report.cleanupWarning = `Profilo Chromium temporaneo non rimosso: ${error?.message || error}`
        await sleep(500)
      }
    }
    fs.writeFileSync(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  }

  if (report.failures.length) {
    console.error(`Audit assistente vocale fallito: ${REPORT_PATH}`)
    console.error(JSON.stringify(report.failures.slice(0, 3), null, 2))
    process.exit(1)
  }
  console.log(`Audit assistente vocale completato: ${REPORT_PATH}`)
  console.log(`${report.routes.length} destinazioni vocali, ${report.totalPhrases} frasi, cliente creato e ripulito.`)
}

await main()
