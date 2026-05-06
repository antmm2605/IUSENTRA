import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-8a-secrets.md')

const files = [
  'web/services/react_compensi_forensi_bridge.py',
  'web/services/react_tariffario_bridge.py',
  'frontend/src/compensiForensiData.ts',
  'frontend/src/tariffarioData.ts',
  'frontend/src/components/CompensiForensiPage.tsx',
  'frontend/src/components/TariffarioPage.tsx',
]

const denied = [
  'api_key',
  'apikey',
  'secret',
  'password',
  'token',
  'private_key',
  'access_key',
  'refresh_token',
  'client_secret',
  'bearer',
  'fiscal_formula_secret',
  'document_template_raw',
  'docx_raw',
  'pdf_raw',
]

const violations = []

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  const lines = source.split(/\r?\n/)
  lines.forEach((line, index) => {
    for (const word of denied) {
      if (new RegExp(word, 'i').test(line)) {
        violations.push(`${file}:${index + 1}: contiene pattern non ammesso "${word}"`)
      }
    }
  })
}

const report = [
  '# Tranche 8A anti-segreti',
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

console.log('Tranche 8A anti-segreti OK')
