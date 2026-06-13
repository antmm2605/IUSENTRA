import { spawn, spawnSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..', '..')
const BASE_URL = process.env.IUSENTRA_LOCAL_SIGNER_E2E_BASE_URL || 'http://127.0.0.1:8080'
const STUDIO_SLUG = process.env.IUSENTRA_LOCAL_SIGNER_E2E_STUDIO || 'antonella-mammola'
const USERNAME = process.env.IUSENTRA_LOCAL_SIGNER_E2E_USERNAME || 'codex-voce-e2e'
const PASSWORD = process.env.IUSENTRA_LOCAL_SIGNER_E2E_PASSWORD || process.env.IUSENTRA_VOICE_E2E_PASSWORD || ''
const TARGET_PATH = process.env.IUSENTRA_LOCAL_SIGNER_E2E_TARGET || '/impostazioni?tab=firma'
const VISIBLE_BROWSER = process.env.IUSENTRA_LOCAL_SIGNER_E2E_VISIBLE === '1'
const FORCE_MISSING_FLOW = process.env.IUSENTRA_LOCAL_SIGNER_E2E_FORCE_MISSING !== '0'
const CLICK_START_PROTOCOL = process.env.IUSENTRA_LOCAL_SIGNER_E2E_CLICK_START === '1'
const REPORT_DIR = path.join(ROOT, 'artifacts', 'react-migration')
const REPORT_PATH = path.join(REPORT_DIR, 'local-signer-monitor-browser-audit.json')
const SCREENSHOT_PATH = path.join(REPORT_DIR, 'local-signer-monitor-browser-audit.png')
const DOWNLOAD_DIR = path.join(REPORT_DIR, 'local-signer-monitor-downloads')

if (!PASSWORD) {
  throw new Error('Impostare IUSENTRA_LOCAL_SIGNER_E2E_PASSWORD o IUSENTRA_VOICE_E2E_PASSWORD.')
}

const chromeCandidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)

function findChrome() {
  const found = chromeCandidates.find((candidate) => fs.existsSync(candidate))
  if (!found) throw new Error('Google Chrome non trovato per il test Local Signer.')
  return found
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitFor(fn, label, timeoutMs = 15000, intervalMs = 200) {
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
    this.events = []
    this.listeners = []
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
      // Connessione già chiusa.
    }
  }
}

async function browserJson(port, endpoint, options = {}) {
  const response = await fetch(`http://127.0.0.1:${port}${endpoint}`, options)
  if (!response.ok) throw new Error(`${endpoint} HTTP ${response.status}`)
  return response.json()
}

async function waitChrome(port) {
  return waitFor(() => browserJson(port, '/json/version').catch(() => null), 'debugger Chrome', 20000, 250)
}

