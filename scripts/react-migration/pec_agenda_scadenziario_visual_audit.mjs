import { spawn, spawnSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..', '..')
const BASE_URL = process.env.IUSENTRA_PEC_AGENDA_E2E_BASE_URL || 'http://127.0.0.1:8080'
const USERNAME = process.env.IUSENTRA_PEC_AGENDA_E2E_USERNAME || 'antmm26051975'
const PASSWORD = process.env.IUSENTRA_PEC_AGENDA_E2E_PASSWORD || ''
const VISIBLE_BROWSER = process.env.IUSENTRA_PEC_AGENDA_E2E_VISIBLE !== '0'
const DEPOSIT_PATH = process.env.IUSENTRA_PEC_AGENDA_DEPOSIT_PATH || '/fascicoli/9B9DF2A1/deposito/prepara'
const EXTRA_DEPOSIT_PATH = process.env.IUSENTRA_PEC_AGENDA_EXTRA_DEPOSIT_PATH || ''
const DEPOSIT_PATHS = Array.from(new Set([DEPOSIT_PATH, EXTRA_DEPOSIT_PATH].map((item) => item.trim()).filter(Boolean)))
const EXTRA_DEPOSIT_EXPECTED_MIN_DOCS = Number(process.env.IUSENTRA_PEC_AGENDA_EXTRA_DEPOSIT_EXPECTED_MIN_DOCS || '1')
const AGENDA_SELECTED_EVENT_PATH = process.env.IUSENTRA_PEC_AGENDA_SELECTED_EVENT_PATH || ''
const REPORT_DIR = path.join(ROOT, 'artifacts', 'react-migration')
const SCREENSHOT_DIR = path.join(REPORT_DIR, 'pec-agenda-scadenziario-visual')
const REPORT_PATH = path.join(REPORT_DIR, 'pec-agenda-scadenziario-visual-audit.json')

function activeStudioSlug() {
  try {
    const registry = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'tenants.json'), 'utf8'))
    const tenants = Array.isArray(registry)
      ? registry
      : Object.values(registry?.tenants && typeof registry.tenants === 'object' ? registry.tenants : registry || {})
    const active = tenants.find((tenant) => String(tenant?.stato || '').toUpperCase() === 'ATTIVO' && (tenant?.slug || tenant?.storage_key))
      || tenants.find((tenant) => tenant?.slug || tenant?.storage_key)
    return String(active?.slug || active?.storage_key || '').trim()
  } catch {
    return ''
  }
}

const STUDIO_SLUG = process.env.IUSENTRA_PEC_AGENDA_E2E_STUDIO || activeStudioSlug() || 'antonella-mammola'

if (!PASSWORD) {
  throw new Error('Impostare IUSENTRA_PEC_AGENDA_E2E_PASSWORD per l audit visuale locale.')
}

const forbiddenVisibleTerms = [
  'PEC_AUDIT',
  'pipeline',
  'audit-grade',
  'source_event',
  'profile_id',
  'payload',
  'runtime',
  'backend',
  'frontend',
  'legacy',
  'json_api',
  'external_uid',
  'external_provider',
  'POSTA CERTIFICATA',
  'Data processuale futura',
  'NOTIFICA TIPO',
  'Comunicazione.xml',
  'worker',
  'job',
  'provider',
  'webhook',
  'endpoint',
  'undefined',
  'null',
  'demo',
  'sample',
  'repository',
]

const chromeCandidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)

function findChrome() {
  const found = chromeCandidates.find((candidate) => fs.existsSync(candidate))
  if (!found) throw new Error('Google Chrome non trovato per l audit visuale.')
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
    const promise = new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
    })
    this.ws.send(JSON.stringify({ id, method, params }))
    return promise
  }

  close() {
    try {
      this.ws.close()
    } catch {
      // connection already closed
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
  await waitFor(() => evaluate(cdp, 'Boolean(document.body && document.body.innerText.length > 0)'), 'contenuto pagina', 30000, 250)
}

async function setViewport(cdp, width, height) {
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 700,
  })
  await sleep(400)
}

async function screenshot(cdp, name) {
  const filePath = path.join(SCREENSHOT_DIR, name)
  const capture = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  fs.writeFileSync(filePath, Buffer.from(capture.data, 'base64'))
  return path.relative(ROOT, filePath)
}

async function scrollToPosition(cdp, position) {
  await pageEval(cdp, (target) => {
    const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight)
    const top = target === 'bottom' ? max : target === 'middle' ? max / 2 : 0
    window.scrollTo(0, top)
    return { top, max }
  }, [position])
  await sleep(500)
}

