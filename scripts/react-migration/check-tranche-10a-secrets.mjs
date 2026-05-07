import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-10a-secrets.md')
mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })

const targets = [
  'web/services/react_giurisprudenza_bridge.py',
  'web/services/react_legal_intelligence_bridge.py',
  'frontend/src/giurisprudenzaData.ts',
  'frontend/src/legalIntelligenceData.ts',
  'frontend/src/components/GiurisprudenzaPage.tsx',
  'frontend/src/components/LegalIntelligencePage.tsx',
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
  'prompt_raw',
  'ai_output_raw',
  'document_raw',
  'html_raw',
  'pdf_raw',
  'docx_raw',
  'source_credentials',
  'crawler_secret',
  'scraper_secret',
]

const violations = []
for (const target of targets) {
  const absolute = resolve(root, target)
  if (!existsSync(absolute)) {
    violations.push(`${target}: file mancante`)
    continue
  }
  const source = readFileSync(absolute, 'utf8')
  for (const word of denied) {
    if (new RegExp(word, 'i').test(source)) {
      violations.push(`${target}: pattern non ammesso ${word}`)
    }
  }
}

const report = [
  '# Tranche 10A anti-segreti',
  '',
  `File controllati: ${targets.length}`,
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
  '',
].join('\n')

writeFileSync(reportPath, report, 'utf8')

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Tranche 10A anti-segreti OK')