async function createTarget(port) {
  try {
    return await browserJson(port, '/json/new?about:blank', { method: 'PUT' })
  } catch {
    return browserJson(port, '/json/new?about:blank')
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
    throw new Error(exception.description || exception.value || result.exceptionDetails.text || 'Errore browser')
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

async function navigate(cdp, url) {
  await cdp.send('Page.navigate', { url })
  await waitReady(cdp)
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

async function clickSelector(cdp, selector, label) {
  const rect = await pageEval(cdp, (query) => {
    const element = document.querySelector(query)
    if (!element) return null
    const box = element.getBoundingClientRect()
    return {
      x: box.left + box.width / 2,
      y: box.top + box.height / 2,
      width: box.width,
      height: box.height,
      text: element.innerText || element.getAttribute('aria-label') || element.title || '',
    }
  }, [selector])
  if (!rect || rect.width <= 0 || rect.height <= 0) {
    throw new Error(`${label} non cliccabile nel viewport`)
  }
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y, button: 'none' })
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await sleep(250)
  return rect
}

async function appState(cdp) {
  return pageEval(cdp, () => {
    const banner = document.getElementById('iusentra-local-signer-status')
    const buttons = Array.from((banner || document).querySelectorAll('button,a')).map((button) => {
      const rect = button.getBoundingClientRect()
      return {
        text: (button.innerText || button.getAttribute('aria-label') || button.title || '').trim(),
        href: button.getAttribute('href') || '',
        action: button.getAttribute('data-local-signer-action') || '',
        width: Math.round(rect.width),
        scrollWidth: button.scrollWidth,
        overflow: button.scrollWidth > Math.ceil(rect.width) + 1,
      }
    })
    return {
      href: location.href,
      bannerVisible: Boolean(banner && !banner.classList.contains('d-none')),
      bannerText: banner?.innerText?.replace(/\s+/g, ' ').trim() || '',
      actions: buttons,
      bodyOverflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      scrollHeight: document.documentElement.scrollHeight,
      viewportHeight: window.innerHeight,
      downloadAnchors: Array.from(document.querySelectorAll('[data-local-signer-action="installer"]')).map((link) => ({
        text: link.innerText.trim(),
        href: link.getAttribute('href') || '',
      })),
    }
  })
}

async function main() {
  fs.mkdirSync(REPORT_DIR, { recursive: true })
  fs.rmSync(DOWNLOAD_DIR, { recursive: true, force: true })
  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true })

  const chromePath = findChrome()
  const port = 9900 + Number.parseInt(crypto.randomBytes(1).toString('hex'), 16)
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'iusentra-local-signer-audit-'))
  const chromeArgs = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--window-size=1365,768',
    'about:blank',
  ]
  if (!VISIBLE_BROWSER) chromeArgs.unshift('--headless=new')
  const chrome = spawn(chromePath, chromeArgs, { stdio: 'ignore' })

  const report = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    targetPath: TARGET_PATH,
    chromePath,
    visibleBrowser: VISIBLE_BROWSER,
    forcedMissingFlow: FORCE_MISSING_FLOW,
    clickStartProtocol: CLICK_START_PROTOCOL,
    forcedLocalSignerUrl: 'http://127.0.0.1:29999',
    screenshot: path.relative(ROOT, SCREENSHOT_PATH),
    downloadDir: path.relative(ROOT, DOWNLOAD_DIR),
    states: [],
    downloads: [],
    consoleErrors: [],
    failures: [],
  }
  try {
    const response = await fetch('http://127.0.0.1:27272/ping?light=1', { signal: AbortSignal.timeout(2500) })
    report.actualLocalSigner = await response.json()
  } catch (error) {
    report.actualLocalSigner = { ok: false, message: error?.message || String(error) }
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
    await cdp.send('Browser.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: DOWNLOAD_DIR.replace(/\\/g, '/'),
    }).catch(() => null)
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
    await navigate(cdp, `${BASE_URL}/login?next=${encodeURIComponent(TARGET_PATH)}`)
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
      const href = await evaluate(cdp, 'location.href')
      return !href.includes('/login') && href.startsWith(BASE_URL)
    }, 'login effettuato', 60000)
    await navigate(cdp, `${BASE_URL}${TARGET_PATH}`)

    await waitFor(async () => evaluate(cdp, 'Boolean(window.IusentraLocalSignerMonitor)'), 'monitor Local Signer caricato', 20000)

    if (FORCE_MISSING_FLOW) {
    await pageEval(cdp, ([forcedUrl, clickStartProtocol]) => {
        const monitor = document.getElementById('iusentra-local-signer-monitor')
        if (!monitor) throw new Error('Nodo monitor Local Signer non trovato')
        monitor.dataset.localSignerUrl = forcedUrl
        if (!clickStartProtocol) {
          monitor.dataset.restartProtocol = 'about:blank'
        }
        window.localStorage?.removeItem('iusentra-local-signer-installer-prompt')
        window.IusentraLocalSignerMonitor.run({ showOk: true })
        return true
      }, [['http://127.0.0.1:29999', CLICK_START_PROTOCOL]])
    }

    await waitFor(async () => {
      const state = await appState(cdp)
      if (report.states.length < 20) report.states.push({ atMs: Date.now(), state })
      return state.bannerVisible
        && state.bannerText.includes('Avvia Local Signer')
        && state.bannerText.includes('Installa o aggiorna Local Signer')
    }, 'banner avvio Local Signer', 20000, 500)

    if (CLICK_START_PROTOCOL) {
      report.startClick = await clickSelector(cdp, '[data-local-signer-action="start"]', 'Pulsante Avvia Local Signer')
      await waitFor(async () => {
        const state = await appState(cdp)
        if (report.states.length < 30) report.states.push({ atMs: Date.now(), state })
        return state.bannerVisible && state.bannerText.includes('Local Signer da installare su questo PC')
      }, 'banner installazione Local Signer', 20000, 500)
    } else {
      report.startClickSkipped = 'Il protocollo esterno iusentra-local-signer:// può aprire un dialogo Chrome/Windows: l’audit automatico verifica il pulsante visibile e clicca l’installer.'
    }

    await pageEval(cdp, () => {
      window.scrollTo(0, 0)
      return true
    })
    await sleep(250)
    await pageEval(cdp, () => {
      window.scrollTo(0, Math.max(0, document.documentElement.scrollHeight / 2))
      return true
    })
    await sleep(250)
    await pageEval(cdp, () => {
      window.scrollTo(0, document.documentElement.scrollHeight)
      return true
    })
    await sleep(250)

    const beforeClick = await appState(cdp)
    report.beforeClick = beforeClick
    if (!beforeClick.downloadAnchors.some((item) => item.href.includes('/polisWeb/local-signer/setup/windows'))) {
      throw new Error(`Pulsante installer non trovato nel banner: ${JSON.stringify(beforeClick)}`)
    }

    report.installerClick = await clickSelector(cdp, '[data-local-signer-action="installer"]', 'Pulsante installer')
    await sleep(3000)
    report.downloads = fs.existsSync(DOWNLOAD_DIR)
      ? fs.readdirSync(DOWNLOAD_DIR).filter((name) => !name.endsWith('.crdownload'))
      : []
    report.afterClick = await appState(cdp)
    await screenshot(cdp, SCREENSHOT_PATH)

    const overflowButtons = report.afterClick.actions.filter((item) => item.overflow)
    if (report.afterClick.bodyOverflowX) {
      report.failures.push({ type: 'layout', message: 'Overflow orizzontale presente' })
    }
    if (overflowButtons.length) {
      report.failures.push({ type: 'button-overflow', buttons: overflowButtons })
    }
    if (!report.afterClick.bannerText.includes('Verifica')) {
      report.failures.push({ type: 'copy', message: 'Manca il pulsante di verifica nel banner Local Signer' })
    }
    const blockedProtocol = report.consoleErrors.filter((entry) =>
      String(entry.details || '').includes('Not allowed to launch')
    )
    if (blockedProtocol.length) {
      report.failures.push({ type: 'protocol-gesture', entries: blockedProtocol })
    }
  } catch (error) {
    report.failures.push({ type: 'fatal', message: error?.stack || String(error) })
  } finally {
    if (cdp) cdp.close()
    try {
      chrome.kill()
      if (process.platform === 'win32' && chrome.pid) {
        spawnSync('taskkill.exe', ['/PID', String(chrome.pid), '/T', '/F'], { stdio: 'ignore' })
      }
      await Promise.race([
        new Promise((resolve) => chrome.once('exit', resolve)),
        sleep(2500),
      ])
    } catch (error) {
      report.cleanupWarning = `Chiusura Chrome non completata: ${error?.message || error}`
    }
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        fs.rmSync(userDataDir, { recursive: true, force: true })
        break
      } catch (error) {
        if (attempt === 4) report.cleanupWarning = `Profilo Chrome temporaneo non rimosso: ${error?.message || error}`
        await sleep(500)
      }
    }
    fs.writeFileSync(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  }

  if (report.failures.length) {
    console.error(`Audit Local Signer fallito: ${REPORT_PATH}`)
    console.error(JSON.stringify(report.failures.slice(0, 3), null, 2))
    process.exit(1)
  }
  console.log(`Audit Local Signer completato: ${REPORT_PATH}`)
  console.log(`Screenshot: ${SCREENSHOT_PATH}`)
  process.exit(0)
}

await main()
