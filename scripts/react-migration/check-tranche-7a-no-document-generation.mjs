import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-7a-no-document-generation.md')

const files = [
  'frontend/src/preventiviData.ts',
  'frontend/src/components/PreventiviPage.tsx',
  'web/services/react_preventivi_bridge.py',
]

const denied = [
  /docx/i,
  /pdf/i,
  /generateDocument/,
  /generatePdf/,
  /generateDocx/,
  /exportPdf/,
  /exportDocx/,
  /blob/i,
  /URL\.createObjectURL/,
  /application\/pdf/i,
  /application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document/i,
]

const violations = []

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  const lines = source.split(/\r?\n/)
  lines.forEach((line, index) => {
    for (const pattern of denied) {
      if (pattern.test(line)) {
        violations.push(`${file}:${index + 1}: contiene pattern documentale non ammesso "${pattern}"`)
      }
    }
  })
}

const report = [
  '# Tranche 7A anti-generazione documenti',
  '',
  `File scansionati: ${files.length}`,
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
  '',
].join('\n')

mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })
writeFileSync(reportPath, report, 'utf8')

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Tranche 7A anti-generazione documenti OK')
