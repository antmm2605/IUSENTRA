import test from 'node:test';
import assert from 'node:assert/strict';
import { registerStandaloneOffline } from '../../web/static/vendor/pdfcraft-direct/editor/offline-registration.mjs';

test('hosted HTTPS editor never touches the sandbox-forbidden service worker getter', async () => {
  let reads = 0;
  const navigator = { get serviceWorker() { reads++; throw new DOMException('sandbox', 'SecurityError'); } };
  assert.equal(await registerStandaloneOffline({ hosted: true, protocol: 'https:', navigator }), false);
  assert.equal(reads, 0);
});

test('HTTP never attempts offline installation', async () => {
  const navigator = { get serviceWorker() { assert.fail('HTTP service worker access'); } };
  assert.equal(await registerStandaloneOffline({ hosted: false, protocol: 'http:', navigator }), false);
});

test('standalone HTTPS preserves registration and cache revalidation', async () => {
  const calls = [];
  const navigator = { serviceWorker: { async register(...args) {
    calls.push(args);
    return { async update() { calls.push('update'); } };
  } } };
  assert.equal(await registerStandaloneOffline({ hosted: false, protocol: 'https:', navigator }), true);
  assert.deepEqual(calls, [['sw.js', { updateViaCache: 'none' }], 'update']);
});

test('a browser policy denying the getter cannot break standalone PDF initialization', async () => {
  const navigator = { get serviceWorker() { throw new DOMException('policy', 'SecurityError'); } };
  assert.equal(await registerStandaloneOffline({ hosted: false, protocol: 'https:', navigator }), false);
});

test('unsupported or rejected optional registration never becomes an unhandled rejection', async () => {
  assert.equal(await registerStandaloneOffline({ hosted: false, protocol: 'https:', navigator: {} }), false);
  const navigator = { serviceWorker: { async register() { throw new Error('unavailable'); } } };
  assert.equal(await registerStandaloneOffline({ hosted: false, protocol: 'https:', navigator }), false);
});