async function clickByText(cdp, text, label = text) {
  const rect = await pageEval(cdp, (wanted) => {
    const normalized = (value) => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase()
    const element = Array.from(document.querySelectorAll('button,a,[role="button"]'))
      .find((candidate) => normalized(candidate.innerText || candidate.getAttribute('aria-label') || candidate.title).includes(normalized(wanted)))
    if (!element) return null
    const box = element.getBoundingClientRect()
    return { x: box.left + box.width / 2, y: box.top + box.height / 2, width: box.width, height: box.height, text: element.innerText || element.getAttribute('aria-label') || '' }
  }, [text])
  if (!rect || rect.width <= 0 || rect.height <= 0) throw new Error(`${label} non cliccabile`)
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y, button: 'none' })
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  await sleep(400)
  return rect
}

function duplicateTexts(items) {
  const counts = new Map()
  for (const item of items.map((value) => String(value || '').replace(/\s+/g, ' ').trim()).filter(Boolean)) {
    counts.set(item, (counts.get(item) || 0) + 1)
  }
  return Array.from(counts.entries()).filter(([, count]) => count > 1).map(([text, count]) => ({ text, count }))
}

async function pageSnapshot(cdp, label) {
  const state = await pageEval(cdp, (terms) => {
    const visibleText = document.body.innerText.replace(/\s+/g, ' ').trim()
    const forbidden = terms.filter((term) => new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i').test(visibleText))
    const buttonOverflow = Array.from(document.querySelectorAll('button,a')).map((element) => {
      const box = element.getBoundingClientRect()
      return {
        text: (element.innerText || element.getAttribute('aria-label') || element.title || '').replace(/\s+/g, ' ').trim().slice(0, 120),
        width: Math.round(box.width),
        scrollWidth: element.scrollWidth,
        overflow: element.scrollWidth > Math.ceil(box.width) + 2,
      }
    }).filter((item) => item.overflow)
    const h1 = Array.from(document.querySelectorAll('h1')).map((item) => item.innerText.trim()).filter(Boolean)
    return {
      href: location.href,
      title: document.title,
      h1,
      visibleTextSample: visibleText.slice(0, 1200),
      forbidden,
      bodyOverflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
      scrollHeight: document.documentElement.scrollHeight,
      viewportHeight: window.innerHeight,
      buttonOverflow,
    }
  }, [forbiddenVisibleTerms])
  return { label, ...state }
}

async function inspectAgenda(cdp) {
  await navigate(cdp, `${BASE_URL}/agenda`)
  await waitFor(() => pageEval(cdp, () => Boolean(document.querySelector('.iu-agenda-page'))), 'pagina Agenda React', 30000)
  await clickByText(cdp, 'Sett.', 'vista settimana').catch(() => null)
  await scrollToPosition(cdp, 'top')
  const topScreenshot = await screenshot(cdp, 'agenda-desktop-top.png')
  const beforeHover = await pageSnapshot(cdp, 'agenda-desktop')
  const snapshots = [beforeHover]
  const screenshots = [topScreenshot]
  const eventState = await pageEval(cdp, () => {
    const cards = Array.from(document.querySelectorAll('.iu-ag-event, .iu-ag-month-event')).map((element) => {
      const box = element.getBoundingClientRect()
      return {
        text: element.innerText.replace(/\s+/g, ' ').trim(),
        aria: element.getAttribute('aria-label') || '',
        title: element.getAttribute('title') || '',
        x: box.left + box.width / 2,
        y: box.top + Math.min(box.height / 2, 28),
        width: Math.round(box.width),
        height: Math.round(box.height),
      }
    }).filter((item) => item.width > 0 && item.height > 0)
    const scadenzeAlleNove = cards.filter((item) => /scadenz|termine/i.test(`${item.text} ${item.aria}`) && /\b09:00\b/.test(item.text))
    return {
      cards,
      nativeTitleCount: cards.filter((item) => item.title).length,
      scadenzeAlleNove,
    }
  })
  eventState.duplicates = duplicateTexts(eventState.cards.map((item) => item.text))
  let hover = { skipped: 'Nessun evento visibile nel range corrente.' }
  if (eventState.cards.length) {
    const first = eventState.cards[0]
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: first.x, y: first.y, button: 'none' })
    await sleep(800)
    hover = await pageEval(cdp, () => {
      const tooltips = Array.from(document.querySelectorAll('.iu-ag-event__tooltip')).map((element) => {
        const style = window.getComputedStyle(element)
        const box = element.getBoundingClientRect()
        return {
          text: element.innerText.replace(/\s+/g, ' ').trim(),
          visible: style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity || '1') > 0.5 && box.width > 0 && box.height > 0,
          width: Math.round(box.width),
          height: Math.round(box.height),
        }
      })
      return {
        visibleCount: tooltips.filter((item) => item.visible).length,
        tooltips: tooltips.filter((item) => item.visible).slice(0, 3),
      }
    })
  }
  const hoverScreenshot = await screenshot(cdp, 'agenda-desktop-hover.png')
  screenshots.push(hoverScreenshot)
  await scrollToPosition(cdp, 'bottom')
  const bottomScreenshot = await screenshot(cdp, 'agenda-desktop-bottom.png')
  screenshots.push(bottomScreenshot)
  let selected = null
  if (AGENDA_SELECTED_EVENT_PATH) {
    await setViewport(cdp, 1365, 768)
    const selectedUrl = AGENDA_SELECTED_EVENT_PATH.startsWith('http')
      ? AGENDA_SELECTED_EVENT_PATH
      : `${BASE_URL}${AGENDA_SELECTED_EVENT_PATH.startsWith('/') ? '' : '/'}${AGENDA_SELECTED_EVENT_PATH}`
    await navigate(cdp, selectedUrl)
    await waitFor(() => pageEval(cdp, () => Boolean(document.querySelector('.iu-agenda-page'))), 'pagina Agenda evento selezionato', 30000)
    await waitFor(() => pageEval(cdp, () => Boolean(document.querySelector('.iu-ag-focus'))), 'dettaglio Agenda evento selezionato', 45000, 250)
    const selectedSnapshot = await pageSnapshot(cdp, 'agenda-selected-event')
    snapshots.push(selectedSnapshot)
    screenshots.push(await screenshot(cdp, 'agenda-selected-event.png'))
    selected = await pageEval(cdp, () => {
      const focus = document.querySelector('.iu-ag-focus')
      const text = focus?.innerText?.replace(/\s+/g, ' ').trim() || ''
      return {
        href: location.href,
        found: Boolean(focus),
        text,
        hasRg274: /RG\s*274\/2026/i.test(text),
        hasPartyAzzaro: /AZZARO\s+FILIPPO/i.test(text),
        hasTime0930: /\b09:30\b/.test(text),
        hasMissingPlaceholders: /\bDa collegare\b|\bDa indicare\b/i.test(text),
        hasTechnicalText: /POSTA CERTIFICATA|Data processuale futura|Presidio PEC|PEC_AUDIT|payload|runtime|backend|frontend|legacy|json_api/i.test(text),
      }
    })
  }
  return { ...beforeHover, snapshots, screenshots, events: eventState, hover, selected }
}

