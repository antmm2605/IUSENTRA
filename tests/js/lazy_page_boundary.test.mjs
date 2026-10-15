import test from 'node:test'
import assert from 'node:assert/strict'
import { assertLazyPageBoundary } from '../../frontend/vite/lazyPageBoundary.ts'

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
