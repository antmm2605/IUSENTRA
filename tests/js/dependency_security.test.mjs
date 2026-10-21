import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { probeMcpRedirect } from './support/mcp_redirect_probe.mjs';

const frontendRequire = createRequire(new URL('../../frontend/package.json', import.meta.url));
const shadcnRequire = createRequire(frontendRequire.resolve('shadcn'));

const globRequire = createRequire(shadcnRequire.resolve('fast-glob'));
const matchRequire = createRequire(globRequire.resolve('micromatch'));
const braces = matchRequire('braces');

test('Storybook development preview rejects foreign origins and preserves local messages', () => {
  const output = execFileSync(process.execPath,
    [fileURLToPath(new URL('./support/storybook_origin_probe.mjs', import.meta.url))],
    { encoding: 'utf8', timeout: 10000 });
  const rows = JSON.parse(output.trim());
  assert.equal(rows.length, 10);
  for (const row of rows) {
    const local = row.origin === 'http://localhost:6006' || row.origin === 'http://localhost:6007';
    assert.equal(row.delivered, local ? 1 : 0, `${row.origin} / ${row.representation}`);
  }
});

test('both workspace importers resolve patched and compatible Storybook package copies', () => {
  const uiRequire = createRequire(new URL('../../packages/ui/package.json', import.meta.url));
  const pending = [[frontendRequire, 'storybook'], [frontendRequire, '@storybook/addon-vitest'],
    [frontendRequire, '@storybook/addon-a11y'], [frontendRequire, '@storybook/addon-docs'],
    [frontendRequire, '@storybook/react-vite'], [uiRequire, '@storybook/react-vite']];
  const visited = new Set();
  while (pending.length) {
    const [resolve, name] = pending.pop();
    if (['@storybook/global', '@storybook/icons'].includes(name)) continue;
    const source = resolve.resolve(`${name}/package.json`);
    if (visited.has(source)) continue;
    visited.add(source);
    const metadata = resolve(`${name}/package.json`);
    const version = /^10\.(\d+)\.(\d+)$/.exec(metadata.version);
    assert.ok(version && (+version[1] > 6 || (+version[1] === 6 && +version[2] >= 2)),
      `${name}@${metadata.version}: verify the advisory before changing the supported release line`);
    const nested = createRequire(source);
    for (const dependency of Object.keys({ ...metadata.dependencies, ...metadata.peerDependencies })) {
      if (dependency === 'storybook' || dependency.startsWith('@storybook/')) {
        if (metadata.peerDependenciesMeta?.[dependency]?.optional) {
          try { nested.resolve(`${dependency}/package.json`); } catch { continue; }
        }
        pending.push([nested, dependency]);
      }
    }
  }
  assert.ok(visited.size >= 7, 'Inspect the reachable Storybook dependency family.');
});

test('Vite denies wasm-query reads outside fs.allow and inside fs.deny', async (t) => {
  const { createServer, normalizePath } = await import(pathToFileURL(frontendRequire.resolve('vite')));
  const base = await mkdtemp(path.join(tmpdir(), 'iusentra-vite-security-'));
  const root = path.join(base, 'allowed');
  await mkdir(root);
  await writeFile(path.join(root, 'ok.json'), '{"control":"allowed"}');
  await writeFile(path.join(root, '.env'), 'ONLY_A_SYNTHETIC_TEST_MARKER=1');
  await writeFile(path.join(root, 'allowed.wasm'), Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]));
  const outside = path.join(base, 'outside.json');
  await writeFile(outside, '{"control":"denied"}');
  const server = await createServer({
    configFile: false, root, cacheDir: path.join(base, 'cache'), logLevel: 'silent',
    optimizeDeps: { noDiscovery: true },
    server: { host: '127.0.0.1', port: 0, ws: false, hmr: false, watch: null, fs: { strict: true, allow: [root] } },
  });
  t.after(async () => {
    await server.close();
    assert.equal(path.dirname(path.resolve(base)), path.resolve(tmpdir()));
    assert.ok(path.basename(base).startsWith('iusentra-vite-security-'));
    await rm(base, { recursive: true });
  });
  await server.listen();
  const origin = server.resolvedUrls.local[0];
  for (const request of [
    '/.env?import&vite-wasm-instance',
    '/.env?import&vite-wasm-instance&x=1',
    `/@fs/${normalizePath(outside)}?import&vite-wasm-instance`,
  ]) {
    const response = await fetch(new URL(request, origin));
    assert.equal(response.status, 403, request);
    assert.ok(!(await response.text()).includes('ONLY_A_SYNTHETIC_TEST_MARKER'));
  }
  for (const request of ['/ok.json', '/ok.json?import', '/allowed.wasm?import&vite-wasm-instance']) {
    const response = await fetch(new URL(request, origin));
    assert.equal(response.status, 200, request);
    await response.text();
  }
});

