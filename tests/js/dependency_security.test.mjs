import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const frontendRequire = createRequire(new URL('../../frontend/package.json', import.meta.url));
const shadcnRequire = createRequire(frontendRequire.resolve('shadcn'));

const globRequire = createRequire(shadcnRequire.resolve('fast-glob'));
const matchRequire = createRequire(globRequire.resolve('micromatch'));
const braces = matchRequire('braces');

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
