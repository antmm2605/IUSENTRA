import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const reportDir = resolve(root, 'artifacts/react-migration')
mkdirSync(reportDir, { recursive: true })

function read(path) {
  return readFileSync(resolve(root, path), 'utf8')
}

function extractPythonStrings(source, name, opener, closer) {
  const pattern = new RegExp(`${name}\\s*=\\s*\\${opener}([^]*?)\\${closer}`, 'm')
  const match = source.match(pattern)
  if (!match) return []
  return [...match[1].matchAll(/["']([^"']+)["']/g)].map((item) => item[1])
}

function extractTuple(source, name) {
  return extractPythonStrings(source, name, '(', ')')
}

function extractSet(source, name) {
  return extractPythonStrings(source, name, '{', '}')
}

function normaliseRoute(route) {
  const raw = String(route || '/').split('?')[0]
  const pathOnly = raw.endsWith('/*') ? `${raw.slice(0, -1)}__wildcard__` : raw.replace(/\*$/, '')
  const clean = pathOnly.replace(/\/+$/, '') || '/'
  return clean.toLowerCase()
}

function isPrefixMatch(path, prefix) {
  const cleanPrefix = normaliseRoute(prefix)
  if (cleanPrefix === '/') return path === '/'
  return path === cleanPrefix || path.startsWith(`${cleanPrefix}/`)
}

function isReactRoute(path, reactExact, reactPrefixes) {
  if (reactExact.has(path)) return true
  return reactPrefixes.some((prefix) => isPrefixMatch(path, prefix))
}

function isBlockedBySpecialRule(path) {
  const isConferimentoDetail = path.startsWith('/preventivi/conferimento/') && path.split('/').length === 4
  return (
    path.startsWith('/backup/') ||
    (path.startsWith('/sito-studio/') && !['/sito-studio/contatti', '/sito-studio/builder', '/sito-studio/redazione-ai'].includes(path)) ||
    path.startsWith('/studio/') ||
    path.startsWith('/amministrazione/') ||
    (path.startsWith('/fatturazione/') && path !== '/fatturazione/nuova') ||
    path.startsWith('/incassi-pagamenti/') ||
    path.startsWith('/impostazioni/pagamenti/') ||
    path.startsWith('/impostazioni/calendario/') ||
    path.startsWith('/sincronizzazione-calendari/') ||
    (path.startsWith('/preventivi/') && path !== '/preventivi/nuovo' && path !== '/preventivi/wizard' && path !== '/preventivi/conferimento/nuovo' && !isConferimentoDetail) ||
    path.startsWith('/compensi-forensi/') ||
    path.startsWith('/tariffario/') ||
    path === '/template-atti/nuovo' ||
    (path.startsWith('/template-atti/') && path !== '/template-atti/catalogo') ||
    path.startsWith('/redazione-atti/') ||
    path === '/checklist' ||
    path.startsWith('/checklist/') ||
    path.startsWith('/deposito/checklist/') ||
    path.startsWith('/giurisprudenza/') ||
    (path.startsWith('/legal-intelligence/') && path !== '/legal-intelligence/news' && path !== '/legal-intelligence/mediazione') ||
    path.startsWith('/ricerca-legale/')
  )
}

const gate = read('web/bootstrap/react_route_gate.py')
const reactShell = read('web/blueprints/react_shell.py')
const checkReactContracts = read('frontend/scripts/check-react-contracts.mjs')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))

