import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(new URL('../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
const files = [
  'frontend/src/components/PreventiviPage.tsx',
  'frontend/src/preventiviData.ts',
]
const banned = [
  'generatePdf',
  'generatePDF',
  'generateDocx',
  'generateDOCX',
  'generateDocument',
  'createDocument',
  'exportPdf',
  'exportDocx',
  'new Blob',
  'URL.createObjectURL',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]
const violations = []
for (const file of files) {
  const content = readFileSync(resolve(root, file), 'utf8')
  for (const pattern of banned) {
    if (content.includes(pattern)) violations.push(`${file}: ${pattern}`)
  }
}
if (violations.length) {
  console.error(`Generazione documenti frontend rilevata:\n- ${violations.join('\n- ')}`)
  process.exit(1)
}
console.log('Tranche 19A no document generation OK.')
