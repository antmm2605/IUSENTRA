import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-9a-secrets.md')

const files = [
  'web/services/react_template_atti_bridge.py',
  'web/services/react_redazione_atti_bridge.py',
  'frontend/src/templateAttiData.ts',
  'frontend/src/redazioneAttiData.ts',
  'frontend/src/components/TemplateAttiPage.tsx',
  'frontend/src/components/RedazioneAttiPage.tsx',
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
  'template_raw',
  'document_raw',
  'html_raw',
  'pdf_raw',
  'docx_raw',
  'prompt_raw',
  'ai_output_raw',
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
  '# Tranche 9A anti-segreti documentali',
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

console.log('Tranche 9A anti-segreti OK')
