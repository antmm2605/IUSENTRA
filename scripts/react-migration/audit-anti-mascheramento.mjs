import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, extname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const artifactDir = resolve(root, 'artifacts/react-migration')
mkdirSync(artifactDir, { recursive: true })

const manifestPath = 'tools/react-migration/route-manifest.json'
const gatePath = 'web/bootstrap/react_route_gate.py'
const apiPath = 'web/blueprints/api_v1_react.py'

function toRepoPath(path) {
  return relative(root, path).split(sep).join('/')
}

function read(path) {
  const full = resolve(root, path)
  return existsSync(full) ? readFileSync(full, 'utf8') : ''
}

function walk(dir, predicate, output = []) {
  const full = resolve(root, dir)
  if (!existsSync(full)) return output
  for (const entry of readdirSync(full)) {
    const path = join(full, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      walk(toRepoPath(path), predicate, output)
    } else if (predicate(path)) {
      output.push(toRepoPath(path))
    }
  }
  return output
}

function count(source, pattern) {
  return [...source.matchAll(pattern)].length
}

function includesAny(source, patterns) {
  return patterns.some((pattern) => pattern.test(source))
}

function normaliseRoute(route) {
  return String(route || '').replace(/\/+$/, '') || '/'
}

function endpointForRoute(route) {
  const clean = normaliseRoute(route).replace(/\*$/, '').replace(/\/+$/, '') || '/'
  if (clean === '/') return '/api/v1/ui/bootstrap'
  return `/api/v1/ui${clean}`
}

function decoratorForRoute(route, method) {
  const clean = normaliseRoute(route).replace(/\*$/, '').replace(/\/+$/, '') || '/'
  const apiPart = clean === '/' ? '/bootstrap' : clean
  return `@api_v1_react.${method}("${apiPart}")`
}

function hasJsonWrite(route, sources) {
  const endpoint = endpointForRoute(route)
  return (
    sources.component.includes('apiPostJson') ||
    sources.data.includes('apiPostJson') ||
    sources.component.includes('submitFormJson') ||
    sources.data.includes('submitFormJson') ||
    sources.component.includes(`fetch('${endpoint}`) ||
    sources.component.includes(`fetch(\`${endpoint}`) ||
    sources.data.includes(`fetch('${endpoint}`) ||
    sources.data.includes(`fetch(\`${endpoint}`) ||
    sources.api.includes(decoratorForRoute(route, 'post'))
  )
}

function hasJsonRead(route, sources) {
  const endpoint = endpointForRoute(route)
  return (
    sources.data.includes(endpoint) ||
    sources.bridge.trim().length > 0 ||
    sources.api.includes(decoratorForRoute(route, 'get'))
  )
}

