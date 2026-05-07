import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(new URL('../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
const files = [
  'frontend/src/components/FatturazionePage.tsx',
  'frontend/src/fatturazioneData.ts',
]
const banned = [
  'calculateTotal',
  'calculateTax',
  'calculateIva',
  'calculateVat',
  'calculateCassa',
  'calculateRitenuta',
  'ivaRate',
  'cassaRate',
  'ritenutaRate',
  'aliquotaIva',
  'aliquotaCassa',
  'Math.round',
  'toFixed',
  'generatePdf',
  'generatePDF',
  'generateXml',
  'generateXML',
  'exportPdf',
  'exportXml',
  'new Blob',
  'URL.createObjectURL',
  'application/pdf',
  'application/xml',
  'text/xml',
]
const violations = []
for (const file of files) {
  const lines = readFileSync(resolve(root, file), 'utf8').split(/\r?\n/)
  lines.forEach((line, index) => {
    const allowed = /PDF|XML|pdfHref|xmlHref|Importo backend|numericInputValue|Number\.parseFloat/.test(line)
    if (allowed) return
    for (const pattern of banned) {
      if (line.includes(pattern)) violations.push(`${file}:${index + 1}: ${pattern}`)
    }
  })
}
if (violations.length) {
  console.error(`Calcolo/documenti fatturazione frontend rilevati:\n- ${violations.join('\n- ')}`)
  process.exit(1)
}
console.log('Tranche 21A no calculation or docs OK.')
