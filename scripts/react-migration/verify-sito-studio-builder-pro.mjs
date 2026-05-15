import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const host = process.env.IUSENTRA_AUDIT_HOST || 'http://127.0.0.1:8080'
const cdpHost = process.env.IUSENTRA_CDP_HOST || 'http://127.0.0.1:9224'
const outDir = resolve('artifacts/react-migration/visual-2.239.1-sito-studio-builder')
mkdirSync(outDir, { recursive: true })

class Cdp {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl)
    this.seq = 0
    this.pending = new Map()
    this.events = []
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.id && this.pending.has(msg.id)) {
        this.pending.get(msg.id)(msg)
        this.pending.delete(msg.id)
      } else if (msg.method) {
        this.events.push(msg)
      }
    }
  }

  async open() {
    await new Promise((resolveOpen, rejectOpen) => {
      this.ws.onopen = resolveOpen
      this.ws.onerror = rejectOpen
    })
  }

  send(method, params = {}) {
    const id = ++this.seq
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolveSend, rejectSend) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        rejectSend(new Error(`${method} timeout`))
      }, 45000)
      this.pending.set(id, (msg) => {
        clearTimeout(timer)
        if (msg.error) rejectSend(new Error(`${method}: ${msg.error.message}`))
        else resolveSend(msg.result || {})
      })
    })
  }

  close() {
    this.ws.close()
  }
}

async function collectBrowserCookies() {
  try {
    const listResponse = await fetch(`${cdpHost}/json/list`)
    if (!listResponse.ok) return []
    const targets = await listResponse.json()
    const authenticatedTarget = targets.find((target) => String(target.url || '').startsWith(host))
    if (!authenticatedTarget?.webSocketDebuggerUrl) return []
    const client = new Cdp(authenticatedTarget.webSocketDebuggerUrl)
    await client.open()
    await client.send('Network.enable')
    const { cookies = [] } = await client.send('Network.getCookies', { urls: [host] })
    client.close()
    return cookies.filter((cookie) => cookie.name && cookie.value)
  } catch {
    return []
  }
}

async function newPage(cookies = []) {
  const response = await fetch(`${cdpHost}/json/new?about:blank`, { method: 'PUT' })
  if (!response.ok) throw new Error(`CDP non disponibile: ${response.status}`)
  const target = await response.json()
  const client = new Cdp(target.webSocketDebuggerUrl)
  await client.open()
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Network.enable')
  await client.send('Log.enable')
  for (const cookie of cookies) {
    await client.send('Network.setCookie', {
      name: cookie.name,
      value: cookie.value,
      url: host,
      path: cookie.path || '/',
      secure: Boolean(cookie.secure),
      httpOnly: Boolean(cookie.httpOnly),
      sameSite: cookie.sameSite || 'Lax',
    })
  }
  return client
}

async function evalJson(client, expression) {
  const { result, exceptionDetails } = await client.send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  if (exceptionDetails) throw new Error(exceptionDetails.text || 'Runtime evaluation failed')
  return result.value
}

async function waitForBuilder(client) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const state = await evalJson(client, `(() => ({
      ready: document.readyState,
      h1: document.querySelector('.iu-builder-topbar-pro h1')?.innerText?.trim() || '',
      panel: Boolean(document.querySelector('.iu-builder-left-pro')),
      preview: Boolean(document.querySelector('.iu-builder-public-page')),
      textLength: document.body?.innerText?.length || 0,
    }))()`)
    if (state.ready === 'complete' && state.h1 && state.panel && state.preview && state.textLength > 1000) {
      return state
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 250))
  }
  throw new Error('Builder Sito Studio non pronto nel browser')
}

async function capture(client, fileName) {
  const screenshot = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  writeFileSync(resolve(outDir, fileName), Buffer.from(screenshot.data, 'base64'))
}

