import { readFile, readdir, stat, unlink } from 'node:fs/promises'
import { basename, dirname, resolve } from 'node:path'
import type { Plugin, ResolvedConfig } from 'vite'

type ManifestEntry = {
  file?: string
  css?: string[]
  assets?: string[]
}

const HASHED_ASSET = /-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$/
const MAX_PREEXISTING_ASSETS_TO_RETAIN = 400

function collectAssetNames(rawManifest: string): Set<string> {
  const manifest = JSON.parse(rawManifest) as Record<string, ManifestEntry>
  const names = new Set<string>()

  for (const entry of Object.values(manifest)) {
    for (const reference of [entry.file, ...(entry.css ?? []), ...(entry.assets ?? [])]) {
      if (reference?.replace(/\\/g, '/').startsWith('assets/')) {
        names.add(basename(reference))
      }
    }
  }

  return names
}

async function readManifestAssets(manifestPath: string): Promise<Set<string>> {
  try {
    return collectAssetNames(await readFile(manifestPath, 'utf8'))
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code
    if (code === 'ENOENT') return new Set()
    throw error
  }
}

export function pruneReactAssets(): Plugin {
  let config: ResolvedConfig
  let previousAssets = new Set<string>()

  return {
    name: 'iusentra-prune-react-assets',
    apply: 'build',
    configResolved(resolvedConfig) {
      config = resolvedConfig
    },
    async buildStart() {
      const manifestPath = resolve(config.build.outDir, '.vite', 'manifest.json')
      previousAssets = await readManifestAssets(manifestPath)

      const assetsDir = resolve(config.build.outDir, 'assets')
      try {
        const existingAssets = (await readdir(assetsDir, { withFileTypes: true }))
          .filter((entry) => entry.isFile() && HASHED_ASSET.test(entry.name))
        if (existingAssets.length <= MAX_PREEXISTING_ASSETS_TO_RETAIN) {
          for (const entry of existingAssets) previousAssets.add(entry.name)
        }
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code
        if (code !== 'ENOENT') throw error
      }
    },
    async closeBundle() {
      const outDir = resolve(config.build.outDir)
      const assetsDir = resolve(outDir, 'assets')
      const manifestPath = resolve(outDir, '.vite', 'manifest.json')
      const currentAssets = await readManifestAssets(manifestPath)

      if (currentAssets.size === 0) {
        throw new Error('Manifest React corrente vuoto: pulizia asset annullata.')
      }

      const protectedAssets = new Set([...previousAssets, ...currentAssets])
      const entries = await readdir(assetsDir, { withFileTypes: true })
      let removedFiles = 0
      let removedBytes = 0

      for (const entry of entries) {
        if (!entry.isFile() || protectedAssets.has(entry.name) || !HASHED_ASSET.test(entry.name)) continue

        const target = resolve(assetsDir, entry.name)
        if (dirname(target) !== assetsDir) {
          throw new Error(`Asset React fuori perimetro: ${target}`)
        }

        removedBytes += (await stat(target)).size
        await unlink(target)
        removedFiles += 1
      }

      if (removedFiles > 0) {
        config.logger.info(
          `Pulizia asset React: rimossi ${removedFiles} file obsoleti (${removedBytes} byte); `
          + `mantenuti bundle corrente e precedente.`,
        )
      }
    },
  }
}
