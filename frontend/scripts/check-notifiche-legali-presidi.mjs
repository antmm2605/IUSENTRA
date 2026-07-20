import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { extname, join, relative, resolve } from 'node:path'
import vm from 'node:vm'
import ts from 'typescript'

const frontendRoot = resolve(import.meta.dirname, '..')
const featureRoot = resolve(frontendRoot, 'src/features/notifiche-legali')

function read(relativePath) {
  return readFileSync(resolve(frontendRoot, relativePath), 'utf8')
}

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = join(directory, entry.name)
    return entry.isDirectory() ? walk(fullPath) : [fullPath]
  })
}

function parse(relativePath) {
  const source = read(relativePath)
  const kind = relativePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  return ts.createSourceFile(relativePath, source, ts.ScriptTarget.Latest, true, kind)
}

function visit(node, predicate) {
  if (predicate(node)) return node
  let found
  ts.forEachChild(node, (child) => {
    if (!found) found = visit(child, predicate)
  })
  return found
}

function findFunction(sourceFile, name) {
  const node = visit(sourceFile, (candidate) => (
    ts.isFunctionDeclaration(candidate) && candidate.name?.text === name
  ))
  assert.ok(node, `Funzione ${name} non trovata in ${sourceFile.fileName}`)
  return node
}

function findVariable(root, name) {
  const node = visit(root, (candidate) => (
    ts.isVariableDeclaration(candidate)
    && ts.isIdentifier(candidate.name)
    && candidate.name.text === name
  ))
  assert.ok(node, `Variabile ${name} non trovata`)
  return node
}

function findTypeAlias(sourceFile, name) {
  const node = sourceFile.statements.find((candidate) => (
    ts.isTypeAliasDeclaration(candidate) && candidate.name.text === name
  ))
  assert.ok(node, `Tipo ${name} non trovato in ${sourceFile.fileName}`)
  return node
}

function staticImports(sourceFile) {
  return sourceFile.statements
    .filter(ts.isImportDeclaration)
    .map((node) => node.moduleSpecifier)
    .filter(ts.isStringLiteral)
    .map((node) => node.text)
}

function dynamicImports(root) {
  const values = []
  const collect = (node) => {
    if (
      ts.isCallExpression(node)
      && node.expression.kind === ts.SyntaxKind.ImportKeyword
      && node.arguments.length === 1
      && ts.isStringLiteral(node.arguments[0])
    ) {
      values.push(node.arguments[0].text)
    }
    ts.forEachChild(node, collect)
  }
  collect(root)
  return values
}

function unwrap(node) {
  let current = node
  while (ts.isParenthesizedExpression(current)) current = current.expression
  return current
}

function jsxTag(node) {
  const current = unwrap(node)
  if (ts.isJsxSelfClosingElement(current)) return current.tagName.getText()
  if (ts.isJsxElement(current)) return current.openingElement.tagName.getText()
  return ''
}

function evaluateFlagExpression(node, flags) {
  const current = unwrap(node)
  if (
    ts.isBinaryExpression(current)
    && current.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
  ) {
    return evaluateFlagExpression(current.left, flags) && evaluateFlagExpression(current.right, flags)
  }
  if (
    ts.isCallExpression(current)
    && current.expression.getText() === 'isFeatureFlagEnabledSync'
    && current.arguments.length === 1
    && ts.isStringLiteral(current.arguments[0])
  ) {
    return flags[current.arguments[0].text] === true
  }
  throw new Error(`Espressione flag non governata: ${current.getText()}`)
}

function stringArrayVariable(sourceFile, name) {
  const declaration = findVariable(sourceFile, name)
  const initializer = declaration.initializer && unwrap(declaration.initializer)
  assert.ok(initializer && ts.isArrayLiteralExpression(initializer), `${name} deve essere un array letterale`)
  return initializer.elements.map((element) => {
    assert.ok(ts.isStringLiteral(element), `${name} deve contenere solo stringhe`)
    return element.text
  })
}

