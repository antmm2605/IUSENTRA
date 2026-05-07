import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const files = [
  'frontend/src/components/AuditPage.tsx',
  'frontend/src/auditData.ts',
]
const forbidden = [
  /password_hash/i,
  /api_key/i,
  /access_token/i,
  /refresh_token/i,
  /stack_trace/i,
  /traceback/i,
  /dangerouslySetInnerHTML/,
  /localStorage/,
  /sessionStorage/,
  /URL\.createObjectURL/,
  /new Blob/,
]

const failures = []
for (const file of files) {
  const source = read(file)
  for (const pattern of forbidden) {
    if (pattern.test(source)) failures.push(`${file}: ${pattern}`)
  }
}

if (failures.length) {
  console.error(['Tranche 25A audit leak KO', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 25A audit leak OK.')
