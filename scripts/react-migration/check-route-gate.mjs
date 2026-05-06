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
  const pathOnly = String(route || '/').split('?')[0].replace(/\*$/, '')
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
    path === '/studio' ||
    path.startsWith('/studio/') ||
    path === '/impostazioni' ||
    path.startsWith('/impostazioni/')
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
const allowedReactUnlocks = new Set(['/statistiche', '/audit', '/registro-attivita', '/utenti', '/profili', '/backup', '/sito-studio', '/sito-studio/contatti'])

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
      violations.push(`${entry.route}: unlockFromGate=true non consentito nelle tranche governate 2A/3A/4A`)
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

for (const route of ['/studio', '/impostazioni', '/sito-studio/builder']) {
  const entry = (manifest.routes ?? []).find((item) => normaliseRoute(item.route) === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    violations.push(`${route}: deve restare legacy_operational con unlockFromGate=false nella Tranche 4A`)
  }
}

for (const snippet of [
  'lower.startswith("/backup/")',
  'lower.startswith("/sito-studio/") and lower not in {"/sito-studio/contatti"}',
  'lower == "/studio" or lower.startswith("/studio/")',
  'lower == "/impostazioni" or lower.startswith("/impostazioni/")',
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
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
].join('\n').trimEnd() + '\n'

writeFileSync(resolve(reportDir, 'route-gate.md'), report)

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Route gate OK: Tranche 4A coerente.')
