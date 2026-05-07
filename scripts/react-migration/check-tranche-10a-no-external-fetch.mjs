import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-10a-no-external-fetch.md')
mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })

const targets = [
  'web/services/react_giurisprudenza_bridge.py',
  'web/services/react_legal_intelligence_bridge.py',
  'frontend/src/giurisprudenzaData.ts',
  'frontend/src/legalIntelligenceData.ts',
  'frontend/src/components/GiurisprudenzaPage.tsx',
  'frontend/src/components/LegalIntelligencePage.tsx',
]

const denied = [
  'fetch("http',
  "fetch('http",
  'requests.get',
  'requests.post',
  'httpx.',
  'urllib.request',
  'BeautifulSoup',
  'bs4',
  'selenium',
  'playwright',
  'puppeteer',
  'crawler',
  'scraper',
  'scrape',
  'crawl',
  'external_fetch: true',
  '"external_fetch": True',
]

const violations = []
for (const target of targets) {
  const absolute = resolve(root, target)
  if (!existsSync(absolute)) {
    violations.push(`${target}: file mancante`)
    continue
  }
  const source = readFileSync(absolute, 'utf8')
  for (const pattern of denied) {
    if (source.includes(pattern)) {
      violations.push(`${target}: pattern non ammesso ${pattern}`)
    }
  }
}

const report = [
  '# Tranche 10A anti-fetch-esterno',
  '',
  `File controllati: ${targets.length}`,
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((item) => `- ${item}`),
  '',
].join('\n')

writeFileSync(reportPath, report, 'utf8')

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('Tranche 10A anti-fetch-esterno OK')
