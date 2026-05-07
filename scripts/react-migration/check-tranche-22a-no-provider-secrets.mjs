import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const files = [
  'frontend/src/components/IncassiPagamentiPage.tsx',
  'frontend/src/incassiPagamentiData.ts',
  'web/services/react_incassi_pagamenti_bridge.py',
]
const forbidden = [
  /provider_secret/i,
  /webhook_secret/i,
  /client_secret/i,
  /api_key/i,
  /access_token/i,
  /refresh_token/i,
  /\bbearer\b/i,
  /stripe_secret/i,
  /paypal_secret/i,
  /satispay_key/i,
  /sumup_key/i,
  /card_number/i,
  /\bcvv\b/i,
  /\bpan\b/i,
  /fetch\s*\(\s*["']http/i,
  /requests\.post\s*\(\s*["']http/i,
  /requests\.get\s*\(\s*["']http/i,
]

const failures = []
for (const file of files) {
  const source = read(file)
  for (const pattern of forbidden) {
    if (pattern.test(source)) {
      failures.push(`${file}: contiene ${pattern}`)
    }
  }
}

if (failures.length) {
  console.error(['Tranche 22A provider/segreti KO', ...failures.map((item) => `- ${item}`)].join('\n'))
  process.exit(1)
}

console.log('Tranche 22A provider/segreti OK.')
