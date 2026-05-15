import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const host = process.env.IUSENTRA_AUDIT_HOST || 'http://localhost:8080'
const cdpHost = process.env.IUSENTRA_CDP_HOST || 'http://127.0.0.1:9224'
const cookie = process.env.IUSENTRA_SESSION_COOKIE || ''
const auditLabel = process.env.IUSENTRA_AUDIT_LABEL || '2.213.0'
const outDir = resolve(root, `artifacts/react-migration/visual-${auditLabel}`)
mkdirSync(outDir, { recursive: true })

const allRoutes = [
  ['Panoramica', '/'],
  ['Regia Operativa', '/workspace-intelligente'],
  ['Ricerca Studio', '/global-search'],
  ['Agenda / Calendario', '/agenda'],
  ['Nuovo Appuntamento', '/agenda/nuovo'],
  ['Timesheet', '/timesheet'],
  ['Fascicoli', '/fascicoli'],
  ['Nuovo Fascicolo', '/fascicoli/nuovo'],
  ['Archivio Fascicoli', '/fascicoli/archivio'],
  ['Clienti e Anagrafiche', '/clienti'],
  ['Nuovo Cliente', '/clienti/nuovo'],
  ['Cartelle Condivise', '/cartelle-condivise'],
  ['Soggetti e Parti', '/soggetti'],
  ['Nuovo Soggetto', '/soggetti/nuovo'],
  ['Email PEC', '/email'],
  ['Email ordinaria SMTP', '/email-ordinaria'],
  ['Messaggi', '/messaggi'],
  ['Nuovo SMS/WA', '/messaggi/nuovo'],
  ['Scadenziario', '/scadenziario'],
  ['Nuova Scadenza', '/scadenziario/nuova'],
  ['Preparazione Udienza Guidata', '/wizard-pro'],
  ['Controlli Atti', '/deposito/checklist'],
  ['Studio', '/studio'],
  ['Parcelle e Fatture', '/fatturazione'],
  ['Preventivi e Incarichi', '/preventivi'],
  ['Nuovo Preventivo', '/preventivi/nuovo'],
  ['Nuovo Conferimento', '/preventivi/conferimento/nuovo'],
  ['Dettaglio Conferimento', '/preventivi/conferimento/f613a379-326a-42b8-8465-777d8998b624'],
  ['Compensi Forensi', '/compensi-forensi'],
  ['Redazione Atti', '/redazione-atti'],
  ['Statistiche', '/statistiche'],
  ['Ricerca Legale', '/ricerca-legale'],
  ['Archivio Giurisprudenza', '/giurisprudenza'],
  ['Strumenti Forensi', '/strumenti-legali'],
  ['Strumenti Operativi', '/strumenti-operativi'],
  ['Sito Studio', '/sito-studio'],
  ['Amministrazione', '/amministrazione'],
  ['Utenti', '/utenti'],
  ['Profili e Permessi', '/profili'],
  ['Registro Attivita', '/audit'],
  ['Database', '/admin/database'],
  ['Registro GDPR', '/privacy/registro'],
  ['Impostazioni', '/impostazioni'],
  ['Backup', '/backup'],
  ['Notifiche', '/notifiche'],
  ['Calendari', '/impostazioni/calendario'],
]

const routeFilter = new Set((process.env.IUSENTRA_AUDIT_ROUTES || '').split(',').map((item) => item.trim()).filter(Boolean))
const routes = routeFilter.size
  ? allRoutes.filter(([, route]) => routeFilter.has(route))
  : allRoutes

const viewports = [
  { name: 'desktop', width: 1440, height: 980, mobile: false },
  { name: 'mobile', width: 390, height: 844, mobile: true },
].filter((viewport) => {
  const filter = (process.env.IUSENTRA_AUDIT_VIEWPORTS || '').split(',').map((item) => item.trim()).filter(Boolean)
  return filter.length ? filter.includes(viewport.name) : true
})
const reuseTab = process.env.IUSENTRA_AUDIT_REUSE_TAB === '1'

const forbidden = [
  /\bbackend\b/i,
  /\bfrontend\b/i,
  /\blegacy\b/i,
  /\bpayload\b/i,
  /\bruntime\b/i,
  /\bjson_api\b/i,
  /\bprovider\b/i,
  /\bwebhook\b/i,
  /\bundefined\b/i,
  /\bnull\b/i,
  /\bdemo\b/i,
]

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

async function newPage() {
  const response = await fetch(`${cdpHost}/json/new?about:blank`, { method: 'PUT' })
  if (!response.ok) throw new Error(`CDP non disponibile: ${response.status}`)
  const target = await response.json()
  const client = new Cdp(target.webSocketDebuggerUrl)
  client.targetId = target.id
  await client.open()
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Network.enable')
  await client.send('Log.enable')
  if (cookie) {
    await client.send('Network.setCookie', {
      name: 'hacs_session',
      value: cookie,
      url: host,
      path: '/',
      sameSite: 'Lax',
    })
  }
  return client
}

