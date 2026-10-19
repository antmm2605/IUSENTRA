import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { verifySourceProvenance } from '../vite/sourceProvenance.ts'

const root = resolve(import.meta.dirname, '../..')
const output = resolve(root, 'web/static/react')
try {
  const proof = JSON.parse(readFileSync(resolve(output, '.vite/source-provenance.json'), 'utf8'))
  const failures = verifySourceProvenance(root, output, proof)
  if (failures.length) throw new Error(failures.slice(0, 20).join('\n'))
  console.log(`Bundle pubblicato concordante: ${Object.keys(proof.sources).length} sorgenti, ${Object.keys(proof.assets).length} asset.`)
} catch (error) {
  console.error('Bundle pubblicato non allineato. Esegui npm --prefix frontend run build:vite e verifica la copia reale prima del push.')
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = 1
}
