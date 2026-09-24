// Blocchi riconosciuti: elenchi raggruppati con tipo e numero di partenza, numeri di pagina esclusi.
import assert from 'node:assert/strict'
import { test } from 'node:test'

// I moduli del frontend si importano fra loro senza estensione, come fa Vite:
// l'aggancio dei test Node li risolve sui file .ts.
import './support/resolve_ts_extensionless.mjs'
const { applyPlainTextToBlocks, blocksToHtml, blocksToPlainText, markerFromText, parseBlocks, updateBlockFormat, updateBlockText, updateSelectionFormat } = await import('../../frontend/src/components/documentCapture/ocrBlocks.ts')

const blocco = (tipo, testo, extra = {}) => ({ tipo, testo, confidenza: 0.9, riquadro: [0, 0, 10, 10], formato: { livello: 0, grassetto: false, corsivo: false, allineamento: 'sinistra', scala: 1 }, ...extra })

test('le voci consecutive dello stesso elenco diventano un solo <ol> con tipo e partenza', () => {
  const blocks = parseBlocks([
    blocco('paragrafo', 'Motivi:'),
    blocco('elenco', 'b) secondo motivo', { marcatore: { tipo: 'lettera', valore: 2, testo: 'b)', livello: 1 } }),
    blocco('elenco', 'c) terzo motivo', { marcatore: { tipo: 'lettera', valore: 3, testo: 'c)', livello: 1 } }),
    blocco('elenco', '- voce puntata', { marcatore: { tipo: 'puntato', valore: 0, testo: '-', livello: 1 } }),
    blocco('elenco', 'III. terzo capo', { marcatore: { tipo: 'romano', valore: 3, testo: 'III.', livello: 1 } }),
  ], 1)
  const html = blocksToHtml(blocks)
  assert.equal(html, '<p>Motivi:</p><ol type="a" start="2"><li>secondo motivo</li><li>terzo motivo</li></ol><ul><li>voce puntata</li></ul><ol type="I" start="3"><li>terzo capo</li></ol>')
})

test('il marcatore corretto a mano dall avvocato vince su quello letto', () => {
  const blocks = parseBlocks([blocco('elenco', '4) quarto', { marcatore: { tipo: 'numerato', valore: 3, testo: '3)', livello: 1 } })], 1)
  assert.equal(blocksToHtml(blocks), '<ol start="4"><li>quarto</li></ol>')
  assert.deepEqual(markerFromText('iv) quarto'), { tipo: 'romano', valore: 4, testo: 'iv)', livello: 1 })
  assert.equal(markerFromText('c. 2 dell articolo'), null)
})

test('il numero di pagina resta fuori dal documento e dal testo semplice, il giustificato passa', () => {
  const blocks = parseBlocks([
    blocco('paragrafo', 'Corpo dell atto.', { formato: { livello: 0, grassetto: false, corsivo: false, allineamento: 'giustificato', scala: 1 } }),
    blocco('numero_pagina', '3'),
  ], 2)
  assert.equal(blocksToHtml(blocks), '<p style="text-align:justify">Corpo dell atto.</p>')
  assert.equal(blocksToPlainText(blocks), 'Corpo dell atto.')
})

test('la correzione continua aggiorna davvero testo e formato finale', () => {
  const blocks = parseBlocks([
    blocco('titolo', 'Titolo vecchio'),
    blocco('paragrafo', 'Primo testo vecchio.'),
    { tipo: 'tabella', testo: '', righe: [['Voce', 'Importo'], ['Spese', '500']], confidenza: 0.9, riquadro: [0, 0, 10, 10] },
    blocco('paragrafo', 'Secondo testo vecchio.'),
  ], 1)
  const corretti = applyPlainTextToBlocks(blocks, 'Titolo corretto\n\nPrimo testo corretto.\n\nSecondo testo corretto.')
  const formattati = updateBlockFormat(corretti, corretti[1].id, { grassetto: true, allineamento: 'giustificato' })
  assert.equal(blocksToPlainText(formattati), 'Titolo corretto\n\nPrimo testo corretto.\n\nVoce | Importo\nSpese | 500\n\nSecondo testo corretto.')
  assert.equal(
    blocksToHtml(formattati),
    '<p><strong>Titolo corretto</strong></p><p style="text-align:justify"><strong>Primo testo corretto.</strong></p><table border="1" cellspacing="0" cellpadding="4"><thead><tr><th>Voce</th><th>Importo</th></tr></thead><tbody><tr><td>Spese</td><td>500</td></tr></tbody></table><p>Secondo testo corretto.</p>',
  )
})

test('carattere e corpo dichiarati arrivano nel documento, quelli non validi no', () => {
  const formato = { livello: 0, grassetto: false, corsivo: false, allineamento: 'centro', scala: 1, colore: '#1f57a4', famiglia: 'Book Antiqua', corpo: 11.96 }
  const blocks = parseBlocks([
    blocco('paragrafo', 'Tribunale di Bari', { formato }),
    blocco('paragrafo', 'Senza formato dichiarato'),
    blocco('paragrafo', 'Nome sporco', { formato: { ...formato, colore: '', allineamento: 'sinistra', famiglia: "x';background:url(y)", corpo: 400 } }),
  ], 1)
  assert.equal(
    blocksToHtml(blocks),
    '<p style="text-align:center;color:#1f57a4;font-family:\'Book Antiqua\';font-size:12pt">Tribunale di Bari</p>'
      + '<p>Senza formato dichiarato</p>'
      + '<p>Nome sporco</p>',
  )
})

