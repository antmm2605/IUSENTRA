import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-6a-secrets.md')

const files = [
  'web/services/react_fatturazione_bridge.py',
  'web/services/react_incassi_pagamenti_bridge.py',
  'frontend/src/fatturazioneData.ts',
  'frontend/src/incassiPagamentiData.ts',
  'frontend/src/components/FatturazionePage.tsx',
  'frontend/src/components/IncassiPagamentiPage.tsx',
]

const denylist = [
  ['api_key', /api_key/i],
  ['apikey', /apikey/i],
  ['secret', /secret/i],
  ['password', /password/i],
  ['token', /token/i],
  ['private_key', /private_key/i],
  ['access_key', /access_key/i],
  ['refresh_token', /refresh_token/i],
  ['client_secret', /client_secret/i],
  ['bearer', /bearer/i],
  ['stripe_secret', /stripe_secret/i],
  ['stripe_key', /stripe_key/i],
  ['paypal_secret', /paypal_secret/i],
  ['paypal_client_secret', /paypal_client_secret/i],
  ['satispay_key', /satispay_key/i],
  ['sumup_key', /sumup_key/i],
  ['webhook_secret', /webhook_secret/i],
  ['iban_raw', /iban_raw/i],
  ['card_number', /card_number/i],
  ['pan', /(^|[^a-z0-9_])pan([^a-z0-9_]|$)/i],
  ['cvv', /(^|[^a-z0-9_])cvv([^a-z0-9_]|$)/i],
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
    for (const [label, regex] of denylist) {
      if (regex.test(line)) {
        findings.push({ file: relativePath, pattern: label, line: index + 1 })
      }
    }
  }
}

mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })
const reportLines = [
  '# Tranche 6A anti-segreti economici',
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
  reportLines.push('Esito: OK, nessun pattern vietato nei nuovi file 6A.')
}

writeFileSync(reportPath, `${reportLines.join('\n')}\n`, 'utf8')

if (findings.length) {
  console.error(JSON.stringify({ ok: false, findings }, null, 2))
  process.exit(1)
}

console.log('Tranche 6A anti-segreti OK')
