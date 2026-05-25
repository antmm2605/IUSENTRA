import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'

const repoRoot = resolve(import.meta.dirname, '..', '..')
const configPath = resolve(import.meta.dirname, 'design-system-governance.json')
const reportPath = resolve(repoRoot, 'artifacts/react-migration/design-system-governance-report.md')

function normalizePath(path) {
  return path.replace(/\\/g, '/')
}

function rel(path) {
  return normalizePath(relative(repoRoot, path))
}

function read(path) {
  return readFileSync(resolve(repoRoot, path), 'utf8')
}

function fail(message) {
  throw new Error(`Design system governance: ${message}`)
}

function walk(dir, exts, output = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist' || entry === 'storybook-static') continue
    const fullPath = resolve(dir, entry)
    const stat = statSync(fullPath)
    if (stat.isDirectory()) {
      walk(fullPath, exts, output)
      continue
    }
    if (exts.some((ext) => fullPath.endsWith(ext))) output.push(fullPath)
  }
  return output
}

function lineNumber(source, index) {
  return source.slice(0, index).split(/\r?\n/).length
}

function countMatches(source, regex) {
  return Array.from(source.matchAll(regex)).length
}

function assertUnique(values, label) {
  const seen = new Set()
  const duplicates = []
  for (const value of values) {
    if (seen.has(value)) duplicates.push(value)
    seen.add(value)
  }
  if (duplicates.length) fail(`${label}: duplicati ${duplicates.join(', ')}`)
}

if (!existsSync(configPath)) fail('manca scripts/react-migration/design-system-governance.json')

const config = JSON.parse(readFileSync(configPath, 'utf8'))
if (config.schemaVersion !== 1) fail('schemaVersion deve essere 1')

const approvedPresetExceptions = config.approvedPresetExceptions ?? []
const exceptionRoutes = approvedPresetExceptions.map((entry) => entry.route)
const normalizedExceptionRoutes = approvedPresetExceptions.map((entry) => entry.normalizedRoute ?? entry.route)
assertUnique(exceptionRoutes, 'approvedPresetExceptions')
assertUnique(normalizedExceptionRoutes, 'approvedPresetExceptions.normalizedRoute')
for (const entry of approvedPresetExceptions) {
  if (!entry.route || !entry.reason) fail('approvedPresetExceptions richiede route e reason')
}
const approvedPresetPatternExceptions = config.approvedPresetPatternExceptions ?? []
const exceptionPatterns = approvedPresetPatternExceptions.map((entry) => entry.routePattern)
assertUnique(exceptionPatterns, 'approvedPresetPatternExceptions')
for (const entry of approvedPresetPatternExceptions) {
  if (!entry.routePattern || !entry.appSnippet || !entry.reason) {
    fail('approvedPresetPatternExceptions richiede routePattern, appSnippet e reason')
  }
}

const approvedCssFiles = config.approvedCssFiles ?? []
if (!Array.isArray(approvedCssFiles) || approvedCssFiles.length === 0) {
  fail('approvedCssFiles deve contenere almeno un file CSS')
}
assertUnique(approvedCssFiles, 'approvedCssFiles')

const cssFiles = walk(resolve(repoRoot, 'frontend/src'), ['.css']).map(rel).sort()
const approvedCss = new Set(approvedCssFiles)
const missingFromConfig = cssFiles.filter((path) => !approvedCss.has(path))
const staleConfig = approvedCssFiles.filter((path) => !cssFiles.includes(path))

if (missingFromConfig.length) fail(`CSS locali non governati: ${missingFromConfig.join(', ')}`)
if (staleConfig.length) fail(`allowlist CSS contiene file non esistenti: ${staleConfig.join(', ')}`)

const forbiddenPatterns = (config.forbiddenCssPatterns ?? []).map((pattern) => ({
  ...pattern,
  regexObject: new RegExp(pattern.regex, 'i'),
}))
for (const cssPath of cssFiles) {
  const source = read(cssPath)
  for (const pattern of forbiddenPatterns) {
    const match = pattern.regexObject.exec(source)
    if (match) fail(`${cssPath}:${lineNumber(source, match.index)} viola ${pattern.id}: ${pattern.reason}`)
  }
}

const backdropPolicy = new Map((config.allowedBackdropFilters ?? []).map((entry) => [entry.file, entry]))
for (const cssPath of cssFiles) {
  const source = read(cssPath)
  const count = countMatches(source, /\bbackdrop-filter\s*:/g)
  const policy = backdropPolicy.get(cssPath)
  if (count > 0 && !policy) fail(`${cssPath}: usa backdrop-filter senza autorizzazione nel gate`)
  if (policy && count !== policy.count) fail(`${cssPath}: backdrop-filter attesi ${policy.count}, trovati ${count}`)
}
for (const path of backdropPolicy.keys()) {
  if (!approvedCss.has(path)) fail(`allowedBackdropFilters cita file non approvato: ${path}`)
}