function unionStrings(sourceFile, name) {
  const alias = findTypeAlias(sourceFile, name)
  const node = alias.type
  const members = ts.isUnionTypeNode(node) ? node.types : [node]
  return members.map((member) => {
    assert.ok(
      ts.isLiteralTypeNode(member) && ts.isStringLiteral(member.literal),
      `${name} deve essere un'unione di stringhe`,
    )
    return member.literal.text
  })
}

function typeProperties(sourceFile, name, seen = new Set()) {
  if (seen.has(name)) return new Set()
  seen.add(name)
  const alias = findTypeAlias(sourceFile, name)
  const collect = (node) => {
    if (ts.isTypeLiteralNode(node)) {
      return new Set(node.members.flatMap((member) => (
        ts.isPropertySignature(member) && member.name ? [member.name.getText().replaceAll("'", '')] : []
      )))
    }
    if (ts.isIntersectionTypeNode(node)) {
      const merged = new Set()
      for (const member of node.types) {
        for (const value of collect(member)) merged.add(value)
      }
      return merged
    }
    if (ts.isTypeReferenceNode(node) && ts.isIdentifier(node.typeName)) {
      return typeProperties(sourceFile, node.typeName.text, seen)
    }
    return new Set()
  }
  return collect(alias.type)
}

function assertProperties(sourceFile, typeName, expected) {
  const properties = typeProperties(sourceFile, typeName)
  for (const property of expected) {
    assert.ok(properties.has(property), `${typeName}: manca la proprietà ${property}`)
  }
}

function jsxAttribute(node, name) {
  return node.attributes?.properties.find((attribute) => (
    ts.isJsxAttribute(attribute) && attribute.name.getText() === name
  ))
}

function collectVisibleStrings(sourceFile) {
  const values = []
  const visibleNames = new Set(['label', 'title', 'message', 'description', 'subtitle', 'placeholder', 'aria-label'])
  const collectRenderBranches = (node) => {
    const current = unwrap(node)
    if (ts.isStringLiteral(current) || ts.isNoSubstitutionTemplateLiteral(current)) {
      values.push(current.text)
      return
    }
    if (ts.isConditionalExpression(current)) {
      collectRenderBranches(current.whenTrue)
      collectRenderBranches(current.whenFalse)
      return
    }
    if (ts.isBinaryExpression(current) && current.operatorToken.kind === ts.SyntaxKind.PlusToken) {
      collectRenderBranches(current.left)
      collectRenderBranches(current.right)
    }
  }
  const scan = (node) => {
    if (ts.isJsxText(node)) {
      const text = node.text.replace(/\s+/g, ' ').trim()
      if (text) values.push(text)
    }
    if (ts.isJsxAttribute(node) && visibleNames.has(node.name.getText())) {
      if (node.initializer && ts.isStringLiteral(node.initializer)) values.push(node.initializer.text)
      if (node.initializer && ts.isJsxExpression(node.initializer) && node.initializer.expression) {
        collectRenderBranches(node.initializer.expression)
      }
    }
    if (ts.isPropertyAssignment(node) && visibleNames.has(node.name.getText().replaceAll("'", ''))) {
      collectRenderBranches(node.initializer)
    }
    if (
      ts.isVariableDeclaration(node)
      && ts.isIdentifier(node.name)
      && /^(?:title|message|description|subtitle|resultLabel)$/.test(node.name.text)
      && node.initializer
    ) {
      collectRenderBranches(node.initializer)
    }
    ts.forEachChild(node, scan)
  }
  scan(sourceFile)
  return values
}

const app = parse('src/App.tsx')
const shell = parse('src/features/notifiche-legali/NotificheLegaliPresidiShell.tsx')
const page = parse('src/features/notifiche-legali/PresidiNotifichePage.tsx')
const types = parse('src/features/notifiche-legali/types.ts')
const appSource = app.getFullText()
const shellSource = shell.getFullText()
const pageSource = page.getFullText()
const apiSource = read('src/features/notifiche-legali/api/presidiApi.ts')
const detailSource = read('src/features/notifiche-legali/components/PresidioDetailDrawer.tsx')
const actionsSource = read('src/features/notifiche-legali/components/PresidioActions.tsx')
const tableSource = read('src/features/notifiche-legali/components/PresidiTable.tsx')
const evidenceSource = read('src/features/notifiche-legali/components/PresidioEvidence.tsx')
const featureFlagsSource = read('src/lib/featureFlags.ts')
const formattingSource = read('src/formatting.ts')
const viteSource = read('vite.config.ts')