const reactPrefixes = extractTuple(gate, '_REACT_PREFIXES')
const reactExact = new Set(extractSet(gate, '_REACT_EXACT').map(normaliseRoute))
const legacyOperationalPrefixes = extractTuple(gate, '_LEGACY_OPERATIONAL_PREFIXES')
const excludedPrefixes = extractTuple(gate, '_EXCLUDED_PREFIXES')
const shellLegacyFirstPrefixes = extractTuple(reactShell, '_LEGACY_FIRST_PREFIXES')
const allowedStatuses = new Set(['legacy_operational', 'react_shell', 'react_bridge', 'react_operational_partial', 'react_operational_full'])
const allowedUnlockStatuses = new Set(['react_bridge', 'react_operational_partial', 'react_operational_full'])
const allowedReactUnlocks = new Set(['/', '/admin/database', '/agenda', '/agenda/nuovo', '/amministrazione', '/audit', '/backup', '/cartelle-condivise', '/clienti', '/clienti/nuovo', '/compensi-forensi', '/deposito/checklist', '/documenti', '/email', '/email-ordinaria', '/notifiche-legali', '/fascicoli', '/fascicoli/archivio', '/fascicoli/nuovo', '/fatturazione', '/fatturazione/nuova', '/giurisprudenza', '/global-search', '/impostazioni', '/impostazioni-studio', '/impostazioni/calendario', '/impostazioni/pagamenti', '/incassi-pagamenti', '/legal-intelligence', '/legal-intelligence/mediazione', '/legal-intelligence/news', '/messaggi', '/messaggi/nuovo', '/notifiche', '/notifiche-whatsapp', '/preventivi', '/preventivi/conferimento/:id', '/preventivi/conferimento/nuovo', '/preventivi/nuovo', '/preventivi/wizard', '/privacy/registro', '/privacy/registro/nuovo', '/profili', '/redazione-atti', '/regia-operativa', '/registro-attivita', '/registro-gdpr', '/ricerca-legale', '/ricerca-studio', '/scadenziario', '/scadenziario/nuova', '/scadenziario/:id', '/scadenziario/:id/modifica', '/sincronizzazione-calendari', '/sito-studio', '/sito-studio/builder', '/sito-studio/contatti', '/sito-studio/redazione-ai', '/soggetti', '/soggetti/nuovo', '/statistiche', '/strumenti-legali', '/strumenti-operativi', '/studio', '/tariffario', '/template-atti', '/template-atti/catalogo', '/timesheet', '/utenti', '/utenti/nuovo', '/wizard-pro', '/workspace-intelligente'])
const expectedStatuses = new Map([
  ['/', 'react_operational_full'],
  ['/admin/database', 'react_operational_full'],
  ['/agenda', 'react_operational_full'],
  ['/agenda/nuovo', 'react_operational_full'],
  ['/amministrazione', 'react_operational_full'],
  ['/audit', 'react_operational_full'],
  ['/backup', 'react_operational_full'],
  ['/cartelle-condivise', 'react_operational_full'],
  ['/clienti', 'react_operational_full'],
  ['/clienti/nuovo', 'react_operational_full'],
  ['/compensi-forensi', 'react_operational_full'],
  ['/deposito/checklist', 'react_operational_full'],
  ['/documenti', 'react_operational_full'],
  ['/email', 'react_operational_full'],
  ['/email-ordinaria', 'react_operational_full'],
  ['/notifiche-legali', 'react_operational_full'],
  ['/fascicoli', 'react_operational_full'],
  ['/fascicoli/archivio', 'react_operational_full'],
  ['/fascicoli/nuovo', 'react_operational_full'],
  ['/fatturazione', 'react_operational_full'],
  ['/fatturazione/nuova', 'react_operational_full'],
  ['/giurisprudenza', 'react_operational_full'],
  ['/global-search', 'react_operational_full'],
  ['/impostazioni', 'react_operational_full'],
  ['/impostazioni-studio', 'react_operational_full'],
  ['/impostazioni/calendario', 'react_operational_full'],
  ['/impostazioni/pagamenti', 'react_operational_full'],
  ['/incassi-pagamenti', 'react_operational_full'],
  ['/legal-intelligence', 'react_operational_full'],
  ['/legal-intelligence/mediazione', 'react_operational_full'],
  ['/legal-intelligence/news', 'react_operational_full'],
  ['/messaggi', 'react_operational_full'],
  ['/messaggi/nuovo', 'react_operational_full'],
  ['/notifiche', 'react_operational_full'],
  ['/notifiche-whatsapp', 'react_operational_full'],
  ['/preventivi', 'react_operational_full'],
  ['/preventivi/conferimento/:id', 'react_operational_full'],
  ['/preventivi/conferimento/nuovo', 'react_operational_full'],
  ['/preventivi/nuovo', 'react_operational_full'],
  ['/preventivi/wizard', 'react_operational_partial'],
  ['/privacy/registro', 'react_operational_full'],
  ['/privacy/registro/nuovo', 'react_operational_full'],
  ['/profili', 'react_operational_full'],
  ['/redazione-atti', 'react_operational_full'],
  ['/regia-operativa', 'react_operational_full'],
  ['/registro-attivita', 'react_operational_full'],
  ['/registro-gdpr', 'react_operational_full'],
  ['/ricerca-legale', 'react_operational_full'],
  ['/ricerca-studio', 'react_operational_full'],
  ['/scadenziario', 'react_operational_full'],
  ['/scadenziario/nuova', 'react_operational_full'],
  ['/scadenziario/:id', 'react_operational_full'],
  ['/scadenziario/:id/modifica', 'react_operational_partial'],
  ['/sincronizzazione-calendari', 'react_operational_full'],
  ['/sito-studio', 'react_operational_full'],
  ['/sito-studio/builder', 'react_operational_full'],
  ['/sito-studio/contatti', 'react_operational_full'],
  ['/sito-studio/redazione-ai', 'react_operational_partial'],
  ['/soggetti', 'react_operational_full'],
  ['/soggetti/nuovo', 'react_operational_full'],
  ['/statistiche', 'react_operational_full'],
  ['/strumenti-legali', 'react_operational_full'],
  ['/strumenti-operativi', 'react_operational_full'],
  ['/studio', 'react_operational_full'],
  ['/tariffario', 'react_operational_full'],
  ['/template-atti', 'react_operational_full'],
  ['/template-atti/catalogo', 'react_operational_full'],
  ['/timesheet', 'react_operational_full'],
  ['/utenti', 'react_operational_full'],
  ['/utenti/nuovo', 'react_operational_full'],
  ['/wizard-pro', 'react_operational_full'],
  ['/workspace-intelligente', 'react_operational_full'],
])