async function inspectScadenziario(cdp) {
  const snapshots = []
  const screenshots = []
  await navigate(cdp, `${BASE_URL}/scadenziario?vista=tutte`)
  await waitFor(() => pageEval(cdp, () => Boolean(document.querySelector('.iu-scadenziario-page, .iu-scad-table, .iu-scad-card-list'))), 'pagina Scadenziario React', 30000)
  for (const position of ['top', 'middle', 'bottom']) {
    await scrollToPosition(cdp, position)
    snapshots.push(await pageSnapshot(cdp, `scadenziario-desktop-${position}`))
    screenshots.push(await screenshot(cdp, `scadenziario-desktop-${position}.png`))
  }
  await scrollToPosition(cdp, 'top')
  const layout = await pageEval(cdp, () => {
    const readCards = (selector) => Array.from(document.querySelectorAll(selector)).map((element) => {
      const box = element.getBoundingClientRect()
      return {
        text: element.innerText.replace(/\s+/g, ' ').trim(),
        top: Math.round(box.top),
        left: Math.round(box.left),
        width: Math.round(box.width),
        height: Math.round(box.height),
        visible: box.width > 0 && box.height > 0,
      }
    }).filter((item) => item.visible)
    const duplicateLocal = (items) => {
      const counts = new Map()
      for (const item of items.map((value) => String(value || '').replace(/\s+/g, ' ').trim()).filter(Boolean)) {
        counts.set(item, (counts.get(item) || 0) + 1)
      }
      return Array.from(counts.entries()).filter(([, count]) => count > 1).map(([text, count]) => ({ text, count }))
    }
    const summarize = (items) => {
      const rows = new Map()
      for (const item of items) {
        const key = String(Math.round(item.top / 8) * 8)
        const row = rows.get(key) || []
        row.push(item)
        rows.set(key, row)
      }
      const heights = items.map((item) => item.height).filter((value) => value > 0)
      const rowCounts = Array.from(rows.values()).map((row) => row.length)
      return {
        count: items.length,
        rowCounts,
        finalRowCount: rowCounts.length ? rowCounts[rowCounts.length - 1] : 0,
        minHeight: heights.length ? Math.min(...heights) : 0,
        maxHeight: heights.length ? Math.max(...heights) : 0,
        duplicateTitles: duplicateLocal(items.map((item) => item.text.split('\n')[0] || item.text)),
        sample: items.slice(0, 10),
      }
    }
    return {
      stats: summarize(readCards('.iu-scad-stat')),
      actions: summarize(readCards('.iu-scad-action-card')),
    }
  })
  await setViewport(cdp, 390, 844)
  await navigate(cdp, `${BASE_URL}/scadenziario?vista=tutte`)
  await waitFor(() => pageEval(cdp, () => Boolean(document.querySelector('.iu-scadenziario-page, .iu-scad-table, .iu-scad-card-list'))), 'Scadenziario mobile', 30000)
  for (const position of ['top', 'middle', 'bottom']) {
    await scrollToPosition(cdp, position)
    snapshots.push(await pageSnapshot(cdp, `scadenziario-mobile-${position}`))
    screenshots.push(await screenshot(cdp, `scadenziario-mobile-${position}.png`))
  }
  const cards = await pageEval(cdp, () => {
    const visibleCards = Array.from(document.querySelectorAll('.iu-scad-mobile-card, .iu-scad-table tbody tr')).map((element) => {
      const box = element.getBoundingClientRect()
      return {
        text: element.innerText.replace(/\s+/g, ' ').trim(),
        width: Math.round(box.width),
        height: Math.round(box.height),
        visible: box.width > 0 && box.height > 0,
      }
    }).filter((item) => item.visible)
    const heights = visibleCards.map((item) => item.height).filter((value) => value > 0)
    return {
      count: visibleCards.length,
      sample: visibleCards.slice(0, 12),
      minHeight: heights.length ? Math.min(...heights) : 0,
      maxHeight: heights.length ? Math.max(...heights) : 0,
      texts: visibleCards.map((item) => item.text),
    }
  })
  cards.duplicates = duplicateTexts(cards.texts)
  delete cards.texts
  await setViewport(cdp, 1365, 768)
  return {
    label: 'scadenziario',
    snapshots,
    screenshots,
    cards,
    layout,
  }
}

