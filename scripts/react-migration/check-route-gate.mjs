import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
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

function isBlockedByGate(path, legacyPrefixes, excludedPrefixes) {
  return (
    isBlockedBySpecialRule(path) ||
    legacyPrefixes.some((prefix) => isPrefixMatch(path, prefix)) ||
    excludedPrefixes.some((prefix) => isPrefixMatch(path, prefix))
  )
}

function isBlockedBySpecialRule(path) {
  return (
    path.startsWith('/backup/') ||
    (path.startsWith('/sito-studio/') && path !== '/sito-studio/contatti') ||
    path.startsWith('/studio/') ||
    path.startsWith('/amministrazione/') ||
    (path.startsWith('/fatturazione/') && path !== '/fatturazione/nuova') ||
    path.startsWith('/incassi-pagamenti/') ||
    path === '/impostazioni/pagamenti' ||
    path.startsWith('/impostazioni/pagamenti/') ||
    path === '/impostazioni' ||
    path.startsWith('/impostazioni/') ||
    path === '/impostazioni-studio' ||
    path.startsWith('/impostazioni-studio/') ||
    path === '/sincronizzazione-calendari' ||
    path.startsWith('/sincronizzazione-calendari/') ||
    (path.startsWith('/preventivi/') && path !== '/preventivi/nuovo' && path !== '/preventivi/conferimento/nuovo') ||
    path.startsWith('/compensi-forensi/') ||
    path.startsWith('/tariffario/') ||
    path === '/template-atti/nuovo' ||
    (path.startsWith('/template-atti/') && path !== '/template-atti/catalogo') ||
    path.startsWith('/redazione-atti/') ||
    path === '/checklist' ||
    path.startsWith('/checklist/') ||
    path === '/deposito/checklist' ||
    path.startsWith('/deposito/checklist/') ||
    path === '/giurisprudenza' ||
    path.startsWith('/giurisprudenza/') ||
    path === '/legal-intelligence' ||
    path.startsWith('/legal-intelligence/') ||
    path === '/ricerca-legale' ||
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
const allowedReactUnlocks = new Set(['/statistiche', '/audit', '/registro-attivita', '/utenti', '/profili', '/backup', '/sito-studio', '/sito-studio/contatti', '/studio', '/amministrazione', '/fatturazione', '/fatturazione/nuova', '/incassi-pagamenti', '/preventivi', '/preventivi/nuovo', '/preventivi/conferimento/nuovo', '/compensi-forensi', '/tariffario', '/template-atti', '/template-atti/catalogo', '/redazione-atti'])

const violations = []
for (const entry of manifest.routes ?? []) {
  const route = normaliseRoute(entry.route)
  const routeIsReact = isReactRoute(route, reactExact, reactPrefixes)
  const blocked = isBlockedByGate(route, legacyOperationalPrefixes, excludedPrefixes)
  const blockedByShell = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const unlockedByGate = routeIsReact && !blocked
  const unlockedByShell = unlockedByGate && !blockedByShell

  if (unlockedByShell && entry.status !== 'react_full') {
    violations.push(`${entry.route}: risulta servibile dal gate ma status=${entry.status}`)
  }

  if (entry.unlockFromGate === true) {
    if (!allowedReactUnlocks.has(route)) {
      violations.push(`${entry.route}: unlockFromGate=true non consentito nelle tranche governate`)
    }
    if (entry.status !== 'react_full') {
      violations.push(`${entry.route}: unlockFromGate=true richiede status react_full`)
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

const unlocked = (manifest.routes ?? []).filter((entry) => entry.unlockFromGate === true)
for (const route of ['/backup', '/sito-studio', '/sito-studio/contatti']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    violations.push(`${route}: deve essere react_full con unlockFromGate=true nella Tranche 4A`)
  }
  const stillBlocked = legacyOperationalPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const stillShellBlocked = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  if (stillBlocked || stillShellBlocked) {
    violations.push(`${route}: non deve restare bloccata da gate o shell legacy`)
  }
}

for (const route of ['/utenti', '/profili']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    violations.push(`${route}: deve essere react_full con unlockFromGate=true nella Tranche 3A`)
  }
  const stillBlocked = legacyOperationalPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const stillShellBlocked = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  if (stillBlocked || stillShellBlocked) {
    violations.push(`${route}: non deve restare bloccata da gate o shell legacy`)
  }
}

for (const route of ['/impostazioni', '/impostazioni-studio', '/impostazioni/calendario', '/impostazioni/pagamenti', '/sincronizzazione-calendari', '/sito-studio/builder']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    violations.push(`${route}: deve restare legacy_operational con unlockFromGate=false`)
  }
}

for (const route of ['/studio', '/amministrazione']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    violations.push(`${route}: deve essere react_full con unlockFromGate=true nella Tranche 5A`)
  }
  const stillBlocked = legacyOperationalPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const stillShellBlocked = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  if (stillBlocked || stillShellBlocked) {
    violations.push(`${route}: non deve restare bloccata da gate o shell legacy`)
  }
}

for (const route of ['/fatturazione', '/fatturazione/nuova', '/incassi-pagamenti']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    violations.push(`${route}: deve essere react_full con unlockFromGate=true nella Tranche 6A`)
  }
  const stillBlocked = legacyOperationalPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const stillShellBlocked = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  if (stillBlocked || stillShellBlocked) {
    violations.push(`${route}: non deve restare bloccata da gate o shell legacy`)
  }
}

