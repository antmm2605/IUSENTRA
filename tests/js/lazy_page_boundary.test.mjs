import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { assertLazyPageBoundary } from '../../frontend/vite/lazyPageBoundary.ts'
import appConfig from '../../frontend/vite.config.ts'
import storybookConfig from '../../frontend/.storybook/main.ts'

const chunk = (fileName, extra = {}) => ({ type: 'chunk', fileName, imports: [], ...extra })
const bundle = () => ({
  app: chunk('app.js', { name: 'app', isEntry: true, imports: ['common.js'], dynamicImports: ['agenda.js', 'editor.js'] }),
  common: chunk('common.js'),
  agenda: chunk('agenda.js', { isDynamicEntry: true, imports: ['common.js'] }),
  editor: chunk('editor.js', { isDynamicEntry: true, imports: ['common.js'] }),
})

test('shared shell and on-demand pages remain separate', () => assert.doesNotThrow(() => assertLazyPageBoundary(bundle())))
test('transitive eager dependency on an on-demand page blocks build', () => {
  const value = bundle()
  value.common.imports = ['agenda.js']
  assert.throws(() => assertLazyPageBoundary(value), /agenda\.js/)
})
test('shared dependency cycles terminate without activating pages', () => {
  const value = bundle()
  value.common.imports = ['app.js']
  assert.doesNotThrow(() => assertLazyPageBoundary(value))
})
test('missing entry and missing emitted dependency fail explicitly', () => {
  assert.throws(() => assertLazyPageBoundary({}), /Entry applicativa assente/)
  const value = bundle()
  value.common.imports = ['missing.js']
  assert.throws(() => assertLazyPageBoundary(value), /missing\.js/)
})

test('the application guard remains mandatory while Storybook builds its own preview entry', async () => {
  const productionPlugins = appConfig.plugins.flat(Infinity)
  const boundary = productionPlugins.find(plugin => plugin?.name === 'iusentra-lazy-page-boundary')
  assert.ok(boundary)
  assert.throws(() => boundary.generateBundle({}, {}), /Entry applicativa assente/)
  const custom = { name: 'controlled-storybook-plugin' }
  const preview = await storybookConfig.viteFinal({ plugins: [...productionPlugins, custom] })
  assert.equal(preview.plugins.some(plugin => plugin?.name === boundary.name), false)
  assert.ok(preview.plugins.includes(custom))
  assert.ok(productionPlugins.includes(boundary))
})

test('the Docker frontend stage contains every configured Vite entry source', () => {
  const root = fileURLToPath(new URL('../../', import.meta.url))
  const docker = readFileSync(path.join(root, 'Dockerfile'), 'utf8')
  const stage = docker.split('AS frontend-builder')[1].split(/^FROM /m)[0]
  const copies = [...stage.matchAll(/^COPY (\S+) (\S+)$/gm)].map(match => match[2].replace(/^\.\//, ''))
  for (const entry of Object.values(appConfig.build.rollupOptions.input)) {
    const relative = path.relative(root, path.resolve(root, 'frontend', entry)).replaceAll('\\', '/')
    assert.ok(existsSync(path.join(root, relative)), relative)
    assert.ok(copies.some(destination => relative === destination || relative.startsWith(destination + '/')), `Docker source missing: ${relative}`)
  }
})
