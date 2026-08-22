import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
const sourceRoot = resolve(frontendRoot, 'src')
const storiesRoot = resolve(sourceRoot, 'stories', 'pages')

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolute = join(directory, entry.name)
    return entry.isDirectory() ? walk(absolute) : [absolute]
  })
}

const expectedSources = walk(sourceRoot)
  .filter((path) => path.endsWith('Page.tsx'))
  .map((path) => `src/${relative(sourceRoot, path).replaceAll('\\', '/')}`)
  .sort()

const storyFiles = walk(storiesRoot).filter((path) => path.endsWith('.stories.tsx'))
assert.ok(storyFiles.length >= 8, 'Storybook pagine: suddivisione per domini mancante')

const coverage = new Map()
for (const file of storyFiles) {
  const source = readFileSync(file, 'utf8')
  assert.match(source, /createPageStory/, `Storybook pagine: harness reale mancante in ${relative(frontendRoot, file)}`)
  for (const match of source.matchAll(/sourcePath: '([^']+Page\.tsx)'/g)) {
    const sourcePath = match[1]
    assert.ok(!coverage.has(sourcePath), `Storybook pagine: sorgente duplicato ${sourcePath}`)
    coverage.set(sourcePath, relative(frontendRoot, file).replaceAll('\\', '/'))
  }
}

const coveredSources = [...coverage.keys()].sort()
assert.deepEqual(coveredSources, expectedSources, 'Storybook pagine: matrice sorgenti incompleta o non allineata')

const harness = readFileSync(resolve(sourceRoot, 'stories', 'pageStory.tsx'), 'utf8')
assert.match(harness, /AppProviders/, 'Storybook pagine: provider applicativi assenti')
assert.match(harness, /installStorybookRuntime/, 'Storybook pagine: fixture runtime assenti')
assert.match(harness, /data-storybook-source/, 'Storybook pagine: tracciabilità sorgente assente')

console.log(`Storybook pagine verificato: ${coveredSources.length}/${expectedSources.length} superfici React, ${storyFiles.length} domini.`)
