import { readFile, writeFile, unlink, mkdir } from 'node:fs/promises'
import { createHash, randomUUID } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputDir = path.resolve(appDir, '../web/static/react')
const bookDir = path.resolve(appDir, 'storybook-static')
const probeFile = path.join(bookDir, `iusentra-tailwind-probe-${randomUUID()}.html`)
if (path.dirname(probeFile) !== bookDir) throw new Error('Percorso della prova non valido')

function buildApp() {
  const result = spawnSync(process.execPath, [path.join(appDir, 'node_modules/vite/bin/vite.js'), 'build'],
    { cwd: appDir, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 })
  if (result.status !== 0) {
    process.stderr.write(result.stdout || '')
    process.stderr.write(result.stderr || '')
    throw new Error('Build Vite non riuscita durante la verifica degli artefatti')
  }
}

async function snapshot() {
  const manifestBytes = await readFile(path.join(outputDir, '.vite/manifest.json'))
  const manifest = JSON.parse(manifestBytes)
  const files = new Set(['.vite/manifest.json', 'index.html'])
  for (const entry of Object.values(manifest)) {
    for (const name of [entry.file, ...(entry.css || []), ...(entry.assets || [])]) {
      if (name) files.add(name)
    }
  }
  const result = {}
  for (const name of [...files].sort()) {
    const target = path.resolve(outputDir, name)
    if (!target.startsWith(outputDir + path.sep)) throw new Error('Artefatto fuori dalla cartella applicativa')
    result[name] = createHash('sha256').update(await readFile(target)).digest('hex')
  }
  return result
}

let created = false
try {
  buildApp()
  const before = await snapshot()
  await mkdir(bookDir, { recursive: true })
  const utility = ['bg-[#', randomUUID().replaceAll('-', '').slice(0, 6), ']'].join('')
  await writeFile(probeFile, `<section class="${utility}">Prova generata, estranea all'applicazione.</section>`, { flag: 'wx' })
  created = true
  buildApp()
  const after = await snapshot()
  const identical = JSON.stringify(before) === JSON.stringify(after)
  console.log(JSON.stringify({ artifacts: Object.keys(after).length, generatedStorybookDoesNotChangeApp: identical }))
  if (!identical) throw new Error('Gli output Storybook alterano CSS o asset della build applicativa')
} finally {
  if (created) await unlink(probeFile)
}
