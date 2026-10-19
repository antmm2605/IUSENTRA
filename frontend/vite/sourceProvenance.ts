import { createHash } from 'node:crypto'
import { readFileSync, realpathSync, statSync, mkdirSync, writeFileSync, renameSync } from 'node:fs'
import { resolve, relative, isAbsolute, sep } from 'node:path'
import type { Plugin, ResolvedConfig } from 'vite'

type Digests = Record<string, string>
export type SourceProvenance = { schemaVersion: 1; sources: Digests; assets: Digests }
const proofName = '.vite/source-provenance.json'
const digest = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex')

function inside(root: string, path: string): string {
  if (!path || isAbsolute(path) || path.includes('\\') || path.includes(':') || path.split('/').includes('..')) throw new Error('Percorso di provenienza non valido.')
  const target = resolve(root, path)
  const actual = relative(realpathSync(root), realpathSync(target))
  if (actual === '..' || actual.startsWith(`..${sep}`) || isAbsolute(actual)) throw new Error('Provenienza fuori dal progetto.')
  return target
}

export function sourceDigest(bytes: Buffer): string {
  const text = bytes.toString('utf8')
  return digest(!bytes.includes(0) && Buffer.from(text).equals(bytes) ? Buffer.from(text.replace(/\r\n/g, '\n')) : bytes)
}

export function verifySourceProvenance(root: string, output: string, proof: SourceProvenance): string[] {
  if (proof?.schemaVersion !== 1 || !proof.sources || !proof.assets || !Object.keys(proof.sources).length || !Object.keys(proof.assets).length) throw new Error('Provenienza del bundle assente o incompleta.')
  const failures: string[] = []
  for (const [kind, folder, values] of [['source', root, proof.sources], ['asset', output, proof.assets]] as const) {
    for (const [name, expected] of Object.entries(values)) {
      if (!/^[a-f0-9]{64}$/.test(expected)) throw new Error('Impronta di provenienza non valida.')
      try {
        const bytes = readFileSync(inside(folder, name))
        if ((kind === 'source' ? sourceDigest(bytes) : digest(bytes)) !== expected) failures.push(`${kind}: ${name}`)
      } catch (error) {
        if (error instanceof Error && /fuori|non valido/.test(error.message)) throw error
        failures.push(`${kind}: ${name} (assente)`)
      }
    }
  }
  return failures
}

export function sourceProvenance(): Plugin {
  let config: ResolvedConfig
  let operational = false
  let sources: Digests = {}
  return {
    name: 'iusentra-source-provenance',
    apply: 'build',
    enforce: 'post',
    configResolved(value) {
      config = value
      operational = resolve(config.root, config.build.outDir) === resolve(config.root, '../web/static/react')
    },
    generateBundle() {
      if (!operational) return
      const root = realpathSync(resolve(config.root, '..'))
      const files = new Set<string>(['frontend/vite.config.ts', 'frontend/vite/sourceProvenance.ts', 'frontend/package.json', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml'])
      for (const id of this.getModuleIds()) {
        if (id.startsWith('\0')) continue
        const path = id.split('?')[0].replace(/^\/([A-Za-z]:\/)/, '$1')
        try {
          const absolute = realpathSync(path)
          const name = relative(root, absolute).split(sep).join('/')
          if (!name.startsWith('../') && !isAbsolute(name) && !name.startsWith('node_modules/') && !name.includes('/node_modules/') && statSync(absolute).isFile()) files.add(name)
        } catch { /* Moduli virtuali e dipendenze esterne non sono sorgenti del progetto. */ }
      }
      sources = Object.fromEntries([...files].sort().map(name => [name, sourceDigest(readFileSync(inside(root, name)))]))
    },
    writeBundle(_options, bundle) {
      if (!operational) return
      const output = resolve(config.root, config.build.outDir)
      const assets = Object.fromEntries([...new Set([...Object.keys(bundle), 'index.html', '.vite/manifest.json'])].filter(name => name !== proofName).sort().map(name => [name, digest(readFileSync(inside(output, name)))]))
      const proof: SourceProvenance = { schemaVersion: 1, sources, assets }
      const path = resolve(output, proofName)
      mkdirSync(resolve(output, '.vite'), { recursive: true })
      writeFileSync(`${path}.pending`, JSON.stringify(proof, null, 2) + '\n', { flush: true })
      renameSync(`${path}.pending`, path)
    },
  }
}