function markdown(report) {
  const { failures, loadMs, base, footer, resize, theme, mobileTablet, formatting } = report
  return [
    '# Visual builder layout B 2.239.1',
    '',
    `Esito: ${failures.length ? 'KO' : 'OK'}`,
    `Caricamento: ${loadMs} ms`,
    `Titolo: ${base.h1}`,
    `Tab: ${base.tabCount}, attiva ${base.activeTab}`,
    `Pannello: ${base.panel.width}px, barra icone ${base.rail.width}px, preview ${base.preview.width}px`,
    `Resize pannello: ${resize.before}px -> ${resize.after}px`,
    `Footer live visibile: ${footer.visible ? 'si' : 'no'}`,
    `Tablet/mobile menu: ${mobileTablet.map((item) => `${item.target} ${item.menuVisible ? 'si' : 'no'} (${item.navItems})`).join(', ')}`,
    `Font: ${theme.fontSelect} / ${theme.headingFont}`,
    `Colori secondario/accento: ${theme.secondary} / ${theme.accent}`,
    `Effetti preview: ${theme.classes}`,
    `Formattazione: ${formatting.rows.map((row) => `${row.label} ${row.buttons.length}`).join(', ')}`,
    `Failure: ${failures.join(', ') || '-'}`,
    '',
    'Screenshot: desktop-builder.png, desktop-builder-themed.png, tablet-builder.png, mobile-builder.png',
    '',
  ].join('\n')
}