for (const route of ['/preventivi', '/preventivi/nuovo', '/preventivi/conferimento/nuovo']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    violations.push(`${route}: deve essere react_full con unlockFromGate=true nella Tranche 7A`)
  }
  const stillBlocked = legacyOperationalPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const stillShellBlocked = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  if (stillBlocked || stillShellBlocked) {
    violations.push(`${route}: non deve restare bloccata da gate o shell legacy`)
  }
}

for (const route of ['/template-atti', '/template-atti/catalogo', '/redazione-atti']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    violations.push(`${route}: deve essere react_full con unlockFromGate=true nella Tranche 9A`)
  }
  const stillBlocked = legacyOperationalPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  const stillShellBlocked = isBlockedBySpecialRule(route) || shellLegacyFirstPrefixes.some((prefix) => isPrefixMatch(route, prefix))
  if (stillBlocked || stillShellBlocked) {
    violations.push(`${route}: non deve restare bloccata da gate o shell legacy`)
  }
}

for (const route of ['/fatturazione/*', '/impostazioni/pagamenti', '/preventivi/*', '/preventivi/wizard', '/compensi-forensi/*', '/tariffario/*', '/template-atti/nuovo', '/template-atti/*', '/redazione-atti/*', '/checklist', '/giurisprudenza', '/legal-intelligence', '/deposito/checklist']) {
  const entry = (manifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    violations.push(`${route}: deve restare legacy_operational con unlockFromGate=false nelle tranche governate`)
  }
}

for (const snippet of [
  'lower.startswith("/backup/")',
  'lower.startswith("/sito-studio/") and lower not in {"/sito-studio/contatti"}',
  'lower.startswith("/studio/")',
  'lower.startswith("/amministrazione/")',
  'lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova"',
  'lower.startswith("/incassi-pagamenti/")',
  'lower == "/impostazioni/pagamenti" or lower.startswith("/impostazioni/pagamenti/")',
  'lower == "/impostazioni" or lower.startswith("/impostazioni/")',
  'lower == "/impostazioni-studio" or lower.startswith("/impostazioni-studio/")',
  'lower == "/sincronizzazione-calendari" or lower.startswith("/sincronizzazione-calendari/")',
  'lower.startswith("/preventivi/") and lower not in {',
  '"/preventivi/nuovo",',
  '"/preventivi/conferimento/nuovo",',
  'lower.startswith("/compensi-forensi/")',
  'lower.startswith("/tariffario/")',
  'lower == "/template-atti/nuovo"',
  'lower.startswith("/template-atti/") and lower != "/template-atti/catalogo"',
  'lower.startswith("/redazione-atti/")',
  'lower == "/checklist" or lower.startswith("/checklist/")',
  'lower == "/deposito/checklist" or lower.startswith("/deposito/checklist/")',
  'lower == "/giurisprudenza" or lower.startswith("/giurisprudenza/")',
  'lower == "/legal-intelligence" or lower.startswith("/legal-intelligence/")',
  'lower == "/ricerca-legale" or lower.startswith("/ricerca-legale/")',
]) {
  if (!gate.includes(snippet)) {
    violations.push(`react_route_gate.py: manca protezione ${snippet}`)
  }
  if (!reactShell.includes(snippet)) {
    violations.push(`react_shell.py: manca protezione ${snippet}`)
  }
}

const report = [
  '# Route gate report',
  '',
  `Route nel manifest: ${(manifest.routes ?? []).length}`,
  `Route con unlockFromGate=true: ${unlocked.length}`,
  `Route governate consentite: ${[...allowedReactUnlocks].join(', ')}`,
  'Tranche 8A: promozione compensi/tariffario exact, sottopercorsi sensibili legacy.',
  'Tranche 9A: promozione template atti/redazione exact, sottopercorsi documentali sensibili legacy.',
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
].join('\n').trimEnd() + '\n'

writeFileSync(resolve(reportDir, 'route-gate.md'), report)

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Route gate OK: Tranche 9A coerente.')
