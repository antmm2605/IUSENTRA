import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, extname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const scriptDir = dirname(fileURLToPath(import.meta.url))
export const root = resolve(scriptDir, '../..')

export function repoPath(path) {
  return relative(root, path).split(sep).join('/')
}

export function read(path) {
  const full = resolve(root, path)
  return existsSync(full) && statSync(full).isFile() ? readFileSync(full, 'utf8') : ''
}

export function walk(dir, predicate, output = []) {
  const full = resolve(root, dir)
  if (!existsSync(full)) return output
  for (const entry of readdirSync(full)) {
    const path = join(full, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      walk(repoPath(path), predicate, output)
    } else if (predicate(path)) {
      output.push(repoPath(path))
    }
  }
  return output
}

export function manifest() {
  return JSON.parse(read('tools/react-migration/route-manifest.json'))
}

export function fullRoutes() {
  return (manifest().routes || []).filter((route) => route.status === 'react_operational_full')
}

export function routeComponentSource(route) {
  const primary = read(route.targetComponent || '')
  const delegated = read(route.actionComponent || '')
  const source = route.targetComponent === 'frontend/src/App.tsx'
    ? primary.replace(/<form className="iu-sidebar__logout-form" method="post" action=\{logoutAction\}>[\s\S]*?<\/form>/, '')
    : primary
  return delegated ? `${source}\n${delegated}` : source
}

export function routeSources(route) {
  return {
    component: routeComponentSource(route),
    data: read(route.targetData || ''),
    bridge: read(route.targetBridge || ''),
  }
}

export function failIf(violations, heading) {
  if (!violations.length) {
    console.log(`${heading}: OK`)
    return
  }
  console.error(`${heading}: ${violations.length} violazioni`)
  for (const violation of violations) console.error(`- ${violation}`)
  process.exit(1)
}

export function tsxFilesInNewReactSurface() {
  return [
    ...walk('frontend/src/app', (path) => ['.tsx', '.ts'].includes(extname(path))),
    ...walk('frontend/src/shell', (path) => ['.tsx', '.ts'].includes(extname(path))),
    ...walk('frontend/src/features', (path) => ['.tsx', '.ts'].includes(extname(path))),
    ...walk('frontend/src/ui', (path) => ['.tsx', '.ts'].includes(extname(path))),
  ]
}
