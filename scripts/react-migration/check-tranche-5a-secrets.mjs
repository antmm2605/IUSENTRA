import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-5a-secrets.md')

const files = [
  'web/services/react_studio_bridge.py',
  'web/services/react_amministrazione_bridge.py',
  'frontend/src/studioData.ts',
  'frontend/src/amministrazioneData.ts',
  'frontend/src/components/StudioPage.tsx',
  'frontend/src/components/AmministrazionePage.tsx',
]

const denylist = [
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
  'stripe_secret',
  'paypal_secret',
  'satispay_key',
  'sumup_key',
  'oauth_token',
]

const findings = []

for (const relativePath of files) {
  const absolutePath = resolve(root, relativePath)
  if (!existsSync(absolutePath)) {
    findings.push({ file: relativePath, pattern: 'missing', line: 0 })
    continue
  }
  const source = readFileSync(absolutePath, 'utf8')
  const lines = source.split(/\r?\n/)
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    for (const pattern of denylist) {
      if (new RegExp(pattern, 'i').test(line)) {
        findings.push({ file: relativePath, pattern, line: index + 1 })
      }
    }
  }
}

mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })
const reportLines = [
  '# Tranche 5A anti-segreti',
  '',
  `File controllati: ${files.length}`,
  '',
]

if (findings.length) {
  reportLines.push('## Violazioni', '')
  for (const finding of findings) {
    reportLines.push(`- ${finding.file}:${finding.line} contiene ${finding.pattern}`)
  }
} else {
  reportLines.push('Esito: OK, nessun pattern vietato nei nuovi file 5A.')
}

writeFileSync(reportPath, `${reportLines.join('\n')}\n`, 'utf8')

if (findings.length) {
  console.error(JSON.stringify({ ok: false, findings }, null, 2))
  process.exit(1)
}

console.log('Tranche 5A anti-segreti OK')
