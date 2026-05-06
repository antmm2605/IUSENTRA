import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-9a-no-legal-generation.md')

const files = [
  'frontend/src/templateAttiData.ts',
  'frontend/src/redazioneAttiData.ts',
  'frontend/src/components/TemplateAttiPage.tsx',
  'frontend/src/components/RedazioneAttiPage.tsx',
  'web/services/react_template_atti_bridge.py',
  'web/services/react_redazione_atti_bridge.py',
]

const denied = [
  /generateAtto/,
  /generateLegal/,
  /generateDraft/,
  /generateTemplate/,
  /composeAtto/,
  /composeLegal/,
  /redigiAtto/,
  /redazioneAutomatica/,
  /promptLex/,
  /promptAI/,
  /callLex/,
  /fetchLex/,
  /OpenAI/,
  /ChatCompletion/,
  /SAMPLE_ATTO/,
  /MOCK_ATTO/,
  /DEMO_ATTO/,
  /atto di citazione.+[.;:]/i,
  /comparsa di costituzione.+[.;:]/i,
  /ricorso.+testo documento/i,
  /diffida.+testo documento/i,
  /costituzione in giudizio.+testo documento/i,
]

const violations = []

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  const lines = source.split(/\r?\n/)
  lines.forEach((line, index) => {
    for (const pattern of denied) {
      if (pattern.test(line)) {
        violations.push(`${file}:${index + 1}: contiene pattern redazionale non ammesso "${pattern}"`)
      }
    }
  })
}

const report = [
  '# Tranche 9A anti-legal-generation',
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

console.log('Tranche 9A anti-legal-generation OK')
