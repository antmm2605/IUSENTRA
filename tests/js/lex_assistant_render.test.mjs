import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const documentsSource = readFileSync(new URL('../../web/static/js/pct-lex-assistant-documents.js', import.meta.url), 'utf8')
const source = readFileSync(new URL('../../web/static/js/pct-lex-assistant.js', import.meta.url), 'utf8')
const context = {
  console,
  __IUSENTRA_LEX_TEST_HOOKS__: true,
  window: null,
  Blob,
  fetch: null,
  location: {
    assign() {},
  },
  document: {
    addEventListener() {},
    getElementById() { return null },
  },
}
context.window = context
context.globalThis = context
vm.createContext(context)
vm.runInContext(documentsSource, context, { filename: 'web/static/js/pct-lex-assistant-documents.js' })
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

const flatDraft = "Sintesi operativa BOZZA \u2014 DIFFIDA E MESSA IN MORA Studio Legale Montagnese Avv. Roberto Montagnese Via NINO BIXIO 4, Taurianova, RC C.F. MNTRRT64L01063H - P.IVA 01301790802 Tel. +393474940097 - Email r.montagnese@tiscali.it - PEC roberto.montagnese@coapalmi.legalmail.it 17/05/2026 Spett.le [Nome e Cognome / Ragione sociale della controparte] [Indirizzo, CAP, Citt\u00e0, Provincia] Oggetto: DIFFIDA E MESSA IN MORA \u2014 [descrizione del credito/obbligo inademputo] Con la presente, il sottoscritto/la sottoscritta Avv. Roberto Montagnese, in qualit\u00e0 di difensore di [Nome del cliente - da completare], si invita e diffida formalmente la S.V. / codesta Spettabile Societ\u00e0 ad adempiere. Fatto [Esporre in modo sintetico e cronologico i fatti rilevanti \u2014 DA COMPLETARE] Diritto Ai sensi dell'art. 1219 c.c., la presente lettera costituisce formale messa in mora. Richiesta formale Si diffida la S.V. a: 1. [Prima richiesta specifica \u2014 DA COMPLETARE] 2. [Eventuale seconda richiesta \u2014 DA COMPLETARE] Avvertenza in difetto si agir\u00e0. Con osservanza, Avv. Roberto Montagnese Dati da completare prima dell'invio: > - Nome e dati completi del cliente mittente > - Dati completi della controparte (CF/PI se societ\u00e0) > - Importo esatto Fonti consultate - Contesto fonte - dep Dato certo - irrilevante"
const normalizedDraft = hooks.sanitizeLexAnswer(flatDraft, { question: 'scrivi diffida' })
assert.ok(hooks.looksLikeLegalDraft(normalizedDraft))
assert.match(normalizedDraft, /\*\*BOZZA \u2014 DIFFIDA E MESSA IN MORA\*\*|BOZZA \u2014 DIFFIDA E MESSA IN MORA/)
assert.match(normalizedDraft, /\n\n---\n\n/)
assert.match(normalizedDraft, /\*\*Spett\.le\*\*\n/)
assert.match(normalizedDraft, /\[Indirizzo, CAP, Citt\u00e0, Provincia\]/)
assert.match(normalizedDraft, /\*\*Oggetto:\*\* DIFFIDA E MESSA IN MORA/)
assert.match(normalizedDraft, /\*\*Fatto\*\*/)
assert.match(normalizedDraft, /\*\*Diritto\*\*/)
assert.match(normalizedDraft, /\*\*Richiesta formale\*\*/)
assert.match(normalizedDraft, /\n1\. \[Prima richiesta specifica/)
assert.match(normalizedDraft, /\n2\. \[Eventuale seconda richiesta/)
assert.match(normalizedDraft, /\*\*Dati da completare prima dell'invio\*\*/)
assert.match(normalizedDraft, /\n- Nome e dati completi del cliente mittente/)
assert.doesNotMatch(normalizedDraft, /\n> - /)
assert.doesNotMatch(normalizedDraft, /Fonti consultate/)
assert.doesNotMatch(normalizedDraft, /Contesto fonte/)

const renderedDraft = hooks.renderMarkdown(normalizedDraft)
assert.match(renderedDraft, /pct-ai-answer--document/)
assert.match(renderedDraft, /pct-ai-answer-rule/)
assert.match(renderedDraft, /pct-ai-answer-subheading">Fatto<\/h4>/)
assert.match(renderedDraft, /<ol class="pct-ai-answer-list">/)
assert.match(renderedDraft, /<ul class="pct-ai-answer-list">/)
assert.doesNotMatch(renderedDraft, /pct-ai-answer-quote/)
assert.doesNotMatch(renderedDraft, /Fonti consultate/)

const docs = context.PctLexDocuments
assert.ok(docs, 'document helpers should be available')
const actionHtml = docs.buildGeneratedDocumentActions({
  title: 'BOZZA \u2014 DIFFIDA E MESSA IN MORA',
  answer: normalizedDraft,
  editorImportUrl: '/api/v1/ui/fascicoli/FAS-1/editor-ai/importa-bozza',
})
assert.match(actionHtml, /data-generated-open-editor="true"/)
assert.match(actionHtml, /Apri nell&#39;editor|Apri nell'editor/)
assert.match(actionHtml, /data-generated-download="docx"/)

let assignedEditorUrl = ''
let postedImport = null
context.location.assign = (value) => {
  assignedEditorUrl = value
}
context.fetch = async (url, options) => {
  postedImport = { url, options }
  return {
    ok: true,
    async json() {
      return { open_url: '/fascicoli/FAS-1/documenti/DOC-1/editor' }
    },
  }
}
await docs.openGeneratedInEditor({
  title: 'BOZZA \u2014 DIFFIDA E MESSA IN MORA',
  answer: normalizedDraft,
  editorImportUrl: '/api/v1/ui/fascicoli/FAS-1/editor-ai/importa-bozza',
})
assert.equal(postedImport.url, '/api/v1/ui/fascicoli/FAS-1/editor-ai/importa-bozza')
assert.equal(JSON.parse(postedImport.options.body).title, 'BOZZA \u2014 DIFFIDA E MESSA IN MORA')
assert.equal(assignedEditorUrl, '/fascicoli/FAS-1/documenti/DOC-1/editor')

assert.equal(hooks.formatReflectionDuration(70_000), '1 minuto e 10 secondi')
assert.equal(hooks.formatReflectionDuration(120_000), '2 minuti')
assert.equal(hooks.formatReflectionDuration(1_200), '1,2 secondi')

const thinkingHtml = hooks.buildThinkingBubbleHtml('scrivi diffida per il cliente marco moscato', 3, 70_000)
assert.match(thinkingHtml, /Sto pensando - 1 minuto e 10 secondi/)
assert.match(thinkingHtml, /pct-ai-thinking-steps/)
assert.match(thinkingHtml, /Recupero dati studio, cliente e fascicolo autorizzati/)
assert.match(thinkingHtml, /Impagino la bozza con grassetto, elenchi e separatori leggibili/)

console.log('lex_assistant_render.test.mjs OK')
