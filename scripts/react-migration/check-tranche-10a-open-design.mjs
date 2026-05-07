import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const reportPath = resolve(root, 'artifacts/react-migration/tranche-10a-open-design-check.md')
mkdirSync(resolve(root, 'artifacts/react-migration'), { recursive: true })

const files = {
  tokenCss: 'frontend/src/theme/impeccable-open-design.css',
  contract: 'frontend/src/ui/openDesign.ts',
  giurisprudenzaTsx: 'frontend/src/components/GiurisprudenzaPage.tsx',
  giurisprudenzaCss: 'frontend/src/components/GiurisprudenzaPage.css',
  legalTsx: 'frontend/src/components/LegalIntelligencePage.tsx',
  legalCss: 'frontend/src/components/LegalIntelligencePage.css',
}

function read(path) {
  const absolute = resolve(root, path)
  if (!existsSync(absolute)) {
    throw new Error(`${path}: file mancante`)
  }
  return readFileSync(absolute, 'utf8')
}

const sources = Object.fromEntries(Object.entries(files).map(([key, path]) => [key, read(path)]))
const violations = []

function checkTsx(source, label) {
  if (source.includes('style={{')) violations.push(`${label}: stili inline vietati`)
  if (/#[0-9A-Fa-f]{3,8}\b/.test(source)) violations.push(`${label}: colore hex hardcoded`)
  if (source.includes('href="#"')) violations.push(`${label}: href vuoto`)
  for (const match of source.matchAll(/className\s*=\s*["'`]([^"'`]+)["'`]/g)) {
    checkClassTokens(match[1], label)
  }
  for (const match of source.matchAll(/className\s*=\s*\{([^}]+)\}/g)) {
    for (const literal of match[1].matchAll(/["'`]([^"'`]+)["'`]/g)) {
      if (literal[1].includes('iu-')) {
        checkClassTokens(literal[1], label)
      }
    }
  }
}

function checkClassTokens(value, label) {
  const tokens = value.split(/\s+/).filter(Boolean)
  for (const token of tokens) {
    if (['btn', 'card', 'container', 'row'].includes(token) || token.startsWith('col-')) {
      violations.push(`${label}: classe Bootstrap vietata ${token}`)
    }
    if (!token.startsWith('iu-')) {
      violations.push(`${label}: classe non prefissata iu- ${token}`)
    }
  }
}

function checkCss(source, label, allowTokenValues = false) {
  if (!allowTokenValues && /#[0-9A-Fa-f]{3,8}\b/.test(source)) {
    violations.push(`${label}: colore hex fuori dal file token`)
  }
  if (source.includes('!important')) violations.push(`${label}: !important non documentato`)
  if (/position\s*:\s*fixed\b/i.test(source)) violations.push(`${label}: position fixed non ammesso`)
  const zMatches = [...source.matchAll(/z-index\s*:\s*(\d+)/gi)]
  for (const match of zMatches) {
    if (Number.parseInt(match[1], 10) > 20) {
      violations.push(`${label}: z-index superiore alla shell`)
    }
  }
  if (/font-family\s*:\s*(?!\s*var\()/i.test(source)) violations.push(`${label}: font-family hardcoded`)
  if (!allowTokenValues && /box-shadow\s*:\s*(?!\s*var\()/i.test(source)) violations.push(`${label}: box-shadow hardcoded`)
  if (!allowTokenValues && /border-radius\s*:\s*(?!\s*var\()/i.test(source)) violations.push(`${label}: border-radius hardcoded`)
  for (const pattern of ['@font-face', 'fonts.googleapis', 'fonts.gstatic', 'cdn.jsdelivr', 'unpkg.com']) {
    if (source.includes(pattern)) violations.push(`${label}: import esterno ${pattern}`)
  }
}

checkTsx(sources.giurisprudenzaTsx, files.giurisprudenzaTsx)
checkTsx(sources.legalTsx, files.legalTsx)
checkCss(sources.tokenCss, files.tokenCss, true)
checkCss(sources.giurisprudenzaCss, files.giurisprudenzaCss)
checkCss(sources.legalCss, files.legalCss)
checkCss(sources.contract, files.contract, true)

for (const expected of [
  '--iu-od-source-gap',
  '--iu-od-source-card-radius',
  '--iu-od-source-meta-size',
  '--iu-od-source-focus-ring',
  '--iu-od-evidence-border',
  '--iu-od-evidence-surface',
  '.iu-od-source-card',
  '.iu-od-source-meta',
  '.iu-od-source-badge',
  '.iu-od-evidence-panel',
  '.iu-od-inference-warning',
  '.iu-od-legal-list',
  '.iu-od-action-row',
]) {
  if (!sources.tokenCss.includes(expected)) violations.push(`${files.tokenCss}: manca ${expected}`)
}
if (!sources.contract.includes('openDesignLegalKnowledgeSurface')) {
  violations.push(`${files.contract}: manca contratto legal knowledge`)
}
if (!sources.giurisprudenzaTsx.includes('iu-legal-evidence-row') || !sources.legalTsx.includes('iu-li-evidence-row')) {
  violations.push('Sezioni fonte/inferenza senza classi distinguibili nei TSX')
}
if (!sources.giurisprudenzaCss.includes('.iu-legal-evidence-row') || !sources.legalCss.includes('.iu-li-evidence-row')) {
  violations.push('Sezioni fonte/inferenza senza classi distinguibili nei CSS')
}

const report = [
  '# Tranche 10A Open Design check',
  '',
  `File controllati: ${Object.keys(files).length}`,
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

console.log('Tranche 10A Open Design OK')
