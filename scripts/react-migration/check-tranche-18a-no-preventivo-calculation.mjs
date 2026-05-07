import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(new URL('../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
const files = [
  'frontend/src/components/PreventiviPage.tsx',
  'frontend/src/preventiviData.ts',
]
const banned = [
  'calculateCompenso',
  'calculatePreventivo',
  'calculateTotal',
  'calculateTax',
  'calculateIva',
  'calculateVat',
  'calculateCassa',
  'calculateRitenuta',
  'dm55',
  'DM55',
  'scaglione',
  'coefficiente',
  'moltiplicatore',
  'ivaRate',
  'aliquotaIva',
  'cassaRate',
  'aliquotaCassa',
  'ritenutaRate',
  'Math.round',
  'toFixed',
  'totale =',
  'netto =',
  'iva = imponibile',
  'cassa = imponibile',
]
const violations = []
for (const file of files) {
  const lines = readFileSync(resolve(root, file), 'utf8').split(/\r?\n/)
  lines.forEach((line, index) => {
    const allowed = /dm55_calculation|parametri forensi|importi finali|Importo backend|numericInputValue|Number\.parseFloat/.test(line)
    if (allowed) return
    for (const pattern of banned) {
      if (line.includes(pattern)) violations.push(`${file}:${index + 1}: ${pattern}`)
    }
  })
}
if (violations.length) {
  console.error(`Calcolo preventivo frontend rilevato:\n- ${violations.join('\n- ')}`)
  process.exit(1)
}
console.log('Tranche 18A no preventivo calculation OK.')
