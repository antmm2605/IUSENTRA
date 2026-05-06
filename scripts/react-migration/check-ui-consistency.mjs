import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = resolve(scriptDir, '../..')
const src = resolve(root, 'frontend/src')
const reportDir = resolve(root, 'artifacts/react-migration')
mkdirSync(reportDir, { recursive: true })

const classPolicy = JSON.parse(readFileSync(resolve(root, 'tools/react-migration/ui-allowed-classes.json'), 'utf8'))
const forbiddenTokens = new Set(classPolicy.forbiddenBootstrapTokens ?? [])
const forbiddenPrefixes = classPolicy.forbiddenBootstrapPrefixes ?? []

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

function rel(path) {
  return path.replace(root + sep, '').replaceAll(sep, '/')
}

function lineFor(source, index) {
  return source.slice(0, index).split(/\r?\n/).length
}

function checkClassName(file, source, violations) {
  const classRegex = /className\s*=\s*["']([^"']+)["']/g
  for (const match of source.matchAll(classRegex)) {
    const tokens = match[1].split(/\s+/).filter(Boolean)
    for (const token of tokens) {
      if (forbiddenTokens.has(token) || forbiddenPrefixes.some((prefix) => token.startsWith(prefix))) {
        violations.push({
          file: rel(file),
          line: lineFor(source, match.index ?? 0),
          rule: `classe Bootstrap vietata: ${token}`,
        })
      }
    }
  }
}

const files = walk(src).filter((path) => /\.(tsx|ts|css)$/.test(path))
const violations = []

for (const file of files) {
  const source = readFileSync(file, 'utf8')
  if (/\.(tsx|ts)$/.test(file)) {
    checkClassName(file, source, violations)
  }
  for (const rule of [
    { regex: /href=["']#["']/, label: 'href placeholder #' },
    { regex: /https:\/\/cdn\.jsdelivr\.net/, label: 'CDN jsdelivr non consentito' },
    { regex: /https:\/\/esm\.sh/, label: 'CDN esm.sh non consentito' },
    { regex: /mockResults/, label: 'mockResults non consentito' },
    { regex: /TODO:?\s*mock/i, label: 'TODO mock non consentito' },
  ]) {
    const match = source.match(rule.regex)
    if (match?.index !== undefined) {
      violations.push({
        file: rel(file),
        line: lineFor(source, match.index),
        rule: rule.label,
      })
    }
  }
}

const report = [
  '# UI consistency report',
  '',
  `File scansionati: ${files.length}`,
  `Violazioni: ${violations.length}`,
  '',
  ...violations.map((violation) => `- ${violation.file}:${violation.line} - ${violation.rule}`),
].join('\n').trimEnd() + '\n'

writeFileSync(resolve(reportDir, 'ui-consistency.md'), report)

if (violations.length) {
  console.error(report)
  process.exit(1)
}

console.log('UI consistency OK')