const allowedInlineStyles = config.allowedInlineStyles ?? []
for (const entry of allowedInlineStyles) {
  if (!Array.isArray(entry.snippets) || entry.snippets.length === 0 || !entry.reason) {
    fail(`allowedInlineStyles non completo per ${entry.file}`)
  }
}
const inlinePolicy = new Map(allowedInlineStyles.map((entry) => [entry.file, entry]))
const sourceFiles = walk(resolve(repoRoot, 'frontend/src'), ['.ts', '.tsx']).map(rel).sort()
const inlineOccurrences = []
for (const filePath of sourceFiles) {
  const source = read(filePath)
  const regex = /style\s*=\s*\{\{/g
  for (const match of source.matchAll(regex)) {
    inlineOccurrences.push({
      filePath,
      line: lineNumber(source, match.index),
      window: source.slice(match.index, match.index + 900),
    })
  }
}

for (const occurrence of inlineOccurrences) {
  const policy = inlinePolicy.get(occurrence.filePath)
  if (!policy) fail(`${occurrence.filePath}:${occurrence.line} usa inline style non autorizzato`)
  const matchedSnippet = policy.snippets.find((snippet) => occurrence.window.includes(snippet))
  if (!matchedSnippet) fail(`${occurrence.filePath}:${occurrence.line} usa inline style non presente nella policy`)
}
for (const [filePath, policy] of inlinePolicy.entries()) {
  const source = read(filePath)
  for (const snippet of policy.snippets) {
    if (!source.includes(snippet)) fail(`${filePath}: snippet inline style autorizzato ma non trovato: ${snippet}`)
  }
}

const packageJson = JSON.parse(read('frontend/package.json'))
const testScript = String(packageJson.scripts?.test ?? '')
if (!testScript.includes('check-design-system-governance.mjs')) {
  fail('frontend/package.json non esegue check-design-system-governance.mjs nello script test')
}

const appSource = read('frontend/src/App.tsx')
for (let index = 0; index < approvedPresetExceptions.length; index += 1) {
  const displayRoute = exceptionRoutes[index]
  const routeForApp = normalizedExceptionRoutes[index]
  if (!appSource.includes(`routeKey === '${routeForApp}'`)) {
    fail(`App.tsx non dichiara eccezione preset esatta per ${displayRoute} (${routeForApp})`)
  }
}
for (const entry of approvedPresetPatternExceptions) {
  if (!appSource.includes(entry.appSnippet)) {
    fail(`App.tsx non dichiara eccezione preset per pattern ${entry.routePattern}`)
  }
}
const presetExceptionLines = appSource
  .split(/\r?\n/)
  .filter((line) => line.includes('isPresetExcludedPage') || line.includes('isFascicoloDetailViewPage'))
  .join('\n')
if (presetExceptionLines.includes("startsWith('/fascicoli/") || presetExceptionLines.includes('startsWith("/fascicoli/')) {
  fail('App.tsx non deve usare un prefisso fascicoli come eccezione preset')
}

const uiDoc = read('docs/UI_DESIGN_SYSTEM.md')
for (const expected of ['check-design-system-governance.mjs', 'design-system-governance.json', 'Nessun nuovo CSS locale']) {
  if (!uiDoc.includes(expected)) fail(`docs/UI_DESIGN_SYSTEM.md non documenta "${expected}"`)
}
for (const route of exceptionRoutes) {
  if (!uiDoc.includes(route)) fail(`docs/UI_DESIGN_SYSTEM.md non documenta eccezione preset ${route}`)
}
for (const pattern of exceptionPatterns) {
  if (!uiDoc.includes(pattern)) fail(`docs/UI_DESIGN_SYSTEM.md non documenta eccezione preset ${pattern}`)
}

const report = [
  '# Design System Governance Report',
  '',
  'Fase 4 - Design system unico.',
  '',
  `- CSS approvati e governati: ${cssFiles.length}`,
  `- Eccezioni preset approvate: ${[
    ...approvedPresetExceptions.map((entry) => entry.normalizedRoute ? `${entry.route} (${entry.normalizedRoute})` : entry.route),
    ...approvedPresetPatternExceptions.map((entry) => entry.routePattern),
  ].join(', ')}`,
  `- Inline style autorizzati: ${inlineOccurrences.length}`,
  `- File con backdrop-filter autorizzato: ${backdropPolicy.size}`,
  `- Pattern CSS vietati attivi: ${forbiddenPatterns.length}`,
  '- Nessun nuovo CSS locale può entrare senza allowlist e motivazione.',
  '- Ogni nuovo inline style deve dichiarare file, snippet e ragione operativa.',
  '- Gli accenti laterali spessi, i testi gradiente e i blur decorativi sono bloccati.',
  '',
  'Esito: gate Design System IUSENTRA verde.',
  '',
].join('\n')

mkdirSync(dirname(reportPath), { recursive: true })
writeFileSync(reportPath, report, 'utf8')

console.log(`Design system governance OK: ${cssFiles.length} CSS, ${inlineOccurrences.length} inline style, ${forbiddenPatterns.length} divieti.`)
