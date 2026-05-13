import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const repo = resolve(root, '..')

function read(path) {
  return readFileSync(resolve(repo, path), 'utf8')
}

function fail(message) {
  throw new Error(message)
}

function assertContains(source, expected, label) {
  if (!source.includes(expected)) fail(`${label}: manca "${expected}"`)
}

function assertNotContains(source, unexpected, label) {
  if (source.includes(unexpected)) fail(`${label}: contiene "${unexpected}"`)
}

const app = read('frontend/src/App.tsx')
const featureFlags = read('frontend/src/lib/featureFlags.ts')
const reactShell = read('web/blueprints/react_shell.py')
const frontendDoc = read('docs/frontend-app-v2-pages.md')
const registryDoc = read('docs/app-v2-page-registry.md')
const openApi = read('docs/openapi.yaml')
const manifest = JSON.parse(read('tools/react-migration/route-manifest.json'))

const phase7RequiredAppSnippets = [
  'appV2NavigationActive(activePath)',
  'appV2UnknownRoute',
  'AppV2NotFoundPage',
  'visibleNavSections',
  'shouldShowNavItem',
  'requiredPermissionsForHref',
  'appV2FeatureFlagForPath(item.href)',
  'isFeatureFlagEnabledSync(flag)',
  'permissions: stringList(root.permissions)',
  'effectiveStandalonePage = isStandalonePage || appV2FlagDenied || appV2UnknownRoute',
]

for (const snippet of phase7RequiredAppSnippets) {
  assertContains(app, snippet, 'guard frontend App V2 fase 7')
}

for (const forbidden of [
  'localStorage',
  'sessionStorage',
  'return_url',
  'tenant_id=',
  'studio_id=',
]) {
  assertNotContains(app, forbidden, `tenant safety App.tsx ${forbidden}`)
}

assertContains(reactShell, '"permissions": permissions', 'bootstrap React espone permessi effettivi')
assertContains(reactShell, 'permessi_effettivi', 'bootstrap React legge RBAC reale')
assertContains(featureFlags, 'appV2RouteFlagRules', 'feature flag rules App V2')
assertContains(featureFlags, "'routes.appV2.telematico.surface'", 'flag superfici telematiche')

for (const column of [
  '| Area | Pagina | App V2 URL | Legacy URL | Component | Flag | API | OpenAPI | RBAC UI | Stati UI | Test | Stato |',
  '## Stato frontend fase 7',
  'complete_tested',
  'pending',
]) {
  assertContains(frontendDoc, column, 'docs/frontend-app-v2-pages.md fase 7')
}

assertContains(registryDoc, 'Stato frontend fase 7', 'registry fase 7')
assertContains(registryDoc, '404 sicura App V2', 'registry 404 App V2')

function priority(route) {
  const status = String(route.status || '')
  const risk = String(route.risk || 'medium')
  if (risk === 'critical' || (risk === 'high' && status !== 'react_operational_full')) return 'P0'
  if (risk === 'high' || (risk === 'medium' && status !== 'react_operational_full')) return 'P1'
  if (risk === 'medium') return 'P2'
  return 'P3'
}

const p0p1 = manifest.routes.filter((route) => ['P0', 'P1'].includes(priority(route)))
const missingRows = p0p1.filter((route) => !frontendDoc.includes(`| ${route.family} |`) || !frontendDoc.includes(`| ${route.route} |`))
if (missingRows.length) {
  fail(`docs/frontend-app-v2-pages.md: mancano righe P0/P1: ${missingRows.map((route) => route.route).join(', ')}`)
}

const p0p1Full = p0p1.filter((route) => route.status === 'react_operational_full')
const incompleteFull = p0p1Full.filter((route) => {
  const rowNeedle = `| ${route.family} | ${route.route} |`
  const index = frontendDoc.indexOf(rowNeedle)
  if (index < 0) return true
  const line = frontendDoc.slice(index, frontendDoc.indexOf('\n', index))
  return !line.includes('complete_tested')
    || !line.includes('flag-off')
    || !line.includes('forbidden')
    || !line.includes('readonly')
})
if (incompleteFull.length) {
  fail(`P0/P1 React full senza stato fase 7 completo: ${incompleteFull.map((route) => route.route).join(', ')}`)
}

for (const endpoint of [
  '/api/v1/ui/feature-flags',
  '/api/v1/ui/notifiche-legali',
  '/api/v1/ui/telematico/surface/{surface}',
  '/api/v1/ui/preventivi',
  '/api/v1/ui/giurisprudenza',
  '/api/v1/ui/legal-intelligence',
]) {
  assertContains(openApi, endpoint, `OpenAPI endpoint fase 7 ${endpoint}`)
}

console.log(`App V2 frontend fase 7 verificato: P0/P1=${p0p1.length}, P0/P1 full=${p0p1Full.length}.`)
