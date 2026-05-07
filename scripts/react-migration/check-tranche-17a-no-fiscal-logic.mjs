import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const artifactDir = resolve(root, 'artifacts/react-migration')
mkdirSync(artifactDir, { recursive: true })

const files = [
  'frontend/src/components/FatturazionePage.tsx',
  'frontend/src/fatturazioneData.ts',
]

const forbidden = [
  ['calculateVat', /calculateVat/i],
  ['calculateIva', /calculateIva/i],
  ['calculateTax', /calculateTax/i],
  ['calculateTotal', /calculateTotal/i],
  ['ivaRate', /ivaRate/i],
  ['aliquotaIva', /aliquotaIva/i],
  ['cassaRate', /cassaRate/i],
  ['aliquotaCassa', /aliquotaCassa/i],
  ['ritenutaRate', /ritenutaRate/i],
  ['Math.round', /Math\.round/],
  ['toFixed', /\.toFixed\s*\(/],
  ['totale =', /\btotale\s*=/i],
  ['netto =', /\bnetto\s*=/i],
  ['iva = imponibile', /\biva\s*=\s*imponibile/i],
  ['cassa = imponibile', /\bcassa\s*=\s*imponibile/i],
]

const failures = []

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  for (const [label, pattern] of forbidden) {
    if (pattern.test(source)) {
      failures.push(`${file}: trovato pattern vietato "${label}"`)
    }
  }
}

const md = [
  '# Check tranche 17A no fiscal logic',
  '',
  `Generato: ${new Date().toISOString()}`,
  '',
  `File scansionati: ${files.join(', ')}`,
  '',
  `Violazioni: ${failures.length}`,
  '',
  ...(failures.length ? failures.map((item) => `- ${item}`) : ['Nessun calcolo fiscale canonico nel frontend della tranche.']),
  '',
].join('\n')

writeFileSync(resolve(artifactDir, 'tranche-17a-no-fiscal-logic.md'), md)

if (failures.length) {
  console.error(md)
  process.exit(1)
}

console.log('Tranche 17A no fiscal logic OK.')
