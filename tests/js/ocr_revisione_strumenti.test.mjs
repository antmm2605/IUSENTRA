// Strumenti della revisione: corpi e caratteri, interlinea e rientro, storia, trova e sostituisci, stampa.
import assert from 'node:assert/strict'
import { test } from 'node:test'

import './support/resolve_ts_extensionless.mjs'
const { blocksToHtml, parseBlocks, updateBlockFormat, updateBlockText } = await import('../../frontend/src/components/documentCapture/ocrBlocks.ts')
const { CARATTERI_COMUNI, CORPI, GRUPPI_CARATTERI, INTERLINEE } = await import('../../frontend/src/components/documentCapture/ocrBarraVoci.ts')
const { annulla, registra, ripeti, storiaVuota, PAUSA_TRA_CAMBI_MS } = await import('../../frontend/src/components/documentCapture/ocrStoria.ts')
const { occorrenze, sostituisciTutto } = await import('../../frontend/src/components/documentCapture/ocrTrova.ts')
const { eUnPdf } = await import('../../frontend/src/components/documentCapture/ocrStampa.ts')

const blocco = (tipo, testo, extra = {}) => ({ tipo, testo, confidenza: 0.9, riquadro: [0, 0, 10, 10], formato: { livello: 0, grassetto: false, corsivo: false, allineamento: 'sinistra', scala: 1 }, ...extra })

test('i corpi vanno da 2 a 48 punti e i caratteri sono quelli di Word e dell editor', () => {
  assert.equal(CORPI[0], 2)
  assert.equal(CORPI[CORPI.length - 1], 48)
  assert.ok(CORPI.includes(10.5) && CORPI.includes(12))
  for (const nome of ['Times New Roman', 'Arial', 'Calibri', 'Cambria', 'Palatino Linotype', 'Verdana', 'Courier New', 'Merriweather']) {
    assert.ok(CARATTERI_COMUNI.includes(nome), nome)
  }
  assert.equal(new Set(CARATTERI_COMUNI).size, CARATTERI_COMUNI.length)
  assert.equal(GRUPPI_CARATTERI.length, 3)
  assert.deepEqual(INTERLINEE.map((voce) => voce.value), [0, 1, 1.15, 1.5, 2, 2.5, 3])
})

test('corpo di 2 punti, interlinea e rientro passano nel documento', () => {
  const [letto] = parseBlocks([blocco('paragrafo', 'Nota a margine.', { formato: { livello: 0, allineamento: 'sinistra', scala: 1, corpo: 2 } })], 1)
  assert.equal(letto.format.corpo, 2)
  const [dato] = updateBlockFormat([letto], letto.id, { interlinea: 1.5, rientro: 10 })
  assert.equal(blocksToHtml([dato]), '<p style="font-size:2pt;line-height:1.5;margin-left:28.3pt">Nota a margine.</p>')
  const [fuori] = parseBlocks([blocco('paragrafo', 'x', { formato: { livello: 0, allineamento: 'sinistra', scala: 1, interlinea: 9, rientro: -3 } })], 1)
  assert.equal(fuori.format.interlinea, 0)
  assert.equal(fuori.format.rientro, 0)
})

test('annulla e ripeti: le battute di seguito nello stesso pezzo sono un passo solo', () => {
  const uno = parseBlocks([blocco('paragrafo', 'a')], 1)
  const due = updateBlockText(uno, uno[0].id, 'ab')
  const tre = updateBlockText(due, uno[0].id, 'abc')
  let storia = registra(storiaVuota(), uno, 'testo:x', 1000)
  storia = registra(storia, due, 'testo:x', 1000 + PAUSA_TRA_CAMBI_MS - 1)
  assert.equal(storia.indietro.length, 1)
  const indietro = annulla(storia, tre)
  assert.equal(indietro.blocchi[0].text, 'a')
  const avanti = ripeti(indietro.storia, indietro.blocchi)
  assert.equal(avanti.blocchi[0].text, 'abc')
  assert.equal(annulla(storiaVuota(), uno), null)
  // un cambio nuovo dopo l annullamento cancella il ripeti
  assert.equal(registra(indietro.storia, indietro.blocchi, 'formato').avanti.length, 0)
})

test('trova e sostituisci corregge l errore ripetuto ovunque, tabelle comprese', () => {
  const blocks = parseBlocks([
    blocco('paragrafo', 'Il Tribunaie di Bari e il TRIBUNAIE di Trani.'),
    blocco('tabella', '', { righe: [['Ufficio', 'Tribunaie']] }),
    blocco('paragrafo', 'Tribunaiesco non si tocca.'),
  ], 1)
  assert.equal(occorrenze(blocks, 'tribunaie', { maiuscole: false, paroleIntere: true }).length, 3)
  assert.equal(occorrenze(blocks, 'Tribunaie', { maiuscole: true, paroleIntere: false }).length, 3)
  const { blocks: nuovi, quante } = sostituisciTutto(blocks, 'tribunaie', 'Tribunale', { maiuscole: false, paroleIntere: true })
  assert.equal(quante, 3)
  assert.equal(nuovi[0].text, 'Il Tribunale di Bari e il Tribunale di Trani.')
  assert.deepEqual(nuovi[1].rows, [['Ufficio', 'Tribunale']])
  assert.equal(nuovi[2].text, 'Tribunaiesco non si tocca.')
  assert.equal(sostituisciTutto(blocks, '', 'x', { maiuscole: false, paroleIntere: false }).quante, 0)
  // caratteri speciali cercati alla lettera
  assert.equal(occorrenze(parseBlocks([blocco('paragrafo', 'art. 1 (a) e art. 2')], 1), '(a)', { maiuscole: false, paroleIntere: false }).length, 1)
})

test('la stampa riconosce un PDF dai primi byte, non dal nome', async () => {
  assert.equal(await eUnPdf(new Blob(['%PDF-1.7 ...'])), true)
  assert.equal(await eUnPdf(new Blob(['<html>errore</html>'], { type: 'application/pdf' })), false)
})
