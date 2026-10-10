import { test } from 'node:test'
import assert from 'node:assert/strict'
import { changeSelectionCase, textCase, dateInWords, linkedDateFormat, linkedValueFormat } from '../../frontend/src/editorTextCase.ts'

test('date collegate: conserva il formato del modello senza accettare date impossibili', () => {
  assert.equal(linkedDateFormat('3/4/1980', 'dots'), '03.04.1980')
  assert.equal(linkedDateFormat('03/04/1980', 'long-padded'), '03 aprile 1980')
  assert.equal(linkedDateFormat('03/04/1980', 'long'), '3 aprile 1980')
  assert.throws(() => linkedDateFormat('31/04/1980', 'dots'))
})

test('date in lettere: separatori italiani, mesi e validazione del calendario', () => {
  assert.equal(dateInWords('30/04/2026'), '30 aprile 2026')
  assert.equal(dateInWords('30.04.2026'), '30 aprile 2026')
  assert.equal(dateInWords('29/02/2024'), '29 febbraio 2024')
  for (const invalid of ['31/04/2026', '29/02/2026', '30/04.2026', '2026-04-30', '00/04/2026']) assert.throws(() => dateInWords(invalid))
})

test('maiuscole e minuscole italiane preservano accenti, numeri e punteggiatura', () => {
  assert.equal(textCase('È già così, R.G. 2313/2025', 'lower'), 'è già così, r.g. 2313/2025')
  assert.equal(textCase('avvocato: città, più', 'upper'), 'AVVOCATO: CITTÀ, PIÙ')
  assert.equal(textCase('TRIBUNALE DI VELLETRI', 'title'), 'Tribunale di Velletri')
  assert.equal(textCase('CORTE D’APPELLO DI ROMA', 'title'), 'Corte D’Appello di Roma')
})

test('spazi tipografici del codice fiscale non cambiano il dato né completano valori parziali', () => {
  assert.equal(linkedValueFormat('RSSMRA80A01H501U', 'cf-grouped'), 'RSS MRA 80A01 H501U')
  assert.equal(linkedValueFormat('RSS MRA 80A01 H501U', 'cf-grouped'), 'RSS MRA 80A01 H501U')
  assert.equal(linkedValueFormat('RSSMRA80', 'cf-grouped'), 'RSSMRA80')
})

function fixture(values, selected, field = null) {
  const nodes = values.map(data => ({ data, get length() { return this.data.length },
    replaceData(from, length, value) { this.data = this.data.slice(0, from) + value + this.data.slice(from + length) },
    parentElement: { closest: () => field } }))
  if (field) { field.contains = node => nodes.includes(node); field.textContent = values.join(''); field.dataset = {} }
  const root = { contains: node => nodes.includes(node) }
  globalThis.NodeFilter = { SHOW_TEXT: 4 }
  globalThis.document = { createTreeWalker: () => { let index = 0; return { nextNode: () => nodes[index++] || null } } }
  const range = { collapsed: false, startContainer: nodes[0], startOffset: selected[0], endContainer: nodes.at(-1), endOffset: selected[1], intersectsNode: () => true }
  return { root, nodes, range }
}

test('selezione tra due formattazioni conserva nodi e testo esterno', () => {
  const { root, nodes, range } = fixture(['prima città', ' già dopo'], [6, 4])
  changeSelectionCase(root, range, 'upper')
  assert.deepEqual(nodes.map(node => node.data), ['prima CITTÀ', ' GIÀ dopo'])
})

test('campo intero conserva associazione e modalità riutilizzabile', () => {
  const field = {}
  const { root, nodes, range } = fixture(['Giuseppe ', 'Montagnese'], [0, 10], field)
  changeSelectionCase(root, range, 'upper')
  assert.equal(nodes.map(node => node.data).join(''), 'GIUSEPPE MONTAGNESE')
  assert.equal(field.dataset.iuTextCase, 'upper')
})

test('campo parziale viene rifiutato senza modificare neppure il testo precedente', () => {
  const field = {}
  const { root, nodes, range } = fixture(['Giuseppe'], [0, 3], field)
  assert.throws(() => changeSelectionCase(root, range, 'lower'), /interamente/)
  assert.equal(nodes[0].data, 'Giuseppe')
  assert.deepEqual(field.dataset, {})
})
