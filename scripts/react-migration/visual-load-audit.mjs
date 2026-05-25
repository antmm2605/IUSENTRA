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
const screenshotMode = process.env.IUSENTRA_AUDIT_SCREENSHOTS || 'all'
const fullPageScreenshots = process.env.IUSENTRA_AUDIT_FULLPAGE_SCREENSHOTS === '1'

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
  ['Dettaglio Fascicolo 0D4A4802', '/fascicoli/0D4A4802'],
  ['Dettaglio Fascicolo DC5BF1DB', '/fascicoli/DC5BF1DB'],
  ['Clienti e Anagrafiche', '/clienti'],
  ['Nuovo Cliente', '/clienti/nuovo'],
  ['Cartelle Condivise', '/cartelle-condivise'],
  ['Soggetti e Parti', '/soggetti'],
  ['Nuovo Soggetto', '/soggetti/nuovo'],
  ['Email PEC', '/email'],
  ['Email ordinaria SMTP', '/email-ordinaria'],
  ['Notifiche Legali', '/notifiche-legali'],
  ['Messaggi', '/messaggi'],
  ['Nuovo SMS/WA', '/messaggi/nuovo'],
  ['Scadenziario', '/scadenziario'],
  ['Nuova Scadenza', '/scadenziario/nuova'],
  ['Preparazione Udienza Guidata', '/wizard-pro'],
  ['Controlli Atti', '/deposito/checklist'],
  ['Tribunali / PEC', '/tribunali'],
  ['Studio', '/studio'],
  ['Parcelle e Fatture', '/fatturazione'],
  ['Preventivi e Incarichi', '/preventivi'],
  ['Nuovo Preventivo', '/preventivi/nuovo'],
  ['Nuovo Conferimento', '/preventivi/conferimento/nuovo'],
  ['Dettaglio Conferimento', '/preventivi/conferimento/f613a379-326a-42b8-8465-777d8998b624'],
  ['Compensi Forensi', '/compensi-forensi'],
  ['Documenti', '/documenti'],
  ['Redazione Atti', '/redazione-atti'],
  ['Statistiche', '/statistiche'],
  ['Legal Skills', '/legal-skills'],
  ['Legal Intelligence', '/legal-intelligence'],
  ['Legal Intelligence Mediazione', '/legal-intelligence/mediazione'],
  ['Ricerca Legale', '/ricerca-legale'],
  ['Ricerca Legale Mediazione', '/ricerca-legale?q=mediazione'],
  ['Archivio Giurisprudenza', '/giurisprudenza'],
  ['Strumenti Forensi', '/strumenti-legali'],
  ['Strumenti Operativi', '/strumenti-operativi'],
  ['Sito Studio', '/sito-studio'],
  ['Sito Studio Builder', '/sito-studio/builder'],
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
  { name: 'tablet', width: 1024, height: 900, mobile: false },
  { name: 'mobile', width: 390, height: 844, mobile: true },
].filter((viewport) => {
  const filter = (process.env.IUSENTRA_AUDIT_VIEWPORTS || '').split(',').map((item) => item.trim()).filter(Boolean)
  return filter.length ? filter.includes(viewport.name) : true
})
const reuseTab = process.env.IUSENTRA_AUDIT_REUSE_TAB === '1'

function isPresetExcludedRoute(route) {
  const normalized = String(route || '').toLowerCase()
  return normalized === '/sito-studio/builder'
    || /^\/fascicoli\/(?!nuovo$|archivio$|importa$)[^/]+$/.test(normalized)
}

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
  await client.send('Network.setCacheDisabled', { cacheDisabled: true })
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

