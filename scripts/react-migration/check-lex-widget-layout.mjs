import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const host = process.env.IUSENTRA_AUDIT_HOST || 'http://localhost:8080'
const cdpHost = process.env.IUSENTRA_CDP_HOST || 'http://127.0.0.1:9224'
const cookie = process.env.IUSENTRA_SESSION_COOKIE || ''
const auditLabel = process.env.IUSENTRA_AUDIT_LABEL || 'lex-widget-layout'
const outDir = resolve(root, `artifacts/react-migration/lex-${auditLabel}`)
mkdirSync(outDir, { recursive: true })

const viewports = [
  { name: 'desktop', width: 1440, height: 980, mobile: false },
  { name: 'tablet', width: 1024, height: 900, mobile: false },
  { name: 'mobile', width: 390, height: 844, mobile: true },
]

const routeFilter = (process.env.IUSENTRA_LEX_AUDIT_ROUTES || '/email,/notifiche-legali,/fascicoli')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean)

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

  async ready() {
    if (this.ws.readyState === WebSocket.OPEN) return
    await new Promise((resolveReady, rejectReady) => {
      const timer = setTimeout(() => rejectReady(new Error('Timeout connessione CDP')), 10000)
      this.ws.onopen = () => {
        clearTimeout(timer)
        resolveReady()
      }
      this.ws.onerror = (error) => {
        clearTimeout(timer)
        rejectReady(error)
      }
    })
  }

  send(method, params = {}) {
    const id = ++this.seq
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolveSend, rejectSend) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        rejectSend(new Error(`Timeout CDP ${method}`))
      }, 30000)
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
  await client.ready()
  return client
}

async function waitForLex(client) {
  const deadline = Date.now() + 12000
  let last = null
  while (Date.now() < deadline) {
    const { result } = await client.send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(() => {
        const widget = document.getElementById('pct-ai-widget');
        const panel = document.getElementById('pct-ai-panel');
        return {
          ready: Boolean(widget && panel && !panel.hidden && widget.classList.contains('pct-ai-widget--open')),
          widget: Boolean(widget),
          panel: Boolean(panel),
          open: Boolean(widget && widget.classList.contains('pct-ai-widget--open')),
          hidden: Boolean(panel && panel.hidden)
        };
      })()`,
    })
    last = result.value
    if (last?.ready) return last
    await new Promise((resolveWait) => setTimeout(resolveWait, 220))
  }
  throw new Error(`Lex non aperto: ${JSON.stringify(last)}`)
}

async function evaluateLayout(client, route, viewportName) {
  const { result } = await client.send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(() => {
      const rectOf = (node) => {
        if (!node) return null;
        const rect = node.getBoundingClientRect();
        return {
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          top: Math.round(rect.top),
          bottom: Math.round(rect.bottom),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        };
      };
      const isVisible = (node) => {
        if (!node) return false;
        const rect = node.getBoundingClientRect();
        const style = window.getComputedStyle(node);
        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const panel = document.getElementById('pct-ai-panel');
      const composer = panel && panel.querySelector('.pct-ai-composer');
      const inputWrap = panel && panel.querySelector('.pct-ai-input-wrap');
      const toolbar = panel && panel.querySelector('.pct-ai-toolbar');
      const input = document.getElementById('pct-ai-input');
      const tools = Array.from(panel ? panel.querySelectorAll('.pct-ai-tool-btn') : []).map((node) => {
        const rect = node.getBoundingClientRect();
        const label = (node.getAttribute('aria-label') || node.getAttribute('title') || node.innerText || '').trim().replace(/\\s+/g, ' ');
        const icon = Boolean(node.querySelector('i, svg, [class*="icon"]'));
        return {
          label,
          icon,
          visible: isVisible(node),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          top: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        };
      });
      const panelRect = rectOf(panel);
      const composerRect = rectOf(composer);
      const inputRect = rectOf(inputWrap);
      const toolbarRect = rectOf(toolbar);
      const overflow = [panel, composer, inputWrap, toolbar, ...Array.from(panel ? panel.querySelectorAll('.pct-ai-tool-btn') : [])]
        .filter(Boolean)
        .map((node) => ({ node, rect: node.getBoundingClientRect() }))
        .filter((item) => item.rect.left < -2 || item.rect.right > window.innerWidth + 2 || item.rect.top < -2 || item.rect.bottom > window.innerHeight + 2)
        .map((item) => ({
          className: String(item.node.className || item.node.id || '').slice(0, 80),
          left: Math.round(item.rect.left),
          right: Math.round(item.rect.right),
          top: Math.round(item.rect.top),
          bottom: Math.round(item.rect.bottom),
          width: Math.round(item.rect.width),
          height: Math.round(item.rect.height)
        }));
      const lateralToolbar = toolbarRect && inputRect ? toolbarRect.left >= inputRect.right - 3 : false;
      const stackedToolbar = toolbarRect && inputRect ? toolbarRect.top >= inputRect.bottom - 3 : false;
      return {
        route: ${JSON.stringify(route)},
        viewport: ${JSON.stringify(viewportName)},
        open: Boolean(panel && !panel.hidden),
        panel: panelRect,
        composer: composerRect,
        input: inputRect,
        toolbar: toolbarRect,
        tools,
        inputPlaceholder: input ? input.getAttribute('placeholder') : '',
        lateralToolbar,
        stackedToolbar,
        overflow,
        consoleErrors: []
      };
    })()`,
  })
  return result.value
}