const client = await newPage(await collectBrowserCookies())
try {
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: 1600,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  })
  const started = Date.now()
  try {
    await client.send('Page.navigate', { url: `${host}/sito-studio/builder` })
  } catch {
    // La navigazione puo restare aperta se qualche richiesta lunga tiene vivo il documento; si prosegue misurando il DOM.
  }
  await waitForBuilder(client)
  const loadMs = Date.now() - started

  const base = await evalJson(client, `(() => {
    const visible = (selector) => {
      const element = document.querySelector(selector)
      if (!element) return false
      const rect = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
    }
    const rect = (selector) => {
      const element = document.querySelector(selector)
      if (!element) return null
      const value = element.getBoundingClientRect()
      return { width: Math.round(value.width), height: Math.round(value.height), top: Math.round(value.top), bottom: Math.round(value.bottom) }
    }
    const text = document.body.innerText
    const forbidden = ['backend','frontend','legacy','payload','runtime','json_api','provider','webhook','undefined','null','demo','sample','repository']
      .filter((word) => new RegExp('\\\\b' + word + '\\\\b', 'i').test(text))
    return {
      h1: document.querySelector('.iu-builder-topbar-pro h1')?.innerText?.trim() || '',
      activeTab: document.querySelector('.iu-builder-tab-panel header h2')?.innerText?.trim() || '',
      tabCount: document.querySelectorAll('.iu-builder-tab-rail button').length,
      panel: rect('.iu-builder-left-pro'),
      rail: rect('.iu-builder-tab-rail'),
      preview: rect('.iu-builder-preview-shell'),
      resizeHandle: visible('.iu-builder-resize-handle'),
      shellSidebarVisible: visible('.iu-sidebar') || visible('.iu-topbar'),
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
      footerExists: Boolean(document.querySelector('.iu-builder-public-footer')),
      forbidden,
    }
  })()`)
  await capture(client, 'desktop-builder.png')

  const footer = await evalJson(client, `new Promise((resolve) => {
    const page = document.querySelector('.iu-builder-public-page')
    const footer = document.querySelector('.iu-builder-public-footer')
    page.scrollTop = page.scrollHeight
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const p = page.getBoundingClientRect()
      const f = footer.getBoundingClientRect()
      resolve({
        scrollTop: Math.round(page.scrollTop),
        scrollHeight: Math.round(page.scrollHeight),
        footerTop: Math.round(f.top),
        footerBottom: Math.round(f.bottom),
        containerTop: Math.round(p.top),
        containerBottom: Math.round(p.bottom),
        visible: f.top < p.bottom && f.bottom > p.top,
      })
    }))
  })`)

  const resize = await evalJson(client, `new Promise((resolve) => {
    const handle = document.querySelector('.iu-builder-resize-handle')
    const before = Math.round(document.querySelector('.iu-builder-left-pro').getBoundingClientRect().width)
    handle.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: before + 24, button: 0 }))
    window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: before + 124, button: 0 }))
    window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: before + 124, button: 0 }))
    setTimeout(() => requestAnimationFrame(() => resolve({
      before,
      after: Math.round(document.querySelector('.iu-builder-left-pro').getBoundingClientRect().width),
      gridColumns: getComputedStyle(document.querySelector('.iu-builder-pro-grid')).gridTemplateColumns,
      gridWidth: Math.round(document.querySelector('.iu-builder-pro-grid').getBoundingClientRect().width),
      title: document.querySelector('.iu-builder-resize-handle')?.getAttribute('title') || '',
    })), 120)
  })`)

  const theme = await evalJson(client, `new Promise((resolve) => {
    const setSelect = (labelText, value) => {
      const label = Array.from(document.querySelectorAll('label.iu-builder-field')).find((item) => item.querySelector('span')?.innerText?.trim() === labelText)
      const select = label?.querySelector('select')
      if (!select) return null
      select.value = value
      select.dispatchEvent(new Event('change', { bubbles: true }))
      return select.value
    }
    const colors = Array.from(document.querySelectorAll('.iu-builder-swatch-row input[type="color"]'))
    const colorSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    if (colors[1]) { colorSetter.call(colors[1], '#6d334f'); colors[1].dispatchEvent(new Event('input', { bubbles: true })); colors[1].dispatchEvent(new Event('change', { bubbles: true })) }
    if (colors[2]) { colorSetter.call(colors[2], '#0f9f8f'); colors[2].dispatchEvent(new Event('input', { bubbles: true })); colors[2].dispatchEvent(new Event('change', { bubbles: true })) }
    setSelect('Font', 'garamond_legal')
    setSelect('Dimensione testo', '18px')
    setSelect('Titolo hero', '48px')
    setSelect('Titoli sezioni', '34px')
    setSelect('Movimento sezioni', 'scale-in')
    setSelect('Ombra card', 'layered')
    setSelect('Header', 'transparent')
    setSelect('Separatore sezioni', 'accent-line')
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const page = document.querySelector('.iu-builder-public-page')
      const h1 = document.querySelector('.iu-builder-public-hero h1')
      const card = document.querySelector('.iu-builder-public-card') || document.querySelector('.iu-builder-public-hero aside')
      resolve({
        fontSelect: Array.from(document.querySelectorAll('label.iu-builder-field')).find((item) => item.querySelector('span')?.innerText?.trim() === 'Font')?.querySelector('select')?.value,
        headingFont: getComputedStyle(h1).fontFamily,
        textSize: getComputedStyle(page).getPropertyValue('--site-text-size').trim(),
        headingSize: getComputedStyle(page).getPropertyValue('--site-heading-size').trim(),
        sectionTitleSize: getComputedStyle(page).getPropertyValue('--site-section-title-size').trim(),
        secondary: getComputedStyle(page).getPropertyValue('--site-secondary').trim(),
        accent: getComputedStyle(page).getPropertyValue('--site-accent').trim(),
        classes: page.className,
        cardShadow: getComputedStyle(card).boxShadow,
      })
    }))
  })`)
  await capture(client, 'desktop-builder-themed.png')

  const mobileTablet = []
  for (const target of ['Tablet', 'Mobile']) {
    const result = await evalJson(client, `new Promise((resolve) => {
      const button = Array.from(document.querySelectorAll('.iu-builder-device-tabs button')).find((item) => item.innerText.trim() === '${target}')
      button?.click()
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const menu = document.querySelector('.iu-builder-public-menu-button')
        const preview = document.querySelector('.iu-builder-preview-shell')
        resolve({
          target: '${target}',
          className: preview?.className || '',
          menuVisible: Boolean(menu) && getComputedStyle(menu).display !== 'none' && menu.getBoundingClientRect().width > 0,
          navItems: document.querySelectorAll('.iu-builder-public-nav nav span').length,
          previewWidth: Math.round(preview?.getBoundingClientRect().width || 0),
          headerHeight: Math.round(document.querySelector('.iu-builder-public-nav')?.getBoundingClientRect().height || 0),
        })
      }))
    })`)
    mobileTablet.push(result)
    await capture(client, `${target.toLowerCase()}-builder.png`)
  }

  const formatting = await evalJson(client, `new Promise((resolve) => {
    const contenuti = Array.from(document.querySelectorAll('.iu-builder-tab-rail button')).find((item) => item.getAttribute('aria-label') === 'Contenuti')
    contenuti?.click()
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const rows = Array.from(document.querySelectorAll('.iu-builder-format-toolbar')).map((row) => ({
        label: row.querySelector('span')?.innerText?.trim() || '',
        buttons: Array.from(row.querySelectorAll('button')).map((button) => button.getAttribute('title')),
      }))
      const alignButtons = Array.from(document.querySelectorAll('.iu-builder-button-group button')).map((button) => button.getAttribute('title'))
      resolve({ rows, alignButtons })
    }))
  })`)

  const media = await evalJson(client, `new Promise((resolve) => {
    const media = Array.from(document.querySelectorAll('.iu-builder-tab-rail button')).find((item) => item.getAttribute('aria-label') === 'Media')
    media?.click()
    requestAnimationFrame(() => requestAnimationFrame(() => resolve({
      uploadInput: Boolean(document.querySelector('.iu-builder-upload input[type="file"]')),
      uploadAltRequired: Boolean(document.querySelector('.iu-builder-upload input[required], .iu-builder-upload textarea[required]')),
      libraryVisible: Boolean(document.querySelector('.iu-builder-asset-grid')),
    })))
  })`)

  const consoleErrors = client.events
    .filter((event) => event.method === 'Runtime.consoleAPICalled' || event.method === 'Log.entryAdded')
    .map((event) => event.params?.entry?.text || event.params?.args?.map((arg) => arg.value || arg.description).join(' ') || '')
    .filter(Boolean)
    .filter((line) => /error|uncaught|failed/i.test(line))

  const failures = []
  if (base.h1 !== 'Sito Studio Builder Pro') failures.push('titolo_non_esatto')
  if (base.activeTab !== 'Aspetto') failures.push('tab_aspetto_non_attiva')
  if (base.tabCount !== 10) failures.push('tab_count')
  if (Math.abs(base.panel.width - 380) > 18) failures.push('pannello_380px')
  if (Math.abs(base.rail.width - 92) > 16) failures.push('barra_icone')
  if (!base.resizeHandle || resize.after <= resize.before + 40 || !/480px/.test(resize.gridColumns || '')) failures.push('resize_pannello')
  if (!base.preview || base.preview.width < 900) failures.push('preview_non_grande')
  if (base.shellSidebarVisible) failures.push('shell_visibile')
  if (base.horizontalOverflow) failures.push('overflow_orizzontale')
  if (!base.footerExists || !footer.visible) failures.push('footer_non_visibile_live')
  if (!media.uploadInput || media.uploadAltRequired || !media.libraryVisible) failures.push('upload_media_non_pronto')
  if (theme.fontSelect !== 'garamond_legal' || !/garamond/i.test(theme.headingFont)) failures.push('font_non_applicato')
  if (theme.textSize !== '18px' || theme.headingSize !== '48px' || theme.sectionTitleSize !== '34px') failures.push('dimensioni_font_non_applicate')
  if (theme.secondary !== '#6d334f' || theme.accent !== '#0f9f8f') failures.push('colori_centrali_non_applicati')
  if (!/has-scale-animation|has-shadow-layered|has-transparent-header|has-divider-accent-line/.test(theme.classes)) failures.push('effetti_non_applicati')
  if (!theme.cardShadow || theme.cardShadow === 'none') failures.push('ombra_card_non_visibile')
  if (!mobileTablet.every((item) => item.menuVisible && item.navItems >= 3)) failures.push('menu_tablet_mobile')
  if (formatting.rows.length < 3 || !formatting.rows.every((row) => row.buttons.length === 4)) failures.push('formattazione_rich_text')
  if (!formatting.alignButtons.includes('Giustificato')) failures.push('allineamenti_mancanti')
  if (base.forbidden.length) failures.push('testo_tecnico_visibile')
  if (consoleErrors.length) failures.push('console_error')

  const report = { checkedAt: new Date().toISOString(), loadMs, base, footer, resize, theme, mobileTablet, formatting, media, consoleErrors, failures }
  writeFileSync(resolve(outDir, 'visual-load-audit.json'), JSON.stringify(report, null, 2))
  const md = markdown(report)
  writeFileSync(resolve(outDir, 'visual-load-audit.md'), md)
  if (failures.length) {
    console.error(md)
    process.exit(1)
  }
  console.log(md)
} finally {
  try {
    await client.send('Page.close')
  } catch {
    client.close()
  }
}
