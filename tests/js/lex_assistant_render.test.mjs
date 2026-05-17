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

const flatDraft = "Sintesi operativa BOZZA \u2014 DIFFIDA E MESSA IN MORA --- Studio Refactor Avv. Refactor Via Roma 1 17/05/2026 Spett.le Alfa S.r.l. Oggetto: DIFFIDA E MESSA IN MORA \u2014 credito Con la presente, il sottoscritto Avv. Refactor, in qualit\u00e0 di difensore di Moscato Marco, diffida. Fatto rapporto non adempiuto Diritto Ai sensi dell'art. 1219 c.c. Richiesta formale Si diffida la S.V. a: 1. pagare 2. consegnare Avvertenza in difetto si agir\u00e0. Con osservanza, Avv. Refactor Fonti consultate - Contesto fonte - dep Dato certo - irrilevante"
const normalizedDraft = hooks.sanitizeLexAnswer(flatDraft, { question: 'scrivi diffida' })
assert.ok(hooks.looksLikeLegalDraft(normalizedDraft))
assert.match(normalizedDraft, /\*\*BOZZA \u2014 DIFFIDA E MESSA IN MORA\*\*|BOZZA \u2014 DIFFIDA E MESSA IN MORA/)
assert.match(normalizedDraft, /\n\n---\n\n/)
assert.match(normalizedDraft, /\*\*Fatto\*\*/)
assert.match(normalizedDraft, /\n1\. pagare/)
assert.doesNotMatch(normalizedDraft, /Fonti consultate/)
assert.doesNotMatch(normalizedDraft, /Contesto fonte/)

const renderedDraft = hooks.renderMarkdown(normalizedDraft)
assert.match(renderedDraft, /pct-ai-answer--document/)
assert.match(renderedDraft, /pct-ai-answer-rule/)
assert.match(renderedDraft, /pct-ai-answer-subheading">Fatto<\/h4>/)
assert.match(renderedDraft, /<ol class="pct-ai-answer-list">/)
assert.doesNotMatch(renderedDraft, /Fonti consultate/)

assert.equal(hooks.formatReflectionDuration(70_000), '1 minuto e 10 secondi')
assert.equal(hooks.formatReflectionDuration(120_000), '2 minuti')
assert.equal(hooks.formatReflectionDuration(1_200), '1,2 secondi')

const thinkingHtml = hooks.buildThinkingBubbleHtml('scrivi diffida per il cliente marco moscato', 3, 70_000)
assert.match(thinkingHtml, /Sto pensando - 1 minuto e 10 secondi/)
assert.match(thinkingHtml, /pct-ai-thinking-steps/)
assert.match(thinkingHtml, /Recupero dati studio, cliente e fascicolo autorizzati/)
assert.match(thinkingHtml, /Impagino la bozza con grassetto, elenchi e separatori leggibili/)

console.log('lex_assistant_render.test.mjs OK')
