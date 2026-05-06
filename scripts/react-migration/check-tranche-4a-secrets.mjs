import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const reportDir = resolve(root, 'artifacts/react-migration')
mkdirSync(reportDir, { recursive: true })

const files = [
  'web/services/react_backup_bridge.py',
  'web/services/react_sito_studio_bridge.py',
  'frontend/src/backupData.ts',
  'frontend/src/sitoStudioData.ts',
  'frontend/src/components/BackupPage.tsx',
  'frontend/src/components/SitoStudioPage.tsx',
]

const forbidden = [
  'api_key',
  'apikey',
  'secret',
  'password',
  'smtp_password',
  'pec_password',
  'token',
  'private_key',
  'access_key',
  'refresh_token',
  'client_secret',
  'bearer',
]

function lineFor(source, index) {
  return source.slice(0, index).split(/\r?\n/).length
}

const violations = []
for (const file of files) {
  const target = resolve(root, file)
  if (!existsSync(target)) {
    violations.push({ file, line: 0, pattern: 'file_missing' })
    continue
  }
  const source = readFileSync(target, 'utf8')
  for (const pattern of forbidden) {
    const regex = new RegExp(pattern, 'i')
    const match = source.match(regex)
    if (match?.index !== undefined) {
      violations.push({ file, line: lineFor(source, match.index), pattern })
    }
  }
}

const reportLines = [
  '# Tranche 4A anti-segreti',
  '',
  `File scansionati: ${files.length}`,
  `Violazioni: ${violations.length}`,
]

if (violations.length) {
  reportLines.push('', ...violations.map((item) => `- ${item.file}:${item.line} - ${item.pattern}`))
}

const report = `${reportLines.join('\n')}\n`

writeFileSync(resolve(reportDir, 'tranche-4a-secrets.md'), report)

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Tranche 4A anti-segreti OK')