// Rollout: entrambi i percorsi restano chunk dinamici e il nuovo ramo esiste
// soltanto quando enabled e primary sono entrambi veri.
assert.ok(!staticImports(app).some((value) => value.includes('notifiche-legali/NotificheLegaliPresidiShell')))
assert.ok(dynamicImports(app).includes('./features/notifiche-legali/NotificheLegaliPresidiShell'))
assert.ok(dynamicImports(app).includes('./components/NotificheLegaliPage'))
assert.match(viteSource, /modulePreload\s*:\s*false/, 'I chunk dinamici non devono essere precaricati')

const legacyDeclaration = findVariable(app, 'LegacyNotificheLegaliPage')
const shellDeclaration = findVariable(app, 'NotificheLegaliPresidiShell')
assert.deepEqual(dynamicImports(legacyDeclaration), ['./components/NotificheLegaliPage'])
assert.deepEqual(dynamicImports(shellDeclaration), ['./features/notifiche-legali/NotificheLegaliPresidiShell'])

const routeFunction = findFunction(app, 'NotificheLegaliPage')
const primaryDeclaration = findVariable(routeFunction, 'primary')
assert.ok(primaryDeclaration.initializer, 'Manca l’espressione primary')
const enabledKey = 'features.legalNotificationPresidia.enabled'
const primaryKey = 'features.legalNotificationPresidia.primary'
const truthTable = [
  [{ [enabledKey]: false, [primaryKey]: false }, false, 'flag OFF'],
  [{ [enabledKey]: true, [primaryKey]: false }, false, 'shadow'],
  [{ [enabledKey]: false, [primaryKey]: true }, false, 'primary senza enabled'],
  [{ [enabledKey]: true, [primaryKey]: true }, true, 'primary'],
]
for (const [flags, expected, label] of truthTable) {
  assert.equal(evaluateFlagExpression(primaryDeclaration.initializer, flags), expected, label)
}

const routeReturn = routeFunction.body?.statements.find(ts.isReturnStatement)
assert.ok(routeReturn?.expression && ts.isConditionalExpression(routeReturn.expression), 'Il routing deve restare condizionale')
assert.equal(routeReturn.expression.condition.getText(), 'primary')
assert.equal(jsxTag(routeReturn.expression.whenTrue), 'NotificheLegaliPresidiShell')
assert.equal(jsxTag(routeReturn.expression.whenFalse), 'LegacyNotificheLegaliPage')
const primaryElement = unwrap(routeReturn.expression.whenTrue)
assert.ok(ts.isJsxSelfClosingElement(primaryElement))
const legacyPageAttribute = jsxAttribute(primaryElement, 'legacyPage')
assert.ok(legacyPageAttribute?.initializer && ts.isJsxExpression(legacyPageAttribute.initializer))
assert.equal(jsxTag(legacyPageAttribute.initializer.expression), 'LegacyNotificheLegaliPage')

for (const key of [enabledKey, primaryKey]) {
  assert.ok(featureFlagsSource.includes(`'${key}'`), `FeatureFlagKey non include ${key}`)
}

