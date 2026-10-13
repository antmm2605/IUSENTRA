import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const frontendRequire = createRequire(new URL('../../frontend/package.json', import.meta.url));
const shadcnRequire = createRequire(frontendRequire.resolve('shadcn'));

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
