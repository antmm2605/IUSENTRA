import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const frontend = createRequire(new URL('../../../frontend/package.json', import.meta.url));
const vitest = createRequire(frontend.resolve('vitest/package.json'));
const { interceptorPlugin } = await import(pathToFileURL(vitest.resolve('@vitest/mocker/node')));

export async function checkManualSource() {
  const url = 'synthetic-quote"-backslash\\-newline\n-module';
  const plugin = interceptorPlugin({ registry: { getById: () => ({
    type: 'manual', url, resolve: async () => ({ ordinary: null }),
  }) } });
  const source = await plugin.load.handler('/controlled-module');
  // Inspect generated source only: never evaluate attacker-controlled code.
  assert.ok(source.includes(`getFactoryModule(${JSON.stringify(url)})`),
    'The actual generator must preserve quotes, separators and newlines as data.');
  assert.ok(source.includes('export {'), 'Ordinary mock exports remain generated.');
}

export async function checkRedirectBoundary(root, outside) {
  const { createServer } = await import(pathToFileURL(frontend.resolve('vite')));
  const server = await createServer({ root, configFile: false, logLevel: 'silent',
    server: { fs: { allow: [root] } } });
  try {
    for (const redirect of ['traversal:../outside.txt', 'traversal:..\\outside.txt',
      'traversal:..\\nested/../outside.txt', 'traversal:/allowed.txt']) {
      const callbacks = new Map();
      const mocks = new Map();
      const registry = { getById: id => mocks.get(id), register: event => mocks.set(event.id, event),
        delete: id => mocks.delete(id), clear: () => mocks.clear() };
      const plugin = interceptorPlugin({ registry });
      plugin.configureServer({ config: server.config, ws: {
        on: (name, callback) => callbacks.set(name, callback), send: () => {},
      } });
      callbacks.get('vitest:interceptor:register')({ type: 'redirect', raw: '',
        id: '/controlled', url: '/controlled', redirect });
      const mock = mocks.get('/controlled');
      if (redirect === 'traversal:/allowed.txt') {
        assert.ok(mock, 'Legitimate redirect remains registered.');
        assert.equal(await plugin.load.handler('/controlled'), 'ALLOWED_SYNTHETIC_CONTROL');
      } else {
        assert.equal(mock, undefined, `Traversal must be rejected before native readFile: ${redirect}`);
      }
    }
    assert.notEqual(path.resolve(root), path.dirname(outside));
    const callbacks = [];
    interceptorPlugin({ registerWebSocketEvents: false }).configureServer({ ws: {
      on: name => callbacks.push(name),
    } });
    assert.deepEqual(callbacks, [], 'Browser Mode must preserve disabled socket registration.');
  } finally {
    await server.close();
  }
}
