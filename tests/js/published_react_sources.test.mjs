import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, basename } from 'node:path'
import { createHash } from 'node:crypto'
import { sourceDigest, verifySourceProvenance, sourceProvenance } from '../../frontend/vite/sourceProvenance.ts'

function fixture(run) {
  const root = mkdtempSync(join(tmpdir(), 'iusentra-bundle-test-'))
  const output = join(root, 'public')
  mkdirSync(output)
  writeFileSync(join(root, 'page.tsx'), 'export const page = "current"\n')
  writeFileSync(join(output, 'page.js'), 'compiled-current')
  const proof = { schemaVersion: 1, sources: { 'page.tsx': sourceDigest(Buffer.from('export const page = "current"\n')) }, assets: { 'page.js': createHash('sha256').update('compiled-current').digest('hex') } }
  try { run({ root, output, proof }) }
  finally {
    assert.ok(basename(root).startsWith('iusentra-bundle-test-'))
    rmSync(root, { recursive: true, force: true })
  }
}

test('bundle e sorgenti concordanti', () => fixture(({root, output, proof}) => {
  assert.deepEqual(verifySourceProvenance(root, output, proof), [])
}))
test('nuova interfaccia e vecchio bundle: blocco prima del push', () => fixture(({root, output, proof}) => {
  writeFileSync(join(root, 'page.tsx'), 'export const page = "new-selection"\n')
  assert.deepEqual(verifySourceProvenance(root, output, proof), ['source: page.tsx'])
}))
test('asset alterato o mancante non passa con metadata invariati', () => fixture(({root, output, proof}) => {
  writeFileSync(join(output, 'page.js'), 'stale-compiled')
  assert.deepEqual(verifySourceProvenance(root, output, proof), ['asset: page.js'])
  rmSync(join(output, 'page.js'))
  assert.deepEqual(verifySourceProvenance(root, output, proof), ['asset: page.js (assente)'])
}))
test('provenienza incompleta o fuori progetto rifiutata', () => fixture(({root, output, proof}) => {
  assert.throws(() => verifySourceProvenance(root, output, { ...proof, sources: {} }), /incompleta/)
  assert.throws(() => verifySourceProvenance(root, output, { ...proof, sources: { '../outside': 'a'.repeat(64) } }), /non valido/)
}))
test('stessa sorgente con terminatori Windows e Linux mantiene la provenienza', () => {
  assert.equal(sourceDigest(Buffer.from('first\r\nsecond\r\n')), sourceDigest(Buffer.from('first\nsecond\n')))
  assert.notEqual(sourceDigest(Buffer.from([0, 13, 10])), sourceDigest(Buffer.from([0, 10])))
})


test('build isolate e Storybook non alterano la provenienza del bundle operativo', () => fixture(({root}) => {
  const plugin = sourceProvenance()
  plugin.configResolved({ root, build: { outDir: join(root, 'storybook-static') } })
  plugin.generateBundle.call({ getModuleIds() { throw new Error('Scansione non richiesta') } })
  plugin.writeBundle({}, {})
}))