const legacyRoutes = [
  '/fatturazione/*',
  '/preventivi/*',
  '/compensi-forensi/*',
  '/tariffario/*',
  '/template-atti/nuovo',
  '/template-atti/*',
  '/redazione-atti/*',
  '/checklist',
  '/giurisprudenza/nuova',
  '/giurisprudenza/*',
  '/legal-intelligence/*',
  '/ricerca-legale/*',
]

const violations = []
for (const entry of manifest.routes ?? []) {
  const route = normaliseRoute(entry.route)
  const routeIsReact = isReactRoute(route, reactExact, reactPrefixes)
  const blocked = isBlockedBySpecialRule(route) || legacyOperationalPrefixes.some((prefix) => isPrefixMatch(route, prefix)) || excludedPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const blockedByShell = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))

  if (!allowedStatuses.has(entry.status)) {
    violations.push(`${entry.route}: status non ammesso (${entry.status})`)
  }
  if (entry.status === 'react_full') {
    violations.push(`${entry.route}: react_full e' deprecato, usare gli status operativi Parte 12A`)
  }
  if (entry.unlockFromGate === true) {
    if (!allowedReactUnlocks.has(route)) {
      violations.push(`${entry.route}: unlockFromGate=true non consentito nelle tranche governate`)
    }
    if (!allowedUnlockStatuses.has(entry.status)) {
      violations.push(`${entry.route}: unlockFromGate=true richiede status react_bridge/react_operational_partial/react_operational_full`)
    }
    if (!routeIsReact) {
      violations.push(`${entry.route}: unlockFromGate=true ma la route non e' in _REACT_PREFIXES/_REACT_EXACT`)
    }
    if (blocked) {
      violations.push(`${entry.route}: unlockFromGate=true ma resta in _LEGACY_OPERATIONAL_PREFIXES o esclusioni`)
    }
    if (blockedByShell) {
      violations.push(`${entry.route}: unlockFromGate=true ma resta in _LEGACY_FIRST_PREFIXES`)
    }
    for (const field of ['targetComponent', 'targetData', 'targetBridge', 'legacyContract']) {
      const value = entry[field]
      if (!value || !existsSync(resolve(root, value))) {
        violations.push(`${entry.route}: manca ${field} (${value || 'non indicato'})`)
      }
    }
    if (!checkReactContracts.includes(entry.route)) {
      violations.push(`${entry.route}: non citata in frontend/scripts/check-react-contracts.mjs`)
    }
  }
}

