import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-6a-no-fiscal-logic.md')

const files = [
  'frontend/src/fatturazioneData.ts',
  'frontend/src/incassiPagamentiData.ts',
  'frontend/src/components/FatturazionePage.tsx',
  'frontend/src/components/IncassiPagamentiPage.tsx',
]

const denylist = [
  ['ivaRate', /ivaRate/i],
  ['aliquotaIva', /aliquotaIva/i],
  ['cassaRate', /cassaRate/i],
  ['aliquotaCassa', /aliquotaCassa/i],
  ['ritenutaRate', /ritenutaRate/i],
  ['calculateVat', /calculateVat/i],
  ['calculateIva', /calculateIva/i],
  ['calculateTax', /calculateTax/i],
  ['calculateTotal', /calculateTotal/i],
  ['imponibile *', /imponibile\s*\*/i],
  ['totale = imponibile', /totale\s*=\s*imponibile/i],
  ['Math.round', /Math\.round/i],
  ['toFixed', /\.toFixed\s*\(/i],
]

const findings = []

for (const relativePath of files) {
  const absolutePath = resolve(root, relativePath)
  if (!existsSync(absolutePath)) {
    findings.push({ file: relativePath, pattern: 'missing', line: 0 })
    continue
  }
  const source = readFileSync(absolutePath, 'utf8')
  const lines = source.split(/\r?\n/)
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    for (const [label, regex] of denylist) {
      if (regex.test(line)) {
        findings.push({ file: relativePath, pattern: label, line: index + 1 })
      }
    }
  }
}

mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })
const reportLines = [
  '# Tranche 6A anti-calcolo frontend',
  '',
  `File controllati: ${files.length}`,
  '',
]

if (findings.length) {
  reportLines.push('## Violazioni', '')
  for (const finding of findings) {
    reportLines.push(`- ${finding.file}:${finding.line} contiene ${finding.pattern}`)
  }
} else {
  reportLines.push('Esito: OK, nessuna logica fiscale canonica nei nuovi file React 6A.')
}

writeFileSync(reportPath, `${reportLines.join('\n')}\n`, 'utf8')

if (findings.length) {
  console.error(JSON.stringify({ ok: false, findings }, null, 2))
  process.exit(1)
}

console.log('Tranche 6A anti-calcolo OK')
