import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-7a-no-compensi-logic.md')

const files = [
  'frontend/src/preventiviData.ts',
  'frontend/src/components/PreventiviPage.tsx',
]

const denied = [
  /DM55/,
  /dm55/,
  /scaglione/i,
  /faseStudio/,
  /faseIntroduttiva/,
  /faseIstruttoria/,
  /faseDecisionale/,
  /valoreControversia/,
  /coefficiente/i,
  /moltiplicatore/i,
  /calculateCompenso/,
  /calculateFees/,
  /calculateOnorari/,
  /calculatePreventivo/,
  /aliquota/i,
  /cassaRate/,
  /ivaRate/,
  /ritenutaRate/,
  /Math\.round/,
  /\.toFixed\s*\(/,
  /importo\s*\*/,
  /totale\s*=\s*importo/,
  /compenso\s*=/,
]

const violations = []

for (const file of files) {
  const source = readFileSync(resolve(root, file), 'utf8')
  const lines = source.split(/\r?\n/)
  lines.forEach((line, index) => {
    for (const pattern of denied) {
      if (pattern.test(line)) {
        violations.push(`${file}:${index + 1}: contiene pattern di logica compensi "${pattern}"`)
      }
    }
  })
}

const report = [
  '# Tranche 7A anti-calcolo compensi frontend',
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

console.log('Tranche 7A anti-calcolo compensi OK')
