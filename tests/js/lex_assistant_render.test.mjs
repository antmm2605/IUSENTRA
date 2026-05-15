import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../../web/static/js/pct-lex-assistant.js', import.meta.url), 'utf8')
const context = {
  console,
  __IUSENTRA_LEX_TEST_HOOKS__: true,
  window: null,
  document: {
    addEventListener() {},
    getElementById() { return null },
  },
}
context.window = context
context.globalThis = context
vm.createContext(context)
vm.runInContext(source, context, { filename: 'web/static/js/pct-lex-assistant.js' })

const hooks = context.IusentraLexAssistantTestHooks
assert.ok(hooks, 'render hooks should be exposed in test mode')

const rendered = hooks.renderMarkdown(`# Sintesi operativa

Perch\u00e9 l'udienza \u00e8 gi\u00e0 fissata, Lex deve mantenere gli accenti: citt\u00e0, societ\u00e0, pi\u00f9, cos\u00ec.

1. Verifica **scadenza** e _documenti_.
2. Apri [fonte ufficiale](https://example.invalid/fonte).

- Punto con \`codice\u00e8\`.

| Voce | Stato |
| --- | --- |
| Societ\u00e0 | Pronta |

> Nota con accento: \u00e8 utile.`)

assert.match(rendered, /<div class="pct-ai-answer">/)
assert.match(rendered, /<h3 class="pct-ai-answer-heading">Sintesi operativa<\/h3>/)
assert.match(rendered, /Perch\u00e9 l&#39;udienza \u00e8 gi\u00e0 fissata/)
assert.match(rendered, /citt\u00e0, societ\u00e0, pi\u00f9, cos\u00ec/)
assert.match(rendered, /<ol class="pct-ai-answer-list">/)
assert.match(rendered, /<strong>scadenza<\/strong>/)
assert.match(rendered, /<em>documenti<\/em>/)
assert.match(rendered, /target="_blank" rel="noopener noreferrer"/)
assert.match(rendered, /<ul class="pct-ai-answer-list">/)
assert.match(rendered, /<code>codice\u00e8<\/code>/)
assert.match(rendered, /<table class="pct-ai-answer-table">/)
assert.match(rendered, /Societ\u00e0/)
assert.match(rendered, /<blockquote class="pct-ai-answer-quote">Nota con accento: \u00e8 utile.<\/blockquote>/)
assert.doesNotMatch(rendered, /<script/i)

console.log('lex_assistant_render.test.mjs OK')
