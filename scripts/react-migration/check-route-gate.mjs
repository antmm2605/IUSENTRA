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
    legacyPrefixes.some((prefix) => isPrefixMatch(path, prefix)) ||
    excludedPrefixes.some((prefix) => isPrefixMatch(path, prefix))
  )
}

const gate = read('web/bootstrap/react_route_gate.py')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))

const reactPrefixes = extractTuple(gate, '_REACT_PREFIXES')
const reactExact = new Set(extractSet(gate, '_REACT_EXACT').map(normaliseRoute))
const legacyOperationalPrefixes = extractTuple(gate, '_LEGACY_OPERATIONAL_PREFIXES')
const excludedPrefixes = extractTuple(gate, '_EXCLUDED_PREFIXES')

const violations = []
for (const entry of manifest.routes ?? []) {
  const route = normaliseRoute(entry.route)
  const routeIsReact = isReactRoute(route, reactExact, reactPrefixes)
  const blocked = isBlockedByGate(route, legacyOperationalPrefixes, excludedPrefixes)
  const unlockedByGate = routeIsReact && !blocked

  if (unlockedByGate && entry.status !== 'react_full') {
    violations.push(`${entry.route}: risulta servibile dal gate ma status=${entry.status}`)
  }

  if (entry.unlockFromGate === true) {
    if (entry.status !== 'react_full') {
      violations.push(`${entry.route}: unlockFromGate=true richiede status react_full`)
    }
    for (const field of ['targetComponent', 'targetData', 'targetBridge', 'legacyContract']) {
      const value = entry[field]
      if (!value || !existsSync(resolve(root, value))) {
        violations.push(`${entry.route}: manca ${field} (${value || 'non indicato'})`)
      }
    }
  }
}

const unlocked = (manifest.routes ?? []).filter((entry) => entry.unlockFromGate === true)
if (unlocked.length) {
  violations.push(`Questa tranche non deve sbloccare route: ${unlocked.map((entry) => entry.route).join(', ')}`)
}

const report = [
  '# Route gate report',
  '',
  `Route nel manifest: ${(manifest.routes ?? []).length}`,
  `Route con unlockFromGate=true: ${unlocked.length}`,
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
].join('\n').trimEnd() + '\n'

writeFileSync(resolve(reportDir, 'route-gate.md'), report)

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Route gate OK: nessuna route legacy sbloccata.')