test('Vite does not promote unresolved SSR import URLs to safe filesystem paths', async (t) => {
  const { createServer, normalizePath } = await import(pathToFileURL(frontendRequire.resolve('vite')));
  const base = await mkdtemp(path.join(tmpdir(), 'iusentra-vite-security-'));
  const entry = normalizePath(path.join(base, 'entry.js'));
  const dependency = normalizePath(path.join(base, 'dependency.js'));
  await writeFile(dependency, 'export const allowed = true;');
  const unresolved = '/unresolved-security-fixture';
  const server = await createServer({
    configFile: false, root: base, cacheDir: path.join(base, 'cache'), logLevel: 'silent',
    optimizeDeps: { noDiscovery: true }, server: { middlewareMode: true, ws: false, watch: null },
    plugins: [{
      name: 'controlled-unresolved-ssr-import',
      resolveId(id) {
        if (id === '/entry.js') return entry;
        if (id === 'controlled-security-alias') return dependency;
      },
      load(id) { if (id === entry) return `import 'controlled-security-alias'; import ${JSON.stringify(unresolved)}`; },
    }],
  });
  t.after(async () => {
    await server.close();
    assert.equal(path.dirname(path.resolve(base)), path.resolve(tmpdir()));
    assert.ok(path.basename(base).startsWith('iusentra-vite-security-'));
    await rm(base, { recursive: true });
  });
  await server.environments.ssr.transformRequest('/entry.js');
  assert.equal(server.config.safeModulePaths.has(unresolved), false);
  assert.equal(server.config.safeModulePaths.has(dependency), true);
});

test('braces rejects excessive structural depth across its public entry points', () => {
  const patterns = [
    '{'.repeat(4500) + 'x' + '}'.repeat(4500),
    '{('.repeat(2200) + 'x' + ')}'.repeat(2200),
    '('.repeat(4500) + 'x' + ')'.repeat(4500),
  ];
  for (const pattern of patterns) {
    for (const method of ['parse', 'compile', 'expand', 'stringify']) {
      assert.throws(() => braces[method](pattern), { code: 'ERR_BRACES_DEPTH_LIMIT' });
    }
    assert.throws(() => braces(pattern), { code: 'ERR_BRACES_DEPTH_LIMIT' });
    assert.throws(() => braces.create(pattern), { code: 'ERR_BRACES_DEPTH_LIMIT' });
    const micromatch = matchRequire('micromatch');
    if (micromatch.hasBraces(pattern)) {
      assert.throws(() => micromatch.braceExpand(pattern), { code: 'ERR_BRACES_DEPTH_LIMIT' });
    } else {
      assert.deepEqual(micromatch.braceExpand(pattern), [pattern]);
    }
  }
});