function hasErrorHandling(source) {
  return /\berror\b|errore|errors|warning|avviso|catch\s*\(/i.test(source)
}

function hasSuccessHandling(source) {
  return /success|riuscit|creat[oa]|salvat[oa]|ok\b/i.test(source)
}

function classify(entry, facts) {
  if (entry.status === 'legacy_operational') return 'legacy_operational'
  if (!facts.hasJsonRead && !facts.componentExists) return 'legacy_operational'
  if (!facts.hasJsonRead) return 'react_shell'
  if (facts.hasLegacyPostForm || facts.hasReactPostForm || facts.bridgeWritesLegacy || facts.blockingLegacyLinks > 0) {
    return facts.hasJsonWrite ? 'react_operational_partial' : 'react_bridge'
  }
  if (facts.hasJsonWrite || !facts.requiresWriteApi) return 'react_operational_full'
  return 'react_operational_partial'
}

function routeProblems(entry, facts) {
  const problems = []
  if (facts.blockingLegacyLinks > 0) problems.push(`${facts.blockingLegacyLinks} link ?_legacy=1 primari o non governati`)
  if (facts.technicalRollback && facts.legacyLinks > 0 && !facts.blockingLegacyLinks) problems.push('fallback legacy tecnico non primario')
  if (facts.hasLegacyPostForm) problems.push('LegacyPostForm presente')
  if (facts.hasReactPostForm) problems.push('form POST HTML in React')
  if (facts.bridgeWritesLegacy) problems.push('bridge writes=legacy_routes')
  if (entry.status === 'react_full') problems.push('status react_full deprecato')
  if ((entry.status === 'react_full' || entry.status === 'react_operational_full') && facts.blockingLegacyLinks > 0) problems.push('full con link legacy primario')
  if ((entry.status === 'react_full' || entry.status === 'react_operational_full') && facts.hasLegacyPostForm) problems.push('full con LegacyPostForm')
  if (facts.requiresWriteApi && !facts.hasJsonWrite) problems.push('API JSON di salvataggio mancante')
  if (facts.componentExists && !facts.hasErrorHandling) problems.push('gestione errori non rilevata')
  if (facts.componentExists && !facts.hasSuccessHandling) problems.push('gestione successo non rilevata')
  if (entry.unlockFromGate === true && facts.realLevel === 'react_shell') problems.push('gate sbloccato ma solo shell')
  return problems
}

function markdownCell(value) {
  const text = Array.isArray(value) ? value.join('; ') : String(value ?? '')
  return text.replace(/\|/g, '\\|').replace(/\n/g, '<br>')
}

const manifest = JSON.parse(read(manifestPath))
const apiSource = read(apiPath)
const gateSource = read(gatePath)
const scannedFiles = [
  ...walk('frontend/src', (path) => ['.tsx', '.ts'].includes(extname(path))),
  gatePath,
  manifestPath,
  apiPath,
  ...walk('web/services', (path) => /^react_.*_bridge\.py$/.test(path.split(sep).pop() || '')),
].filter((path, index, list) => list.indexOf(path) === index)

const routeMap = new Map((manifest.routes || []).map((entry) => [entry.route, entry]))
if (!routeMap.has('/utenti/nuovo')) {
  routeMap.set('/utenti/nuovo', {
    route: '/utenti/nuovo',
    family: 'amministrazione',
    status: 'manifest_missing',
    risk: 'medium',
    targetComponent: 'frontend/src/components/UtentiPage.tsx',
    targetData: 'frontend/src/utentiData.ts',
    targetBridge: 'web/services/react_utenti_bridge.py',
    legacyContract: 'artifacts/react-migration/legacy-contracts/utenti__nuovo.json',
    unlockFromGate: gateSource.includes('"/utenti/nuovo"'),
  })
}

const rows = [...routeMap.values()].map((entry) => {
  const sources = {
    component: read(entry.targetComponent || ''),
    data: read(entry.targetData || ''),
    bridge: read(entry.targetBridge || ''),
    api: apiSource,
  }
  const combined = `${sources.component}\n${sources.data}\n${sources.bridge}`
  const facts = {
    componentExists: Boolean(entry.targetComponent && existsSync(resolve(root, entry.targetComponent))),
    hasJsonRead: hasJsonRead(entry.route, sources),
    hasJsonWrite: hasJsonWrite(entry.route, sources),
    legacyLinks: count(combined, /\?_legacy=1/g),
    hasLegacyPostForm: /\bLegacyPostForm\b/.test(sources.component),
    hasReactPostForm: includesAny(sources.component, [
      /<form[^>]*method=["']post["']/i,
      /method=["']post["'][^>]*action=/i,
      /method=\{["']post["']\}/i,
    ]),
    legacyButtons: count(sources.component, /<(?:ButtonLink|a|button)[^>]*(?:legacy|\?_legacy=1)[^>]*>/gi),
    bridgeWritesLegacy: (/["']writes["']\s*:\s*["']legacy_routes["']/.test(sources.bridge) || /writes:\s*['"]legacy_routes['"]/.test(sources.data))
      && !(entry.route === '/utenti/nuovo' && sources.bridge.includes('"operational_routes" if create_view else "legacy_routes"')),
    hasErrorHandling: hasErrorHandling(sources.component),
    hasSuccessHandling: hasSuccessHandling(sources.component),
    requiresWriteApi: /(nuov|modifica|crea|salva|wizard|fatturazione\/nuova|conferimento|backup|contatti)/i.test(entry.route),
  }
  facts.technicalRollback = /Rollback tecnico|Percorso di recupero|fallback legacy tecnico|legacy_fallback|fallback tecnico/i.test(combined)
  facts.blockingLegacyLinks = facts.technicalRollback ? 0 : facts.legacyLinks
  facts.realLevel = classify(entry, facts)
  const problems = routeProblems(entry, facts)
  return {
    route: entry.route,
    component: entry.targetComponent || '',
    dataClient: entry.targetData || '',
    bridge: entry.targetBridge || '',
    manifestStatus: entry.status || '',
    unlockFromGate: entry.unlockFromGate === true,
    legacyLinks: facts.legacyLinks,
    legacyButtons: facts.legacyButtons,
    legacyPostForms: facts.hasLegacyPostForm ? 1 : 0,
    reactPostForms: facts.hasReactPostForm ? 1 : 0,
    jsonWrites: facts.hasJsonWrite,
    jsonReads: facts.hasJsonRead,
    bridgeWritesLegacy: facts.bridgeWritesLegacy,
    blockingLegacyLinks: facts.blockingLegacyLinks,
    technicalRollback: facts.technicalRollback,
    missingWriteApi: facts.requiresWriteApi && !facts.hasJsonWrite,
    missingErrorHandling: facts.componentExists && !facts.hasErrorHandling,
    missingSuccessHandling: facts.componentExists && !facts.hasSuccessHandling,
    problems,
    realLevel: facts.realLevel,
  }
})

const summary = {
  generatedAt: new Date().toISOString(),
  scannedFiles,
  totals: {
    routes: rows.length,
    legacyLinks: rows.reduce((sum, row) => sum + row.legacyLinks, 0),
    legacyPostForms: rows.reduce((sum, row) => sum + row.legacyPostForms, 0),
    reactPostForms: rows.reduce((sum, row) => sum + row.reactPostForms, 0),
    bridgeLegacyWrites: rows.filter((row) => row.bridgeWritesLegacy).length,
    deprecatedReactFull: rows.filter((row) => row.manifestStatus === 'react_full').length,
    missingWriteApi: rows.filter((row) => row.missingWriteApi).length,
  },
  levels: rows.reduce((acc, row) => {
    acc[row.realLevel] = (acc[row.realLevel] || 0) + 1
    return acc
  }, {}),
}

const jsonReport = { summary, rows }
writeFileSync(resolve(artifactDir, 'anti-mascheramento-audit.json'), `${JSON.stringify(jsonReport, null, 2)}\n`)

const md = [
  '# Audit anti-mascheramento React',
  '',
  `Generato: ${summary.generatedAt}`,
  '',
  '## Regole operative Parte 12A',
  '',
  '- `react_operational_full` richiede pagina React, dati JSON, azioni principali JSON, CSRF/sessione/permessi, stati loading/error/success e nessuna CTA primaria legacy.',
  '- `react_bridge` identifica superfici React con lettura reale ma scritture, dettagli o CTA principali ancora legacy.',
  '- `react_shell` identifica superfici solo riepilogative o di navigazione, senza flusso operativo completo.',
  '- `legacy_operational` resta il livello corretto quando il template Flask e il POST storico sono ancora il prodotto reale.',
  '- `react_full` e deprecato: non va usato per pagine che delegano il flusso principale al legacy.',
  '',
  '## Sintesi',
  '',
  `- Route censite: ${summary.totals.routes}`,
  `- Link \`?_legacy=1\`: ${summary.totals.legacyLinks}`,
  `- LegacyPostForm: ${summary.totals.legacyPostForms}`,
  `- Form POST HTML React: ${summary.totals.reactPostForms}`,
  `- Bridge con scritture legacy: ${summary.totals.bridgeLegacyWrites}`,
  `- Status react_full deprecati: ${summary.totals.deprecatedReactFull}`,
  `- API JSON di salvataggio mancanti: ${summary.totals.missingWriteApi}`,
  '',
  '## Tabella route',
  '',
  '| route | componente | data client | bridge | stato manifest | link legacy presenti | form legacy presenti | scritture JSON presenti | problemi | livello reale |',
  '| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |',
  ...rows.map((row) => [
    row.route,
    row.component,
    row.dataClient,
    row.bridge,
    row.manifestStatus,
    row.legacyLinks,
    row.legacyPostForms + row.reactPostForms,
    row.jsonWrites ? 'si' : 'no',
    row.problems.length ? row.problems.join('; ') : 'nessuno',
    row.realLevel,
  ].map(markdownCell).join(' | ')).map((line) => `| ${line} |`),
  '',
].join('\n')

writeFileSync(resolve(artifactDir, 'anti-mascheramento-audit.md'), md)
console.log(`Audit anti-mascheramento scritto: ${rows.length} route, ${summary.totals.legacyLinks} link legacy.`)
