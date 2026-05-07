import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const files = [
  'frontend/src/components/CompensiForensiPage.tsx',
  'frontend/src/compensiForensiData.ts',
]
const forbidden = [
  /calculateTotal/,
  /calculateCompenso/,
  /calculateOnorari/,
  /calculateDM55/,
  /computeDM55/,
  /computeCompenso/,
  /computeOnorari/,
  /dm55Table/,
  /scaglione/,
  /coefficiente/,
  /moltiplicatore/,
  /faseStudioValue/,
  /faseIntroduttivaValue/,
  /faseIstruttoriaValue/,
  /faseDecisionaleValue/,
  /ivaRate/,
  /cassaRate/,
  /ritenutaRate/,
  /Math\.round/,
  /\.toFixed\s*\(/,
  /compenso\s*=/,
  /totale\s*=/,
  /onorario\s*=/,
]

const failures = []
for (const file of files) {
  const source = read(file).replace(/calculateCompensiForensi/g, 'backendCalculationCall')
  for (const pattern of forbidden) {
    if (pattern.test(source)) failures.push(`${file}: ${pattern}`)
  }
}

if (failures.length) {
  console.error(['Tranche 23A no frontend calculation KO', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 23A no frontend calculation OK.')