for (const [route, status] of expectedStatuses) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== status || entry.unlockFromGate !== true) {
    violations.push(`${route}: deve essere ${status} con unlockFromGate=true`)
  }
}

for (const route of legacyRoutes) {
  const entry = (manifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    violations.push(`${route}: deve restare legacy_operational con unlockFromGate=false`)
  }
}

for (const snippet of [
  'lower.startswith("/backup/")',
  '_SITO_STUDIO_REACT_SUBPATHS',
  '"/sito-studio/builder"',
  '"/sito-studio/redazione-ai"',
  'lower.startswith("/studio/")',
  'lower.startswith("/amministrazione/")',
  'lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova"',
  'lower.startswith("/incassi-pagamenti/")',
  'lower.startswith("/impostazioni/pagamenti/")',
  'lower.startswith("/impostazioni/calendario/")',
  'lower.startswith("/sincronizzazione-calendari/")',
  'lower.startswith("/preventivi/") and lower not in {',
  '"/preventivi/nuovo",',
  '"/preventivi/wizard",',
  '"/preventivi/conferimento/nuovo",',
  'lower.startswith("/compensi-forensi/")',
  'lower.startswith("/tariffario/")',
  'lower == "/template-atti/nuovo"',
  'lower.startswith("/template-atti/") and lower != "/template-atti/catalogo"',
  'lower.startswith("/redazione-atti/")',
  'lower == "/checklist" or lower.startswith("/checklist/")',
  'lower.startswith("/deposito/checklist/")',
  'lower.startswith("/giurisprudenza/")',
  'lower.startswith("/legal-intelligence/") and lower not in {',
  '"/legal-intelligence/news",',
  '"/legal-intelligence/mediazione",',
  'lower.startswith("/ricerca-legale/")',
]) {
  if (!gate.includes(snippet)) {
    violations.push(`react_route_gate.py: manca protezione ${snippet}`)
  }
  if (!reactShell.includes(snippet)) {
    violations.push(`react_shell.py: manca protezione ${snippet}`)
  }
}

const unlocked = (manifest.routes ?? []).filter((entry) => entry.unlockFromGate === true)
const report = [
  '# Route gate report',
  '',
  `Route nel manifest: ${(manifest.routes ?? []).length}`,
  `Route con unlockFromGate=true: ${unlocked.length}`,
  `Route governate consentite: ${[...allowedReactUnlocks].join(', ')}`,
  'Tranche 4A: route studio/backup censite come bridge se conservano scritture legacy.',
  'Tranche 5A: studio e amministrazione restano bridge quando sono hub di navigazione.',
  'Tranche 6A: fatturazione e incassi restano bridge se le scritture principali sono legacy.',
  'Tranche 7A: preventivi non wizard restano bridge finche i POST principali sono legacy.',
  'Tranche 8A: compensi/tariffario declassati quando mantengono fallback o bridge legacy.',
  'Tranche 9A: template atti/redazione exact restano bridge finche le azioni principali sono legacy.',
  'Tranche 10A: giurisprudenza/legal intelligence declassate se non hanno workflow React operativo pieno.',
  'Parte 12A: react_full deprecato; unlockFromGate=true richiede status react_bridge/react_operational_partial/react_operational_full.',
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
].join('\n').trimEnd() + '\n'

writeFileSync(resolve(reportDir, 'route-gate.md'), report)

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Route gate OK: Parte 12A coerente.')
