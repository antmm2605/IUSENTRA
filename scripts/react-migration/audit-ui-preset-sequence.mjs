import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const repoRoot = resolve(import.meta.dirname, '..', '..')

function read(path) {
  return readFileSync(resolve(repoRoot, path), 'utf8')
}

function fail(message) {
  throw new Error(`Audit preset sequenza IUSENTRA: ${message}`)
}

function assertContains(source, expected, label) {
  if (!source.includes(expected)) fail(`${label}: manca "${expected}"`)
}

function assertNotContains(source, unexpected, label) {
  if (source.includes(unexpected)) fail(`${label}: contiene ancora "${unexpected}"`)
}

const preset = read('frontend/src/components/iusentra/IusentraPreset.tsx')
const presetIndex = read('frontend/src/components/iusentra/index.ts')
const sectionHeader = read('frontend/src/components/iusentra/IusSectionHeader.tsx')
const css = read('frontend/src/styles/iusentra-design-system.css')
const app = read('frontend/src/App.tsx')
const docs = read('docs/UI_PRESET_IUSENTRA.md')
const visualAudit = read('scripts/react-migration/visual-load-audit.mjs')
const packageJson = JSON.parse(read('frontend/package.json'))

const sequence = [
  ['page-header', 'Header pagina'],
  ['operational-subtitle', 'Sottotitolo operativo'],
  ['primary-actions', 'Azioni principali'],
  ['filters', 'Filtri'],
  ['context-filters', 'Contesto filtri / riepilogo'],
  ['main-content', 'Contenuto principale'],
  ['pagination-footer', 'Paginazione / footer'],
  ['support-sidebar', 'Sidebar di supporto'],
]

assertContains(preset, 'IUSENTRA_PAGE_SEQUENCE', 'preset globale espone la sequenza canonica')
assertContains(preset, 'IUSENTRA_PAGE_SEQUENCE_VERSION', 'preset globale versiona la sequenza')
assertContains(preset, 'IUSENTRA_SEQUENCE_ROOT_SELECTORS', 'preset globale registra le radici sequenza')
assertContains(preset, "'.iusentra-main-area'", 'preset globale considera MainArea come radice della sequenza')
assertContains(preset, 'classifySequenceSlot', 'preset globale classifica gli slot pagina')
assertContains(preset, 'applyRouteSequencePreset', 'preset globale applica la sequenza alle rotte')
assertContains(preset, 'iusentraSequenceManaged', 'preset globale non cancella gli slot dichiarati dai componenti')
assertContains(preset, 'applySequencePart', 'preset globale promuove sottotitolo e azioni a slot verificabili')
assertContains(preset, "classifySequenceSlot(child) ?? 'main-content'", 'preset globale manda ogni blocco non riconosciuto nel contenuto principale')
assertContains(preset, '/(?:tabs|tablist|switcher)$/', 'preset globale tratta tab e selettori pagina come filtri')
assertContains(preset, '/(?:note|summary)$/', 'preset globale tratta note e riepiloghi come contesto')
assertContains(preset, 'applyRouteGridPreset(root)', 'preset globale conserva la griglia')
assertContains(preset, 'applyRouteSequencePreset(root)', 'frame globale applica anche la sequenza')
assertContains(preset, "route === '/sito-studio/builder'", 'builder resta escluso dal preset')
assertContains(app, 'IusentraRoutePresetFrame routeKey={routeKey} enabled={!isSitoStudioBuilderPage}', 'App avvolge tutte le rotte operative')
assertContains(app, "isSitoStudioBuilderPage?'excluded':'active'", 'App dichiara esclusione builder')
assertNotContains(app, 'enabled={false}', 'nessuna rotta operativa disattiva il preset')

for (const [slot, label] of sequence) {
  assertContains(preset, `'${slot}'`, `slot ${label} registrato nel preset`)
  assertContains(css, `data-iusentra-sequence-slot="${slot}"`, `CSS ordina ${label}`)
  assertContains(docs, label, `documentazione descrive ${label}`)
}

for (const order of ['order: 10', 'order: 20', 'order: 30', 'order: 40', 'order: 50', 'order: 60', 'order: 70', 'order: 80']) {
  assertContains(css, order, `ordine CSS ${order}`)
}
assertContains(css, '.iusentra-route-sequence > :not([data-iusentra-sequence-slot])', 'CSS fallback impedisce blocchi senza slot prima del titolo')
assertContains(css, 'section[class*="-hero"][data-iusentra-sequence-slot="page-header"]', 'CSS normalizza gli hero locali nel preset unico')
assertContains(visualAudit, 'sequenza_header_non_primo', 'audit browser blocca contenuto sopra al titolo')
assertContains(visualAudit, 'builder_preset_attivo', 'audit browser controlla esclusione builder')

for (const marker of [
  'data-iusentra-sequence-slot="page-header"',
  'data-iusentra-sequence-slot="operational-subtitle"',
  'data-iusentra-sequence-part="operational-subtitle"',
  'data-iusentra-sequence-slot="primary-actions"',
  'data-iusentra-sequence-part="primary-actions"',
]) {
  assertContains(sectionHeader, marker, `IusSectionHeader marca ${marker}`)
}

for (const marker of [
  'data-iusentra-sequence-slot="filters"',
  'data-iusentra-sequence-slot="context-filters"',
  'data-iusentra-sequence-slot="main-content"',
  'data-iusentra-sequence-slot="pagination-footer"',
  'data-iusentra-sequence-slot="support-sidebar"',
  'data-iusentra-sequence-slot="primary-actions"',
]) {
  assertContains(preset, marker, `primitive preset marcano ${marker}`)
}

assertContains(presetIndex, 'IUSENTRA_PAGE_SEQUENCE', 'export indice sequenza')
assertContains(presetIndex, 'IusentraPageSequenceSlot', 'export tipo slot sequenza')
assertContains(packageJson.scripts.test, 'audit-ui-preset-sequence.mjs', 'test frontend include audit sequenza preset')

console.log(`Audit preset sequenza IUSENTRA OK: ${sequence.length}/8 slot canonici governati, builder escluso.`)