test('braces preserves boundary depths, ordinary alternatives and literal patterns', () => {
  for (const depth of [127, 128]) {
    const pattern = '('.repeat(depth) + 'x' + ')'.repeat(depth);
    assert.equal(braces.stringify(pattern), pattern);
    assert.equal(braces.compile(pattern), pattern);
    assert.deepEqual(braces.expand(pattern), [pattern]);
  }
  for (const method of ['parse', 'compile', 'expand', 'stringify']) {
    assert.throws(() => braces[method]('('.repeat(129) + 'x' + ')'.repeat(129)), { code: 'ERR_BRACES_DEPTH_LIMIT' });
  }
  assert.deepEqual(braces.expand('doc-{a,b}-{1..3}.pdf'), [
    'doc-a-1.pdf', 'doc-a-2.pdf', 'doc-a-3.pdf', 'doc-b-1.pdf', 'doc-b-2.pdf', 'doc-b-3.pdf',
  ]);
  assert.equal(braces.stringify('"{{a,b}}"', { keepQuotes: true }), '"{{a,b}}"');
  assert.equal(braces.stringify('[{}]'), '[{}]');
});

test('braces also guards supplied AST nodes and nested array values', () => {
  let node = { type: 'text', value: 'x' };
  for (let depth = 0; depth < 300; depth++) node = { type: 'root', nodes: [node] };
  for (const method of ['compile', 'expand', 'stringify']) {
    assert.throws(() => braces[method](node), { code: 'ERR_BRACES_DEPTH_LIMIT' });
  }
  let value = 'x';
  for (let depth = 0; depth < 20000; depth++) value = [value];
  assert.throws(() => braces.expand({ type: 'root', nodes: [{ type: 'text', value }] }), { code: 'ERR_BRACES_DEPTH_LIMIT' });
});

