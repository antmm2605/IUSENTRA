// Blocchi riconosciuti: elenchi raggruppati con tipo e numero di partenza, numeri di pagina esclusi.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'

// ocrBlocks importa ocrMarkers e ocrBlockEdits senza estensione: Node li risolve solo con il percorso completo.
const cartella = new URL('../../frontend/src/components/documentCapture/', import.meta.url)
const sorgente = stripTypeScriptTypes(readFileSync(new URL('ocrBlocks.ts', cartella), 'utf8'))
  .replaceAll("'./ocrMarkers'", JSON.stringify(new URL('ocrMarkers.ts', cartella).href))
  .replace("'./ocrBlockEdits'", JSON.stringify(new URL('ocrBlockEdits.ts', cartella).href))
const { applyPlainTextToBlocks, blocksToHtml, blocksToPlainText, markerFromText, parseBlocks, updateBlockFormat } = await import(`data:text/javascript;base64,${Buffer.from(sorgente).toString('base64')}`)

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
