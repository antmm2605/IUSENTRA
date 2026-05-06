import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-9a-no-document-generation.md')

const files = [
  'frontend/src/templateAttiData.ts',
  'frontend/src/redazioneAttiData.ts',
  'frontend/src/components/TemplateAttiPage.tsx',
  'frontend/src/components/RedazioneAttiPage.tsx',
  'web/services/react_template_atti_bridge.py',
  'web/services/react_redazione_atti_bridge.py',
]

const denied = [
  /generateDocument/,
  /generatePdf/,
  /generateDocx/,
  /exportPdf/,
  /exportDocx/,
  /renderDocx/,
  /renderPdf/,
  /\bblob\b/i,
  /URL\.createObjectURL/,
  /application\/pdf/i,
  /application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document/i,
  /pdf_raw/i,
  /docx_raw/i,
  /template_raw/i,
  /html_to_pdf/i,
  /docx_template/i,
]

const violations = []

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  const lines = source.split(/\r?\n/)
  lines.forEach((line, index) => {
    for (const pattern of denied) {
      if (pattern.test(line)) {
        violations.push(`${file}:${index + 1}: contiene pattern di produzione file non ammesso "${pattern}"`)
      }
    }
  })
}

const report = [
  '# Tranche 9A anti-generazione documenti',
  '',
  `File scansionati: ${files.length}`,
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
].join('\n').trimEnd() + '\n'

mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })
writeFileSync(reportPath, report, 'utf8')

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Tranche 9A anti-generazione documenti OK')