test('Hono escapes an untrusted root and preserves ordinary text', async () => {
  const { renderToString } = shadcnRequire('hono/jsx/dom/server');
  assert.equal(await renderToString('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
  assert.equal(await renderToString('Attività dello studio'), 'Attività dello studio');
});

test('flat CSS selectors finish within a bounded time without changing their content', () => {
  const parser = shadcnRequire('postcss-selector-parser');
  const ordinary = '.documento > p[data-campo="cliente"]';
  assert.equal(parser().processSync(ordinary), ordinary);
  const flat = '.a'.repeat(200000);
  const start = performance.now();
  assert.equal(parser().processSync(flat), flat);
  assert.ok(performance.now() - start < 5000);
});

test('source maps reject hostile and nested offsets while preserving valid mappings', () => {
  const postcssRequire = createRequire(frontendRequire.resolve('postcss'));
  const { SourceMapConsumer, SourceMapGenerator, SourceNode } = postcssRequire('source-map-js');
  const map = { version: 3, sources: ['original.js'], names: [], mappings: 'AAAA' };
  for (const line of [1e8, Infinity, -1, 0.5]) {
    assert.throws(() => new SourceMapConsumer({ version: 3, sections: [{ offset: { line, column: 0 }, map }] }), /Section offset/);
  }
  const nested = { version: 3, sections: [{ offset: { line: 6000000, column: 0 }, map }] };
  assert.throws(() => new SourceMapConsumer({ version: 3, sections: [{ offset: { line: 6000000, column: 0 }, map: nested }] }), /nested sections/);
  const generator = new SourceMapGenerator({ file: 'output.js' });
  generator.addMapping({ generated: { line: 1, column: 0 }, original: { line: 1, column: 0 }, source: 'original.js' });
  assert.equal(SourceNode.fromStringWithSourceMap('let x=1;', new SourceMapConsumer(generator.toJSON())).toString(), 'let x=1;');
});

test('the MCP stdio server used by shadcn remains available', () => {
  const { Server } = shadcnRequire('@modelcontextprotocol/sdk/server/index.js');
  const { StdioServerTransport } = shadcnRequire('@modelcontextprotocol/sdk/server/stdio.js');
  assert.ok(new Server({ name: 'controlled-security-check', version: '1.0.0' }, { capabilities: { tools: {} } }));
  assert.ok(new StdioServerTransport());
});

test('MCP HTTP redirects reject foreign origins and preserve same-origin calls', async () => {
  for (const status of [307, 308]) {
    const foreign = await probeMcpRedirect(true, status);
    assert.equal(foreign.received, 0);
    assert.equal(foreign.markerReceived, false);
    assert.match(foreign.error, /Redirect.*not followed/);
    const same = await probeMcpRedirect(false, status);
    assert.equal(same.tools, 0);
    assert.equal(same.error, '');
  }
});

test('the installed shadcn MCP command initializes and lists tools over stdio', { timeout: 45000 }, async (t) => {
  const { Client } = shadcnRequire('@modelcontextprotocol/sdk/client/index.js');
  const { StdioClientTransport } = shadcnRequire('@modelcontextprotocol/sdk/client/stdio.js');
  const fixture = await mkdtemp(path.join(tmpdir(), 'iusentra-mcp-stdio-'));
  const client = new Client({ name: 'controlled-stdio-check', version: '1' }, { capabilities: {} });
  t.after(async () => {
    await client.close();
    assert.equal(path.dirname(path.resolve(fixture)), path.resolve(tmpdir()));
    assert.ok(path.basename(fixture).startsWith('iusentra-mcp-stdio-'));
    await rm(fixture, { recursive: true });
  });
  await writeFile(path.join(fixture, 'package.json'), '{"name":"controlled-mcp-fixture","private":true}');
  const transport = new StdioClientTransport({
    command: process.execPath, args: [frontendRequire.resolve('shadcn'), 'mcp', '--cwd', fixture],
    cwd: fixture, stderr: 'pipe', env: { NO_COLOR: '1' },
  });
  await client.connect(transport, { timeout: 30000 });
  const { tools } = await client.listTools({}, { timeout: 10000 });
  assert.ok(tools.length > 0);
  assert.ok(tools.every((tool) => tool.name && tool.inputSchema));
});


test('Hono static files cannot bypass prefix authentication through a malformed encoded path', async () => {
  const { Hono } = shadcnRequire('hono');
  const { serveStatic } = shadcnRequire('hono/serve-static');
  const app = new Hono();
  const files = new Map([
    ['/fixture/public.txt', 'PUBLIC'],
    ['/fixture/private/secret.txt', 'PRIVATE_FIXTURE'],
  ]);
  app.use('/private/*', async (context, next) => context.req.header('Authorization') === 'Bearer fixture'
    ? next() : context.text('denied', 401));
  app.use('*', serveStatic({ root: '/fixture', getContent: async (path) => files.get(path) ?? null }));

  const publicFile = await app.request('http://example.test/public.txt');
  assert.equal(publicFile.status, 200);
  assert.equal(await publicFile.text(), 'PUBLIC');
  assert.equal((await app.request('http://example.test/private/secret.txt')).status, 401);
  const malformed = await app.request('http://example.test/priv%6%31te/secret.txt');
  assert.equal(malformed.status, 404);
  assert.notEqual(await malformed.text(), 'PRIVATE_FIXTURE');
  const authorized = await app.request('http://example.test/private/secret.txt', { headers: { Authorization: 'Bearer fixture' } });
  assert.equal(authorized.status, 200);
  assert.equal(await authorized.text(), 'PRIVATE_FIXTURE');
});

test('Vitest manual mock generator treats the URL as data', async () => {
  const { checkManualSource } = await import('./support/vitest_mocker_probe.mjs');
  await checkManualSource();
});

test('Vitest redirect registration preserves the filesystem boundary on Windows', async () => {
  const { checkRedirectBoundary } = await import('./support/vitest_mocker_probe.mjs');
  const base = await mkdtemp(path.join(tmpdir(), 'iusentra-mocker-boundary-'));
  const root = path.join(base, 'allowed');
  try {
    await mkdir(root);
    await writeFile(path.join(root, 'allowed.txt'), 'ALLOWED_SYNTHETIC_CONTROL');
    const outside = path.join(base, 'outside.txt');
    await writeFile(outside, 'OUTSIDE_SYNTHETIC_CONTROL');
    await checkRedirectBoundary(root, outside);
  } finally { await rm(base, { recursive: true, force: true }); }
});