async function inspectCalendarSettings(cdp) {
  await setViewport(cdp, 1365, 768)
  await navigate(cdp, `${BASE_URL}/impostazioni/calendario`)
  await waitFor(() => pageEval(cdp, () => {
    const text = document.body.innerText.replace(/\s+/g, ' ')
    return (
      Boolean(document.querySelector('.iu-calendar-settings'))
      || text.includes('Sincronizzazione diretta')
      || text.includes('Collega Google Calendar')
      || (!text.includes('Caricamento impostazioni') && text.includes('Calendari collegati'))
    )
  }), 'Impostazioni calendari operative', 45000)
  await scrollToPosition(cdp, 'top')
  const top = await pageSnapshot(cdp, 'impostazioni-calendario-top')
  const topScreenshot = await screenshot(cdp, 'impostazioni-calendario-top.png')
  await scrollToPosition(cdp, 'bottom')
  const bottom = await pageSnapshot(cdp, 'impostazioni-calendario-bottom')
  const bottomScreenshot = await screenshot(cdp, 'impostazioni-calendario-bottom.png')
  const checks = await pageEval(cdp, () => {
    const text = document.body.innerText.replace(/\s+/g, ' ')
    return {
      stillLoading: text.includes('Caricamento impostazioni'),
      directSyncCopy: text.includes('Sincronizzazione diretta'),
      googlePrimary: text.includes('Collega Google Calendar'),
      readOnlyCopy: text.includes('sola lettura'),
      oldWebCalPrimary: text.includes('Aggiungi WebCal / ICS') || text.includes('Link riservati da sottoscrivere'),
    }
  })
  return { label: 'impostazioni-calendario', snapshots: [top, bottom], screenshots: [topScreenshot, bottomScreenshot], checks }
}