async function waitForPage(client, startedAt, route) {
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
        const visibleLoadingText = Array.from(document.querySelectorAll('main *, .iu-content *'))
          .filter(isVisible)
          .map((node) => (node.innerText || node.textContent || '').trim())
          .filter((value) => /^Caricamento/i.test(value));
        const primaryLoaders = Array.from(document.querySelectorAll('main .ius-loading-state, main .iu-share-loading, main .iu-timesheet-loading, main .iu-wiz-loading, main .iu-de-empty, main [aria-busy="true"]'))
          .filter(isVisible)
          .map((node) => (node.innerText || node.textContent || '').trim())
          .filter((value) => /Caricamento/i.test(value));
        const primaryLoading = primaryLoaders.length > 0 || visibleLoadingText.length > 0 || /^Caricamento/i.test(h1) || /^Caricamento/i.test(h2);
        const presetActive = Boolean(document.querySelector('.iusentra-route-preset--active'));
        const sequenceRoot = document.querySelector('.iu-content.iusentra-route-sequence, .iusentra-route-sequence');
        const sequenceItems = sequenceRoot
          ? Array.from(sequenceRoot.children)
              .filter((node) => node instanceof HTMLElement && isVisible(node))
              .map((node, index) => {
                const rect = node.getBoundingClientRect();
                const cssOrder = Number(window.getComputedStyle(node).order);
                return {
                  index,
                  slot: node.dataset.iusentraSequenceSlot || '',
                  order: Number.isFinite(cssOrder) ? cssOrder : 0,
                  top: Math.round(rect.top),
                  left: Math.round(rect.left),
                  text: (node.innerText || node.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 90),
                };
              })
          : [];
        const visualSlots = [...sequenceItems].sort((a, b) => a.top - b.top || a.left - b.left || a.index - b.index);
        const headerIndex = visualSlots.findIndex((item) => item.slot === 'page-header');
        const itemsBeforeHeader = headerIndex > 0 ? visualSlots.slice(0, headerIndex) : [];
        const parseRgb = (value) => {
          const match = String(value || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?/i);
          if (!match) return null;
          if (match[4] !== undefined && Number(match[4]) <= 0.05) return null;
          return [Number(match[1]), Number(match[2]), Number(match[3])];
        };
        const luminance = (rgb) => {
          if (!rgb) return null;
          const [r, g, b] = rgb.map((channel) => channel / 255);
          return Math.round((0.2126 * r + 0.7152 * g + 0.0722 * b) * 255);
        };
        const headerNode = Array.from(document.querySelectorAll('.iusentra-route-sequence > [data-iusentra-sequence-slot="page-header"]')).find(isVisible);
        const headerBackground = headerNode ? window.getComputedStyle(headerNode).backgroundColor : '';
        const headerBackgroundImage = headerNode ? window.getComputedStyle(headerNode).backgroundImage : '';
        const routeRails = Array.from(document.querySelectorAll('.iusentra-route-grid[data-iusentra-layout-has-rail="true"] > .iusentra-route-rail'))
          .filter(isVisible)
          .map((rail) => {
            const rect = rail.getBoundingClientRect();
            const style = window.getComputedStyle(rail);
            const children = Array.from(rail.children).filter((child) => child instanceof HTMLElement && isVisible(child));
            const childWidths = children.map((child) => Math.round(child.getBoundingClientRect().width));
            return {
              width: Math.round(rect.width),
              columnCount: style.gridTemplateColumns ? style.gridTemplateColumns.split(' ').filter(Boolean).length : 1,
              childMinWidth: childWidths.length ? Math.min(...childWidths) : Math.round(rect.width),
            };
          });
        const emailLayout = document.querySelector('.iu-mail-layout.iusentra-route-grid');
        const emailList = emailLayout?.querySelector('.iu-mail-list-card');
        const emailPreview = emailLayout?.querySelector('.iu-mail-preview-card');
        const emailSplit = emailLayout && emailList && emailPreview && isVisible(emailList) && isVisible(emailPreview)
          ? {
              listWidth: Math.round(emailList.getBoundingClientRect().width),
              previewWidth: Math.round(emailPreview.getBoundingClientRect().width),
              listLeft: Math.round(emailList.getBoundingClientRect().left),
              previewLeft: Math.round(emailPreview.getBoundingClientRect().left),
              listTop: Math.round(emailList.getBoundingClientRect().top),
              previewTop: Math.round(emailPreview.getBoundingClientRect().top),
            }
          : null;
        const agendaWeekNode = document.querySelector('.iu-ag-week--week');
        const agendaDays = agendaWeekNode
          ? Array.from(agendaWeekNode.querySelectorAll('.iu-ag-day')).filter((day) => day instanceof HTMLElement && isVisible(day))
          : [];
        const agendaWeekRect = agendaWeekNode ? agendaWeekNode.getBoundingClientRect() : null;
        const agendaVisibleDays = agendaWeekRect
          ? agendaDays.filter((day) => {
              const rect = day.getBoundingClientRect();
              return rect.left >= agendaWeekRect.left - 4 && rect.right <= agendaWeekRect.right + 4;
            }).length
          : 0;
        const agendaInspector = document.querySelector('.iu-ag-layout.iusentra-route-grid > .iu-ag-inspector.iusentra-route-rail');
        const agendaInspectorStyle = agendaInspector ? window.getComputedStyle(agendaInspector) : null;
        const agendaInspectorColumns = agendaInspectorStyle?.gridTemplateColumns
          ? agendaInspectorStyle.gridTemplateColumns.split(' ').filter(Boolean).length
          : null;
        const agendaWeek = agendaWeekNode && agendaWeekRect
          ? {
              days: agendaDays.length,
              visibleDays: agendaVisibleDays,
              width: Math.round(agendaWeekRect.width),
              scrollWidth: agendaWeekNode.scrollWidth,
              dayMinWidth: agendaDays.length ? Math.min(...agendaDays.map((day) => Math.round(day.getBoundingClientRect().width))) : 0,
              inspectorColumns: agendaInspectorColumns,
            }
          : null;
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
          loadingContext: [...primaryLoaders, ...visibleLoadingText].slice(0, 3),
          postForms,
          links,
          actions: document.querySelectorAll('button, main a[href], .iu-content a[href]').length,
          cards: document.querySelectorAll('.iu-card, .ius-card, .iu-action-card, .iu-metric-card, .iu-panel, [class*="card"], [class*="panel"]').length,
          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
          scrollHeight: document.documentElement.scrollHeight,
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
          styleSystem: styleLinks.some((href) => href.includes('/static/react/') || href.includes('app.css')),
          presetActive,
          sequenceRoot: Boolean(sequenceRoot),
          sequenceItems,
          sequenceUnordered: sequenceItems.filter((item) => !item.slot).length,
          sequenceHeaderFirst: headerIndex === 0,
          sequenceBeforeHeader: itemsBeforeHeader.map((item) => ({ slot: item.slot, text: item.text })),
          headerLuminance: luminance(parseRgb(headerBackground) || parseRgb(headerBackgroundImage)),
          routeRails,
          emailSplit,
          agendaWeek,
        };
      })()`,
    })
    last = result.value || {}
    const elapsed = Date.now() - startedAt
    const login = /\/login\b/.test(String(last.url || '')) || /Accesso sicuro/i.test(String(last.text || ''))
    const pageUsable = last.ready === 'complete' && !login && !last.loading && last.textLength > 280
    const sequenceReady = isPresetExcludedRoute(route)
      || (
        last.presetActive
        && last.sequenceRoot
        && (last.sequenceUnordered || 0) === 0
      )
    const usable = pageUsable && sequenceReady
    if (usable || elapsed > 18000) return { ...last, elapsedMs: elapsed, login }
    await new Promise((resolveWait) => setTimeout(resolveWait, 250))
  }
}

async function inspectScrolledPage(client, route) {
  const initial = await client.send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(() => ({
      ...(() => {
        const candidates = [
          document.scrollingElement,
          document.documentElement,
          document.body,
          document.querySelector('.iu-content'),
          document.querySelector('main'),
          document.querySelector('.ius-page-shell'),
          document.querySelector('.iusentra-page-shell__body')
        ].filter(Boolean);
        const scored = candidates.map((node) => {
          const isDocument = node === document.scrollingElement || node === document.documentElement || node === document.body;
          const scrollHeight = isDocument
            ? Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight || 0)
            : node.scrollHeight;
          const clientHeight = isDocument ? window.innerHeight : node.clientHeight;
          return { node, isDocument, scrollHeight, clientHeight, scrollable: Math.max(0, scrollHeight - clientHeight) };
        }).sort((a, b) => b.scrollable - a.scrollable);
        const best = scored[0] || { isDocument: true, scrollHeight: window.innerHeight, clientHeight: window.innerHeight, scrollable: 0 };
        if (best.node && !best.isDocument) best.node.dataset.iusentraAuditScroller = 'true';
        return {
          scrollHeight: best.scrollHeight,
          viewportHeight: best.clientHeight || window.innerHeight,
          viewportWidth: window.innerWidth,
          scrollsDocument: best.isDocument,
        };
      })()
    }))()`,
  })
  const metrics = initial.result?.value || { scrollHeight: 0, viewportHeight: 0, viewportWidth: 0 }
  const viewportHeight = Math.max(1, Number(metrics.viewportHeight || 1))
  const scrollHeight = Math.max(viewportHeight, Number(metrics.scrollHeight || viewportHeight))
  const maxY = Math.max(0, scrollHeight - viewportHeight)
  const positions = [0]
  if (maxY > 0) {
    const step = Math.max(Math.round(viewportHeight * 0.72), 320)
    for (let y = step; y < maxY; y += step) positions.push(y)
    positions.push(maxY)
  }
  const roundedPositions = [...new Set(positions.map((position) => Math.round(position)))]
  const maxSnapshots = 64
  const uniquePositions = roundedPositions.length <= maxSnapshots
    ? roundedPositions
    : [...new Set(Array.from({ length: maxSnapshots }, (_, index) => {
      if (index === 0) return 0
      if (index === maxSnapshots - 1) return Math.round(maxY)
      return Math.round((maxY * index) / (maxSnapshots - 1))
    }))]
  const snapshots = []
  for (const position of uniquePositions) {
    await client.send('Runtime.evaluate', {
      expression: `(() => {
        const scroller = document.querySelector('[data-iusentra-audit-scroller="true"]');
        if (scroller) {
          scroller.scrollTo({ top: ${position}, left: 0, behavior: 'instant' });
        } else {
          window.scrollTo({ top: ${position}, left: 0, behavior: 'instant' });
        }
      })()`,
    })
    await new Promise((resolveWait) => setTimeout(resolveWait, 140))
    const { result } = await client.send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(() => {
        const isVisible = (node) => {
          const rect = node.getBoundingClientRect();
          const style = window.getComputedStyle(node);
          return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight
            && style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
        };
        const visibleNodes = Array.from(document.querySelectorAll('main *, .iu-content *, #root *'))
          .filter((node) => node instanceof HTMLElement && isVisible(node));
        const internalScrollSelectors = [
          '.iu-mobile__rail',
          '.iu-fas-section-nav',
          '.iusentra-data-surface__scroll',
          '.iu-fas-table-wrap',
          '.iu-fas-table-card',
          '.iu-ag-date-nav',
          '.iu-ag-week',
          '.iu-builder-public-nav nav',
          '.iu-builder-browser-frame',
          '.iu-builder-preview',
          '.iu-builder-preview-frame',
          '.iu-mail-folders',
          '.iu-mail-folder-tabs',
          '.iu-mail-tag-row',
          '.iu-mail-list',
          '.iu-msg-thread-tabs',
          '.iu-search-filterbar',
          '.iu-cli-table-wrap',
          '.iu-profiles-matrix',
          '.iu-db-table-wrap',
          '.iu-settings-tabs__list',
          '.iu-li-registry-filters'
        ];
        const insideGovernedScroller = (node) => {
          const scroller = internalScrollSelectors
            .map((selector) => node.closest(selector))
            .find(Boolean);
          const candidates = scroller ? [scroller] : [];
          for (let current = node.parentElement; current && current !== document.body; current = current.parentElement) {
            candidates.push(current);
          }
          return candidates.some((candidate) => {
            const rect = candidate.getBoundingClientRect();
            const style = window.getComputedStyle(candidate);
            const clips = /auto|scroll|hidden|clip/i.test(style.overflowX + ' ' + style.overflow);
            const scrollsHorizontally = candidate.scrollWidth > candidate.clientWidth + 2;
            return clips && scrollsHorizontally && rect.left >= -4 && rect.right <= window.innerWidth + 4;
          });
        };
        const overflowNodes = visibleNodes
          .filter((node) => !insideGovernedScroller(node))
          .map((node) => {
            const rect = node.getBoundingClientRect();
            return {
              tag: node.tagName.toLowerCase(),
              className: String(node.className || '').slice(0, 90),
              text: (node.innerText || node.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
              left: Math.round(rect.left),
              right: Math.round(rect.right),
              width: Math.round(rect.width),
            };
          })
          .filter((node) => node.right > window.innerWidth + 2 || node.left < -2)
          .slice(0, 8);
        const loadingTexts = visibleNodes
          .map((node) => (node.innerText || node.textContent || '').trim().replace(/\\s+/g, ' '))
          .filter((value) => /^Caricamento/i.test(value))
          .slice(0, 5);
        const composeButtons = Array.from(document.querySelectorAll('main a, main button, .iu-content a, .iu-content button'))
          .filter((node) => node instanceof HTMLElement)
          .map((node) => {
            const rect = node.getBoundingClientRect();
            const style = window.getComputedStyle(node);
            const text = (node.innerText || node.textContent || node.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
            const visible = rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight
              && style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
            return {
              text,
              visible,
              disabled: node.hasAttribute('disabled') || node.getAttribute('aria-disabled') === 'true',
              top: Math.round(rect.top),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
            };
          })
          .filter((node) => /Componi/i.test(node.text));
        const actionNodes = Array.from(document.querySelectorAll('main a[href], main button, .iu-content a[href], .iu-content button'))
          .filter((node) => node instanceof HTMLElement && isVisible(node))
          .filter((node) => !node.closest('nav') && !node.closest('[aria-hidden="true"]'))
          .filter((node) => !node.closest('.iu-builder-resize-handle') && !node.classList.contains('iu-builder-resize-handle'));
        const actionIssues = actionNodes
          .map((node) => {
            const rect = node.getBoundingClientRect();
            const style = window.getComputedStyle(node);
            const visibleText = (node.innerText || node.textContent || '').trim().replace(/\\s+/g, ' ');
            const accessibleName = (node.getAttribute('aria-label') || node.getAttribute('title') || '').trim().replace(/\\s+/g, ' ');
            const text = visibleText || accessibleName;
            const href = node.getAttribute('href') || '';
            const icon = Boolean(node.querySelector('svg, i, [class*="icon"], [data-lucide], .bi'));
            const textNode = Array.from(node.childNodes).some((child) => child.nodeType === Node.TEXT_NODE && child.textContent && child.textContent.trim());
            const hasVisibleText = visibleText.length > 0;
            const hasAccessibleName = accessibleName.length > 0;
            const children = Array.from(node.children).filter((child) => child instanceof HTMLElement && isVisible(child));
            const childOutside = children.some((child) => {
              const childRect = child.getBoundingClientRect();
              return childRect.left < rect.left - 2 || childRect.right > rect.right + 2 || childRect.top < rect.top - 2 || childRect.bottom > rect.bottom + 2;
            });
            const textClipped = node.scrollWidth > node.clientWidth + 2 || node.scrollHeight > node.clientHeight + 2;
            const tooSmall = hasVisibleText && (rect.height < 32 || rect.width < 42);
            const targetMissing = node.tagName.toLowerCase() === 'a' && (!href || href === '#' || /^javascript:/i.test(href));
            const recoveryMarked = node.dataset.iusentraSecondaryAction === 'recovery'
              || Boolean(node.closest('[data-iusentra-secondary-action="recovery"]'));
            const recoveryPath = recoveryMarked || (
              /Percorso di recupero/i.test(text)
              && !node.closest('[data-iusentra-sequence-slot="page-header"]')
            );
            const technicalFallback = /_legacy=1|legacy|debug|payload|backend|frontend|json_api/i.test(href + ' ' + text) && !recoveryPath;
            const textIconRisk = icon && hasVisibleText && (textClipped || childOutside || tooSmall);
            const emptyVisibleAction = !hasVisibleText && !icon && !hasAccessibleName;
            const issueNames = [];
            if (textIconRisk) issueNames.push('testo_icona_non_contenuti');
            if (textClipped) issueNames.push('testo_tagliato');
            if (childOutside) issueNames.push('icona_fuori_bottone');
            if (tooSmall) issueNames.push('dimensione_insufficiente');
            if (targetMissing) issueNames.push('destinazione_secondaria_mancante');
            if (technicalFallback) issueNames.push('azione_secondaria_tecnica');
            if (emptyVisibleAction) issueNames.push('azione_senza_nome');
          return {
            text: text.slice(0, 80),
            href: href.slice(0, 160),
            tag: node.tagName.toLowerCase(),
            className: String(node.className || '').slice(0, 90),
            secondaryAction: node.dataset.iusentraSecondaryAction || node.closest('[data-iusentra-secondary-action]')?.dataset?.iusentraSecondaryAction || '',
            icon,
            textNode,
            x: Math.round(rect.left),
              y: Math.round(rect.top + window.scrollY),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
              clientWidth: node.clientWidth,
              scrollWidth: node.scrollWidth,
              clientHeight: node.clientHeight,
              scrollHeight: node.scrollHeight,
              issues: issueNames,
            };
          })
          .filter((item) => item.issues.length)
          .slice(0, 12);
        const visibleLandmarks = Array.from(document.querySelectorAll('main h1, main h2, main h3, main button, main a[href], .iu-content h1, .iu-content h2, .iu-content h3, .iu-content button, .iu-content a[href]'))
          .filter((node) => node instanceof HTMLElement && isVisible(node))
          .map((node) => (node.innerText || node.textContent || node.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' '))
          .filter(Boolean)
          .slice(0, 10);
        return {
          ...(() => {
            const scroller = document.querySelector('[data-iusentra-audit-scroller="true"]');
            const y = scroller ? scroller.scrollTop : window.scrollY;
            const height = scroller ? scroller.clientHeight : window.innerHeight;
            return {
              y: Math.round(y),
              viewportBottom: Math.round(y + height),
            };
          })(),
          documentWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
          overflowNodes,
          loadingTexts,
          composeButtons,
          actionIssues,
          visibleLandmarks,
        };
      })()`,
    })
    snapshots.push(result.value || { y: position })
  }
  await client.send('Runtime.evaluate', { expression: 'window.scrollTo({ top: 0, left: 0, behavior: "instant" })' })
  return {
    checked: true,
    positions: uniquePositions,
    stepCount: snapshots.length,
    scrollHeight,
    viewportHeight,
    maxY,
    snapshots,
    bottomReached: snapshots.some((item) => Number(item.viewportBottom || 0) >= scrollHeight - Math.max(4, Math.min(120, viewportHeight * 0.12))),
    overflow: snapshots.flatMap((item) => item.overflowNodes || []),
    loadingTexts: [...new Set(snapshots.flatMap((item) => item.loadingTexts || []))],
    composeButtons: snapshots.flatMap((item) => item.composeButtons || []),
    actionIssues: snapshots.flatMap((item) => item.actionIssues || []),
    visibleLandmarks: snapshots.map((item) => ({ y: item.y, items: item.visibleLandmarks || [] })),
    expectedCompose: /^\/email(?:-ordinaria)?\/?$/i.test(route),
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
  const data = await waitForPage(client, startedAt, route)
  const scrollAudit = await inspectScrolledPage(client, route)
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
  const consoleEntries = client.events
    .filter((event) => event.method === 'Runtime.consoleAPICalled' || event.method === 'Log.entryAdded')
    .map((event) => event.params?.entry?.text || event.params?.args?.map((arg) => arg.value || arg.description).join(' ') || '')
    .filter(Boolean)
  const expectedMissingFascicolo = /^\/fascicoli\/(?!nuovo$|archivio$|importa$)[^/]+$/i.test(route)
    && /Fascicolo non trovato/i.test(String(data.h1 || data.h2 || data.text || ''))
  const expectedMissingConferimento = /^\/preventivi\/conferimento\/(?!nuovo$)[^/]+$/i.test(route)
    && (
      /Conferimento (?:non disponibile|non trovato)|Dati non disponibili/i.test(String(data.h1 || data.h2 || data.text || ''))
      || data.textLength < 1200
    )
  const relevantConsoleErrors = consoleEntries.filter((line) => {
    const looksLikeError = /\berror\b|uncaught|failed/i.test(line)
    if (!looksLikeError) return false
    if (/ERR_NO_BUFFER_SPACE/i.test(line)) return false
    if (expectedMissingFascicolo && /404|not found|failed to load resource/i.test(line)) return false
    if (expectedMissingConferimento && /404|not found|failed to load resource/i.test(line)) return false
    return true
  })
  const failures = []
  const isBuilderPresetException = route === '/sito-studio/builder'
  if (data.login) failures.push('redirect_login')
  if (!data.hasRoot || !data.hasShell) failures.push('react_shell_assente')
  if (data.loading) failures.push('caricamento_non_chiuso')
  if (data.textLength < 280) failures.push('contenuto_vuoto')
  if (data.postForms?.length) failures.push('form_post_html')
  if (hits.length) failures.push('testo_tecnico_visibile')
  if (!isBuilderPresetException && data.horizontalOverflow && scrollAudit.overflow.length) failures.push('overflow_orizzontale')
  if (scrollAudit.scrollHeight > scrollAudit.viewportHeight + 20 && scrollAudit.stepCount < 2) failures.push('scroll_non_verificato')
  if (scrollAudit.scrollHeight > scrollAudit.viewportHeight + 20 && !scrollAudit.bottomReached) failures.push('scroll_fondo_non_raggiunto')
  if (!isBuilderPresetException && scrollAudit.overflow.length) failures.push('overflow_orizzontale_scroll')
  if (scrollAudit.loadingTexts.length) failures.push('caricamento_visibile_durante_scroll')
  if (scrollAudit.expectedCompose && !scrollAudit.composeButtons.some((button) => button.visible)) failures.push('componi_email_non_visibile')
  if (!isBuilderPresetException && scrollAudit.actionIssues.some((issue) => issue.issues?.some((name) => [
    'testo_icona_non_contenuti',
    'testo_tagliato',
    'icona_fuori_bottone',
    'dimensione_insufficiente',
  ].includes(name)))) failures.push('bottoni_testo_icona_non_contenuti')
  if (!isBuilderPresetException && scrollAudit.actionIssues.some((issue) => issue.issues?.some((name) => [
    'destinazione_secondaria_mancante',
    'azione_secondaria_tecnica',
    'azione_senza_nome',
  ].includes(name)))) failures.push('procedure_secondarie_non_governate')
  if (relevantConsoleErrors.length) failures.push('console_error')
  if (isPresetExcludedRoute(route)) {
    if (data.presetActive) {
      failures.push(route === '/sito-studio/builder' ? 'builder_preset_attivo' : 'dettaglio_fascicolo_preset_attivo')
    }
  } else {
    if (!data.presetActive) failures.push('preset_globale_assente')
    if (!data.sequenceRoot) failures.push('sequenza_preset_assente')
    if (data.sequenceUnordered > 0) failures.push('sequenza_blocchi_senza_slot')
    if (data.sequenceRoot && data.sequenceItems?.some((item) => item.slot === 'page-header') && !data.sequenceHeaderFirst) {
      failures.push('sequenza_header_non_primo')
    }
    if ((data.routeRails || []).some((rail) => rail.width <= 520 && (rail.columnCount > 1 || rail.childMinWidth < 220))) {
      failures.push('support_rail_card_troppo_stretta')
    }
    if (route === '/agenda' && viewport.name === 'desktop' && data.agendaWeek?.days >= 7 && data.agendaWeek.visibleDays < 7) {
      failures.push('agenda_settimana_incompleta')
    }
    if (route === '/agenda' && viewport.name === 'desktop' && data.agendaWeek?.inspectorColumns && data.agendaWeek.inspectorColumns > 1) {
      failures.push('agenda_supporto_non_verticale')
    }
    const emailSideBySide = data.emailSplit
      && Math.abs(data.emailSplit.previewTop - data.emailSplit.listTop) <= 32
      && data.emailSplit.previewLeft > data.emailSplit.listLeft
    if (emailSideBySide && viewport.name !== 'mobile' && data.emailSplit.previewWidth <= data.emailSplit.listWidth + 120) {
      failures.push('email_preview_troppo_stretta')
    }
    if (viewport.name === 'desktop' && typeof data.headerLuminance === 'number' && data.headerLuminance < 170) {
      failures.push('header_preset_scuro')
    }
  }
  let screenshotName = ''
  let screenshotWarning = ''
  const shouldCaptureScreenshot = screenshotMode === 'all' || (screenshotMode === 'failures' && failures.length > 0)
  if (shouldCaptureScreenshot) {
    screenshotName = `${viewport.name}-load-${routeName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}.png`
    try {
      const captureOptions = fullPageScreenshots
        ? { format: 'png', fromSurface: true, captureBeyondViewport: true }
        : { format: 'png', fromSurface: true }
      const screenshot = await client.send('Page.captureScreenshot', captureOptions)
      writeFileSync(resolve(outDir, screenshotName), Buffer.from(screenshot.data, 'base64'))
    } catch (error) {
      screenshotName = ''
      screenshotWarning = `screenshot_non_acquisito: ${String(error?.message || error)}`
    }
  }
  const warnings = []
  if (screenshotWarning) warnings.push(screenshotWarning)
  if (expectedMissingFascicolo) warnings.push('fascicolo_non_trovato_locale')
  if ((data.links?.length || 0) < 2 && (data.actions || 0) < 3 && route !== '/') warnings.push('collegamenti_o_azioni_da_arricchire')
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
    presetActive: data.presetActive,
    sequenceRoot: data.sequenceRoot,
    sequenceItems: data.sequenceItems || [],
    sequenceUnordered: data.sequenceUnordered,
    sequenceHeaderFirst: data.sequenceHeaderFirst,
    sequenceBeforeHeader: data.sequenceBeforeHeader || [],
    headerLuminance: data.headerLuminance,
    routeRails: data.routeRails || [],
    emailSplit: data.emailSplit || null,
    agendaWeek: data.agendaWeek || null,
    scrollAudit,
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
  screenshotMode,
  fullPageScreenshots,
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
