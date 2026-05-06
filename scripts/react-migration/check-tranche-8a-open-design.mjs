import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-8a-open-design-check.md')

const checks = [
  {
    file: 'frontend/src/theme/impeccable-open-design.css',
    required: [
      '--iu-od-space-',
      '--iu-od-radius-',
      '--iu-od-shadow-',
      '--iu-od-border',
      '--iu-od-surface',
      '--iu-od-focus',
      '.iu-od-focus-ring:focus-visible',
    ],
  },
  {
    file: 'frontend/src/ui/openDesign.ts',
    required: ['openDesignContract', 'classPrefix', 'iu-', 'nuove dipendenze UI'],
  },
  {
    file: 'frontend/src/components/CompensiForensiPage.css',
    required: ["@import '../theme/impeccable-open-design.css'", 'iu-comp-page', 'grid-template-columns'],
  },
  {
    file: 'frontend/src/components/TariffarioPage.css',
    required: ["@import '../theme/impeccable-open-design.css'", 'iu-tar-page', 'grid-template-columns'],
  },
  {
    file: 'artifacts/react-migration/tranche-8a-open-design.md',
    required: ['Impeccable / Open Design', 'Token creati', 'Nessuna formula economica in React'],
  },
]

const forbidden = [
  { pattern: /https:\/\/cdn\./i, label: 'CDN non consentito' },
  { pattern: /className=["'][^"']*\b(card|btn|row|col|container)\b/i, label: 'classe Bootstrap nei TSX' },
  { pattern: /href=["']#["']/, label: 'href placeholder' },
]

const violations = []

for (const check of checks) {
  const source = readFileSync(resolve(root, check.file), 'utf8')
  for (const token of check.required) {
    if (!source.includes(token)) {
      violations.push(`${check.file}: manca "${token}"`)
    }
  }
  for (const rule of forbidden) {
    if (rule.pattern.test(source)) {
      violations.push(`${check.file}: ${rule.label}`)
    }
  }
}

const report = [
  '# Tranche 8A Open Design check',
  '',
  `File scansionati: ${checks.length}`,
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

console.log('Tranche 8A Open Design OK')