async function inspectDeposito(cdp, depositPath, label = 'deposito-prepara') {
  const screenshotPrefix = label.replace(/[^a-z0-9_-]+/gi, '-').toLowerCase()
  await navigate(cdp, `${BASE_URL}${depositPath}`)
  await waitFor(() => pageEval(cdp, () => Boolean(document.querySelector('main'))), 'pagina deposito', 30000)
  await waitFor(() => pageEval(cdp, () => {
    const text = document.body.innerText.replace(/\s+/g, ' ')
    return text.includes('Fascicolo non trovato') || text.includes('Dati aggiornati')
  }), 'dati deposito caricati', 45000, 250)
  const selectionInteraction = await pageEval(cdp, () => {
    const root = document.querySelector('.iu-fas-deposit-selection')
    const checkboxes = Array.from(root?.querySelectorAll('input[type="checkbox"]') || [])
    const countChecked = () => checkboxes.filter((node) => node.checked).length
    const beforeChecked = countChecked()
    const first = checkboxes[0]
    if (!root || !first) {
      return {
        interactionAvailable: false,
        beforeChecked,
        afterFirstClickChecked: beforeChecked,
        restoredChecked: beforeChecked,
        changed: false,
        restored: true,
      }
    }
    first.click()
    const afterFirstClickChecked = countChecked()
    first.click()
    const restoredChecked = countChecked()
    return {
      interactionAvailable: true,
      beforeChecked,
      afterFirstClickChecked,
      restoredChecked,
      changed: afterFirstClickChecked !== beforeChecked,
      restored: restoredChecked === beforeChecked,
    }
  })
  await scrollToPosition(cdp, 'top')
  const top = await pageSnapshot(cdp, `${label}-top`)
  const topScreenshot = await screenshot(cdp, `${screenshotPrefix}-top.png`)
  await scrollToPosition(cdp, 'bottom')
  const bottom = await pageSnapshot(cdp, `${label}-bottom`)
  const bottomScreenshot = await screenshot(cdp, `${screenshotPrefix}-bottom.png`)
  const checks = await pageEval(cdp, () => {
    const text = document.body.innerText.replace(/\s+/g, ' ')
    const statNodes = Array.from(document.querySelectorAll('.iu-fas-deposit-cockpit .iu-fas-stat'))
    const stats = statNodes.map((node) => ({
      label: node.querySelector('span')?.textContent?.trim() || '',
      value: node.querySelector('strong')?.textContent?.trim() || '',
      note: node.querySelector('small')?.textContent?.trim() || '',
    }))
    const statLayout = statNodes.map((node) => {
      const box = node.getBoundingClientRect()
      const labelBox = node.querySelector('span')?.getBoundingClientRect()
      const valueBox = node.querySelector('strong')?.getBoundingClientRect()
      const noteBox = node.querySelector('small')?.getBoundingClientRect()
      return {
        label: node.querySelector('span')?.textContent?.trim() || '',
        width: Math.round(box.width),
        height: Math.round(box.height),
        overflowX: node.scrollWidth > Math.ceil(box.width) + 1,
        overflowY: node.scrollHeight > Math.ceil(box.height) + 1,
        labelToValue: labelBox && valueBox ? Math.round(valueBox.top - labelBox.bottom) : null,
        valueToNote: valueBox && noteBox ? Math.round(noteBox.top - valueBox.bottom) : null,
      }
    })
    const statHeights = statLayout.map((item) => item.height).filter(Boolean)
    const documentRows = Array.from(document.querySelectorAll('.iu-fas-doc-row, .iu-fas-comm-row')).map((node) => ({
      role: node.querySelector('.iu-badge')?.textContent?.trim() || '',
      title: node.querySelector('strong')?.textContent?.trim() || '',
      meta: node.querySelector('span')?.textContent?.trim() || '',
      text: node.textContent?.replace(/\s+/g, ' ').trim() || '',
    })).filter((row) => row.title)
    const documentTitleProblems = documentRows.filter((row) => (
      /^\d{10,}\.(?:pdf|p7m)$/i.test(row.title)
      || /\bIMPORT_ESTERNO\b/i.test(row.text)
      || /^\s*QuickOrganizer\s*$/i.test(row.meta)
    ))
    const wholeCase = stats.find((item) => item.label.toLowerCase() === 'tutto fascicolo') || null
    const wholeCaseDocuments = wholeCase ? Number(String(wholeCase.value || '').replace(/[^\d.-]/g, '')) : 0
    const selectionRoot = document.querySelector('.iu-fas-deposit-selection')
    const selectionRows = Array.from(selectionRoot?.querySelectorAll('.iu-fas-deposit-selection__row') || [])
    const selectionCheckboxes = Array.from(selectionRoot?.querySelectorAll('input[type="checkbox"]') || [])
    const selectionBox = selectionRoot?.getBoundingClientRect()
    return {
      notLegacyQuery: !location.search.includes('_legacy=1'),
      hasReactRoot: Boolean(document.getElementById('root') || document.querySelector('[data-reactroot]') || document.querySelector('.iu-fascicoli-page')),
      hasDepositCopy: /deposito|busta|document/i.test(text),
      hasDocumentsCopy: /documenti|fascicolo/i.test(text),
      topbarSignals: /Notifiche|Recenti|Scadenze/i.test(text),
      stillLoading: text.includes('Caricamento...'),
      notFound: text.includes('Fascicolo non trovato'),
      wholeCaseDocuments,
      wholeCaseNote: wholeCase?.note || '',
      depositSelection: {
        visible: Boolean(selectionRoot && selectionBox && selectionBox.width > 0 && selectionBox.height > 0),
        title: selectionRoot?.querySelector('header strong')?.textContent?.trim() || '',
        selectedBadge: selectionRoot?.querySelector('header .iu-badge')?.textContent?.trim() || '',
        rowCount: selectionRows.length,
        checkboxCount: selectionCheckboxes.length,
        checkedCount: selectionCheckboxes.filter((node) => node.checked).length,
        rows: selectionRows.slice(0, 8).map((node) => node.textContent?.replace(/\s+/g, ' ').trim() || ''),
      },
      depositCardLayout: {
        count: statLayout.length,
        maxHeight: statHeights.length ? Math.max(...statHeights) : 0,
        minHeight: statHeights.length ? Math.min(...statHeights) : 0,
        overflow: statLayout.filter((item) => item.overflowX || item.overflowY),
        looseSpacing: statLayout.filter((item) => (
          (typeof item.labelToValue === 'number' && item.labelToValue > 8)
          || (typeof item.valueToNote === 'number' && item.valueToNote > 8)
        )),
        rows: statLayout,
      },
      visibleCaseIdentity: /Moscato Marco|RG 12\/2026|2DE106E6|Spagnolo Sara|RG 3950\/2026|249A4053/i.test(text),
      quickOrganizerClient: /Spagnolo Sara \(da collegare in anagrafica\)/i.test(text),
      quickOrganizerObjectCode: /222050\s*-\s*Retribuzione/i.test(text),
      professionalDocumentNames: documentRows.some((row) => /Atto giudiziario|Procura alle liti|Ricorso|Provvedimento - sentenza/i.test(row.title)),
      documentRows: documentRows.slice(0, 12),
      documentTitleProblems: documentTitleProblems.slice(0, 8),
    }
  })
  checks.depositSelection = { ...(checks.depositSelection || {}), ...selectionInteraction }
  if (label.includes('fascicolo-reale') && !checks.notFound && checks.wholeCaseDocuments < EXTRA_DEPOSIT_EXPECTED_MIN_DOCS) {
    throw new Error(`Deposito fascicolo reale senza documenti visibili: attesi almeno ${EXTRA_DEPOSIT_EXPECTED_MIN_DOCS}, trovati ${checks.wholeCaseDocuments}`)
  }
  return { label, depositPath, snapshots: [top, bottom], screenshots: [topScreenshot, bottomScreenshot], checks }
}