async function closePage(client) {
  if (!client) return
  try {
    await client.send('Page.close')
  } catch {
    try {
      client.close()
    } catch {
      // Browser gia chiuso.
    }
  }
}

async function waitForPage(client, startedAt) {
  let last = {}
  for (;;) {
    const { result } = await client.send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(() => {
        const text = document.body ? document.body.innerText : '';
        const main = document.querySelector('main, .iu-content, #root, #iusentra-root');
        const links = Array.from(document.querySelectorAll('main a[href], .iu-content a[href]'))
          .filter((link) => !link.closest('nav'))
          .map((link) => ({ text: (link.innerText || link.textContent || '').trim(), href: link.getAttribute('href') }))
          .filter((link) => link.href)
          .slice(0, 18);
        const postForms = Array.from(document.forms)
          .filter((form) => String(form.method || '').toLowerCase() === 'post')
          .map((form) => form.getAttribute('action') || location.pathname);
        const styleLinks = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map((link) => link.getAttribute('href') || '');
        const h1 = document.querySelector('h1')?.innerText?.trim() || '';
        const h2 = document.querySelector('h2')?.innerText?.trim() || '';
        const isVisible = (node) => {
          const rect = node.getBoundingClientRect();
          const style = window.getComputedStyle(node);
          return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
        };
        const primaryLoaders = Array.from(document.querySelectorAll('main .ius-loading-state, main .iu-share-loading, main .iu-timesheet-loading, main .iu-wiz-loading, main .iu-de-empty, main [aria-busy="true"]'))
          .filter(isVisible)
          .map((node) => (node.innerText || node.textContent || '').trim())
          .filter((value) => /Caricamento/i.test(value));
        const primaryLoading = primaryLoaders.length > 0 || /^Caricamento/i.test(h1) || /^Caricamento/i.test(h2);
        return {
          url: location.href,
          title: document.title,
          ready: document.readyState,
          h1,
          h2,
          text,
          textLength: text.trim().length,
          hasRoot: Boolean(document.querySelector('#root, #iusentra-root, [data-reactroot]')),
          hasShell: Boolean(document.querySelector('.iu-app-shell, .iu-sidebar, .iu-topbar, .iu-content')),
          loading: primaryLoading,
          loadingContext: primaryLoaders.slice(0, 3),
          postForms,
          links,
          actions: document.querySelectorAll('button, main a[href], .iu-content a[href]').length,
          cards: document.querySelectorAll('.iu-card, .ius-card, .iu-action-card, .iu-metric-card, .iu-panel, [class*="card"], [class*="panel"]').length,
          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
          scrollHeight: document.documentElement.scrollHeight,
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
          styleSystem: styleLinks.some((href) => href.includes('/static/react/') || href.includes('app.css')),
        };
      })()`,
    })
    last = result.value || {}
    const elapsed = Date.now() - startedAt
    const login = /\/login\b/.test(String(last.url || '')) || /Accesso sicuro/i.test(String(last.text || ''))
    const usable = last.ready === 'complete' && !login && !last.loading && last.textLength > 280
    if (usable || elapsed > 18000) return { ...last, elapsedMs: elapsed, login }
    await new Promise((resolveWait) => setTimeout(resolveWait, 250))
  }
}

async function auditOne(client, routeName, route, viewport) {
  client.events = []
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: 1,
    mobile: viewport.mobile,
  })
  const startedAt = Date.now()
  try {
    await client.send('Page.navigate', { url: `${host}${route}` })
  } catch (error) {
    return {
      routeName,
      route,
      viewport: viewport.name,
      elapsedMs: Date.now() - startedAt,
      url: `${host}${route}`,
      title: '',
      h1: '',
      h2: '',
      textLength: 0,
      hasRoot: false,
      hasShell: false,
      actions: 0,
      cards: 0,
      links: [],
      postForms: [],
      forbidden: [],
      forbiddenContexts: [],
      horizontalOverflow: false,
      scrollHeight: 0,
      console: [String(error?.message || error)],
      screenshot: '',
      warnings: [],
      failures: ['navigazione_timeout'],
    }
  }
  const data = await waitForPage(client, startedAt)
  const text = String(data.text || '')
  const hits = forbidden
    .filter((pattern) => pattern.test(text))
    .map((pattern) => pattern.source)
  const forbiddenContexts = forbidden
    .flatMap((pattern) => {
      const match = text.match(pattern)
      if (!match || match.index === undefined) return []
      const start = Math.max(0, match.index - 80)
      const end = Math.min(text.length, match.index + 140)
      return [{ pattern: pattern.source, context: text.slice(start, end).replace(/\s+/g, ' ').trim() }]
    })
  let screenshotName = `${viewport.name}-load-${routeName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}.png`
  let screenshotWarning = ''
  try {
    const screenshot = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
    writeFileSync(resolve(outDir, screenshotName), Buffer.from(screenshot.data, 'base64'))
  } catch (error) {
    screenshotName = ''
    screenshotWarning = `screenshot_non_acquisito: ${String(error?.message || error)}`
  }
  const consoleEntries = client.events
    .filter((event) => event.method === 'Runtime.consoleAPICalled' || event.method === 'Log.entryAdded')
    .map((event) => event.params?.entry?.text || event.params?.args?.map((arg) => arg.value || arg.description).join(' ') || '')
    .filter(Boolean)
  const failures = []
  if (data.login) failures.push('redirect_login')
  if (!data.hasRoot || !data.hasShell) failures.push('react_shell_assente')
  if (data.loading) failures.push('caricamento_non_chiuso')
  if (data.textLength < 280) failures.push('contenuto_vuoto')
  if (data.postForms?.length) failures.push('form_post_html')
  if (hits.length) failures.push('testo_tecnico_visibile')
  if (data.horizontalOverflow) failures.push('overflow_orizzontale')
  if (consoleEntries.some((line) => /\berror\b|uncaught|failed/i.test(line))) failures.push('console_error')
  const warnings = []
  if (screenshotWarning) warnings.push(screenshotWarning)
  if ((data.links?.length || 0) < 2 && route !== '/') warnings.push('collegamenti_pagina_da_arricchire')
  if ((data.actions || 0) < 3 && route !== '/') warnings.push('azioni_pagina_da_arricchire')
  return {
    routeName,
    route,
    viewport: viewport.name,
    elapsedMs: data.elapsedMs,
    url: data.url,
    title: data.title,
    h1: data.h1,
    h2: data.h2,
    textLength: data.textLength,
    hasRoot: data.hasRoot,
    hasShell: data.hasShell,
    actions: data.actions,
    cards: data.cards,
    links: data.links,
    postForms: data.postForms,
    forbidden: hits,
    forbiddenContexts,
    horizontalOverflow: data.horizontalOverflow,
    scrollHeight: data.scrollHeight,
    loadingContext: data.loadingContext || [],
    console: consoleEntries,
    screenshot: screenshotName,
    warnings,
    failures,
  }
}

let client = null
const startedAt = new Date().toISOString()
const results = []
let checkedInClient = 0
try {
  for (const viewport of viewports) {
    for (const [routeName, route] of routes) {
      if (!client || (!reuseTab && checkedInClient >= 1) || (reuseTab && checkedInClient >= 18)) {
        await closePage(client)
        client = await newPage()
        checkedInClient = 0
      }
      let result = await auditOne(client, routeName, route, viewport)
      if (result.failures.some((failure) => ['navigazione_timeout', 'react_shell_assente', 'contenuto_vuoto', 'caricamento_non_chiuso'].includes(failure))) {
        const retry = await auditOne(client, routeName, route, viewport)
        if (!retry.failures.length) {
          retry.warnings = [...(retry.warnings || []), `retry_ok_dopo: ${result.failures.join(',')}`]
          result = retry
        } else {
          await closePage(client)
          client = await newPage()
          const freshRetry = await auditOne(client, routeName, route, viewport)
          if (!freshRetry.failures.length) {
            freshRetry.warnings = [...(freshRetry.warnings || []), `retry_browser_nuovo_dopo: ${result.failures.join(',')}`]
            result = freshRetry
          }
        }
      }
      results.push(result)
      checkedInClient += 1
      const mark = result.failures.length ? 'FAIL' : 'OK'
      console.log(`${mark} ${viewport.name} ${route} ${result.elapsedMs}ms ${result.failures.join(',')}`)
    }
  }
} finally {
  await closePage(client)
}

const failures = results.filter((item) => item.failures.length)
const report = {
  startedAt,
  finishedAt: new Date().toISOString(),
  host,
  cdpHost,
  browser: 'Chrome CDP',
  reuseTab,
  routeCount: routes.length,
  totalChecks: results.length,
  failures,
  results,
}
writeFileSync(resolve(outDir, 'visual-load-audit.json'), JSON.stringify(report, null, 2))

const markdown = [
  `# Visual load audit ${auditLabel}`,
  '',
  `Host: ${host}`,
  `Route verificate: ${routes.length}`,
  `Controlli totali: ${results.length}`,
  `Failure: ${failures.length}`,
  '',
  '| Esito | Viewport | Route | Tempo | H1 | Problemi | Avvisi |',
  '| --- | --- | --- | ---: | --- | --- | --- |',
  ...results.map((item) => [
    item.failures.length ? 'KO' : 'OK',
    item.viewport,
    item.route,
    `${item.elapsedMs} ms`,
    String(item.h1 || item.h2 || '').replace(/\|/g, '/'),
    item.failures.join(', ') || '-',
    item.warnings?.join(', ') || '-',
  ].join(' | ').replace(/^/, '| ').replace(/$/, ' |')),
  '',
].join('\n')
writeFileSync(resolve(outDir, 'visual-load-audit.md'), markdown)

if (failures.length) {
  console.error(`${failures.length} visual/load checks failed. See ${resolve(outDir, 'visual-load-audit.md')}`)
  process.exit(1)
}
console.log(`visual-load-audit: OK (${results.length} checks)`)