// Deep link storici: qualsiasi query operativa forza il ramo legacy.
const expectedLegacyKeys = [
  'fase',
  'id_fascicolo',
  'id_fasc',
  'fascicolo',
  'documenti',
  'documenti_ids',
  'id_documento',
  'id_documenti',
  'documento',
]
const legacyKeys = stringArrayVariable(shell, 'LEGACY_QUERY_KEYS')
for (const key of expectedLegacyKeys) assert.ok(legacyKeys.includes(key), `Deep link legacy non protetto: ${key}`)
const sectionFunction = findFunction(shell, 'sectionFromLocation')
const sectionText = sectionFunction.getText(shell)
assert.match(sectionText, /params\.get\(['"]section['"]\)\s*===\s*['"]operazioni['"]/)
assert.match(sectionText, /LEGACY_QUERY_KEYS\.some\(\(key\)\s*=>\s*params\.has\(key\)\)/)
assert.equal((sectionText.match(/return ['"]operazioni['"]/g) || []).length, 2)
assert.match(sectionText, /return ['"]presidi['"]/)
assert.ok(!staticImports(shell).some((value) => value.includes('components/NotificheLegaliPage')))
assert.ok(!shellSource.includes('notificheLegaliData'))

const shellComponent = findFunction(shell, 'NotificheLegaliPresidiShell')
const sectionConditional = visit(shellComponent, (candidate) => (
  ts.isConditionalExpression(candidate) && candidate.condition.getText(shell).replaceAll(' ', '') === "section==='presidi'"
))
assert.ok(sectionConditional, 'Manca la separazione presidi/operazioni')
assert.equal(jsxTag(sectionConditional.whenTrue), 'PresidiNotifichePage')
assert.ok(!sectionConditional.whenTrue.getText(shell).includes('legacyPage'))
assert.ok(sectionConditional.whenFalse.getText(shell).includes('{legacyPage}'))

const featureSources = walk(featureRoot)
  .filter((path) => ['.ts', '.tsx'].includes(extname(path)))
  .map((path) => readFileSync(path, 'utf8'))
  .join('\n')
assert.ok(!featureSources.includes("from '@/notificheLegaliData'"))
assert.ok(!featureSources.includes("from '../../notificheLegaliData'"))
assert.ok(!featureSources.includes('components/NotificheLegaliPage'))

// Contratto TypeScript: filtri, payload, permessi, mutazioni e stati espliciti.
assert.deepEqual(unionStrings(types, 'PresidioMutation'), [
  'confirm',
  'not-required',
  'assign',
  'link-document',
  'reconcile',
  'retry',
])
for (const state of ['idle', 'loading', 'refreshing', 'ready', 'forbidden', 'flag-off', 'repository-unavailable', 'error']) {
  assert.ok(unionStrings(types, 'PresidioResourceStatus').includes(state), `Stato UI assente: ${state}`)
}
assertProperties(types, 'PresidioListFilters', [
  'statuses', 'priority', 'fascicolo', 'assigned_user', 'date_from', 'date_to',
  'recipient', 'channel', 'legacy', 'needs_review', 'cursor', 'limit',
])
assertProperties(types, 'PresidioListPayload', [
  'ok', 'items', 'pagination', 'facets', 'filter_options', 'permissions', 'partial', 'warnings',
])
assertProperties(types, 'PresidioPermissions', ['can_read', 'can_write', 'can_link_document', 'can_view_evidence'])
assertProperties(types, 'PresidioDetailPayload', ['ok', 'presidio', 'permissions', 'warnings'])
assertProperties(types, 'PresidioMutationResult', ['ok', 'message', 'status', 'code', 'presidio', 'warnings'])

for (const forbidden of [
  'tenant_id',
  'studio_id',
  'filesystem_path',
  'source_locator',
  'zip_member_path',
  'outer_sha256',
  'content_sha256',
  'eml_sha256',
]) {
  assert.ok(!types.getFullText().includes(forbidden), `Campo tecnico esposto al frontend: ${forbidden}`)
  assert.ok(!apiSource.includes(`'${forbidden}'`), `Parametro client vietato: ${forbidden}`)
}

// Esecuzione reale del client API transpilandolo in memoria con dipendenze simulate.
// Non è uno snapshot: verifica URL, query, payload e propagazione degli errori.
class TestApiClientError extends Error {
  constructor(status, payload) {
    super(String(payload?.message || 'Operazione non riuscita'))
    this.name = 'ApiClientError'
    this.status = status
    this.payload = payload || {}
  }
}

const apiCalls = []
let ensureResult = { ok: true }
let postResult = { ok: true, message: 'Operazione completata.' }
const apiClientMock = {
  ApiClientError: TestApiClientError,
  ensureJson: async (url, options) => {
    apiCalls.push({ kind: 'GET', url, options })
    return ensureResult
  },
  apiPostJson: async (url, body, fallback, options) => {
    apiCalls.push({ kind: 'POST', url, body, fallback, options })
    return postResult
  },
}
const transpiledApi = ts.transpileModule(apiSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
  fileName: 'presidiApi.ts',
}).outputText
const commonJsModule = { exports: {} }
const executeModule = vm.runInNewContext(
  `(function (require, module, exports) { ${transpiledApi}\n })`,
  { URLSearchParams, encodeURIComponent, console },
)
executeModule((specifier) => {
  if (specifier === '@/lib/apiClient') return apiClientMock
  throw new Error(`Import inatteso nel client API: ${specifier}`)
}, commonJsModule, commonJsModule.exports)
const api = commonJsModule.exports

const signal = new AbortController().signal
await api.getPresidi({
  statuses: ['NEEDS_REVIEW', 'DELIVERY_FAILED'],
  priority: 'P0',
  fascicolo: '  FASC-001  ',
  assigned_user: 'USR-1',
  date_from: '2026-07-20',
  date_to: '2026-07-31',
  recipient: '  destinatario@example.invalid ',
  channel: 'PEC',
  legacy: 'false',
  needs_review: 'true',
  cursor: 'next+/=',
  limit: 30,
}, signal)
const listCall = apiCalls.shift()
assert.equal(listCall.kind, 'GET')
assert.equal(listCall.options.signal, signal)
const listUrl = new URL(listCall.url, 'https://app.iusentra.test')
assert.equal(listUrl.pathname, '/api/v1/ui/notifiche-legali/presidi')
assert.deepEqual(Object.fromEntries(listUrl.searchParams), {
  status: 'NEEDS_REVIEW,DELIVERY_FAILED',
  priority: 'P0',
  fascicolo: 'FASC-001',
  assigned_user: 'USR-1',
  date_from: '2026-07-20',
  date_to: '2026-07-31',
  recipient: 'destinatario@example.invalid',
  channel: 'PEC',
  legacy: 'false',
  needs_review: 'true',
  cursor: 'next+/=',
  limit: '30',
})
assert.ok(!listUrl.searchParams.has('tenant_id'))
assert.ok(!listUrl.searchParams.has('studio_id'))

for (const [method, suffix] of [
  ['getPresidio', ''],
  ['getPresidioEvidence', '/evidence'],
  ['getPresidioTransitions', '/transitions'],
]) {
  ensureResult = { ok: true }
  await api[method]('PR/ 1', signal)
  const call = apiCalls.shift()
  assert.equal(call.url, `/api/v1/ui/notifiche-legali/presidi/PR%2F%201${suffix}`)
  assert.equal(call.options.signal, signal)
}
assert.equal(
  api.evidenceContentUrl('PR/1', 'EV 2'),
  '/api/v1/ui/notifiche-legali/presidi/PR%2F1/evidence/EV%202/content',
)
assert.equal(
  api.evidenceContentUrl('PR/1', 'EV 2', true),
  '/api/v1/ui/notifiche-legali/presidi/PR%2F1/evidence/EV%202/content?download=1',
)

const mutations = ['confirm', 'not-required', 'assign', 'link-document', 'reconcile', 'retry']
for (const mutation of mutations) {
  postResult = { ok: true, message: 'Operazione completata.' }
  const body = { marker: mutation }
  await api.mutatePresidio('PR/1', mutation, body)
  const call = apiCalls.shift()
  assert.equal(call.kind, 'POST')
  assert.equal(call.url, `/api/v1/ui/notifiche-legali/presidi/PR%2F1/${mutation}`)
  assert.deepEqual(call.body, body)
  assert.equal(call.fallback.status, 503)
  assert.equal(call.fallback.code, 'network_unavailable')
}

postResult = {
  ok: false,
  status: 409,
  code: 'state_conflict',
  message: 'Il presidio è stato aggiornato. Ricarica e riprova.',
}
await assert.rejects(
  api.mutatePresidio('PR-1', 'confirm', {}),
  (error) => (
    error instanceof TestApiClientError
    && error.status === 409
    && error.payload.code === 'state_conflict'
    && error.message === 'Il presidio è stato aggiornato. Ricarica e riprova.'
  ),
)
apiCalls.shift()

ensureResult = { ok: false }
await assert.rejects(
  api.getPresidio('PR-1'),
  (error) => error instanceof TestApiClientError && error.status === 500 && error.payload.code === 'invalid_response',
)
apiCalls.shift()

for (const [status, expected] of [
  [401, 'error'],
  [403, 'forbidden'],
  [409, 'error'],
  [500, 'error'],
  [503, 'repository-unavailable'],
]) {
  const result = api.classifyPresidioError(new TestApiClientError(status, { message: 'Dettaglio tecnico riservato' }))
  assert.equal(result.status, expected, `Classificazione HTTP ${status}`)
  assert.ok(result.message.length > 10)
  assert.ok(!result.message.includes(String(status)))
  assert.ok(!result.message.includes('Dettaglio tecnico riservato'))
}
for (const code of ['feature_disabled', 'feature_flag_disabled']) {
  const result = api.classifyPresidioError(new TestApiClientError(404, { code, message: 'Dettaglio tecnico' }))
  assert.equal(result.status, 'flag-off')
}

assert.match(pageSource, /payload\?\.partial/)
assert.match(pageSource, /I dati sono parziali\./)
assert.match(pageSource, /!payload\.permissions\.can_write/)
assert.match(pageSource, /Consultazione in sola lettura\./)
assert.match(actionsSource, /action\.kind === ['"]mutation['"] && readOnly/)
assert.match(detailSource, /\[400, 409, 422\]\.includes\(error\.status\)/)
assert.match(detailSource, /tone: ['"]success['"]/)
assert.match(tableSource, /<EmptyState/)

// Date italiane, copy professionale e nessun dettaglio tecnico visibile.
assert.match(formattingSource, /ITALIAN_TIME_ZONE\s*=\s*['"]Europe\/Rome['"]/)
assert.match(formattingSource, /Intl\.DateTimeFormat\(['"]it-IT['"]/)
for (const source of [tableSource, evidenceSource, detailSource]) {
  assert.ok(source.includes('formatDateTimeIt'), 'Ogni superficie temporale deve usare formatDateTimeIt')
  for (const forbidden of ['toLocaleString(', 'toLocaleDateString(', 'Intl.DateTimeFormat(', '.slice(0, 10)']) {
    assert.ok(!source.includes(forbidden), `Formattazione data locale vietata: ${forbidden}`)
  }
}
for (const expected of [
  'formatDateTimeIt(item.source_effective_at',
  'formatDateTimeIt(item.explicit_due_at',
  'formatDateTimeIt(item.created_at',
  'formatDateTimeIt(detail.source_effective_at',
  'formatDateTimeIt(detail.explicit_due_at',
  'formatDateTimeIt(transition.occurred_at',
]) {
  assert.ok(featureSources.includes(expected), `Timestamp non formattato: ${expected}`)
}

const uiSourceFiles = walk(featureRoot).filter((path) => extname(path) === '.tsx')
const visibleStrings = uiSourceFiles.flatMap((path) => {
  const relativePath = relative(frontendRoot, path).replaceAll('\\', '/')
  return collectVisibleStrings(parse(relativePath))
})
const visibleText = visibleStrings.join('\n')
for (const pattern of [
  /(?:[A-Za-z]:\\|\\\\[^\\]+\\|file:\/\/|\/(?:opt|home|var|srv|tmp)\/)/i,
  /\b(?:repository|payload|endpoint|filesystem|tenant_id|studio_id|source_message_id|sha-?256|zip_member_path|JSON|UTC)\b/i,
  /\b(?:perche|poiche|cosi|piu|gia|attivita|necessita|disponibilita|qualita)\b/i,
  /\b20\d{2}-\d{2}-\d{2}(?:T\d{2}:\d{2})?\b/,
]) {
  assert.ok(!pattern.test(visibleText), `Testo visibile non professionale: ${pattern}`)
}

// Accessibilità essenziale: controlli nominati, semantica dei form e niente
// override che rimuova il focus da tastiera.
for (const relativePath of uiSourceFiles.map((path) => relative(frontendRoot, path).replaceAll('\\', '/'))) {
  const sourceFile = parse(relativePath)
  const check = (node) => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(sourceFile)
      if (tag === 'Button' || tag === 'button') {
        assert.ok(jsxAttribute(node, 'type'), `${relativePath}: pulsante senza type esplicito`)
      }
      if (tag === 'form') {
        assert.ok(jsxAttribute(node, 'onSubmit'), `${relativePath}: form senza onSubmit governato`)
      }
      if (tag === 'time') {
        assert.ok(jsxAttribute(node, 'dateTime'), `${relativePath}: time senza valore macchina`)
      }
    }
    ts.forEachChild(node, check)
  }
  check(sourceFile)
}
assert.match(shellSource, /<nav[^>]+aria-label=['"]Sezioni notifiche legali['"]/)
assert.match(read('src/features/notifiche-legali/components/PresidiTabs.tsx'), /<nav[^>]+aria-label=['"]Code dei presidi['"]/)
assert.match(pageSource, /aria-busy=['"]true['"]/)
assert.match(read('src/features/notifiche-legali/components/PresidiFilters.tsx'), /aria-label=['"]Cerca destinatario['"]/)
assert.ok(!read('src/features/notifiche-legali/PresidiNotifiche.css').match(/outline\s*:\s*(?:0|none)/i))

// Budget sorgenti: guardrail stretto sul nuovo perimetro, separato dal limite
// globale Vite da 500 KB. I margini consentono correzioni senza crescita muta.
const sourceBudgets = {
  'types.ts': [300, 15_000],
  'presentation.ts': [130, 9_000],
  'api/presidiApi.ts': [190, 12_000],
  'hooks/usePresidi.ts': [80, 6_500],
  'hooks/usePresidioDetail.ts': [110, 8_000],
  'components/PresidioActions.tsx': [230, 16_000],
  'PresidiNotifichePage.tsx': [280, 21_000],
  'NotificheLegaliPresidiShell.tsx': [120, 9_000],
  'components/PresidioEvidence.tsx': [90, 8_000],
  'components/PresidioDetailDrawer.tsx': [230, 18_000],
  'components/PresidiTabs.tsx': [60, 6_000],
  'components/PresidiFilters.tsx': [230, 17_000],
  'components/PresidiTable.tsx': [190, 14_000],
  'PresidiNotifiche.css': [360, 18_000],
}
let totalLines = 0
let totalBytes = 0
for (const [relativePath, [maxLines, maxBytes]] of Object.entries(sourceBudgets)) {
  const fullPath = resolve(featureRoot, relativePath)
  const source = readFileSync(fullPath, 'utf8')
  const lines = source.split(/\r?\n/).length
  const bytes = Buffer.byteLength(source)
  assert.ok(lines <= maxLines, `${relativePath}: ${lines} righe, budget ${maxLines}`)
  assert.ok(bytes <= maxBytes, `${relativePath}: ${bytes} byte, budget ${maxBytes}`)
  totalLines += lines
  totalBytes += bytes
}
assert.ok(totalLines <= 2_500, `Perimetro presidi: ${totalLines} righe, budget 2500`)
assert.ok(totalBytes <= 125_000, `Perimetro presidi: ${totalBytes} byte, budget 125000`)

console.log(`Presidi notifiche frontend verificati: ${totalLines} righe, ${totalBytes} byte, ${mutations.length} mutazioni.`)
