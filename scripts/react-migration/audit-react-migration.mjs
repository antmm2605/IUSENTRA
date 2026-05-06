import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const outDir = resolve(root, 'artifacts/react-migration')
mkdirSync(outDir, { recursive: true })

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

function uniqueSorted(values) {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b, 'it'))
}

const gate = read('web/bootstrap/react_route_gate.py')
const app = read('frontend/src/App.tsx')
const studioModules = read('frontend/src/studioModuleData.ts')
const packageJson = JSON.parse(read('frontend/package.json'))

const lazyComponents = [...app.matchAll(/const\s+(\w+)\s*=\s*lazy\(\(\)\s*=>\s*import\('([^']+)'/g)]
  .map((match) => ({ name: match[1], importPath: match[2] }))

const routeChecks = [...app.matchAll(/const\s+(is\w+Page|is\w+)\s*=/g)]
  .map((match) => match[1])

const studioModuleRoutes = uniqueSorted(
  [...studioModules.matchAll(/routes:\s*\[([^\]]+)\]/g)]
    .flatMap((match) => [...match[1].matchAll(/["']([^"']+)["']/g)].map((route) => route[1])),
)

const inventory = {
  generatedAt: new Date().toISOString(),
  react: {
    dependencies: packageJson.dependencies ?? {},
    devDependencies: packageJson.devDependencies ?? {},
    scripts: packageJson.scripts ?? {},
  },
  gate: {
    reactPrefixes: extractTuple(gate, '_REACT_PREFIXES'),
    reactExact: extractSet(gate, '_REACT_EXACT'),
    excludedPrefixes: extractTuple(gate, '_EXCLUDED_PREFIXES'),
    legacyOperationalPrefixes: extractTuple(gate, '_LEGACY_OPERATIONAL_PREFIXES'),
  },
  app: {
    lazyComponents,
    routeChecks,
  },
  studioModules: {
    routes: studioModuleRoutes,
  },
}

writeFileSync(
  resolve(outDir, 'route-inventory.json'),
  JSON.stringify(inventory, null, 2),
)

const dependencyList = Object.keys(inventory.react.dependencies)
const scriptList = Object.keys(inventory.react.scripts)
const audit = [
  '# Audit migrazione React',
  '',
  `Generato: ${inventory.generatedAt}`,
  '',
  '## Frontend',
  '',
  `Dipendenze runtime: ${dependencyList.length ? dependencyList.join(', ') : 'nessuna'}`,
  `Script disponibili: ${scriptList.length ? scriptList.join(', ') : 'nessuno'}`,
  '',
  '## Gate React',
  '',
  `Route React prefixes: ${inventory.gate.reactPrefixes.length}`,
  `Route React exact: ${inventory.gate.reactExact.length}`,
  `Excluded prefixes: ${inventory.gate.excludedPrefixes.length}`,
  `Legacy operational prefixes: ${inventory.gate.legacyOperationalPrefixes.length}`,
  '',
  '## App React',
  '',
  `Lazy components: ${inventory.app.lazyComponents.length}`,
  `Route checks: ${inventory.app.routeChecks.length}`,
  `Studio module routes: ${inventory.studioModules.routes.length}`,
  '',
  '## Nota operativa',
  '',
  'Questo audit fotografa lo stato reale della migrazione. Non promuove route e non modifica il gate.',
  '',
].join('\n')

writeFileSync(resolve(outDir, 'audit.md'), audit)

console.log('Audit scritto in artifacts/react-migration/')
