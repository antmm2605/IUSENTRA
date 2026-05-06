import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-9a-open-design-check.md')

const files = [
  'frontend/src/theme/impeccable-open-design.css',
  'frontend/src/ui/openDesign.ts',
  'frontend/src/components/TemplateAttiPage.tsx',
  'frontend/src/components/TemplateAttiPage.css',
  'frontend/src/components/RedazioneAttiPage.tsx',
  'frontend/src/components/RedazioneAttiPage.css',
]

const required = [
  ['frontend/src/theme/impeccable-open-design.css', '--iu-od-doc-gap'],
  ['frontend/src/theme/impeccable-open-design.css', '--iu-od-doc-card-radius'],
  ['frontend/src/theme/impeccable-open-design.css', '--iu-od-doc-section-gap'],
  ['frontend/src/theme/impeccable-open-design.css', '--iu-od-doc-meta-size'],
  ['frontend/src/theme/impeccable-open-design.css', '--iu-od-doc-focus-ring'],
  ['frontend/src/theme/impeccable-open-design.css', '.iu-od-card'],
  ['frontend/src/theme/impeccable-open-design.css', '.iu-od-warning'],
  ['frontend/src/theme/impeccable-open-design.css', '.iu-od-action-row'],
  ['frontend/src/ui/openDesign.ts', 'openDesignDocumentSurface'],
  ['frontend/src/components/TemplateAttiPage.css', "impeccable-open-design.css"],
  ['frontend/src/components/RedazioneAttiPage.css', "impeccable-open-design.css"],
]

const violations = []

function lineFor(source, index) {
  return source.slice(0, index).split(/\r?\n/).length
}

function checkClassNames(file, source) {
  const classRegex = /className\s*=\s*(?:["']([^"']+)["']|\{`([^`]+)`\})/g
  for (const match of source.matchAll(classRegex)) {
    const value = match[1] || match[2] || ''
    const tokens = value.split(/\s+/).filter(Boolean).map((item) => item.replace(/\$\{[^}]+\}/g, '').trim()).filter(Boolean)
    for (const className of tokens) {
      if (['btn', 'card', 'container', 'row'].includes(className) || className.startsWith('col-')) {
        violations.push(`${file}:${lineFor(source, match.index ?? 0)}: classe Bootstrap vietata "${className}"`)
      }
      if (!className.startsWith('iu-')) {
        violations.push(`${file}:${lineFor(source, match.index ?? 0)}: classe non prefissata iu- "${className}"`)
      }
    }
  }
}

for (const [file, needle] of required) {
  const source = readFileSync(resolve(root, file), 'utf8')
  if (!source.includes(needle)) {
    violations.push(`${file}: manca "${needle}"`)
  }
}

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  if (file.endsWith('.tsx')) {
    checkClassNames(file, source)
    for (const rule of [
      { pattern: /style=\{\{/, label: 'inline style vietato' },
      { pattern: /#[0-9a-fA-F]{3,8}\b/, label: 'colore hex vietato nei TSX' },
      { pattern: /https?:\/\/.*(?:cdn|fonts)\./i, label: 'CDN o font esterno vietato' },
    ]) {
      const match = source.match(rule.pattern)
      if (match?.index !== undefined) {
        violations.push(`${file}:${lineFor(source, match.index)}: ${rule.label}`)
      }
    }
  }
  if (file.endsWith('.css') && file !== 'frontend/src/theme/impeccable-open-design.css') {
    for (const rule of [
      { pattern: /#[0-9a-fA-F]{3,8}\b/, label: 'colore hex vietato fuori dai token' },
      { pattern: /!important/, label: 'important non documentato' },
      { pattern: /position\s*:\s*fixed/i, label: 'position fixed non documentato' },
      { pattern: /z-index\s*:\s*(?:[2-9]\d{2,}|\d{4,})/i, label: 'z-index elevato non documentato' },
      { pattern: /font-family\s*:/i, label: 'font-family hardcoded fuori dai token' },
      { pattern: /box-shadow\s*:(?!\s*var\()/i, label: 'box-shadow hardcoded fuori dai token' },
      { pattern: /border-radius\s*:(?!\s*var\()/i, label: 'border-radius hardcoded fuori dai token' },
      { pattern: /\.iu-shell\b/, label: 'duplicazione regole shell globale' },
      { pattern: /\.iu-sidebar\b/, label: 'duplicazione regole sidebar globale' },
    ]) {
      const match = source.match(rule.pattern)
      if (match?.index !== undefined) {
        violations.push(`${file}:${lineFor(source, match.index)}: ${rule.label}`)
      }
    }
  }
}

const report = [
  '# Tranche 9A Open Design check',
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

console.log('Tranche 9A Open Design OK')