const tratto = (testo, extra = {}) => ({ testo, grassetto: false, corsivo: false, sottolineato: false, barrato: false, colore: '', ...extra })
const conTratti = () => parseBlocks([
  blocco('paragrafo', 'Il Tribunale rigetta la domanda di studio@pec.it', {
    tratti: [
      tratto('Il Tribunale '),
      tratto('rigetta', { grassetto: true, sottolineato: true }),
      tratto(' la domanda di '),
      tratto('studio@pec.it', { colore: '#0000ff' }),
    ],
  }),
], 1)

test('il formato dentro la riga arriva nel documento parola per parola', () => {
  assert.equal(
    blocksToHtml(conTratti()),
    '<p>Il Tribunale <strong><u>rigetta</u></strong> la domanda di <span style="color:#0000ff">studio@pec.it</span></p>',
  )
})

test('i tratti che non ridanno il testo non si usano', () => {
  const [block] = parseBlocks([blocco('paragrafo', 'Testo vero', { tratti: [tratto('Testo '), tratto('falso', { grassetto: true })] })], 1)
  assert.deepEqual(block.tratti, [])
})

test('correggere una parola in neretto la lascia in neretto, il resto non si sposta', () => {
  const [block] = conTratti()
  const [corretto] = updateBlockText([block], block.id, 'Il Tribunale rigettta la domanda di studio@pec.it')
  assert.equal(
    blocksToHtml([corretto]),
    '<p>Il Tribunale <strong><u>rigettta</u></strong> la domanda di <span style="color:#0000ff">studio@pec.it</span></p>',
  )
  const [accorciato] = updateBlockText([corretto], corretto.id, 'Il Tribunale rigettta la domanda')
  assert.equal(blocksToHtml([accorciato]), '<p>Il Tribunale <strong><u>rigettta</u></strong> la domanda</p>')
})

test('un comando della barra agisce su tutto il pezzo', () => {
  const [block] = conTratti()
  const [tutto] = updateBlockFormat([block], block.id, { grassetto: true })
  assert.equal(
    blocksToHtml([tutto]),
    '<p><strong>Il Tribunale </strong><strong><u>rigetta</u></strong><strong> la domanda di </strong><span style="color:#0000ff"><strong>studio@pec.it</strong></span></p>',
  )
})

test('la voce di elenco perde il marcatore anche nei tratti', () => {
  const [voce] = parseBlocks([
    blocco('elenco', 'a) si rigetta', {
      marcatore: { tipo: 'lettera', valore: 1, testo: 'a)', livello: 1 },
      tratti: [tratto('a) si '), tratto('rigetta', { sottolineato: true })],
    }),
  ], 1)
  assert.equal(blocksToHtml([voce]), '<ol type="a"><li>si <u>rigetta</u></li></ol>')
})

const { stileTra } = await import('../../frontend/src/components/documentCapture/ocrTratti.ts')

test('il neretto sulla parola selezionata tocca solo quella', () => {
  const [block] = parseBlocks([blocco('paragrafo', 'Il Tribunale rigetta la domanda')], 1)
  const [dopo] = updateSelectionFormat([block], block.id, 13, 20, { grassetto: true })
  assert.equal(blocksToHtml([dopo]), '<p>Il Tribunale <strong>rigetta</strong> la domanda</p>')
  // il pezzo nel suo insieme resta tondo
  assert.equal(dopo.format.grassetto, false)
})

test('selezione e colore si sommano ai tratti che ci sono gia', () => {
  const [block] = conTratti()
  // «la domanda» in rosso, dentro un capoverso che ha gia' neretto e blu
  const [dopo] = updateSelectionFormat([block], block.id, 21, 31, { colore: '#cc0000' })
  assert.equal(
    blocksToHtml([dopo]),
    '<p>Il Tribunale <strong><u>rigetta</u></strong> <span style="color:#cc0000">la domanda</span> di <span style="color:#0000ff">studio@pec.it</span></p>',
  )
})

test('il comando sulla selezione si spegne se tutta la selezione lo ha gia', () => {
  const [block] = conTratti()
  assert.equal(stileTra(block.tratti, 13, 20, 'grassetto'), true, '«rigetta» e\' tutto in neretto')
  assert.equal(stileTra(block.tratti, 10, 20, 'grassetto'), false, 'mezza selezione non e\' in neretto')
  const [spento] = updateSelectionFormat([block], block.id, 13, 20, { grassetto: false, sottolineato: false })
  assert.equal(blocksToHtml([spento]).includes('<strong>'), false)
})

test('se tutto torna uguale i tratti tornano formato del pezzo', () => {
  const [block] = parseBlocks([blocco('paragrafo', 'Tutto in corsivo')], 1)
  const [tutto] = updateSelectionFormat([block], block.id, 0, block.text.length, { corsivo: true })
  assert.deepEqual(tutto.tratti, [])
  assert.equal(tutto.format.corsivo, true)
  assert.equal(blocksToHtml([tutto]), '<p><em>Tutto in corsivo</em></p>')
})