function failuresFor(result, viewport) {
  const failures = []
  if (!result.open) failures.push('lex_non_aperto')
  if (!result.panel || result.panel.width < 300 || result.panel.height < 420) failures.push('pannello_troppo_piccolo')
  if (!result.composer || result.composer.width < 260) failures.push('composer_troppo_stretto')
  if (!result.input || result.input.height < 42) failures.push('input_non_operativo')
  const labels = result.tools.map((tool) => tool.label).join(' | ')
  if (!/Carica documenti/i.test(labels)) failures.push('upload_documenti_assente')
  if (!/Microfono|Detta/i.test(labels)) failures.push('microfono_assente')
  if (!/Web libero|ricerca web/i.test(labels)) failures.push('web_libero_assente')
  if (result.tools.length < 3 || result.tools.some((tool) => !tool.visible || !tool.icon)) failures.push('strumenti_lex_non_visibili')
  if (result.tools.some((tool) => tool.width < 40 || tool.height < 40)) failures.push('strumenti_lex_troppo_piccoli')
  if (viewport.name === 'desktop' && !result.lateralToolbar) failures.push('toolbar_lex_non_laterale')
  if (viewport.name === 'mobile' && !result.stackedToolbar) failures.push('toolbar_lex_mobile_non_ottimizzata')
  if (result.overflow.length) failures.push('overflow_lex')
  return failures
}

async function auditOne(client, route, viewport) {
  client.events = []
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: 1,
    mobile: viewport.mobile,
  })
  await client.send('Page.navigate', { url: `${host}${route}` })
  await client.send('Runtime.evaluate', {
    awaitPromise: true,
    expression: `new Promise((resolve) => {
      if (document.readyState !== 'loading') resolve(true);
      else document.addEventListener('DOMContentLoaded', () => resolve(true), { once: true });
    })`,
  })
  await new Promise((resolveWait) => setTimeout(resolveWait, 700))
  await client.send('Runtime.evaluate', {
    expression: `(() => {
      try { localStorage.removeItem('iusentra-pct-ai-layout-v1'); } catch (_) {}
      try { sessionStorage.removeItem('iusentra-pct-ai-layout-v1:session'); } catch (_) {}
      window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex', { detail: { context: 'verifica-grafica', title: 'Lex verifica grafica' } }));
      const fab = document.getElementById('pct-ai-fab');
      const panel = document.getElementById('pct-ai-panel');
      if (fab && panel && panel.hidden) fab.click();
      return true;
    })()`,
  })
  await waitForLex(client)
  const result = await evaluateLayout(client, route, viewport.name)
  const consoleErrors = client.events
    .filter((event) => event.method === 'Runtime.consoleAPICalled' || event.method === 'Log.entryAdded')
    .map((event) => event.params?.entry?.text || event.params?.args?.map((arg) => arg.value || arg.description).join(' ') || '')
    .filter((line) => /\berror\b|uncaught|failed/i.test(String(line || '')))
    .filter((line) => !/ERR_NO_BUFFER_SPACE/i.test(String(line || '')))
  result.consoleErrors = consoleErrors
  const failures = failuresFor(result, viewport)
  if (consoleErrors.length) failures.push('console_error')
  const screenshotName = `${viewport.name}-${route.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'home'}-lex.png`
  const screenshot = await client.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  writeFileSync(resolve(outDir, screenshotName), Buffer.from(screenshot.data, 'base64'))
  return { ...result, screenshot: screenshotName, failures }
}

async function main() {
  const client = await newPage()
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Log.enable')
  await client.send('Network.enable')
  await client.send('Network.setCacheDisabled', { cacheDisabled: true })
  if (cookie) {
    await client.send('Network.setCookie', {
      name: 'hacs_session',
      value: cookie,
      url: host,
      path: '/',
      httpOnly: true,
      sameSite: 'Lax',
    })
  }
  const results = []
  try {
    for (const route of routeFilter) {
      for (const viewport of viewports) {
        const result = await auditOne(client, route, viewport)
        results.push(result)
        const status = result.failures.length ? 'FAIL' : 'OK'
        console.log(`${status} ${viewport.name} ${route} ${result.failures.join(',')}`)
      }
    }
  } finally {
    client.close()
  }
  const failures = results.filter((item) => item.failures.length)
  const rows = results.map((item) => `| ${item.failures.length ? 'KO' : 'OK'} | ${item.viewport} | ${item.route} | ${item.panel?.width || 0}x${item.panel?.height || 0} | ${item.lateralToolbar ? 'laterale' : item.stackedToolbar ? 'verticale' : 'non rilevata'} | ${item.failures.join(', ') || '-'} |`).join('\n')
  const md = [
    `# Lex widget layout audit ${auditLabel}`,
    '',
    `Host: ${host}`,
    `Route verificate: ${routeFilter.length}`,
    `Controlli totali: ${results.length}`,
    `Failure: ${failures.length}`,
    '',
    '| Esito | Viewport | Route | Pannello | Toolbar | Problemi |',
    '| --- | --- | --- | ---: | --- | --- |',
    rows,
    '',
    '## Dettaglio JSON',
    '',
    `Report macchina: \`lex-widget-layout.json\``,
    '',
  ].join('\n')
  writeFileSync(resolve(outDir, 'lex-widget-layout.md'), md, 'utf8')
  writeFileSync(resolve(outDir, 'lex-widget-layout.json'), JSON.stringify({ auditLabel, host, failures, results }, null, 2), 'utf8')
  if (failures.length) {
    console.error(`${failures.length} Lex layout checks failed. See ${resolve(outDir, 'lex-widget-layout.md')}`)
    process.exit(1)
  }
  console.log(`lex-widget-layout: OK (${results.length} checks)`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
