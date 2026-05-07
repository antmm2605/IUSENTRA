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
  'scaglione',
  'coefficiente',
  'moltiplicatore',
  'ivaRate',
  'cassaRate',
  'ritenutaRate',
  'Math.round',
  'toFixed',
  'generatePdf',
  'generatePDF',
  'generateDocx',
  'generateDOCX',
  'generateDocument',
  'createDocument',
  'exportPdf',
  'exportDocx',
  'new Blob',
  'URL.createObjectURL',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
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
  console.error(`Calcolo/documenti preventivi frontend rilevati:\n- ${violations.join('\n- ')}`)
  process.exit(1)
}
console.log('Tranche 20A no calculation or docs OK.')
