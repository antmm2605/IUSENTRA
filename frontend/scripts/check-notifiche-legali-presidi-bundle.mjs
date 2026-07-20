import assert from 'node:assert/strict'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
const outputRoot = resolve(frontendRoot, '../web/static/react')
const manifestPath = resolve(outputRoot, '.vite/manifest.json')

assert.ok(
  existsSync(manifestPath),
  'Manifest Vite assente: esegui prima `npm --prefix frontend run build:vite`.',
)

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
const entryKey = 'index.html'
const shellKey = 'src/features/notifiche-legali/NotificheLegaliPresidiShell.tsx'
const detailKey = 'src/features/notifiche-legali/components/PresidioDetailDrawer.tsx'
const legacyKey = 'src/components/NotificheLegaliPage.tsx'

function entryRecord(key, expectedName = '') {
  const direct = manifest[key]
  if (direct) return { key, value: direct }
  const found = Object.entries(manifest).find(([, value]) => (
    value?.src === key || (expectedName && value?.name === expectedName)
  ))
  assert.ok(found, `Manifest Vite: entry mancante ${key}`)
  return { key: found[0], value: found[1] }
}

function entry(key, expectedName = '') {
  return entryRecord(key, expectedName).value
}

function edges(value) {
  return [...(value.imports || []), ...(value.dynamicImports || [])]
}

function assetBytes(fileName) {
  const fullPath = resolve(outputRoot, fileName)
  assert.ok(existsSync(fullPath), `Asset dichiarato ma assente: ${fileName}`)
  return statSync(fullPath).size
}

const appEntry = entry(entryKey)
const shellRecord = entryRecord(shellKey, 'NotificheLegaliPresidiShell')
const shellEntry = shellRecord.value
const detailEntry = entry(detailKey)
const legacyEntry = entry(legacyKey)

assert.equal(shellEntry.isDynamicEntry, true, 'La shell presidi deve restare un chunk dinamico')
assert.equal(detailEntry.isDynamicEntry, true, 'Il dettaglio deve restare lazy e separato')
assert.equal(legacyEntry.isDynamicEntry, true, 'La pagina operativa legacy deve restare lazy')
assert.ok((appEntry.dynamicImports || []).includes(shellRecord.key), 'Entry app senza import dinamico della shell')
assert.ok((appEntry.dynamicImports || []).includes(legacyKey), 'Entry app senza import dinamico legacy')
assert.ok(!(appEntry.imports || []).includes(shellRecord.key), 'La shell presidi è entrata nel bundle iniziale')
assert.ok(!(appEntry.imports || []).includes(legacyKey), 'La pagina legacy è entrata nel bundle iniziale')

assert.ok(!edges(shellEntry).includes(legacyKey), 'Il chunk presidi carica eager il legacy')
assert.ok(!edges(legacyEntry).includes(shellRecord.key), 'Il chunk legacy carica il nuovo presidio')
assert.ok(!edges(legacyEntry).includes(detailKey), 'Il chunk legacy carica il dettaglio presidi')
assert.ok((shellEntry.dynamicImports || []).includes(detailKey), 'Il drawer dettaglio non è più lazy')

const jsBudgets = new Map([
  [shellKey, 120_000],
  [detailKey, 90_000],
])
let totalJs = 0
for (const [key, maxBytes] of jsBudgets) {
  const value = key === shellKey ? shellEntry : entry(key)
  const bytes = assetBytes(value.file)
  assert.ok(bytes <= maxBytes, `${value.file}: ${bytes} byte, budget ${maxBytes}`)
  totalJs += bytes
}
assert.ok(totalJs <= 170_000, `Chunk JS presidi: ${totalJs} byte, budget combinato 170000`)

const cssFiles = new Set([
  ...(shellEntry.css || []),
  ...(detailEntry.css || []),
])
let totalCss = 0
for (const fileName of cssFiles) totalCss += assetBytes(fileName)
assert.ok(totalCss <= 45_000, `CSS presidi: ${totalCss} byte, budget 45000`)

console.log(`Bundle presidi verificato: JS ${totalJs} byte, CSS ${totalCss} byte, legacy separato.`)