async function login(cdp) {
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
    const href = await evaluate(cdp, 'location.href')
    return !href.includes('/login') && href.startsWith(BASE_URL)
  }, 'login effettuato', 90000)
}

function collectFailures(report) {
  const failures = []
  for (const page of report.pages) {
    const snapshots = page.snapshots || [page]
    for (const snapshot of snapshots) {
      if (snapshot.forbidden?.length) failures.push({ type: 'testi-tecnici-visibili', page: snapshot.label, terms: snapshot.forbidden })
      if (snapshot.bodyOverflowX) failures.push({ type: 'overflow-orizzontale', page: snapshot.label })
      if (snapshot.buttonOverflow?.length) failures.push({ type: 'testo-pulsante-tagliato', page: snapshot.label, buttons: snapshot.buttonOverflow.slice(0, 5) })
    }
  }
  const agenda = report.pages.find((page) => page.label === 'agenda-desktop')
  if (agenda?.events?.nativeTitleCount) failures.push({ type: 'tooltip-nativo-agenda', count: agenda.events.nativeTitleCount })
  if (agenda?.hover && !agenda.hover.skipped && agenda.hover.visibleCount !== 1) failures.push({ type: 'tooltip-agenda-non-unico', hover: agenda.hover })
  if (agenda?.events?.duplicates?.length) failures.push({ type: 'duplicati-agenda-visibili', duplicates: agenda.events.duplicates.slice(0, 5) })
  if (agenda?.events?.scadenzeAlleNove?.length) failures.push({ type: 'scadenze-agenda-ore-0900', items: agenda.events.scadenzeAlleNove.slice(0, 5) })
  if (agenda?.selected) {
    if (!agenda.selected.found) failures.push({ type: 'agenda-evento-selezionato-non-visibile', href: agenda.selected.href })
    if (!agenda.selected.hasRg274) failures.push({ type: 'agenda-evento-selezionato-senza-rg-274', selected: agenda.selected })
    if (!agenda.selected.hasPartyAzzaro) failures.push({ type: 'agenda-evento-selezionato-senza-parte', selected: agenda.selected })
    if (!agenda.selected.hasTime0930) failures.push({ type: 'agenda-evento-selezionato-orario-non-letto-da-pec', selected: agenda.selected })
    if (agenda.selected.hasMissingPlaceholders) failures.push({ type: 'agenda-evento-selezionato-dati-non-collegati', selected: agenda.selected })
    if (agenda.selected.hasTechnicalText) failures.push({ type: 'agenda-evento-selezionato-testo-tecnico', selected: agenda.selected })
  }

  const scadenziario = report.pages.find((page) => page.label === 'scadenziario')
  if (scadenziario?.cards?.duplicates?.length) failures.push({ type: 'duplicati-scadenziario-visibili', duplicates: scadenziario.cards.duplicates.slice(0, 5) })
  if (scadenziario?.cards?.minHeight && scadenziario.cards.maxHeight / Math.max(1, scadenziario.cards.minHeight) > 3.5) {
    failures.push({ type: 'dimensioni-card-scadenziario-da-verificare', minHeight: scadenziario.cards.minHeight, maxHeight: scadenziario.cards.maxHeight })
  }
  if (scadenziario?.layout?.stats?.count > 1 && scadenziario.layout.stats.finalRowCount === 1) {
    failures.push({ type: 'kpi-scadenziario-card-isolata', layout: scadenziario.layout.stats })
  }
  if (scadenziario?.layout?.actions?.count > 1 && scadenziario.layout.actions.finalRowCount === 1) {
    failures.push({ type: 'azioni-scadenziario-card-isolata', layout: scadenziario.layout.actions })
  }
  if (scadenziario?.layout?.actions?.minHeight && scadenziario.layout.actions.maxHeight / Math.max(1, scadenziario.layout.actions.minHeight) > 1.45) {
    failures.push({ type: 'dimensioni-card-operative-scadenziario', layout: scadenziario.layout.actions })
  }
  if (scadenziario?.layout?.actions?.duplicateTitles?.length) {
    failures.push({ type: 'duplicati-card-operative-scadenziario', duplicates: scadenziario.layout.actions.duplicateTitles.slice(0, 5) })
  }

  const settings = report.pages.find((page) => page.label === 'impostazioni-calendario')
  if (settings?.checks.stillLoading) failures.push({ type: 'impostazioni-calendario-caricamento-bloccato' })
  if (settings && !settings.checks.directSyncCopy) failures.push({ type: 'impostazioni-calendario-manca-sync-diretta' })
  if (settings && !settings.checks.googlePrimary) failures.push({ type: 'impostazioni-calendario-google-non-primario' })
  if (settings?.checks.oldWebCalPrimary) failures.push({ type: 'impostazioni-calendario-webcal-ancora-primario' })

  const depositi = report.pages.filter((page) => String(page.label || '').startsWith('deposito-prepara'))
  for (const deposito of depositi) {
    if (!deposito.checks.notLegacyQuery) failures.push({ type: 'deposito-query-legacy', page: deposito.label, path: deposito.depositPath })
    if (!deposito.checks.hasReactRoot) failures.push({ type: 'deposito-non-react-visibile', page: deposito.label, path: deposito.depositPath, checks: deposito.checks })
    if (!deposito.checks.hasDepositCopy) failures.push({ type: 'deposito-copy-non-rilevata', page: deposito.label, path: deposito.depositPath, checks: deposito.checks })
    if (deposito.checks.stillLoading) failures.push({ type: 'deposito-caricamento-non-concluso', page: deposito.label, path: deposito.depositPath })
    if (!deposito.checks.notFound) {
      if (!deposito.checks.depositSelection?.visible) failures.push({ type: 'deposito-selezione-documenti-non-visibile', page: deposito.label, path: deposito.depositPath })
      if (Number(deposito.checks.depositSelection?.checkboxCount || 0) < 1) failures.push({ type: 'deposito-selezione-documenti-senza-checkbox', page: deposito.label, path: deposito.depositPath, selection: deposito.checks.depositSelection })
      if (Number(deposito.checks.depositSelection?.checkedCount || 0) < 1) failures.push({ type: 'deposito-selezione-documenti-nessun-documento', page: deposito.label, path: deposito.depositPath, selection: deposito.checks.depositSelection })
      if (deposito.checks.depositSelection?.interactionAvailable && !deposito.checks.depositSelection?.changed) failures.push({ type: 'deposito-selezione-documenti-click-inefficace', page: deposito.label, path: deposito.depositPath, selection: deposito.checks.depositSelection })
      if (deposito.checks.depositSelection?.interactionAvailable && !deposito.checks.depositSelection?.restored) failures.push({ type: 'deposito-selezione-documenti-ripristino-fallito', page: deposito.label, path: deposito.depositPath, selection: deposito.checks.depositSelection })
    }
    if (deposito.checks.depositCardLayout?.overflow?.length) {
      failures.push({ type: 'deposito-card-overflow', page: deposito.label, path: deposito.depositPath, rows: deposito.checks.depositCardLayout.overflow })
    }
    if (deposito.checks.depositCardLayout?.looseSpacing?.length) {
      failures.push({ type: 'deposito-card-spaziatura-da-ridurre', page: deposito.label, path: deposito.depositPath, rows: deposito.checks.depositCardLayout.looseSpacing })
    }
    if (Number(deposito.checks.depositCardLayout?.maxHeight || 0) > 96) {
      failures.push({ type: 'deposito-card-troppo-alte', page: deposito.label, path: deposito.depositPath, layout: deposito.checks.depositCardLayout })
    }
    if (deposito.checks.documentTitleProblems?.length) {
      failures.push({ type: 'deposito-documenti-con-nomi-tecnici', page: deposito.label, path: deposito.depositPath, rows: deposito.checks.documentTitleProblems })
    }
    if (deposito.label.includes('fascicolo-reale') && !deposito.checks.notFound && Number(deposito.checks.wholeCaseDocuments || 0) < EXTRA_DEPOSIT_EXPECTED_MIN_DOCS) {
      failures.push({ type: 'deposito-fascicolo-reale-senza-documenti', page: deposito.label, path: deposito.depositPath, documents: deposito.checks.wholeCaseDocuments || 0 })
    }
    if (deposito.depositPath.includes('249A4053') && !deposito.checks.notFound) {
      if (!deposito.checks.quickOrganizerClient) failures.push({ type: 'deposito-cliente-importato-non-compilato', page: deposito.label, path: deposito.depositPath })
      if (!deposito.checks.quickOrganizerObjectCode) failures.push({ type: 'deposito-codice-oggetto-importato-non-compilato', page: deposito.label, path: deposito.depositPath })
      if (!deposito.checks.professionalDocumentNames) failures.push({ type: 'deposito-nomi-documenti-non-professionali', page: deposito.label, path: deposito.depositPath })
    }
  }

  const hardConsoleErrors = report.consoleErrors.filter((entry) => {
    const text = String(entry.details || '')
    return !/favicon|Unchecked runtime\.lastError|ERR_BLOCKED_BY_CLIENT/i.test(text)
  })
  if (hardConsoleErrors.length) failures.push({ type: 'console-errori-browser', entries: hardConsoleErrors.slice(0, 8) })
  return failures
}

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
  const chromePath = findChrome()
  const port = 9910 + Number.parseInt(crypto.randomBytes(1).toString('hex'), 16)
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'iusentra-pec-agenda-audit-'))
  const chromeArgs = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--window-size=1365,768',
    '--window-position=40,40',
    'about:blank',
  ]
  if (!VISIBLE_BROWSER) chromeArgs.unshift('--headless=new')
  const chrome = spawn(chromePath, chromeArgs, { stdio: 'ignore' })
  const report = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    chromePath,
    visibleBrowser: VISIBLE_BROWSER,
    depositPath: DEPOSIT_PATH,
    depositPaths: DEPOSIT_PATHS,
    screenshotsDir: path.relative(ROOT, SCREENSHOT_DIR),
    pages: [],
    consoleErrors: [],
    failures: [],
    notes: [],
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

    await login(cdp)
    report.pages.push(await inspectAgenda(cdp))
    report.pages.push(await inspectScadenziario(cdp))
    report.pages.push(await inspectCalendarSettings(cdp))
    for (let index = 0; index < DEPOSIT_PATHS.length; index += 1) {
      const label = index === 0 ? 'deposito-prepara-url-riferito' : 'deposito-prepara-fascicolo-reale'
      report.pages.push(await inspectDeposito(cdp, DEPOSIT_PATHS[index], label))
    }
    report.failures = collectFailures(report)
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
    console.error(`Audit visuale PEC/Agenda/Scadenziario fallito: ${REPORT_PATH}`)
    console.error(JSON.stringify(report.failures.slice(0, 8), null, 2))
    process.exit(1)
  }
  console.log(`Audit visuale PEC/Agenda/Scadenziario riuscito: ${REPORT_PATH}`)
  console.log(`Screenshot: ${SCREENSHOT_DIR}`)
}

await main()
