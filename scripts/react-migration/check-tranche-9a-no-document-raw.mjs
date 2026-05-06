import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-9a-no-document-raw.md')

const files = [
  'web/services/react_template_atti_bridge.py',
  'web/services/react_redazione_atti_bridge.py',
  'frontend/src/templateAttiData.ts',
  'frontend/src/redazioneAttiData.ts',
  'frontend/src/components/TemplateAttiPage.tsx',
  'frontend/src/components/RedazioneAttiPage.tsx',
]

const denied = [
  'dangerouslySetInnerHTML',
  'contentEditable',
  'templateBody',
  'templateHtml',
  'bodyHtml',
  'rawHtml',
  'rawText',
  'documentText',
  'documentHtml',
  'attoCompleto',
  'testoAtto',
  'bozzaAtto',
  'legalDraft',
  'generatedText',
  'promptText',
  'aiPrompt',
  'aiResponse',
  'new Blob',
  'URL.createObjectURL',
  'FileReader',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

const violations = []

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  const lines = source.split(/\r?\n/)
  lines.forEach((line, index) => {
    for (const word of denied) {
      if (line.includes(word)) {
        violations.push(`${file}:${index + 1}: contiene contenuto documentale non ammesso "${word}"`)
      }
    }
  })
}

const report = [
  '# Tranche 9A anti-document raw',
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

console.log('Tranche 9A anti-document raw OK')
